# Upstream decision record

Rechecked `samcrow/cmsis_dsp.rs` on 2026-09-05. Its default branch is `master`
at `b48ce6945d9ca1f466507c3b7d7237dd64876689` (2026-02-25,
"chore: Release"). The `v0.2.0` tag points to that commit; there is no GitHub
Release. `Cargo.toml` declares `cmsis_dsp` 0.2.0, edition 2018 and the 0BSD
license, but no minimum supported Rust version.

No high-level FIR wrapper was found in `src`, and there is no open FIR pull
request. The existing `cmsis_dsp_sys_pregenerated` bindings already expose
`arm_fir_instance_f32`, `arm_fir_init_f32` and `arm_fir_f32`. Its build script
downloads CMSIS 5.7.0 prebuilt libraries and selects them by target; it does not
link the source-built CMSIS-DSP 1.16.2 implementation used by this repository.
Open issue [#9](https://github.com/samcrow/cmsis_dsp.rs/issues/9) requests FIR/IIR
functions and records that a contribution is welcome, but this is not an API or
MSRV acceptance decision. Issue [#4](https://github.com/samcrow/cmsis_dsp.rs/issues/4)
also records the lack of systematic upstream tests. No `CONTRIBUTING.md`, CI
workflow or other repository-specific contribution guide was present.

This repository builds a narrow verification adapter from official C sources
so host and Cortex-M can share an exact source revision and compiler flags. It
is an unpublished workspace crate, not an ecosystem fork. An upstream patch
must use upstream's existing bindings and license conventions; this source-build
harness and generic verifier stay here. The current host and Cortex-M build
results do not validate that different dependency chain. Do not open a draft
pull request until the high-level wrapper has been adapted to
`cmsis_dsp_sys_pregenerated`, validated on the real NUCLEO-F401RE through that
chain, and its API and MSRV expectations have been confirmed with the maintainer.

Sources: https://github.com/samcrow/cmsis_dsp.rs
https://github.com/ARM-software/CMSIS-DSP/tree/v1.16.2
