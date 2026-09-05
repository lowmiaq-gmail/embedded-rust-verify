"""Standard-library regression tests for the strict hardware collector."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "hardware"
SCRIPT = ROOT / "tools" / "collect-hardware.py"
RAW_FIXTURE = FIXTURES / "valid_raw.log"
SAFE_FIXTURE = FIXTURES / "valid_safe.log"
HOST_FIXTURE = FIXTURES / "valid_host.json"
RAW_BUILD_ID = "1" * 64
SAFE_BUILD_ID = "2" * 64
CORPUS_ID = "3" * 64
RAW_ELF_SHA = "a" * 64
SAFE_ELF_SHA = "b" * 64
EXPECTED_DIGEST = "84bd49eb9b034da3"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class CollectorRegressionTests(unittest.TestCase):
    """Exercise a valid synthetic pair and each known false-acceptance class."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="collector-test-")
        self.work = pathlib.Path(self.temp_dir.name)
        self.host_path = self.work / "host.json"
        self.host_path.write_bytes(HOST_FIXTURE.read_bytes())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_log(self, name: str, data: bytes) -> pathlib.Path:
        path = self.work / name
        path.write_bytes(data)
        return path

    def _write_manifests(
        self,
        raw_path: pathlib.Path,
        safe_path: pathlib.Path,
        *,
        clock_hz: int = 16_000_000,
        run_update: dict | None = None,
        build_update: dict | None = None,
    ) -> tuple[pathlib.Path, pathlib.Path]:
        build = {
            "schema": 2,
            "target": "thumbv7em-none-eabihf",
            "corpus": {
                "id": CORPUS_ID,
                "schema": 1,
                "seed": "0x514f2701",
                "taps": 31,
                "block": 64,
                "samples": 512,
                "blocks": 8,
                "expected_digest": EXPECTED_DIGEST,
                "coeff_digest": "1111111111111111",
                "input_digest": "2222222222222222",
            },
            "host_report": {"sha256": _sha256(self.host_path.read_bytes())},
            "binaries": {
                "raw": {"build_id": RAW_BUILD_ID, "sha256": RAW_ELF_SHA},
                "safe": {"build_id": SAFE_BUILD_ID, "sha256": SAFE_ELF_SHA},
            },
        }
        if build_update:
            for key, value in build_update.items():
                if isinstance(value, dict) and isinstance(build.get(key), dict):
                    build[key].update(value)
                else:
                    build[key] = value

        run = {
            "schema": 1,
            "status": "CAPTURED",
            "batch_id": "synthetic-batch-001",
            "board": {
                "model": "NUCLEO-F401RE",
                "mcu": "STM32F401RE",
                "core": "Arm Cortex-M4F",
                "serial": "SYNTHETIC-STLINK-001",
                "supply": "synthetic fixture",
            },
            "clock": {
                "hz": clock_hz,
                "source": "reset-default HSI",
                "verification": "synthetic fixture; no hardware verification",
                "maximum_rating_used_as_measurement": False,
            },
            "debugger": {
                "tool": "openocd",
                "version": "synthetic",
                "probe_command": ["openocd", "synthetic-probe-check"],
            },
            "environment": {
                "host_os": "synthetic",
                "board_config": "synthetic",
                "flash_execution": "synthetic",
                "static_data": "synthetic",
                "flash_wait_states": "synthetic",
                "prefetch": "synthetic",
                "interrupts": "synthetic",
                "fpu": "synthetic",
            },
            "runs": {
                "raw": {
                    "mode": "raw",
                    "build_id": RAW_BUILD_ID,
                    "elf_sha256": RAW_ELF_SHA,
                    "command": ["openocd", "raw.elf"],
                    "exit_code": 0,
                    "timed_out": False,
                    "log_sha256": _sha256(raw_path.read_bytes()),
                    "log_path": raw_path.name,
                    "started_at": "synthetic-start",
                    "completed_at": "synthetic-end",
                },
                "safe": {
                    "mode": "safe",
                    "build_id": SAFE_BUILD_ID,
                    "elf_sha256": SAFE_ELF_SHA,
                    "command": ["openocd", "safe.elf"],
                    "exit_code": 0,
                    "timed_out": False,
                    "log_sha256": _sha256(safe_path.read_bytes()),
                    "log_path": safe_path.name,
                    "started_at": "synthetic-start",
                    "completed_at": "synthetic-end",
                },
            },
        }
        if run_update:
            for key, value in run_update.items():
                if isinstance(value, dict) and isinstance(run.get(key), dict):
                    if key == "runs":
                        for mode, mode_update in value.items():
                            run[key][mode].update(mode_update)
                    else:
                        run[key].update(value)
                else:
                    run[key] = value

        build_path = self.work / "build.json"
        run_path = self.work / "run.json"
        build_path.write_text(json.dumps(build, indent=2) + "\n", encoding="utf-8")
        run_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
        return build_path, run_path

    def _run(
        self,
        *,
        raw: pathlib.Path | None = None,
        safe: pathlib.Path | None = None,
        clock_cli: int = 16_000_000,
        run_update: dict | None = None,
        build_update: dict | None = None,
        stale_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        raw = raw or RAW_FIXTURE
        safe = safe or SAFE_FIXTURE
        build_path, run_path = self._write_manifests(
            raw,
            safe,
            clock_hz=clock_cli,
            run_update=run_update,
            build_update=build_update,
        )
        output = self.work / "hardware.json"
        if stale_output:
            output.write_text('{"status":"PASS"}\n', encoding="utf-8")
        command = [
            sys.executable,
            str(SCRIPT),
            "--raw",
            str(raw),
            "--safe",
            str(safe),
            "--board-serial",
            "SYNTHETIC-STLINK-001",
            "--clock-hz",
            str(clock_cli),
            "--host-report",
            str(self.host_path),
            "--build-manifest",
            str(build_path),
            "--run-manifest",
            str(run_path),
            "--out",
            str(output),
        ]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        result.output_path = output  # type: ignore[attr-defined]
        return result

    def _assert_rejected(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_valid_synthetic_pair_passes_and_preserves_evidence(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.output_path.read_text(encoding="utf-8"))  # type: ignore[attr-defined]
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(report["runs"]["raw"]["samples"]), 21)
        self.assertEqual(report["runs"]["raw"]["samples"][0]["run"], 0)
        self.assertEqual(report["runs"]["safe"]["samples"][-1]["run"], 20)
        self.assertEqual(report["runs"]["raw"]["cycles_run1_to_20"], {"min": 1001, "median": 1010.5, "max": 1020})
        self.assertEqual(report["runs"]["safe"]["cycles_run1_to_20"], {"min": 1101, "median": 1110.5, "max": 1120})
        self.assertEqual(report["cycle_comparison"]["raw_to_safe"]["median"]["absolute"], 100)
        self.assertEqual(report["memory"]["stack_peak_bytes"], None)
        self.assertEqual(report["memory"]["heap_peak_bytes"], None)
        self.assertEqual(report["application_budget"]["status"], "NOT_EVALUATED")
        self.assertEqual(report["artifacts"]["logs"]["raw_sha256"], _sha256(RAW_FIXTURE.read_bytes()))
        self.assertEqual(report["artifacts"]["logs"]["safe_sha256"], _sha256(SAFE_FIXTURE.read_bytes()))

    def test_same_file_is_rejected(self) -> None:
        result = self._run(safe=RAW_FIXTURE)
        self._assert_rejected(result)
        self.assertIn("different files", result.stderr)

    def test_same_bytes_in_different_files_are_rejected(self) -> None:
        safe = self._write_log("safe-copy.log", RAW_FIXTURE.read_bytes())
        result = self._run(safe=safe)
        self._assert_rejected(result)
        self.assertIn("identical", result.stderr)

    def test_zero_clock_is_rejected(self) -> None:
        result = self._run(clock_cli=0)
        self._assert_rejected(result)
        self.assertIn("greater than zero", result.stderr)

    def test_cycles_above_hardware_counter_range_are_rejected(self) -> None:
        data = RAW_FIXTURE.read_bytes().replace(b",0,1000,10,", b",0,4294967296,10,")
        raw = self._write_log("cycles-too-large.log", data)
        result = self._run(raw=raw)
        self._assert_rejected(result)
        self.assertIn("cycles is outside", result.stderr)

    def test_reference_pass_string_false_is_rejected(self) -> None:
        host = json.loads(self.host_path.read_text(encoding="utf-8"))
        host["hardware_corpus"]["reference_pass"] = "false"
        self.host_path.write_text(json.dumps(host, indent=2) + "\n", encoding="utf-8")
        result = self._run()
        self._assert_rejected(result)
        self.assertIn("boolean true", result.stderr)

    def test_role_mixing_is_rejected_even_when_log_has_different_bytes(self) -> None:
        mixed = RAW_FIXTURE.read_bytes() + b"debugger trailer\n"
        safe = self._write_log("safe-role-mixed.log", mixed)
        result = self._run(safe=safe)
        self._assert_rejected(result)
        self.assertIn("role", result.stderr)

    def test_old_build_identity_is_rejected(self) -> None:
        old = RAW_FIXTURE.read_bytes().replace(RAW_BUILD_ID.encode(), ("4" * 64).encode())
        raw = self._write_log("old-build.log", old)
        result = self._run(raw=raw)
        self._assert_rejected(result)
        self.assertIn("build_id", result.stderr)

    def test_wrong_corpus_identity_is_rejected(self) -> None:
        wrong = RAW_FIXTURE.read_bytes().replace(CORPUS_ID.encode(), ("4" * 64).encode())
        raw = self._write_log("wrong-corpus.log", wrong)
        result = self._run(raw=raw)
        self._assert_rejected(result)
        self.assertIn("corpus_id", result.stderr)

    def test_wrong_host_summary_is_rejected(self) -> None:
        host = json.loads(self.host_path.read_text(encoding="utf-8"))
        host["hardware_corpus"]["expected_digest"] = "deadbeefdeadbeef"
        self.host_path.write_text(json.dumps(host, indent=2) + "\n", encoding="utf-8")
        result = self._run()
        self._assert_rejected(result)
        self.assertIn("expected_digest", result.stderr)

    def test_digest_mismatch_writes_fail_report_and_nonzero_status(self) -> None:
        data = SAFE_FIXTURE.read_bytes().replace(
            b",0,1100,10,84bd49eb9b034da3",
            b",0,1100,10,deadbeefdeadbeef",
            1,
        )
        safe = self._write_log("digest-mismatch.log", data)
        result = self._run(safe=safe)
        self._assert_rejected(result)
        report = json.loads(result.output_path.read_text(encoding="utf-8"))  # type: ignore[attr-defined]
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["functional_digest_match"])

    def test_truncated_log_is_rejected(self) -> None:
        truncated = b"\n".join(RAW_FIXTURE.read_bytes().splitlines()[:-1]) + b"\n"
        raw = self._write_log("truncated.log", truncated)
        result = self._run(raw=raw)
        self._assert_rejected(result)
        self.assertIn("missing EVR_COMPLETE", result.stderr)

    def test_duplicate_run_is_rejected(self) -> None:
        lines = RAW_FIXTURE.read_bytes().splitlines()
        duplicate = lines[4]
        lines.insert(5, duplicate)
        raw = self._write_log("duplicate-run.log", b"\n".join(lines) + b"\n")
        result = self._run(raw=raw)
        self._assert_rejected(result)
        self.assertIn("run sequence", result.stderr)

    def test_missing_manifest_metadata_is_rejected(self) -> None:
        result = self._run(run_update={"debugger": {"version": None}})
        self._assert_rejected(result)
        self.assertIn("debugger.version", result.stderr)

    def test_failed_exit_status_is_rejected(self) -> None:
        result = self._run(run_update={"runs": {"raw": {"exit_code": 1}}})
        self._assert_rejected(result)
        self.assertIn("exit_code must be 0", result.stderr)

    def test_damaged_evr_line_is_rejected(self) -> None:
        damaged = RAW_FIXTURE.read_bytes().replace(
            b"EVR_RESULT,1,raw,", b"EVR_RESULT,1,raw,", 1
        )
        # Remove one digest nibble from the first result while retaining EVR_.
        damaged = damaged.replace(
            b",0,1000,10,84bd49eb9b034da3", b",0,1000,10,84bd49eb9b034da", 1
        )
        raw = self._write_log("damaged-evr.log", damaged)
        result = self._run(raw=raw)
        self._assert_rejected(result)
        self.assertIn("digest", result.stderr)

    def test_stale_pass_output_is_removed_on_failure(self) -> None:
        result = self._run(raw=self._write_log("bad.log", b"EVR_RESULT,bad\n"), stale_output=True)
        self._assert_rejected(result)
        self.assertFalse(result.output_path.exists())  # type: ignore[attr-defined]

    def test_cli_board_identity_must_match_manifest(self) -> None:
        build_path, run_path = self._write_manifests(RAW_FIXTURE, SAFE_FIXTURE)
        output = self.work / "board-mismatch.json"
        command = [
            sys.executable,
            str(SCRIPT),
            "--raw",
            str(RAW_FIXTURE),
            "--safe",
            str(SAFE_FIXTURE),
            "--board-serial",
            "WRONG-SERIAL",
            "--clock-hz",
            "16000000",
            "--host-report",
            str(self.host_path),
            "--build-manifest",
            str(build_path),
            "--run-manifest",
            str(run_path),
            "--out",
            str(output),
        ]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self._assert_rejected(result)
        self.assertIn("board.serial", result.stderr)


if __name__ == "__main__":
    unittest.main()
