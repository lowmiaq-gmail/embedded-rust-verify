#![forbid(unsafe_code)]
use std::{fs, path::Path};
pub fn write(dir: &Path, report: &serde_json::Value) -> std::io::Result<()> {
    fs::create_dir_all(dir)?;
    fs::write(dir.join("host.json"), serde_json::to_string_pretty(report)?)?;
    let mut md=String::from("# Host FIR verification\n\nHardware performance: NOT MEASURED. These tests are not an algorithm equivalence proof.\n\n| Case | Block | Taps | Raw C / reference | Wrapper / C | Max reference error |\n|---|---:|---:|---|---|---:|\n");
    for row in report["cases"].as_array().unwrap() {
        md += &format!(
            "| {} | {} | {} | {} | {} | {} |\n",
            row["case"],
            row["block"],
            row["taps"],
            row["reference_pass"],
            row["wrapper_pass"],
            row["max_abs"]
        );
    }
    md += "\nSee host.json for metadata, tolerance, corpus identity and per-case digests.\n";
    fs::write(dir.join("host.md"), md)
}
