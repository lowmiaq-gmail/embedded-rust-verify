import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "hardware-impact.py"
SPEC = importlib.util.spec_from_file_location("hardware_impact", SCRIPT)
assert SPEC and SPEC.loader
hardware_impact = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = hardware_impact
SPEC.loader.exec_module(hardware_impact)


class HardwareImpactClassificationTests(unittest.TestCase):
    def classify(self, *paths):
        return hardware_impact.classify_paths(paths)

    def test_empty_diff_is_no_change(self):
        result = self.classify()
        self.assertEqual(result.classification, hardware_impact.NO_CHANGE)
        self.assertEqual(result.paths, ())

    def test_documentation_status_launch_and_reports_do_not_need_hardware(self):
        result = self.classify(
            "README.md", "docs/STATUS.md", "docs/launch-posts.md", "reports/initial/host.json"
        )
        self.assertEqual(result.classification, hardware_impact.DOCUMENTATION)
        self.assertFalse(result.requires_new_hardware)

    def test_evidence_parser_change_reuses_identity_matched_logs(self):
        result = self.classify("tools/collect-hardware.py", "tools/size-report.py")
        self.assertEqual(result.classification, hardware_impact.EVIDENCE_REPARSE)
        self.assertIn("identity-matched", result.reason)

    def test_pipeline_only_includes_ci_and_this_classifier(self):
        result = self.classify(".github/workflows/verify.yml", "tools/hardware-impact.py")
        self.assertEqual(result.classification, hardware_impact.PIPELINE_ONLY)
        self.assertFalse(result.requires_new_hardware)

    def test_test_only_change_is_not_hardware_invalidation(self):
        result = self.classify("tests/test_hardware_impact.py")
        self.assertEqual(result.classification, hardware_impact.PIPELINE_ONLY)

    def test_host_reference_change_requires_reference_recheck(self):
        result = self.classify("crates/verify-core/src/comparator.rs", "tests/fixtures/reference.json")
        self.assertEqual(result.classification, hardware_impact.HOST_REFERENCE)
        self.assertTrue(result.may_require_new_hardware)
        self.assertIn("escalate", result.reason)

    def test_known_production_change_requires_hardware(self):
        result = self.classify(
            "adapters/cmsis-dsp/src/ffi.rs",
            "platforms/cortex-m/memory.x",
            "tools/cross-build.sh",
            "corpus/board.json",
        )
        self.assertEqual(result.classification, hardware_impact.HARDWARE_REQUIRED)
        self.assertTrue(result.requires_new_hardware)

    def test_unknown_non_documentation_change_is_conservative(self):
        result = self.classify("src/new_integration.py")
        self.assertEqual(result.classification, hardware_impact.HARDWARE_REQUIRED)
        self.assertIn("unknown impact", result.reason)

    def test_unknown_mixed_with_documentation_still_names_unknown_path(self):
        result = self.classify("README.md", "src/new_integration.py")
        self.assertEqual(result.classification, hardware_impact.HARDWARE_REQUIRED)
        self.assertIn("src/new_integration.py", result.reason)
        self.assertNotIn("README.md", result.reason)

    def test_mixed_changes_take_highest_impact(self):
        self.assertEqual(
            self.classify("README.md", "tools/collect-hardware.py").classification,
            hardware_impact.EVIDENCE_REPARSE,
        )
        self.assertEqual(
            self.classify("tools/collect-hardware.py", "tools/reference.py").classification,
            hardware_impact.HOST_REFERENCE,
        )
        self.assertEqual(
            self.classify("docs/hardware.md", "adapters/cmsis-dsp/src/lib.rs").classification,
            hardware_impact.HARDWARE_REQUIRED,
        )

    def test_paths_are_deduplicated_and_stable(self):
        result = self.classify("./README.md", "README.md", "docs/STATUS.md")
        self.assertEqual(result.paths, ("README.md", "docs/STATUS.md"))


class HardwareImpactCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_direct_path_json_is_machine_readable_and_successful(self):
        completed = self.run_cli("--path", "README.md", "--json")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["classification"], hardware_impact.DOCUMENTATION)
        self.assertFalse(report["requires_new_hardware"])

    def test_base_head_interface_and_empty_diff(self):
        completed = self.run_cli("HEAD", "HEAD", "--json")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["classification"], hardware_impact.NO_CHANGE)

    def test_missing_arguments_is_parameter_error(self):
        completed = self.run_cli("--json")
        self.assertNotEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
