# Delivery status

Implemented locally: pinned source and dual license, safe FIR interface, generic
verification primitives, host differential reports, paired Cortex-M builds,
CI configuration, hardware log parser, source fingerprints and launch drafts.

Not completed: public repository creation (connected GitHub toolset exposes no
repository-create operation; no authenticated gh CLI), real hardware logs (no USB
probe in this environment), remote CI execution, release, mature upstream PR,
community publication. These are not PASS and must not be inferred from local tests.

The hardware-request workflow is intentionally blocked until a runner/board is
provisioned. No automatic hardware runner is claimed. Publication helper uses an
already authenticated local gh CLI, verifies lowmiaq-gmail, and creates only the
repository. It never tags or publishes a release.

Next concrete execution: restore this repository, authenticate gh locally, run
`bash tools/publish-repository.sh`; connect NUCLEO-F401RE, execute docs/hardware.md,
review measured deltas against chosen acceptance budgets, check remote CI, then
create the first release. Upstream adaptation follows evidence and maintainer review.
