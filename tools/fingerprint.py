#!/usr/bin/env python3
"""Stable source, corpus and Cortex-M build identities.

Documentation and reports are excluded from binary identities. Final ELF and host
report hashes live in the external build manifest to avoid self-referential ELFs.
"""

import argparse
import hashlib
import json
import os
import pathlib
import subprocess


ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = "thumbv7em-none-eabihf"
PROFILE = "release opt-level=3 lto=false codegen-units=1 panic=abort"
C_FLAGS = "-O3 -ffp-contract=off -fno-fast-math -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard"
CORPUS_KEYS = (
    "schema",
    "seed",
    "taps",
    "block",
    "blocks",
    "samples",
    "coeff_digest",
    "input_digest",
    "expected_digest",
)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(pathlib.Path(path).read_bytes())


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def tracked_files():
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [name.decode() for name in raw.split(b"\0") if name]


def source_fingerprint():
    digest = hashlib.sha256()
    for name in sorted(tracked_files()):
        if name.startswith(("reports/", "docs/")) or name.endswith(".md"):
            continue
        path = ROOT / name
        if path.is_file():
            digest.update(name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def build_input_files():
    prefixes = (
        "adapters/cmsis-dsp/",
        "crates/verify-core/",
        "platforms/cortex-m/",
    )
    fixed = {
        "rust-toolchain.toml",
        "tools/cross-build.sh",
        "tools/fingerprint.py",
        "vendor/manifest.json",
    }
    manifest = json.loads((ROOT / "vendor/manifest.json").read_text())
    vendor_files = set(manifest["files"])
    return sorted(
        name
        for name in tracked_files()
        if name in fixed or name in vendor_files or name.startswith(prefixes)
    )


def build_input_fingerprint():
    digest = hashlib.sha256()
    for name in build_input_files():
        path = ROOT / name
        if not path.is_file():
            raise SystemExit(f"Missing build input: {name}")
        digest.update(name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def require_hardware_corpus(host_report):
    host = json.loads(pathlib.Path(host_report).read_text())
    corpus = host.get("hardware_corpus")
    if not isinstance(corpus, dict):
        raise SystemExit("host report hardware_corpus must be an object")
    if corpus.get("reference_pass") is not True:
        raise SystemExit("host report hardware_corpus.reference_pass must be boolean true")
    missing = [key for key in CORPUS_KEYS if key not in corpus]
    if missing:
        raise SystemExit("host report hardware_corpus missing: " + ", ".join(missing))
    integers = {"schema": 1, "taps": 31, "block": 64, "blocks": 8, "samples": 512}
    for key, expected in integers.items():
        if type(corpus[key]) is not int or corpus[key] != expected:
            raise SystemExit(f"host report hardware_corpus.{key} must equal {expected}")
    if corpus["seed"] != "0x514f2701":
        raise SystemExit("host report hardware_corpus.seed mismatch")
    for key in ("coeff_digest", "input_digest", "expected_digest"):
        value = corpus[key]
        if not isinstance(value, str) or len(value) != 16:
            raise SystemExit(f"host report hardware_corpus.{key} must be 16 hex digits")
        try:
            int(value, 16)
        except ValueError as error:
            raise SystemExit(f"host report hardware_corpus.{key} must be hex") from error
    return {key: corpus[key] for key in CORPUS_KEYS}


def corpus_identity(host_report):
    corpus = require_hardware_corpus(host_report)
    payload = json.dumps(corpus, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(payload)


def toolchain_metadata():
    return {
        "rustc": command("rustc", "-Vv"),
        "arm_gcc": command("arm-none-eabi-gcc", "--version"),
    }


def environment_metadata():
    return {name: os.environ.get(name) for name in ("CC", "CFLAGS", "RUSTFLAGS")}


def build_identity(mode, host_report):
    if mode not in ("raw", "safe"):
        raise SystemExit("mode must be raw or safe")
    payload = {
        "schema": 1,
        "mode": mode,
        "target": TARGET,
        "profile": PROFILE,
        "c_flags": C_FLAGS,
        "build_inputs": build_input_fingerprint(),
        "corpus_id": corpus_identity(host_report),
        "toolchain": toolchain_metadata(),
        "environment": environment_metadata(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(encoded)


def write_build_manifest(args):
    host_path = pathlib.Path(args.host_report)
    raw_path = pathlib.Path(args.raw_elf)
    safe_path = pathlib.Path(args.safe_elf)
    expected = {
        "raw": build_identity("raw", host_path),
        "safe": build_identity("safe", host_path),
    }
    supplied = {"raw": args.raw_build_id, "safe": args.safe_build_id}
    if supplied != expected:
        raise SystemExit("supplied build IDs do not match current build inputs")
    corpus = require_hardware_corpus(host_path)
    corpus["id"] = corpus_identity(host_path)
    report_dir = raw_path.parent
    size_path = report_dir / "size.json"
    if not size_path.is_file():
        raise SystemExit("size.json is required before writing the build manifest")
    size_report = json.loads(size_path.read_text())
    if size_report.get("status") != "BUILD_ONLY":
        raise SystemExit("size.json must be a BUILD_ONLY report")
    supporting = {}
    for name in (
        "size.json",
        "raw.size.txt",
        "safe.size.txt",
        "raw.map",
        "safe.map",
        "rustc.txt",
        "arm-gcc.txt",
        "c-builds.json",
        "source-fingerprint.txt",
        "build-commit.txt",
    ):
        path = report_dir / name
        if path.is_file():
            supporting[name] = sha256_file(path)
    manifest = {
        "schema": 2,
        "target": TARGET,
        "profile": PROFILE,
        "c_flags": C_FLAGS,
        "source_fingerprint": source_fingerprint(),
        "build_input_fingerprint": build_input_fingerprint(),
        "corpus": corpus,
        "host_report": {
            "path": host_path.name,
            "sha256": sha256_file(host_path),
        },
        "toolchain": toolchain_metadata(),
        "environment": environment_metadata(),
        "memory": {
            "execution": "Flash",
            "static_data": "RAM",
            "stack_reserved_bytes": 16384,
            "stack_peak_bytes": None,
            "stack_peak_reason": "No reliable physical-board high-water observation has been collected.",
            "heap_peak_bytes": None,
            "heap_policy": "No global allocator or heap region is configured in the no_std firmware or linker script.",
        },
        "size_report": {"sha256": sha256_file(size_path), "report": size_report},
        "supporting_artifacts": supporting,
        "binaries": {
            "raw": {
                "build_id": expected["raw"],
                "path": raw_path.name,
                "sha256": sha256_file(raw_path),
            },
            "safe": {
                "build_id": expected["safe"],
                "path": safe_path.name,
                "sha256": sha256_file(safe_path),
            },
        },
    }
    out = pathlib.Path(args.write_build_manifest)
    temporary = out.with_suffix(out.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(out)


def main():
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--corpus-id", action="store_true")
    actions.add_argument("--build-id", choices=("raw", "safe"))
    actions.add_argument("--write-build-manifest")
    parser.add_argument("--host-report")
    parser.add_argument("--raw-elf")
    parser.add_argument("--safe-elf")
    parser.add_argument("--raw-build-id")
    parser.add_argument("--safe-build-id")
    args = parser.parse_args()
    if args.corpus_id or args.build_id or args.write_build_manifest:
        if not args.host_report:
            parser.error("--host-report is required")
    if args.corpus_id:
        print(corpus_identity(args.host_report))
    elif args.build_id:
        print(build_identity(args.build_id, args.host_report))
    elif args.write_build_manifest:
        required = (args.raw_elf, args.safe_elf, args.raw_build_id, args.safe_build_id)
        if not all(required):
            parser.error("build manifest requires both ELFs and build IDs")
        write_build_manifest(args)
    else:
        print(source_fingerprint())


if __name__ == "__main__":
    main()
