"""Tests for CI revalidation of a committed manual evidence package."""

import json
import hashlib
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_collect_hardware as collector_fixture


ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify-hardware-evidence.py"


class HardwareEvidenceVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="evidence-test-")
        self.evidence = pathlib.Path(self.temporary.name) / "capture"
        artifacts = self.evidence / "artifacts"
        artifacts.mkdir(parents=True)

        helper = collector_fixture.CollectorRegressionTests()
        helper.setUp()
        self.addCleanup(helper.tearDown)
        build, run = helper._write_manifests(
            collector_fixture.RAW_FIXTURE, collector_fixture.SAFE_FIXTURE
        )
        shutil.copy2(collector_fixture.RAW_FIXTURE, self.evidence / "raw.log")
        shutil.copy2(collector_fixture.SAFE_FIXTURE, self.evidence / "safe.log")
        shutil.copy2(helper.host_path, artifacts / "host.json")
        shutil.copy2(build, artifacts / "build-manifest.json")
        shutil.copy2(run, self.evidence / "run-manifest.json")
        raw_elf = b"synthetic raw ELF fixture"
        safe_elf = b"synthetic safe ELF fixture"
        (artifacts / "raw.elf").write_bytes(raw_elf)
        (artifacts / "safe.elf").write_bytes(safe_elf)
        build_value = json.loads((artifacts / "build-manifest.json").read_text())
        run_value = json.loads((self.evidence / "run-manifest.json").read_text())
        for mode, value in (("raw", raw_elf), ("safe", safe_elf)):
            digest = hashlib.sha256(value).hexdigest()
            build_value["binaries"][mode]["path"] = f"{mode}.elf"
            build_value["binaries"][mode]["sha256"] = digest
            run_value["runs"][mode]["elf_sha256"] = digest
        (artifacts / "build-manifest.json").write_text(
            json.dumps(build_value, indent=2) + "\n", encoding="utf-8"
        )
        (self.evidence / "run-manifest.json").write_text(
            json.dumps(run_value, indent=2) + "\n", encoding="utf-8"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(collector_fixture.SCRIPT),
                "--raw",
                str(self.evidence / "raw.log"),
                "--safe",
                str(self.evidence / "safe.log"),
                "--board-serial",
                "SYNTHETIC-STLINK-001",
                "--clock-hz",
                "16000000",
                "--host-report",
                str(artifacts / "host.json"),
                "--build-manifest",
                str(artifacts / "build-manifest.json"),
                "--run-manifest",
                str(self.evidence / "run-manifest.json"),
                "--out",
                str(self.evidence / "hardware.json"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def tearDown(self):
        self.temporary.cleanup()

    def run_verifier(self):
        return subprocess.run(
            [sys.executable, str(VERIFIER), "--evidence-dir", str(self.evidence)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_exact_evidence_package_passes(self):
        result = self.run_verifier()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("hardware evidence: PASS", result.stdout)

    def test_modified_summary_is_rejected(self):
        path = self.evidence / "hardware.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["cycle_comparison"]["raw_to_safe"]["median"]["absolute"] += 1
        path.write_text(json.dumps(report) + "\n", encoding="utf-8")
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exactly match", result.stderr)

    def test_modified_elf_is_rejected(self):
        (self.evidence / "artifacts" / "raw.elf").write_bytes(b"stale ELF")
        result = self.run_verifier()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("raw ELF SHA-256", result.stderr)


if __name__ == "__main__":
    unittest.main()
