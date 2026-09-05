#!/usr/bin/env python3
"""Revalidate a committed manual hardware evidence directory."""

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_json(path, label):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"Invalid {label} {path}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"Invalid {label} {path}: expected a JSON object")
    return value


def require_file(path, label):
    if not path.is_file():
        raise SystemExit(f"Missing {label}: {path}")
    return path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_path(artifacts, relative, label):
    if not isinstance(relative, str) or not relative:
        raise SystemExit(f"Build manifest has no {label} path")
    path = (artifacts / relative).resolve()
    if not path.is_relative_to(artifacts.resolve()):
        raise SystemExit(f"Build manifest {label} path escapes the artifact directory")
    return require_file(path, label)


def main():
    parser = argparse.ArgumentParser(
        description="Revalidate identity-bound manual Cortex-M hardware evidence"
    )
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()

    evidence = pathlib.Path(args.evidence_dir).resolve()
    artifacts = evidence / "artifacts"
    raw = require_file(evidence / "raw.log", "raw log")
    safe = require_file(evidence / "safe.log", "safe log")
    run_path = require_file(evidence / "run-manifest.json", "run manifest")
    saved_path = require_file(evidence / "hardware.json", "hardware report")
    build_path = require_file(artifacts / "build-manifest.json", "build manifest")
    host_path = require_file(artifacts / "host.json", "host report")

    build = load_json(build_path, "build manifest")
    binaries = build.get("binaries")
    if not isinstance(binaries, dict):
        raise SystemExit("Build manifest has no binaries object")
    for mode in ("raw", "safe"):
        entry = binaries.get(mode)
        if not isinstance(entry, dict):
            raise SystemExit(f"Build manifest has no {mode} binary")
        elf = artifact_path(artifacts, entry.get("path"), f"{mode} ELF")
        if sha256(elf) != entry.get("sha256"):
            raise SystemExit(f"{mode} ELF SHA-256 does not match build manifest")
    supporting = build.get("supporting_artifacts", {})
    if not isinstance(supporting, dict):
        raise SystemExit("Build manifest supporting_artifacts must be an object")
    for name, expected in supporting.items():
        artifact = artifact_path(artifacts, name, f"supporting artifact {name}")
        if sha256(artifact) != expected:
            raise SystemExit(f"Supporting artifact SHA-256 mismatch: {name}")

    run = load_json(run_path, "run manifest")
    board = run.get("board")
    clock = run.get("clock")
    if not isinstance(board, dict) or not isinstance(board.get("serial"), str):
        raise SystemExit("Run manifest has no board serial")
    if not isinstance(clock, dict) or type(clock.get("hz")) is not int:
        raise SystemExit("Run manifest has no integer clock frequency")

    with tempfile.TemporaryDirectory(prefix="verify-hardware-") as temporary:
        generated_path = pathlib.Path(temporary) / "hardware.json"
        command = [
            sys.executable,
            str(ROOT / "tools/collect-hardware.py"),
            "--raw",
            str(raw),
            "--safe",
            str(safe),
            "--board-serial",
            board["serial"],
            "--clock-hz",
            str(clock["hz"]),
            "--host-report",
            str(host_path),
            "--build-manifest",
            str(build_path),
            "--run-manifest",
            str(run_path),
            "--out",
            str(generated_path),
        ]
        result = subprocess.run(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise SystemExit("Hardware evidence revalidation failed:\n" + result.stdout)
        generated = load_json(generated_path, "regenerated hardware report")

    saved = load_json(saved_path, "saved hardware report")
    if generated != saved:
        raise SystemExit(
            "Saved hardware report does not exactly match the identity-bound logs and manifests"
        )
    if saved.get("status") != "PASS":
        raise SystemExit("Saved hardware report status is not PASS")
    print(f"hardware evidence: PASS ({evidence})")


if __name__ == "__main__":
    main()
