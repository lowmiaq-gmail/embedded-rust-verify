//! The only Rust C-FFI/raw-pointer boundary. Supported C variants are restricted by build.rs.
#[repr(C)]
struct Instance {
    taps: u16,
    state: *mut f32,
    coeff: *const f32,
}
extern "C" {
    fn arm_fir_f32(s: *const Instance, input: *const f32, output: *mut f32, block: u32);
    fn verify_raw_stream(
        coeff: *const f32,
        taps: u16,
        state: *mut f32,
        input: *const f32,
        output: *mut f32,
        block: u32,
        blocks: u32,
    );
}
pub(super) fn process(coeff: &[f32], state: &mut [f32], input: &[f32], output: &mut [f32]) {
    let s = Instance {
        taps: coeff.len() as u16,
        state: state.as_mut_ptr(),
        coeff: coeff.as_ptr(),
    };
    // SAFETY: only Fir::process calls this private function. Constructor checks nonzero
    // taps <= u16::MAX, nonzero block <= u32::MAX, and state >= taps+block-1.
    // process checks exact input/output block lengths. Rust borrows guarantee aligned,
    // live, nonoverlapping mutable state/output and immutable coeff/input throughout
    // the synchronous call. C retains no pointers. repr(C) matches the pinned scalar
    // and M4F header; ABI layout is tested against C on host. No MVE/Neon variants.
    unsafe { arm_fir_f32(&s, input.as_ptr(), output.as_mut_ptr(), input.len() as u32) }
}
pub(super) fn raw_stream(
    coeff: &[f32],
    state: &mut [f32],
    input: &[f32],
    output: &mut [f32],
    block: usize,
) {
    // SAFETY: public raw_stream validated sizes/counts and C integer conversions.
    // Each block remains within slices; state has taps+block-1 elements. Exclusive
    // borrows rule out mutable aliasing; all pointers stay live; C stores none.
    unsafe {
        verify_raw_stream(
            coeff.as_ptr(),
            coeff.len() as u16,
            state.as_mut_ptr(),
            input.as_ptr(),
            output.as_mut_ptr(),
            block as u32,
            (input.len() / block) as u32,
        )
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    extern "C" {
        fn verify_instance_size() -> usize;
        fn verify_state_offset() -> usize;
        fn verify_coeff_offset() -> usize;
    }
    #[test]
    fn c_layout_matches() {
        // SAFETY: these C helpers accept no pointers and return compile-time layout values.
        unsafe {
            assert_eq!(verify_instance_size(), core::mem::size_of::<Instance>());
            assert_eq!(
                verify_state_offset(),
                core::mem::offset_of!(Instance, state)
            );
            assert_eq!(
                verify_coeff_offset(),
                core::mem::offset_of!(Instance, coeff)
            );
        }
    }
}
