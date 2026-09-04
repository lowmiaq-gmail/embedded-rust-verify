#![no_std]
#![deny(unsafe_op_in_unsafe_fn)]
//! A private verification adapter for the scalar/M4F CMSIS-DSP FIR implementation.
//! Coefficients use CMSIS order: oldest sample first (reverse impulse response).
mod ffi;
pub const C_BUILD_METADATA: &str = include_str!(concat!(env!("OUT_DIR"), "/c-build.txt"));
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error {
    Taps,
    Block,
    State,
    Input,
    Output,
}
fn validate(coeff: &[f32], state: &[f32], block: usize) -> Result<(), Error> {
    if coeff.is_empty() || coeff.len() > u16::MAX as usize {
        return Err(Error::Taps);
    }
    if block == 0 || block > u32::MAX as usize {
        return Err(Error::Block);
    }
    let required = coeff.len().checked_add(block - 1).ok_or(Error::State)?;
    if state.len() < required {
        return Err(Error::State);
    }
    Ok(())
}
/// Exclusive state borrowing prevents overlapping streams and concurrent mutation.
/// The block size is fixed for this instance. No allocation is performed.
pub struct Fir<'a> {
    coeff: &'a [f32],
    state: &'a mut [f32],
    block: usize,
}
impl<'a> Fir<'a> {
    pub fn new(coeff: &'a [f32], state: &'a mut [f32], block: usize) -> Result<Self, Error> {
        validate(coeff, state, block)?;
        state.fill(0.0);
        Ok(Self {
            coeff,
            state,
            block,
        })
    }
    pub fn process(&mut self, input: &[f32], output: &mut [f32]) -> Result<(), Error> {
        if input.len() != self.block {
            return Err(Error::Input);
        }
        if output.len() != self.block {
            return Err(Error::Output);
        }
        ffi::process(self.coeff, self.state, input, output);
        Ok(())
    }
}
/// Test-only raw C baseline. The C implementation owns initialization and block iteration.
/// This safe entry point checks buffer sizes but does not use `Fir`.
pub fn raw_stream(
    coeff: &[f32],
    state: &mut [f32],
    input: &[f32],
    output: &mut [f32],
    block: usize,
) -> Result<(), Error> {
    validate(coeff, state, block)?;
    if input.is_empty()
        || !input.len().is_multiple_of(block)
        || input.len() / block > u32::MAX as usize
    {
        return Err(Error::Input);
    }
    if input.len() != output.len() {
        return Err(Error::Output);
    }
    ffi::raw_stream(coeff, state, input, output, block);
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_invalid_parameters() {
        assert!(matches!(Fir::new(&[], &mut [0.; 8], 1), Err(Error::Taps)));
        assert!(matches!(
            Fir::new(&[1.], &mut [0.; 8], 0),
            Err(Error::Block)
        ));
        assert!(matches!(
            Fir::new(&[1., 2.], &mut [0.; 1], 1),
            Err(Error::State)
        ));
        let mut state = [0.; 4];
        let mut f = Fir::new(&[1., 2.], &mut state, 2).unwrap();
        assert_eq!(f.process(&[1.], &mut [0.; 2]), Err(Error::Input));
        assert_eq!(f.process(&[1.; 2], &mut [0.; 1]), Err(Error::Output));
        let mut out = [0.; 2];
        f.process(&[1., 2.], &mut out).unwrap();
        assert_eq!(out, [2., 5.]); // invalid calls did not advance state
    }
    #[test]
    fn state_tail_is_not_written() {
        let mut s = [123.; 8];
        {
            let mut f = Fir::new(&[1., 2.], &mut s[..3], 2).unwrap();
            f.process(&[1., 2.], &mut [0.; 2]).unwrap();
        }
        assert_eq!(&s[3..], &[123.; 5]);
    }
    #[test]
    fn rejects_oversized_taps_and_bad_stream() {
        let c = [0.; 65536];
        assert!(matches!(Fir::new(&c, &mut [], 1), Err(Error::Taps)));
        assert_eq!(
            raw_stream(&[1.], &mut [0.; 2], &[0.; 3], &mut [0.; 3], 2),
            Err(Error::Input)
        );
    }
}
