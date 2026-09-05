# embedded-rust-verify

How can we check that an embedded C → Rust / Safe Rust interface migration has
not broken behavior or introduced unacceptable performance regressions?

**First case: CMSIS-DSP `arm_fir_f32`, unchanged official C implementation.**
Status: pre-release prototype; host verification and Cortex-M4F cross-build PASS.
Hardware cycles are **not measured**. No release or zero-cost claim is made.
Public repository: https://github.com/lowmiaq-gmail/embedded-rust-verify.

```sh
# After cloning this repository, Linux x86_64 with rustup, C compiler, Python 3:
cargo test --workspace --locked
cargo run --release --locked -p cmsis-fir-f32 -- reports/local
bash tools/install-arm.sh
export PATH="$PWD/.tools/arm-gnu-toolchain-12.3.rel1-x86_64-arm-none-eabi/bin:$PATH"
bash tools/cross-build.sh
```

| Current evidence | C baseline | Safe Rust wrapper |
|---|---:|---:|
| Host cases / independent reference | 120 PASS | 120 bitwise matches to C |
| Cortex-M4F linked Flash section bytes | 8,568 | 8,544 |
| Static RAM bytes | 12 | 12 |
| Reserved stack bytes | 16,384 | 16,384 |
| Actual peak RAM | not measured | not measured |
| Hardware cycles | not measured | not measured |

Flash totals include vector table, code, read-only data and initialized data.
The wrapper's read-only data grew by 16 bytes even though aggregate Flash fell
by 24 bytes. This is one linked workload, not a general zero-cost result.
The raw C stream is reached via checked Rust dispatch in the same Rust harness.
Timing covers initialization plus block iteration; details in [hardware procedure](docs/hardware.md).

**Unsafe surface:** two production unsafe call sites in
[`adapters/cmsis-dsp/src/ffi.rs`](adapters/cmsis-dsp/src/ffi.rs), plus its C layout
test. No raw pointers in the user API. verify-core, report/example and firmware
entry code forbid unsafe. Official C code and external runtime crates remain
trusted native dependencies; “two sites” is not their total unsafe surface.

**Raw reports:** [initial evidence](reports/initial/README.md),
[functional JSON](reports/initial/host.json), [section JSON](reports/initial/size.json),
[hardware status](reports/initial/hardware.json). Reports identify the measured
source commit rather than pretending later documentation commits were retested.

## What is checked

1. **Wrapper behavioral equivalence:** original C streaming calls versus safe
   borrowed-buffer Rust calls into the same C algorithm, bitwise output comparison.
2. **Independent reference cross-check:** direct test-only convolution using
   double-precision accumulation; absolute tolerance 0.00002 plus relative 0.00002.
3. **Performance overhead measurement:** linked sizes exist; physical-board cycle
   observations and peak RAM remain pending. A/B agreement is not a proof that a
   separately implemented Rust algorithm equals C.

Corpus: 1/3/16/31 taps, 1/3/16/64/127 samples per block; normal, zero, impulse,
constant, finite extrema ±16 and seeded random streams. Each case spans multiple
blocks; the large case spans 257 blocks. Not a guarantee over NaN, infinities,
subnormals, every coefficient range or every compiler. Nonfinite comparisons fail.

## Safe API

```rust
use verify_cmsis_dsp::Fir;
let coefficients = [0.25, 0.5, 0.25]; // CMSIS order: oldest coefficient first
let mut state = [0.0; 6]; // taps + block_size - 1
let mut output = [0.0; 4];
let mut fir = Fir::new(&coefficients, &mut state, 4).unwrap();
fir.process(&[1.0, 0.0, 0.0, 0.0], &mut output).unwrap();
```

State is exclusively borrowed; coefficient storage remains borrowed; process
requires exact fixed-size input/output blocks. Empty or oversized tap counts,
zero/oversized blocks, short state and wrong block buffers return errors.
Coefficients are stored in reverse impulse-response order, as in CMSIS.
No allocation, unchecked public pointers or production FIR rewrite.

## Reproducibility and layout

Rust 1.90.0 is pinned. Cargo.lock files pin dependencies. Official CMSIS-DSP
1.16.2 commit `d5717e454fec0337bef114a21f1d2d01d74f2701` and CMSIS-Core 5.9.0
headers are vendored unchanged; hashes are in vendor/manifest.json. The Arm
12.3.Rel1 download has a SHA-256 check. Use the recorded compiler versions,
no CC/CFLAGS/RUSTFLAGS overrides, and the pinned target configuration for comparison.
First build requires downloads; subsequent builds reuse toolchain/dependency caches.

- `crates/verify-core`: platform-independent corpus, comparator and metric contracts.
- `crates/verify-report`: JSON / Markdown output.
- `adapters/cmsis-dsp`: private verification adapter and C boundary.
- `examples/cmsis-fir-f32`: host three-path checks and independent oracle.
- `platforms/cortex-m`: paired NUCLEO-F401RE Cortex-M4F firmware.
- `tools`: source identity, size collection, log parsing and publication helper.

The verify workflow artifact carries a build manifest that binds the exact host
report, corpus, build inputs, toolchains and both ELF hashes. On a board-connected
host, `python3 tools/run-hardware.py --artifact-dir reports/local --check-only`
validates the artifact/OpenOCD prerequisites without flashing. The full
one-command capture procedure is in [hardware procedure](docs/hardware.md).

Fresh-clone reproduction was executed for the source commit recorded in initial
reports. [Local delivery status](docs/STATUS.md) lists remaining work.

## Validation and release policy

Each pull request runs formatting, lint, host tests, deterministic differential
tests and Cortex-M cross-build. Hardware is requested for relevant implementation,
interface, benchmark, compiler/linker/platform changes, release candidates, or an
explicit hardware-validation label. Documentation changes do not require hardware.
The hardware runner is **not provisioned**; its request workflow deliberately
fails instead of claiming an unexecuted test passed. See [policy](docs/verification-policy.md).

First release requires physical cycle observations, memory accounting, functional
PASS, fresh-clone reproduction, remote CI green and complete licensing. Application
budgets must define what regression is acceptable; an Arm core name alone does not.
The public repository exists, but no tag or GitHub Release has been created.

## Ecosystem and next steps

[Upstream review](docs/upstream.md): cmsis_dsp 0.2.0 has pre-generated low-level
bindings but no high-level FIR API in the inspected tree. Its prebuilt library
strategy differs from this source-built verification harness. Keep this adapter
unpublished; propose a compatible upstream binding after evidence and review.
Do not imply upstream acceptance. [Expansion gates](docs/roadmap.md) keep fixed-point,
Renesas, Zephyr and C2000 out of the first case. No Rust C28x target is assumed.

[Article draft](docs/launch-article.md) · [Launch drafts](docs/launch-posts.md) ·
[Third-party notices](THIRD-PARTY-NOTICES.md) · [Contributing](CONTRIBUTING.md).
Own code: MIT OR Apache-2.0; third-party licenses remain unchanged.

## Service entry

For one existing embedded C module, the offered engagement is deliberately
narrow: analyze its memory-safety boundary, add a gradual borrowed Safe Rust
interface, classify which changes invalidate evidence, and deliver reproducible
host/build/hardware reports. The customer's production algorithm stays in place;
source disclosure, target expansion and a general wrapper framework are not
assumed. Contact is manual and scoped to one candidate module.
