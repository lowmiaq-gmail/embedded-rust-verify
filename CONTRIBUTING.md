# Contributing
Keep the first case limited to arm_fir_f32. Do not rewrite the production algorithm.
Use `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets -- -D warnings`, and `cargo test --workspace`.
Changes to unsafe code need a documented safety argument and invalid-input regression test.
Report negative results. Do not call differential testing a mathematical proof.
Reuse evidence only when source, compiler, flags, target, linker and corpus identities match.
Ordinary documentation changes must not trigger hardware testing.
Contributions are MIT OR Apache-2.0, except unchanged third-party files.
