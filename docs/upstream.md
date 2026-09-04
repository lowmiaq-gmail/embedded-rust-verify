# Upstream decision record
Inspected samcrow/cmsis_dsp.rs at b48ce6945d9ca1f466507c3b7d7237dd64876689
(2026-02-25, "chore: Release"). Cargo.toml declares cmsis_dsp 0.2.0, 0BSD.
No FIR high-level wrapper was found in src. Bottom layer is
cmsis_dsp_sys_pregenerated 0.1.0. Its build.rs downloads CMSIS 5.7.0 prebuilt
libraries, selects by target, and does not link a host implementation.
No CONTRIBUTING file was present in the inspected tree. A recent release is
evidence of activity, not a promise that this design will be accepted.

This repository builds a narrow verification adapter from official C sources
so host and Cortex-M can share an exact source revision and compiler flags.
It is an unpublished workspace crate, not an ecosystem fork. An upstream patch
must use upstream's existing bindings and license conventions; this source-build
harness and generic verifier stay here. Do not submit a "mature" binding until
hardware data and a review of upstream's currently selected C version exist.

Sources: https://github.com/samcrow/cmsis_dsp.rs
https://github.com/ARM-software/CMSIS-DSP/tree/v1.16.2
