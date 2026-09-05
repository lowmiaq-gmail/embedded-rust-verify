# Delivery status

The public repository is
https://github.com/lowmiaq-gmail/embedded-rust-verify. Remote verify run
[33936084100](https://github.com/lowmiaq-gmail/embedded-rust-verify/actions/runs/33936084100)
passed the Python regressions, Rust host suite, 120-case report and paired
Cortex-M4F builds for closure commit `54bd85a` on pull request #1. Earlier run
[33919823405](https://github.com/lowmiaq-gmail/embedded-rust-verify/actions/runs/33919823405)
remains the reviewed `6fa720f` baseline.

Software implemented: pinned official C sources and dual license, borrowed Safe
Rust FIR interface, platform-independent verification primitives, independent
host reference, paired Cortex-M4F firmware, build/ELF/corpus identities, strict
hardware-log parsing, sequential OpenOCD capture, impact classification and
pre-release drafts. The capture entry has a no-hardware check mode and requires a
fresh output directory so a failed run cannot leave a reusable old PASS report.

Historical evidence in `reports/initial` remains bound to source commit
`028b33e`. It was not relabelled as a hardware run or as a measurement of later
commits.

Blocked: no NUCLEO-F401RE/ST-LINK was available in the closing environment, so
real probe serial, raw semihosting logs, cycle observations and stack high-water
data do not exist. Peak stack and cycles remain `null` with reasons. No
application Flash/RAM/cycle budget has been supplied, so application-level
acceptance is `NOT_EVALUATED`.

No tag, GitHub Release, upstream pull request or community post has been created.
After a board is connected, run the single command in `docs/hardware.md`, review
the measured deltas against an application budget, and only then evaluate release
gates. Upstream adaptation is independent and still requires its own dependency-
chain and hardware evidence.
