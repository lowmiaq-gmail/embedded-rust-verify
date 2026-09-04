# Launch materials — drafts, not submitted

## GitHub Release notes
Initial arm_fir_f32 verification case: checked borrowed-buffer Rust interface,
unchanged pinned CMSIS-DSP C sources, deterministic three-path checks, paired
Cortex-M4F firmware, report tooling and targeted hardware evidence policy.
Publish only after all gates in verification-policy.md pass. Include actual
Flash/RAM/cycle table, raw logs, compiler versions and known regressions.
No release has been created; performance conclusion remains pending.

## This Week in Rust submission
embedded-rust-verify explores evidence-based validation of a safe Rust interface
to CMSIS-DSP arm_fir_f32. It separates wrapper behavior, an independent numerical
reference and measured overhead. Add public repository and completed report links
before submitting to the project's current submission channel.

## Reddit / Rust Embedded
Title: Measuring a safe Rust wrapper around CMSIS-DSP FIR: behavior, size and cycles
I built a deliberately narrow verification case around the existing C arm_fir_f32,
not a new DSP implementation. The report separates bitwise wrapper/C agreement,
an independent convolution check, and board measurements. I would welcome review
of the safety boundary and benchmark comparability. Add actual measured results,
limitations and report links before posting. Do not claim zero overhead without data.

## LinkedIn
How do we validate an embedded C → Rust interface migration? Our first case keeps
CMSIS-DSP FIR unchanged and checks behavior, linked size, RAM accounting and board
cycles separately. Add the completed evidence report and public repository here.

## X / Bluesky
Can a safe Rust API wrap CMSIS-DSP without unacceptable overhead? We built one FIR
case with reproducible behavior checks and explicit measurement boundaries.
Add measured results + public report link before posting.
