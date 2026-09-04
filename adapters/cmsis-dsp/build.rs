fn main() {
    let target = std::env::var("TARGET").unwrap();
    let mut b = cc::Build::new();
    b.include("../../vendor/cmsis-dsp/Include")
        .file("../../vendor/cmsis-dsp/Source/arm_fir_f32.c")
        .file("../../vendor/cmsis-dsp/Source/arm_fir_init_f32.c")
        .file("src/baseline.c")
        .opt_level(3)
        .flag("-ffp-contract=off")
        .flag("-fno-fast-math");
    if target == "thumbv7em-none-eabihf" {
        b.include("../../vendor/cmsis-core/Include")
            .flag("-mcpu=cortex-m4")
            .flag("-mfpu=fpv4-sp-d16")
            .flag("-mfloat-abi=hard");
    } else if target == "x86_64-unknown-linux-gnu" {
        b.define("__GNUC_PYTHON__", None);
    } else {
        panic!("Only reviewed x86_64 Linux and Cortex-M4F configurations are supported");
    }
    let compiler = b.get_compiler();
    let version = std::process::Command::new(compiler.path())
        .arg("--version")
        .output()
        .expect("C compiler version");
    assert!(version.status.success());
    let metadata = format!(
        "compiler={}\nargs={:?}\nversion={}\n",
        compiler.path().display(),
        compiler.args(),
        String::from_utf8_lossy(&version.stdout)
    );
    std::fs::write(
        std::path::PathBuf::from(std::env::var_os("OUT_DIR").unwrap()).join("c-build.txt"),
        metadata,
    )
    .unwrap();
    b.compile("verify_fir");
    println!("cargo:rerun-if-changed=../../vendor");
    println!("cargo:rerun-if-changed=src/baseline.c");
    println!("cargo:rerun-if-changed=build.rs");
}
