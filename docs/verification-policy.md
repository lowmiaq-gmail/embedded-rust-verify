# Minimum sufficient verification

Every pull request: formatting, lint, unit tests, deterministic host differential
suite and Cortex-M cross-build. No full hardware test on every commit.

Adapter/FFI, corpus/benchmark, core behavior, C sources, toolchain, build flags,
linker and platform changes invalidate relevant hardware evidence. Documentation
changes do not. The impact script flags code changes conservatively. An explicit
hardware-validation label and release-candidate tag request hardware evidence.
No hardware runner is provisioned; the request workflow fails explicitly instead
of turning an unexecuted hardware job green. Automatic hardware execution is an
unfinished deployment step, not a implemented service.

Source fingerprint + exact compiler identities/flags + target/board/clock +
corpus identity + ELF hash define reusable evidence. Docs-only commits may retain
old evidence with its original source commit; never relabel old observations as
newly measured. Record relevant environment overrides, especially CC/CFLAGS and
RUSTFLAGS. Current reference build assumes no caller overrides.

Release checklist: fresh clone reproduction; raw C PASS; safe wrapper PASS;
independent oracle PASS; Cortex-M linked builds PASS; real cycle logs and memory
accounting; application acceptance budgets decided; documented negative results;
licenses/notices; remote CI green. No release is currently authorized by evidence.
