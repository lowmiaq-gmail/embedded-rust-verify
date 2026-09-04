#![no_std]
#![no_main]
#![forbid(unsafe_code)]
use cortex_m_rt::entry;
use cortex_m_semihosting::{debug, hprintln};
use verify_core::{digest, Corpus};
#[cfg(all(feature = "raw", feature = "safe"))]
compile_error!("choose exactly one of raw/safe");
#[cfg(not(any(feature = "raw", feature = "safe")))]
compile_error!("choose exactly one of raw/safe");
#[entry]
fn main() -> ! {
    let mut cp = cortex_m::Peripherals::take().unwrap();
    cp.DCB.enable_trace();
    cp.DWT.enable_cycle_counter();
    let mut rng = Corpus::new(0x514f2701);
    let mut coeff = [0.; 31];
    for c in &mut coeff {
        *c = rng.sample() / 31.;
    }
    let mut input = [0.; 512];
    for x in &mut input {
        *x = rng.sample();
    }
    let mut state = [0.; 94];
    let mut output = [0.; 512];
    // Reset-default HSI clock is retained: no PLL, peripheral or vendor SDK setup.
    // Measure full stream initialization + dispatch + 8 FIR blocks, not kernel alone.
    for run in 0..21 {
        let empty_start = cortex_m::peripheral::DWT::cycle_count();
        cortex_m::asm::dsb();
        cortex_m::asm::isb();
        let empty = cortex_m::peripheral::DWT::cycle_count().wrapping_sub(empty_start);
        cortex_m::asm::dsb();
        cortex_m::asm::isb();
        let start = cortex_m::peripheral::DWT::cycle_count();
        #[cfg(feature = "raw")]
        verify_cmsis_dsp::raw_stream(
            core::hint::black_box(&coeff),
            core::hint::black_box(&mut state),
            core::hint::black_box(&input),
            core::hint::black_box(&mut output),
            64,
        )
        .unwrap();
        #[cfg(feature = "safe")]
        {
            let mut f = verify_cmsis_dsp::Fir::new(
                core::hint::black_box(&coeff),
                core::hint::black_box(&mut state),
                64,
            )
            .unwrap();
            for (i, o) in core::hint::black_box(&input)
                .chunks(64)
                .zip(core::hint::black_box(&mut output).chunks_mut(64))
            {
                f.process(i, o).unwrap();
            }
        }
        cortex_m::asm::dsb();
        cortex_m::asm::isb();
        let cycles = cortex_m::peripheral::DWT::cycle_count().wrapping_sub(start);
        let hash = digest(core::hint::black_box(&output));
        hprintln!("FIR,{},{},{},{:016x}", run, cycles, empty, hash);
    }
    debug::exit(debug::EXIT_SUCCESS);
    loop {
        cortex_m::asm::nop();
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    debug::exit(debug::EXIT_FAILURE);
    loop {
        cortex_m::asm::nop();
    }
}
