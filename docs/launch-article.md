# Can We Put a Safe Rust API on CMSIS-DSP Without Paying for It?

**Draft: hardware results and first release are pending.**

An embedded migration needs more than code that compiles. A safe interface can
change buffer ownership, initialization and dispatch costs even when the C
algorithm underneath stays untouched. embedded-rust-verify asks three separate
questions: does the wrapper preserve behavior, do both paths agree with an
independent numerical reference, and what does the complete measured workload cost?

The first case is deliberately just CMSIS-DSP arm_fir_f32. Official C sources
are pinned, unchanged, and compiled for both host and Cortex-M4F. The wrapper
borrows coefficients and state, checks block and buffer lengths, and exposes no
raw pointers. Its C boundary lives in one small private Rust module.

Our host corpus varies taps, block sizes, zeros, impulses, constants, bounded
extremes and deterministic random streams. A separate direct convolution uses
double-precision accumulation. Bitwise wrapper/C agreement and tolerant oracle
agreement answer different questions. Neither is a proof covering every input,
compiler, platform or floating-point mode.

The paired board programs share startup and logging. One measures C initialization
and C block iteration through checked dispatch; the other measures safe-wrapper
initialization and per-block processing. End-to-end timing includes those costs.
This is not a Rust FIR implementation competing with a C FIR implementation.

The build reports expose all relevant sections, static RAM and stack reservation.
Cycle logs will retain a warm-up plus twenty observations, including timer overhead.
If the wrapper increases size or cycles, that result belongs in the first table.
As of this draft, cycle measurements and peak-stack observations do not exist.
The title is a question, not a conclusion.

Hardware evidence should be rerun when its inputs change, not when a paragraph
changes. Evidence is tied to source/build fingerprints, compiler versions,
board configuration and binary hashes. The generic verifier has no CMSIS or
vendor dependency; future backends may reuse it, but they do not expand this release.

Before publishing this article, link the actual public repository, immutable
release, raw reports and CI run. Replace pending results only with observations.
