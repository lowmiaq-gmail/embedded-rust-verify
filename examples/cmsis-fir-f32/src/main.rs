#![forbid(unsafe_code)]
use serde_json::json;
use verify_cmsis_dsp::{raw_stream, Fir};
use verify_core::{digest, Corpus, Tolerance};
// Independent test oracle: direct convolution with f64 accumulation, no CMSIS state layout.
fn reference(coeff: &[f32], input: &[f32]) -> Vec<f32> {
    (0..input.len())
        .map(|n| {
            coeff
                .iter()
                .rev()
                .enumerate()
                .filter(|(k, _)| *k <= n)
                .map(|(k, c)| f64::from(*c) * f64::from(input[n - k]))
                .sum::<f64>() as f32
        })
        .collect()
}
fn command(program: &str, args: &[&str]) -> String {
    let o = std::process::Command::new(program)
        .args(args)
        .output()
        .expect("metadata command");
    assert!(o.status.success());
    String::from_utf8(o.stdout).unwrap().trim().to_string()
}
fn main() {
    let mut rows = vec![];
    let mut pass = true;
    let tolerance = Tolerance {
        absolute: 2e-5,
        relative: 2e-5,
    };
    for taps in [1, 3, 16, 31] {
        for block in [1, 3, 16, 64, 127] {
            let mut rng = Corpus::new(0x514f2701);
            let coeff: Vec<_> = (0..taps).map(|_| rng.sample() / taps as f32).collect();
            for case in [
                "normal",
                "zero",
                "impulse",
                "constant",
                "bounded-extrema",
                "seeded-large",
            ] {
                let n = if case == "seeded-large" {
                    block * 257
                } else {
                    block * 5
                };
                let input: Vec<f32> = (0..n)
                    .map(|i| match case {
                        "zero" => 0.,
                        "impulse" => {
                            if i == 0 {
                                1.
                            } else {
                                0.
                            }
                        }
                        "constant" => 0.25,
                        "bounded-extrema" => {
                            if i % 2 == 0 {
                                16.
                            } else {
                                -16.
                            }
                        }
                        "normal" => (i % 13) as f32 / 6. - 1.,
                        _ => rng.sample(),
                    })
                    .collect();
                let mut raw = vec![0.; n];
                let mut safe = vec![0.; n];
                raw_stream(
                    &coeff,
                    &mut vec![0.; taps + block - 1],
                    &input,
                    &mut raw,
                    block,
                )
                .unwrap();
                let mut state = vec![0.; taps + block - 1];
                let mut f = Fir::new(&coeff, &mut state, block).unwrap();
                for (i, o) in input.chunks(block).zip(safe.chunks_mut(block)) {
                    f.process(i, o).unwrap();
                }
                let expected = reference(&coeff, &input);
                let comparison = tolerance.compare(&expected, &raw);
                let reference_pass = comparison.mismatches == 0;
                let wrapper_pass = raw
                    .iter()
                    .zip(&safe)
                    .all(|(a, b)| a.to_bits() == b.to_bits());
                pass &= reference_pass && wrapper_pass;
                rows.push(json!({"case":case,"block":block,"taps":taps,"samples":n,"input_digest":format!("{:016x}",digest(&input)),"coeff_digest":format!("{:016x}",digest(&coeff)),"raw_digest":format!("{:016x}",digest(&raw)),"safe_digest":format!("{:016x}",digest(&safe)),"reference_pass":reference_pass,"wrapper_pass":wrapper_pass,"max_abs":comparison.max_abs}));
            }
        }
    }
    let report = json!({"schema":1,"status":if pass {"PASS"} else {"FAIL"},"claim":"wrapper behavioral equivalence and independent reference cross-check; no hardware performance claim","metadata":{"rustc":command("rustc",&["-Vv"]),"cc":command("cc",&["--version"]),"commit":command("git",&["rev-parse","HEAD"]),"dirty":!command("git",&["status","--porcelain"]).is_empty(),"target":"x86_64-unknown-linux-gnu","c_flags":"-O3 -ffp-contract=off -fno-fast-math -D__GNUC_PYTHON__","rust_profile":"release opt-level=3 lto=false codegen-units=1","cmsis_commit":"d5717e454fec0337bef114a21f1d2d01d74f2701","seed":"0x514f2701"},"tolerance":{"absolute":2e-5,"relative":2e-5,"domain":"finite samples in [-16,16]; coefficients normalized by taps; nonfinite always fails"},"hardware":{"status":"NOT_MEASURED","cycles":null,"flash":null,"ram":null},"cases":rows});
    let dir = std::env::args().nth(1).unwrap_or("reports/local".into());
    verify_report::write(std::path::Path::new(&dir), &report).unwrap();
    println!(
        "{}: {} cases",
        report["status"],
        report["cases"].as_array().unwrap().len()
    );
    if !pass {
        std::process::exit(1)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn oracle_coefficient_order() {
        assert_eq!(
            reference(&[1., 2., 3.], &[1., 0., 0., 0.]),
            vec![3., 2., 1., 0.]
        );
    }
}
