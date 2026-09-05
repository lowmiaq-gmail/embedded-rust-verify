#!/usr/bin/env python3
"""Validate and summarize the two real-board FIR measurement logs.

The collector deliberately accepts only the versioned EVR semihosting
protocol. OpenOCD/debugger chatter is allowed around the protocol records,
but a line containing ``EVR_`` is never silently ignored. The manifests bind
the logs to the exact build, corpus, ELF, host oracle, board, and command
that produced them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import statistics
import sys
import tempfile
from typing import Any


MAX_U32 = 2**32 - 1
HEX64 = re.compile(r"[0-9a-fA-F]{64}\Z")
HEX16 = re.compile(r"[0-9a-fA-F]{16}\Z")
DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\Z")


class CollectorError(ValueError):
    """A user/actionable evidence validation failure."""


def _error(message: str) -> None:
    raise CollectorError(message)


def _read_bytes(path: pathlib.Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        _error(f"cannot read {label} {path}: {exc}")
    raise AssertionError("unreachable")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: pathlib.Path, label: str) -> tuple[dict[str, Any], bytes, str]:
    data = _read_bytes(path, label)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _error(f"{label} is not valid UTF-8 JSON: {exc}")
    if type(value) is not dict:
        _error(f"{label} must contain a JSON object")
    return value, data, _sha256(data)


def _dict(value: Any, name: str) -> dict[str, Any]:
    if type(value) is not dict:
        _error(f"{name} must be an object")
    return value


def _str(value: Any, name: str, *, nonempty: bool = True) -> str:
    if type(value) is not str or (nonempty and not value):
        _error(f"{name} must be a non-empty string")
    return value


def _int(value: Any, name: str) -> int:
    # bool is an int subclass, but is not an integer in a manifest contract.
    if type(value) is not int:
        _error(f"{name} must be an integer")
    return value


def _hex(value: Any, name: str, digits: int) -> str:
    if type(value) is not str:
        _error(f"{name} must be {digits} hexadecimal characters")
    expression = HEX64 if digits == 64 else HEX16 if digits == 16 else re.compile(
        rf"[0-9a-fA-F]{{{digits}}}\Z"
    )
    if expression.fullmatch(value) is None:
        _error(f"{name} must be {digits} hexadecimal characters")
    return value.lower()


def _decimal(token: str, name: str) -> int:
    if DECIMAL.fullmatch(token) is None:
        _error(f"{name} is not a canonical decimal integer")
    return int(token)


def _schema(value: dict[str, Any], expected: int, name: str) -> None:
    if _int(value.get("schema"), f"{name}.schema") != expected:
        _error(f"{name}.schema must be {expected}")


def _validate_build_manifest(
    value: dict[str, Any], path: pathlib.Path
) -> dict[str, Any]:
    name = f"build manifest {path}"
    _schema(value, 2, name)
    target = _str(value.get("target"), f"{name}.target")

    corpus_value = _dict(value.get("corpus"), f"{name}.corpus")
    corpus = {
        "id": _hex(corpus_value.get("id"), f"{name}.corpus.id", 64),
        "schema": _int(corpus_value.get("schema"), f"{name}.corpus.schema"),
        "seed": _str(corpus_value.get("seed"), f"{name}.corpus.seed"),
        "taps": _int(corpus_value.get("taps"), f"{name}.corpus.taps"),
        "block": _int(corpus_value.get("block"), f"{name}.corpus.block"),
        "samples": _int(corpus_value.get("samples"), f"{name}.corpus.samples"),
        "blocks": _int(corpus_value.get("blocks"), f"{name}.corpus.blocks"),
        "expected_digest": _hex(
            corpus_value.get("expected_digest"),
            f"{name}.corpus.expected_digest",
            16,
        ),
        "coeff_digest": _hex(
            corpus_value.get("coeff_digest"),
            f"{name}.corpus.coeff_digest",
            16,
        ),
        "input_digest": _hex(
            corpus_value.get("input_digest"),
            f"{name}.corpus.input_digest",
            16,
        ),
    }
    if corpus["schema"] != 1:
        _error(f"{name}.corpus.schema must be 1")
    for key in ("taps", "block", "samples", "blocks"):
        if corpus[key] <= 0:
            _error(f"{name}.corpus.{key} must be positive")
    if corpus["samples"] != corpus["block"] * corpus["blocks"]:
        _error(f"{name}.corpus.samples must equal block * blocks")

    host_value = _dict(value.get("host_report"), f"{name}.host_report")
    host_report = {
        "sha256": _hex(
            host_value.get("sha256"), f"{name}.host_report.sha256", 64
        )
    }

    binaries_value = _dict(value.get("binaries"), f"{name}.binaries")
    binaries: dict[str, dict[str, str]] = {}
    for mode in ("raw", "safe"):
        binary_value = _dict(
            binaries_value.get(mode), f"{name}.binaries.{mode}"
        )
        binaries[mode] = {
            "build_id": _hex(
                binary_value.get("build_id"),
                f"{name}.binaries.{mode}.build_id",
                64,
            ),
            "sha256": _hex(
                binary_value.get("sha256"),
                f"{name}.binaries.{mode}.sha256",
                64,
            ),
        }
    if binaries["raw"]["build_id"] == binaries["safe"]["build_id"]:
        _error("build manifest raw and safe build_id values must differ")
    if binaries["raw"]["sha256"] == binaries["safe"]["sha256"]:
        _error("build manifest raw and safe ELF hashes must differ")

    # These fields are optional in the minimal schema but, when supplied by
    # the build producer, they are part of the configuration identity that
    # makes an ELF/build_id meaningful. Keep them in the output instead of
    # reducing the association to a bare filename and hash.
    identity_fields = (
        "profile",
        "c_flags",
        "source_fingerprint",
        "build_input_fingerprint",
        "toolchain",
        "environment",
        "memory",
        "size_report",
        "supporting_artifacts",
    )
    identity = {key: value[key] for key in identity_fields if key in value}
    return {
        "schema": 2,
        "target": target,
        "corpus": corpus,
        "host_report": host_report,
        "binaries": binaries,
        "identity": identity,
    }


def _validate_command(value: Any, name: str) -> list[str]:
    if type(value) is not list or not value:
        _error(f"{name} must be a non-empty list")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_str(item, f"{name}[{index}]"))
    return result


def _validate_run_manifest(value: dict[str, Any], path: pathlib.Path) -> dict[str, Any]:
    name = f"run manifest {path}"
    _schema(value, 1, name)
    if value.get("status") not in ("CAPTURED", "ACCEPTED"):
        _error(f"{name}.status must indicate completed capture")
    batch_id = _str(value.get("batch_id"), f"{name}.batch_id")

    board_value = _dict(value.get("board"), f"{name}.board")
    board = dict(board_value)
    for key in ("model", "mcu", "core", "serial", "supply"):
        board[key] = _str(board_value.get(key), f"{name}.board.{key}")

    clock_value = _dict(value.get("clock"), f"{name}.clock")
    clock_hz = _int(clock_value.get("hz"), f"{name}.clock.hz")
    if clock_hz <= 0:
        _error(f"{name}.clock.hz must be greater than zero")
    maximum_as_measurement = clock_value.get("maximum_rating_used_as_measurement")
    if type(maximum_as_measurement) is not bool or maximum_as_measurement:
        _error(f"{name}.clock.maximum_rating_used_as_measurement must be false")
    clock = {
        **clock_value,
        "hz": clock_hz,
        "source": _str(clock_value.get("source"), f"{name}.clock.source"),
        "verification": _str(
            clock_value.get("verification"), f"{name}.clock.verification"
        ),
    }

    debugger_value = _dict(value.get("debugger"), f"{name}.debugger")
    debugger = {
        **debugger_value,
        "tool": _str(debugger_value.get("tool"), f"{name}.debugger.tool"),
        "version": _str(
            debugger_value.get("version"), f"{name}.debugger.version"
        ),
        "probe_command": _validate_command(
            debugger_value.get("probe_command"), f"{name}.debugger.probe_command"
        ),
    }
    environment = _dict(value.get("environment"), f"{name}.environment")
    for key in (
        "host_os",
        "board_config",
        "flash_execution",
        "static_data",
        "flash_wait_states",
        "prefetch",
        "interrupts",
        "fpu",
    ):
        _str(environment.get(key), f"{name}.environment.{key}")

    runs_value = _dict(value.get("runs"), f"{name}.runs")
    runs: dict[str, dict[str, Any]] = {}
    for mode in ("raw", "safe"):
        run_value = _dict(runs_value.get(mode), f"{name}.runs.{mode}")
        if _str(run_value.get("mode"), f"{name}.runs.{mode}.mode") != mode:
            _error(f"{name}.runs.{mode}.mode must be {mode}")
        exit_code = _int(
            run_value.get("exit_code"), f"{name}.runs.{mode}.exit_code"
        )
        if exit_code != 0:
            _error(f"{name}.runs.{mode}.exit_code must be 0")
        timed_out = run_value.get("timed_out")
        if type(timed_out) is not bool or timed_out:
            _error(f"{name}.runs.{mode}.timed_out must be false")
        runs[mode] = {
            **run_value,
            "mode": mode,
            "build_id": _hex(
                run_value.get("build_id"),
                f"{name}.runs.{mode}.build_id",
                64,
            ),
            "elf_sha256": _hex(
                run_value.get("elf_sha256"),
                f"{name}.runs.{mode}.elf_sha256",
                64,
            ),
            "command": _validate_command(
                run_value.get("command"), f"{name}.runs.{mode}.command"
            ),
            "exit_code": 0,
            "timed_out": False,
            "log_sha256": _hex(
                run_value.get("log_sha256"),
                f"{name}.runs.{mode}.log_sha256",
                64,
            ),
            "log_path": _str(
                run_value.get("log_path"), f"{name}.runs.{mode}.log_path"
            ),
            "started_at": _str(
                run_value.get("started_at"), f"{name}.runs.{mode}.started_at"
            ),
            "completed_at": _str(
                run_value.get("completed_at"), f"{name}.runs.{mode}.completed_at"
            ),
        }

    return {
        "schema": 1,
        "batch_id": batch_id,
        "board": board,
        "clock": clock,
        "debugger": debugger,
        "environment": environment,
        "runs": runs,
    }


def _validate_host_report(
    value: dict[str, Any], path: pathlib.Path, corpus: dict[str, Any]
) -> dict[str, Any]:
    name = f"host report {path}"
    # A host report with a failing top-level status is not an oracle for a
    # board run, even if one nested digest happens to match.
    if value.get("status") != "PASS":
        _error(f"{name}.status must be PASS")
    corpus_value = _dict(value.get("hardware_corpus"), f"{name}.hardware_corpus")

    reference_pass = corpus_value.get("reference_pass")
    if type(reference_pass) is not bool or reference_pass is not True:
        _error(
            f"{name}.hardware_corpus.reference_pass must be the boolean true"
        )

    # Require every corpus dimension from the host oracle.  This prevents an
    # old summary with only a digest from being silently paired with new logs.
    for key in ("schema", "seed", "taps", "block", "samples", "blocks"):
        actual = corpus_value.get(key)
        if type(actual) is not type(corpus[key]) or actual != corpus[key]:
            _error(f"{name}.hardware_corpus.{key} does not match build corpus")
    for key in ("coeff_digest", "input_digest"):
        actual = _hex(
            corpus_value.get(key),
            f"{name}.hardware_corpus.{key}",
            16,
        )
        if actual != corpus[key]:
            _error(f"{name}.hardware_corpus.{key} does not match build corpus")
    expected_digest = _hex(
        corpus_value.get("expected_digest"),
        f"{name}.hardware_corpus.expected_digest",
        16,
    )
    if expected_digest != corpus["expected_digest"]:
        _error(
            f"{name}.hardware_corpus.expected_digest does not match build corpus"
        )

    # New reports carry the identity explicitly. Accept the historical
    # spelling only if present, but never accept a conflicting identity.
    for key in ("id", "corpus_id"):
        if key in corpus_value:
            if _hex(corpus_value[key], f"{name}.hardware_corpus.{key}", 64) != corpus["id"]:
                _error(f"{name}.hardware_corpus.{key} does not match build corpus")

    return {
        "status": value["status"],
        "hardware_corpus": {
            **corpus_value,
            "reference_pass": True,
            "expected_digest": expected_digest,
        },
    }


def _parse_log(
    data: bytes,
    label: str,
    expected_mode: str,
    expected_build_id: str,
    expected_corpus_id: str,
) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        _error(f"{label} is not valid UTF-8: {exc}")

    header: tuple[str, str] | None = None
    rows: list[dict[str, Any]] = []
    complete = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        # Debugger/OpenOCD chatter is intentionally tolerated. EVR markers
        # are not: an unknown or malformed marker is a damaged evidence line.
        if "EVR_" not in line:
            continue
        if complete:
            _error(f"{label}:{line_number}: EVR data follows completion marker")

        fields = line.split(",")
        kind = fields[0] if fields else ""
        if kind == "EVR_HEADER":
            if len(fields) != 5 or fields[1] != "1":
                _error(f"{label}:{line_number}: malformed EVR_HEADER")
            mode = fields[2]
            build_id = _hex(fields[3], f"{label}:{line_number} build_id", 64)
            corpus_id = _hex(fields[4], f"{label}:{line_number} corpus_id", 64)
            if header is not None:
                _error(f"{label}:{line_number}: duplicate EVR_HEADER")
            if mode != expected_mode:
                _error(
                    f"{label}:{line_number}: log role {mode!r} does not match {expected_mode!r}"
                )
            if build_id != expected_build_id:
                _error(f"{label}:{line_number}: build_id does not match manifest")
            if corpus_id != expected_corpus_id:
                _error(f"{label}:{line_number}: corpus_id does not match manifest")
            header = (build_id, corpus_id)
        elif kind == "EVR_RESULT":
            if header is None:
                _error(f"{label}:{line_number}: EVR_RESULT precedes EVR_HEADER")
            if len(fields) != 9 or fields[1] != "1":
                _error(f"{label}:{line_number}: malformed EVR_RESULT")
            mode = fields[2]
            if mode != expected_mode:
                _error(f"{label}:{line_number}: result role does not match manifest")
            build_id = _hex(fields[3], f"{label}:{line_number} build_id", 64)
            corpus_id = _hex(fields[4], f"{label}:{line_number} corpus_id", 64)
            if build_id != expected_build_id or corpus_id != expected_corpus_id:
                _error(f"{label}:{line_number}: result identity does not match manifest")
            run = _decimal(fields[5], f"{label}:{line_number} run")
            cycles = _decimal(fields[6], f"{label}:{line_number} cycles")
            overhead = _decimal(fields[7], f"{label}:{line_number} timer_overhead")
            digest = _hex(fields[8], f"{label}:{line_number} digest", 16)
            if run != len(rows) or run < 0 or run > 20:
                _error(f"{label}:{line_number}: run sequence is not exactly 0..20")
            if cycles < 1 or cycles > MAX_U32:
                _error(f"{label}:{line_number}: cycles is outside 1..2^32-1")
            if overhead < 0 or overhead > MAX_U32:
                _error(f"{label}:{line_number}: timer_overhead is outside 0..2^32-1")
            rows.append(
                {
                    "run": run,
                    "cycles": cycles,
                    "timer_overhead": overhead,
                    "digest": digest,
                }
            )
        elif kind == "EVR_COMPLETE":
            if header is None:
                _error(f"{label}:{line_number}: EVR_COMPLETE precedes EVR_HEADER")
            if len(fields) != 7 or fields[1] != "1" or fields[2] != expected_mode:
                _error(f"{label}:{line_number}: malformed EVR_COMPLETE")
            build_id = _hex(fields[3], f"{label}:{line_number} build_id", 64)
            corpus_id = _hex(fields[4], f"{label}:{line_number} corpus_id", 64)
            if build_id != expected_build_id or corpus_id != expected_corpus_id:
                _error(f"{label}:{line_number}: completion identity does not match manifest")
            if fields[5] != "21" or fields[6] != "0":
                _error(f"{label}:{line_number}: invalid EVR_COMPLETE counts/status")
            if len(rows) != 21:
                _error(f"{label}:{line_number}: completion does not follow 21 results")
            complete = True
        else:
            _error(f"{label}:{line_number}: malformed or unknown EVR marker")

    if header is None:
        _error(f"{label}: missing EVR_HEADER")
    if len(rows) != 21 or [row["run"] for row in rows] != list(range(21)):
        _error(f"{label}: need exactly one ordered run 0..20")
    if not complete:
        _error(f"{label}: missing EVR_COMPLETE")
    return {"samples": rows, "build_id": header[0], "corpus_id": header[1]}


def _stats(samples: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [sample[key] for sample in samples[1:]]
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def _delta(raw: dict[str, Any], safe: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("min", "median", "max"):
        absolute = safe[key] - raw[key]
        raw_value = raw[key]
        result[key] = {
            "absolute": absolute,
            "relative": (absolute / raw_value) if raw_value else None,
        }
    return result


def _remove_output(path: pathlib.Path) -> None:
    try:
        if path.is_symlink() or path.exists():
            if path.is_dir() and not path.is_symlink():
                _error(f"output path is a directory: {path}")
            path.unlink()
    except OSError as exc:
        _error(f"cannot remove stale output {path}: {exc}")


def _remove_output_best_effort(path: pathlib.Path) -> None:
    try:
        if path.is_symlink() or path.exists():
            if not path.is_dir() or path.is_symlink():
                path.unlink()
    except OSError:
        pass


def _atomic_write(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp_name = stream.name
            json.dump(value, stream, indent=2, sort_keys=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        temp_name = None
    except OSError as exc:
        _error(f"cannot atomically write output {path}: {exc}")
    finally:
        if temp_name is not None:
            try:
                pathlib.Path(temp_name).unlink()
            except OSError:
                pass


def collect(args: argparse.Namespace) -> dict[str, Any]:
    raw_path = pathlib.Path(args.raw)
    safe_path = pathlib.Path(args.safe)
    build_manifest_path = pathlib.Path(args.build_manifest)
    run_manifest_path = pathlib.Path(args.run_manifest)
    host_path = pathlib.Path(args.host_report)
    out_path = pathlib.Path(args.out)

    resolved_raw = raw_path.resolve()
    resolved_safe = safe_path.resolve()
    if resolved_raw == resolved_safe:
        _error("raw and safe must be different files; role identity cannot come from a filename")
    input_paths = [raw_path, safe_path, build_manifest_path, run_manifest_path, host_path]
    if any(out_path.resolve() == input_path.resolve() for input_path in input_paths):
        _error("output path must not overwrite an input evidence file")

    build_manifest, build_bytes, build_hash = _load_json(
        build_manifest_path, "build manifest"
    )
    build = _validate_build_manifest(build_manifest, build_manifest_path)
    run_manifest, run_bytes, run_hash = _load_json(
        run_manifest_path, "run manifest"
    )
    run = _validate_run_manifest(run_manifest, run_manifest_path)
    if run["board"]["serial"] != args.board_serial:
        _error("--board-serial does not match run manifest board.serial")
    if run["clock"]["hz"] != args.clock_hz:
        _error("--clock-hz does not match run manifest clock.hz")

    host_report, host_bytes, host_hash = _load_json(host_path, "host report")
    if host_hash != build["host_report"]["sha256"]:
        _error("host report SHA-256 does not match build manifest")
    host = _validate_host_report(host_report, host_path, build["corpus"])

    raw_bytes = _read_bytes(raw_path, "raw log")
    safe_bytes = _read_bytes(safe_path, "safe log")
    raw_hash = _sha256(raw_bytes)
    safe_hash = _sha256(safe_bytes)
    if raw_hash == safe_hash:
        _error("raw and safe log bytes are identical; role mix-up is not accepted")

    parsed: dict[str, dict[str, Any]] = {}
    for mode, data in (("raw", raw_bytes), ("safe", safe_bytes)):
        manifest_run = run["runs"][mode]
        if manifest_run["log_sha256"] != _sha256(data):
            _error(f"{mode} log SHA-256 does not match run manifest")
        binary = build["binaries"][mode]
        if manifest_run["build_id"] != binary["build_id"]:
            _error(f"{mode} run build_id does not match build manifest")
        if manifest_run["elf_sha256"] != binary["sha256"]:
            _error(f"{mode} run ELF SHA-256 does not match build manifest")
        parsed[mode] = _parse_log(
            data,
            f"{mode} log",
            mode,
            binary["build_id"],
            build["corpus"]["id"],
        )

    all_digests = {
        sample["digest"]
        for mode in ("raw", "safe")
        for sample in parsed[mode]["samples"]
    }
    functional_digest_match = len(all_digests) == 1
    independent_reference_crosscheck = (
        host["hardware_corpus"]["reference_pass"] is True
        and all(
            sample["digest"] == build["corpus"]["expected_digest"]
            for mode in ("raw", "safe")
            for sample in parsed[mode]["samples"]
        )
    )

    run_output: dict[str, Any] = {}
    cycle_stats: dict[str, dict[str, Any]] = {}
    overhead_stats: dict[str, dict[str, Any]] = {}
    for mode in ("raw", "safe"):
        manifest_run = run["runs"][mode]
        samples = parsed[mode]["samples"]
        cycle_stats[mode] = _stats(samples, "cycles")
        overhead_stats[mode] = _stats(samples, "timer_overhead")
        run_output[mode] = {
            **manifest_run,
            "corpus_id": build["corpus"]["id"],
            "samples": samples,
            "cycles_run1_to_20": cycle_stats[mode],
            "timer_overhead_run1_to_20": overhead_stats[mode],
        }

    environment = run["environment"]
    build_memory = build["identity"].get("memory", {})
    size_report = build["identity"].get("size_report")
    cycle_delta = _delta(cycle_stats["raw"], cycle_stats["safe"])
    report = {
        "schema": 2,
        "status": "PASS" if functional_digest_match and independent_reference_crosscheck else "FAIL",
        "claim": (
            "functional digest and independent host-reference cross-check for the exact corpus; "
            "identity/completeness checks reduce accidental evidence mix-ups but do not prevent forgery"
        ),
        "target": build["target"],
        "build_identity": build["identity"],
        "scope": {
            "taps": build["corpus"]["taps"],
            "block": build["corpus"]["block"],
            "samples": build["corpus"]["samples"],
            "blocks": build["corpus"]["blocks"],
            "timed_work": "initialization plus all blocks; logging and digest calculation outside timing",
        },
        "batch_id": run["batch_id"],
        "board": run["board"],
        "clock": run["clock"],
        "debugger": run["debugger"],
        "environment": environment,
        "corpus": build["corpus"],
        "artifacts": {
            "build_manifest_sha256": build_hash,
            "run_manifest_sha256": run_hash,
            "host_report_sha256": host_hash,
            "binaries": build["binaries"],
            "logs": {"raw_sha256": raw_hash, "safe_sha256": safe_hash},
        },
        "runs": run_output,
        "functional_digest_match": functional_digest_match,
        "independent_reference_crosscheck": independent_reference_crosscheck,
        "cycle_comparison": {
            "basis": "run 1..20 min/median/max; run 0 retained as warm-up only",
            "raw_to_safe": cycle_delta,
        },
        "memory": {
            "linked_size_report": size_report,
            "stack_peak_bytes": None,
            "stack_peak_reason": "No reliable stack high-water mark is present in this run manifest/log protocol.",
            "heap_peak_bytes": None,
            "heap_peak_reason": "Heap peak was not measured; unknown is not represented as zero.",
            "heap_policy": build_memory.get("heap_policy"),
        },
        "application_budget": {
            "status": "NOT_EVALUATED",
            "reason": "No application-level Flash, RAM, or cycle budget was supplied.",
        },
    }
    # Keep the hashes read above visible in the report even when a future
    # caller supplies a manifest with extra metadata. build_bytes/run_bytes
    # are intentionally read and hashed by _load_json as evidence inputs.
    del build_bytes, run_bytes, host_bytes
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate paired EVR hardware logs against build/run manifests"
    )
    parser.add_argument("--raw", required=True, help="raw C-path log")
    parser.add_argument("--safe", required=True, help="safe Rust wrapper log")
    parser.add_argument("--board-serial", required=True)
    parser.add_argument("--clock-hz", required=True, type=int)
    parser.add_argument("--host-report", default="reports/local/host.json")
    parser.add_argument("--build-manifest", required=True)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--out", default="reports/local/hardware.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    out_path = pathlib.Path(args.out)
    try:
        # Remove an old PASS before any new validation. A failed collection
        # must never leave a stale report for a downstream release step.
        _remove_output(out_path)
        report = collect(args)
        _atomic_write(out_path, report)
        if report["status"] != "PASS":
            print(
                "hardware collection failed: functional digest/reference cross-check did not pass; "
                f"see {out_path}",
                file=sys.stderr,
            )
            return 1
    except CollectorError as exc:
        _remove_output_best_effort(out_path)
        print(f"hardware collection failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        _remove_output_best_effort(out_path)
        print(f"hardware collection failed: {exc}", file=sys.stderr)
        return 1
    print(f"hardware report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
