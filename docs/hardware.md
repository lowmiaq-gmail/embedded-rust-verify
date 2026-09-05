# Cortex-M4F hardware procedure — execution still required

Board: NUCLEO-F401RE, STM32F401RE, on-board ST-LINK. Rust target
thumbv7em-none-eabihf; no board dependency enters verify-core.
Sources: https://www.st.com/en/evaluation-tools/nucleo-f401re.html
https://doc.rust-lang.org/rustc/platform-support/thumbv7em-none-eabi.html

The reviewed build host is Linux x86-64. `tools/install-arm.sh` intentionally
rejects other host systems because its pinned archive is platform-specific.
Produce artifacts on that host (the verify workflow does this), or download the
workflow artifact to the board-connected computer. Do not rebuild it with an
unreviewed native toolchain.

On Linux x86-64, create a bound artifact set:

```sh
cargo run --release --locked -p cmsis-fir-f32 -- reports/local
bash tools/install-arm.sh
export PATH="$PWD/.tools/arm-gnu-toolchain-12.3.rel1-x86_64-arm-none-eabi/bin:$PATH"
bash tools/cross-build.sh
```

`reports/local/build-manifest.json` binds the host-report bytes, corpus identity,
build inputs, target, toolchains and final raw/safe ELF SHA-256 values. The build
ID embedded in each firmware excludes prose and reports and does not contain its
own ELF hash.
The board firmware keeps reset-default HSI (nominal 16 MHz), no PLL or interrupts.
Power cycle/reset before each image. Verify clock configuration on the actual board;
record probe serial, supply, debugger version and clock settings in the report.
The 84 MHz rated maximum is NOT the benchmark clock.

Check artifacts and native OpenOCD without flashing:

```sh
python3 tools/run-hardware.py --artifact-dir reports/local --check-only
```

Supplying `--device-serial` makes check mode open the selected probe and halt the
actual target without programming it. The default board configuration is
`board/st_nucleo_f4.cfg`, but the default is an expected target, not evidence that
the board is present.

After verifying the actual board, clock and settings, one entry performs the two
serial flashes, captures logs, and parses the evidence:

```sh
python3 tools/run-hardware.py \
  --artifact-dir reports/local \
  --output-dir reports/hardware/<fresh-run-id> \
  --device-serial <actual-ST-LINK-serial> \
  --clock-hz 16000000 \
  --clock-source HSI \
  --clock-verification "<how the reset clock was checked>" \
  --supply "<actual supply condition>" \
  --flash-wait-states "<observed setting>" \
  --prefetch "<observed setting>" \
  --timeout-seconds 60
```

The output directory must not already exist. It contains copied build artifacts,
`raw.log`, `safe.log`, `run-manifest.json` and, only after strict acceptance,
`hardware.json`. The run manifest records the actual command, OpenOCD version,
selected serial, exit/timeout state, clock declaration and raw byte hashes. A
flash, verify, run, timeout, identity or parser failure leaves the batch marked
`FAILED` and no hardware PASS report.

Scope: end-to-end stream initialization and eight 64-sample blocks, 31 taps.
The raw baseline is C initialization and C block iteration, reached through a
checked Rust dispatch entry. The safe variant initializes its borrowed state
and checks each block. Both use identical Rust startup, logging and C object.
This is not a pure-C startup/whole-program language comparison or kernel-only
benchmark. Both have identical input, output and state arrays. Full timed work
and timer overhead are retained; no unexplained subtraction. Run 0 is retained
but excluded from summary. Runs 1..20 report minimum, median and maximum plus
raw-to-safe absolute and relative deltas. Logging, protocol headers, completion
markers and digest calculation are outside timing. The DWT window rejects a
detected 32-bit wrap; the parser rejects zero or out-of-range cycle values. These
finite samples are observations, not a worst-case execution time guarantee.

Flash section bytes are linked image section totals, not physical occupied
address span. Static RAM is data+bss+uninit. Reserved RAM adds 16 KiB stack;
peak stack remains `null` until a reliable board observation is implemented.
The firmware has no configured allocator or heap region; this is recorded as a
policy/link fact, not a measured zero-byte peak. Arrays are stack-allocated:
static RAM alone MUST NOT be presented as total working RAM.
Keep ELFs, link maps, section dumps, raw logs, source commit, source fingerprint, compiler
versions and exact build environment together. Compare digests with the host
oracle for this exact hardware corpus before accepting a release; A/B agreement
alone is insufficient. The parser checks the hardware digest against the host C output for the exact board corpus, which the host independently cross-checks. Hardware acceptance remains pending until logs exist.

The protocol and hashes catch accidental role mixing, stale artifacts, truncation
and metadata mismatch. They do not prove that a person did not fabricate a log;
real-device custody and review remain part of evidence acceptance.

Before first release, define acceptable absolute/relative Flash/RAM/cycle budgets
for the intended application. No universal "unacceptable regression" threshold
can be inferred from an Arm core name alone. A report can show measured deltas
without claiming application-level acceptance.
