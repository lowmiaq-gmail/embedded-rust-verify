# Scope and expansion gates
Only after the first case is complete and public: evaluate a fixed-point CMSIS API,
Renesas FSP, Zephyr mixed C/Rust, other vendor SDKs, then TI C2000.
Reuse verify-core; add platform-specific compilation, metric and transport adapters.
For classic C28x use TI's official C compiler for both C reference/candidate firmware.
Do not assume a Rust C28x target, create a compiler, or block Cortex-M on C2000.
A maintainable future Rust target is a separate evaluation.
