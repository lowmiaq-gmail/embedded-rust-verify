# Cortex-M4F hardware procedure — execution still required

Board: NUCLEO-F401RE, STM32F401RE, on-board ST-LINK. Rust target
thumbv7em-none-eabihf; no board dependency enters verify-core.
Sources: https://www.st.com/en/evaluation-tools/nucleo-f401re.html
https://doc.rust-lang.org/rustc/platform-support/thumbv7em-none-eabi.html

Install Rust via rustup and Arm GNU Toolchain 12.3.Rel1; put its bin directory on PATH.
Build from the repository root: `bash tools/cross-build.sh`.
The board firmware keeps reset-default HSI (nominal 16 MHz), no PLL or interrupts.
Power cycle/reset before each image. Verify clock configuration on the actual board;
record probe serial, supply, debugger version and clock settings in the report.
The 84 MHz rated maximum is NOT the benchmark clock.

Use OpenOCD with `board/st_nucleo_f4.cfg`, enable semihosting, load each ELF,
and retain stdout as raw.log / safe.log. Example (run once per variant):

```sh
openocd -f board/st_nucleo_f4.cfg \
 -c 'program reports/local/raw.elf verify reset' \
 -c 'arm semihosting enable' -c 'resume'
```

Some OpenOCD versions need `reset halt` before enabling semihosting, followed by
`resume`. Capture all FIR lines; parser requires exactly runs 0..20. A missing
or stuck cycle counter is a failure. No simulator timing is admissible.

```sh
python3 tools/collect-hardware.py --raw raw.log --safe safe.log \
 --board-serial ACTUAL_SERIAL --clock-hz 16000000
```

Scope: end-to-end stream initialization and eight 64-sample blocks, 31 taps.
The raw baseline is C initialization and C block iteration, reached through a
checked Rust dispatch entry. The safe variant initializes its borrowed state
and checks each block. Both use identical Rust startup, logging and C object.
This is not a pure-C startup/whole-program language comparison or kernel-only
benchmark. Both have identical input, output and state arrays. Full timed work
and timer overhead are retained; no unexplained subtraction. Run 0 is retained
but excluded from summary. Logging/digest calculation is outside timing.

Flash section bytes are linked image section totals, not physical occupied
address span. Static RAM is data+bss+uninit. Reserved RAM adds 16 KiB stack;
peak stack/heap remain unknown until measured. Arrays are stack-allocated:
static RAM alone MUST NOT be presented as total working RAM.
Keep ELFs, section dumps, raw logs, source commit, source fingerprint, compiler
versions and exact build environment together. Compare digests with the host
oracle for this exact hardware corpus before accepting a release; A/B agreement
alone is insufficient. The parser checks the hardware digest against the host C output for the exact board corpus, which the host independently cross-checks. Hardware acceptance remains pending until logs exist.

Before first release, define acceptable absolute/relative Flash/RAM/cycle budgets
for the intended application. No universal "unacceptable regression" threshold
can be inferred from an Arm core name alone. A report can show measured deltas
without claiming application-level acceptance.
