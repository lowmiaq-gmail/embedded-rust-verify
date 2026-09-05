# Minimum sufficient verification

Every pull request: formatting, lint, unit tests, deterministic host differential
suite and Cortex-M cross-build. No full hardware test on every commit.

The small path classifier reports one of these outcomes, taking the highest
impact when a change spans categories:

- `documentation_or_evidence_only`: check changed text/links; retain evidence
  under its original identity.
- `pipeline_only`: check trigger/cache behavior; do not infer a new measurement.
- `evidence_reparse`: run parser/report tests and reparse only identity-complete
  raw logs; do not automatically reflash.
- `host_reference_recheck`: rerun the host reference and escalate if corpus
  identity changes or cannot be proven unchanged.
- `hardware_required`: adapter/FFI, official C, firmware, target, build flags,
  linker, toolchain, corpus or digest changed. Unknown non-documentation paths
  conservatively enter this class.

Tests alone do not invalidate hardware evidence. An explicit hardware-validation
label and release-candidate tag request evidence review. No unattended hardware
runner is provisioned; manually captured evidence is accepted only when its
build/run identities, raw logs and strict parser checks match.

The build manifest binds relevant source/build inputs, exact compiler identities
and flags, target, corpus, host report and final ELF hashes. The run manifest
adds board/probe identity, OpenOCD command and version, clock declaration,
environment settings, exit/timeout status and raw-byte log hashes. Docs-only
commits may retain old evidence with its original source commit; never relabel
old observations as newly measured. Record relevant environment overrides,
especially CC/CFLAGS and RUSTFLAGS. Current reference build assumes no caller
overrides.

Functional agreement, completion of measurement and satisfaction of an
application budget are separate conclusions. Without an application-provided
Flash/RAM/cycle budget, the last conclusion is `NOT_EVALUATED`; the project does
not invent a universal threshold.

Release checklist: fresh clone reproduction; raw C PASS; safe wrapper PASS;
independent oracle PASS; Cortex-M linked builds PASS; real cycle logs and memory
accounting; application acceptance budgets decided; documented negative results;
licenses/notices; remote CI green. No release is currently authorized by evidence.
