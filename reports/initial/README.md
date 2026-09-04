# Initial evidence — pre-release

Source commit: `028b33e` (full hash in build-commit.txt and host.json).
Created from a fresh local Git clone with no target build directories.
All six host unit tests, workspace lint, both format checks, 120 deterministic
cases and both Cortex-M linked builds passed. This is local evidence, not a
remote GitHub Actions green run. Subsequent prose/report-only commits reuse it.

| Metric | C stream baseline | Safe wrapper | Difference |
|---|---:|---:|---:|
| .text | 6932 | 6892 | -40 |
| .rodata | 612 | 628 | +16 |
| .data | 0 | 0 | 0 |
| .bss | 12 | 12 | 0 |
| vector table | 1024 | 1024 | 0 |
| Flash sections, bytes | 8568 | 8544 | -24 |
| Static RAM, bytes | 12 | 12 | 0 |
| Reserved stack, bytes | 16384 | 16384 | 0 |
| Static + reserved stack, bytes | 16396 | 16396 | 0 |
| Actual peak stack | unknown | unknown | unknown |
| Board cycles | not measured | not measured | unknown |

The C stream baseline includes checked Rust dispatch, shared Rust startup and
logging. This is a wrapper experiment, not a pure-C-versus-Rust firmware contest.
An extra 16 bytes of read-only data appears in the wrapper image; it is not hidden
by the smaller aggregate. Size depends on the exact linked harness and compiler.

[host.json](host.json) / [host.md](host.md): machine/human functional results.
[size.json](size.json): raw section accounting and ELF hashes.
[raw.size.txt](raw.size.txt), [safe.size.txt](safe.size.txt): tool output.
[raw.elf](raw.elf), [safe.elf](safe.elf): binaries, not hardware observations.
[c-builds.json](c-builds.json), [rustc.txt](rustc.txt), [arm-gcc.txt](arm-gcc.txt): compiler evidence.
[source-fingerprint.txt](source-fingerprint.txt): reusable source identity.
[hardware.json](hardware.json): explicit missing hardware evidence.

These results do not establish zero overhead, universal behavior equivalence,
application-level regression acceptance, or cycle performance.
