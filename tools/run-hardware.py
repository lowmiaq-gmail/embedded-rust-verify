#!/usr/bin/env python3
"""Serial OpenOCD capture for one explicitly selected STM32 board."""

import argparse
import datetime
import fcntl
import hashlib
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import uuid


ROOT = pathlib.Path(__file__).resolve().parent.parent


def sha256(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def load_build(artifact_dir):
    artifact_dir = pathlib.Path(artifact_dir).resolve()
    path = artifact_dir / "build-manifest.json"
    if not path.is_file():
        raise SystemExit(f"Missing build manifest: {path}")
    manifest = json.loads(path.read_text())
    if manifest.get("schema") != 2:
        raise SystemExit("Unsupported build manifest schema")
    if manifest.get("target") != "thumbv7em-none-eabihf":
        raise SystemExit("Build manifest target is not thumbv7em-none-eabihf")
    corpus = manifest.get("corpus", {})
    if not isinstance(corpus.get("id"), str) or len(corpus["id"]) != 64:
        raise SystemExit("Build manifest has no valid corpus identity")
    binaries = manifest.get("binaries", {})
    for mode in ("raw", "safe"):
        entry = binaries.get(mode, {})
        elf = artifact_dir / entry.get("path", "")
        if not elf.is_file():
            raise SystemExit(f"Missing {mode} ELF: {elf}")
        if sha256(elf) != entry.get("sha256"):
            raise SystemExit(f"{mode} ELF SHA-256 does not match build manifest")
        if not isinstance(entry.get("build_id"), str) or len(entry["build_id"]) != 64:
            raise SystemExit(f"Invalid {mode} build identity")
        entry["resolved_path"] = str(elf)
    if binaries["raw"]["build_id"] == binaries["safe"]["build_id"]:
        raise SystemExit("raw and safe build identities must differ")
    host = artifact_dir / manifest.get("host_report", {}).get("path", "")
    if not host.is_file() or sha256(host) != manifest.get("host_report", {}).get("sha256"):
        raise SystemExit("Host report is missing or does not match build manifest")
    manifest["host_report"]["resolved_path"] = str(host)
    for name, expected in manifest.get("supporting_artifacts", {}).items():
        artifact = artifact_dir / name
        if not artifact.is_file() or sha256(artifact) != expected:
            raise SystemExit(f"Supporting artifact is missing or stale: {name}")
    return path, manifest


def run_checked(command, timeout=None, env=None):
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def maybe_build(args):
    if not args.build:
        return
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit(
            "--build is reviewed only on Linux x86_64; download the verify workflow artifact instead"
        )
    artifact_dir = pathlib.Path(args.artifact_dir).resolve()
    if artifact_dir != (ROOT / "reports/local").resolve():
        raise SystemExit("--build currently requires --artifact-dir reports/local")
    host = run_checked(
        [
            "cargo",
            "run",
            "--release",
            "--locked",
            "-p",
            "cmsis-fir-f32",
            "--",
            str(artifact_dir),
        ]
    )
    if host.returncode != 0:
        sys.stdout.buffer.write(host.stdout)
        raise SystemExit("Host reference build failed")
    install = run_checked(["bash", "tools/install-arm.sh"])
    if install.returncode != 0:
        sys.stdout.buffer.write(install.stdout)
        raise SystemExit("Arm toolchain installation failed")
    tool_dir = install.stdout.decode().strip().splitlines()[-1]
    environment = os.environ.copy()
    environment["PATH"] = tool_dir + os.pathsep + environment["PATH"]
    cross = run_checked(["bash", "tools/cross-build.sh"], env=environment)
    if cross.returncode != 0:
        sys.stdout.buffer.write(cross.stdout)
        raise SystemExit("Cortex-M4F build failed")


def openocd_version(executable):
    result = run_checked([executable, "--version"], timeout=10)
    if result.returncode != 0:
        raise SystemExit("OpenOCD version check failed:\n" + result.stdout.decode(errors="replace"))
    return result.stdout.decode(errors="replace").strip()


def probe_command(args):
    return [
        args.openocd,
        "-f",
        args.board_config,
        "-c",
        f"adapter serial {args.device_serial}",
        "-c",
        "init",
        "-c",
        "reset halt",
        "-c",
        "shutdown",
    ]


def capture_command(args, elf):
    timeout_ms = args.timeout_seconds * 1000
    return [
        args.openocd,
        "-f",
        args.board_config,
        "-c",
        f"adapter serial {args.device_serial}",
        "-c",
        "init",
        "-c",
        "reset halt",
        "-c",
        f"program {elf} verify",
        "-c",
        "arm semihosting enable",
        "-c",
        "reset run",
        "-c",
        f"wait_halt {timeout_ms}",
        "-c",
        "shutdown",
    ]


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_json(path, value):
    path = pathlib.Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def copy_artifacts(source_dir, output_dir):
    source_dir = pathlib.Path(source_dir).resolve()
    destination = pathlib.Path(output_dir) / "artifacts"
    destination.mkdir()
    required = ("build-manifest.json", "host.json", "raw.elf", "safe.elf")
    optional = (
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
    )
    for name in required:
        source = source_dir / name
        if not source.is_file():
            raise SystemExit(f"Required artifact is missing: {source}")
        shutil.copy2(source, destination / name)
    for name in optional:
        source = source_dir / name
        if source.is_file():
            shutil.copy2(source, destination / name)
    return load_build(destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", default="reports/local")
    parser.add_argument("--output-dir")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--device-serial")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--openocd", default="openocd")
    parser.add_argument("--board-config", default="board/st_nucleo_f4.cfg")
    parser.add_argument("--board-model", default="NUCLEO-F401RE")
    parser.add_argument("--mcu", default="STM32F401RE")
    parser.add_argument("--core", default="Arm Cortex-M4F")
    parser.add_argument("--clock-hz", type=int)
    parser.add_argument("--clock-source")
    parser.add_argument("--clock-verification")
    parser.add_argument("--supply")
    parser.add_argument("--flash-wait-states")
    parser.add_argument("--prefetch")
    parser.add_argument("--interrupts", default="disabled by firmware")
    parser.add_argument("--fpu", default="FPv4-SP-D16, hard-float ABI")
    args = parser.parse_args()
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    maybe_build(args)
    build_path, build = load_build(args.artifact_dir)
    executable = shutil.which(args.openocd)
    if executable is None:
        raise SystemExit(f"OpenOCD executable not found: {args.openocd}")
    args.openocd = executable
    version = openocd_version(executable)
    print(f"Artifacts: PASS ({build_path})")
    print(f"OpenOCD: PASS ({version.splitlines()[0]})")
    if not args.device_serial:
        if args.check_only:
            print("Device: NOT CHECKED (--device-serial was not supplied)")
            return
        parser.error("--device-serial is required for hardware execution")
    probe = run_checked(probe_command(args), timeout=20)
    if probe.returncode != 0:
        sys.stdout.buffer.write(probe.stdout)
        raise SystemExit("Selected probe/board check failed")
    print(f"Device: PASS (selected serial {args.device_serial})")
    if args.check_only:
        return
    required = {
        "--output-dir": args.output_dir,
        "--clock-hz": args.clock_hz,
        "--clock-source": args.clock_source,
        "--clock-verification": args.clock_verification,
        "--supply": args.supply,
        "--flash-wait-states": args.flash_wait_states,
        "--prefetch": args.prefetch,
    }
    missing = [name for name, value in required.items() if value in (None, "")]
    if missing:
        parser.error("hardware execution requires " + ", ".join(missing))
    if args.clock_hz <= 0:
        parser.error("--clock-hz must be positive")
    output_dir = pathlib.Path(args.output_dir).resolve()
    if output_dir.exists():
        raise SystemExit(f"Output directory already exists; choose a fresh run directory: {output_dir}")
    output_dir.mkdir(parents=True)
    build_path, build = copy_artifacts(args.artifact_dir, output_dir)
    lock_path = pathlib.Path("/tmp") / f"embedded-rust-verify-{args.device_serial}.lock"
    lock = lock_path.open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise SystemExit(f"Probe is already in use: {args.device_serial}") from error
    run_manifest = {
        "schema": 1,
        "status": "IN_PROGRESS",
        "batch_id": str(uuid.uuid4()),
        "started_at": utc_now(),
        "board": {
            "model": args.board_model,
            "mcu": args.mcu,
            "core": args.core,
            "serial": args.device_serial,
            "supply": args.supply,
        },
        "clock": {
            "hz": args.clock_hz,
            "source": args.clock_source,
            "verification": args.clock_verification,
            "maximum_rating_used_as_measurement": False,
        },
        "debugger": {"tool": "OpenOCD", "version": version, "probe_command": probe_command(args)},
        "environment": {
            "host_os": platform.platform(),
            "board_config": args.board_config,
            "flash_execution": "internal Flash",
            "static_data": "internal SRAM",
            "flash_wait_states": args.flash_wait_states,
            "prefetch": args.prefetch,
            "interrupts": args.interrupts,
            "fpu": args.fpu,
        },
        "runs": {},
    }
    manifest_path = output_dir / "run-manifest.json"
    write_json(manifest_path, run_manifest)
    try:
        for mode in ("raw", "safe"):
            binary = build["binaries"][mode]
            command = capture_command(args, binary["resolved_path"])
            started = utc_now()
            timed_out = False
            try:
                result = run_checked(command, timeout=args.timeout_seconds + 20)
                returncode = result.returncode
                data = result.stdout
            except subprocess.TimeoutExpired as error:
                timed_out = True
                returncode = None
                data = error.stdout or b""
            log_path = output_dir / f"{mode}.log"
            log_path.write_bytes(data)
            run_manifest["runs"][mode] = {
                "mode": mode,
                "build_id": binary["build_id"],
                "elf_sha256": binary["sha256"],
                "command": command,
                "started_at": started,
                "completed_at": utc_now(),
                "exit_code": returncode,
                "timed_out": timed_out,
                "log_path": log_path.name,
                "log_sha256": sha256(log_path),
            }
            write_json(manifest_path, run_manifest)
            if timed_out:
                raise SystemExit(f"{mode} OpenOCD execution timed out; see {log_path}")
            if returncode != 0:
                raise SystemExit(
                    f"{mode} OpenOCD execution failed with exit {returncode}; see {log_path}"
                )
        run_manifest["status"] = "CAPTURED"
        run_manifest["completed_at"] = utc_now()
        write_json(manifest_path, run_manifest)
        report = output_dir / "hardware.json"
        collect = run_checked(
            [
                sys.executable,
                str(ROOT / "tools/collect-hardware.py"),
                "--raw",
                str(output_dir / "raw.log"),
                "--safe",
                str(output_dir / "safe.log"),
                "--board-serial",
                args.device_serial,
                "--clock-hz",
                str(args.clock_hz),
                "--host-report",
                build["host_report"]["resolved_path"],
                "--build-manifest",
                str(build_path),
                "--run-manifest",
                str(manifest_path),
                "--out",
                str(report),
            ]
        )
        if collect.returncode != 0:
            sys.stdout.buffer.write(collect.stdout)
            raise SystemExit(f"Evidence collection rejected the run; see {manifest_path}")
        print(f"Hardware report: {report}")
    except BaseException:
        if run_manifest["status"] != "CAPTURED" or not (
            output_dir / "hardware.json"
        ).is_file():
            run_manifest["status"] = "FAILED"
            run_manifest["completed_at"] = utc_now()
            write_json(manifest_path, run_manifest)
            (output_dir / "hardware.json").unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
