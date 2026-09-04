#![no_std]
#![forbid(unsafe_code)]
//! Platform-independent deterministic data, comparisons, and metric contracts.
pub trait Implementation {
    type Error;
    fn run(&mut self, input: &[f32], output: &mut [f32]) -> Result<(), Self::Error>;
}
pub struct Comparison {
    pub mismatches: usize,
    pub max_abs: f64,
}
#[derive(Clone, Copy)]
pub struct Tolerance {
    pub absolute: f64,
    pub relative: f64,
}
impl Tolerance {
    pub fn compare(self, reference: &[f32], candidate: &[f32]) -> Comparison {
        let mut r = Comparison {
            mismatches: reference.len().abs_diff(candidate.len()),
            max_abs: 0.0,
        };
        for (&a, &b) in reference.iter().zip(candidate) {
            let d = (f64::from(a) - f64::from(b)).abs();
            if !a.is_finite()
                || !b.is_finite()
                || d > self.absolute + self.relative * f64::from(a).abs()
            {
                r.mismatches += 1;
            }
            if d > r.max_abs {
                r.max_abs = d;
            }
        }
        r
    }
}
pub struct Corpus {
    seed: u32,
}
impl Corpus {
    pub const fn new(seed: u32) -> Self {
        Self { seed }
    }
    pub fn sample(&mut self) -> f32 {
        self.seed = self.seed.wrapping_mul(1664525).wrapping_add(1013904223);
        ((self.seed >> 8) as f32 / 8388608.0) - 1.0
    }
}
pub fn digest(values: &[f32]) -> u64 {
    let mut h = 0xcbf29ce484222325u64;
    for v in values {
        for b in v.to_bits().to_le_bytes() {
            h = (h ^ u64::from(b)).wrapping_mul(0x100000001b3);
        }
    }
    h
}
pub struct BinarySize {
    pub text: u64,
    pub rodata: u64,
    pub data: u64,
    pub bss: u64,
    pub flash_total: u64,
}
pub struct RamMetrics {
    pub static_bytes: u64,
    pub stack_reserved: u64,
    pub stack_peak: Option<u64>,
    pub heap_peak: Option<u64>,
}
pub struct CycleMetrics<'a> {
    pub raw_samples: &'a [u32],
    pub timer_overhead: &'a [u32],
}
pub struct Metadata<'a> {
    pub compiler: &'a str,
    pub flags: &'a str,
    pub target: &'a str,
    pub commit: &'a str,
    pub toolchain: &'a str,
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn comparator_detects_corruption_and_nonfinite() {
        let t = Tolerance {
            absolute: 0.0,
            relative: 0.0,
        };
        assert_eq!(t.compare(&[1.], &[2.]).mismatches, 1);
        assert_eq!(t.compare(&[1.], &[]).mismatches, 1);
        assert_eq!(t.compare(&[f32::NAN], &[f32::NAN]).mismatches, 1);
    }
}
