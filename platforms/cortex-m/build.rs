fn main() {
    let out = std::path::PathBuf::from(std::env::var_os("OUT_DIR").unwrap());
    std::fs::copy("memory.x", out.join("memory.x")).unwrap();
    println!("cargo:rustc-link-search={}", out.display());
    println!("cargo:rerun-if-changed=memory.x");
    let mode =
        std::env::var("EVR_MODE").expect("EVR_MODE must be supplied by tools/cross-build.sh");
    let expected_mode = if std::env::var_os("CARGO_FEATURE_RAW").is_some() {
        "raw"
    } else if std::env::var_os("CARGO_FEATURE_SAFE").is_some() {
        "safe"
    } else {
        panic!("choose exactly one firmware mode")
    };
    assert_eq!(mode, expected_mode, "EVR_MODE does not match Cargo feature");
    println!("cargo:rustc-env=EVR_MODE={mode}");
    for name in ["EVR_BUILD_ID", "EVR_CORPUS_ID"] {
        let value = std::env::var(name)
            .unwrap_or_else(|_| panic!("{name} must be supplied by tools/cross-build.sh"));
        assert!(
            value.len() == 64
                && value
                    .bytes()
                    .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)),
            "{name} must be 64 lowercase hexadecimal characters"
        );
        println!("cargo:rustc-env={name}={value}");
        println!("cargo:rerun-if-env-changed={name}");
    }
    println!("cargo:rerun-if-env-changed=EVR_MODE");
}
