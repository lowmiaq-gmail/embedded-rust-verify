import hashlib
import importlib.util
import json
import pathlib
import tempfile
import types
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "tools" / "run-hardware.py"
SPEC = importlib.util.spec_from_file_location("run_hardware", MODULE_PATH)
run_hardware = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_hardware)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class RunHardwareTests(unittest.TestCase):
    def artifact_dir(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = pathlib.Path(temporary.name)
        raw = b"raw elf"
        safe = b"safe elf"
        host = b'{"hardware_corpus":{}}'
        (root / "raw.elf").write_bytes(raw)
        (root / "safe.elf").write_bytes(safe)
        (root / "host.json").write_bytes(host)
        manifest = {
            "schema": 2,
            "target": "thumbv7em-none-eabihf",
            "corpus": {"id": "c" * 64},
            "host_report": {"path": "host.json", "sha256": digest(host)},
            "binaries": {
                "raw": {"path": "raw.elf", "sha256": digest(raw), "build_id": "a" * 64},
                "safe": {"path": "safe.elf", "sha256": digest(safe), "build_id": "b" * 64},
            },
        }
        (root / "build-manifest.json").write_text(json.dumps(manifest))
        return root

    def test_build_manifest_binds_elf_and_host_bytes(self):
        root = self.artifact_dir()
        _, manifest = run_hardware.load_build(root)
        self.assertEqual(manifest["binaries"]["raw"]["sha256"], digest(b"raw elf"))
        (root / "raw.elf").write_bytes(b"stale")
        with self.assertRaisesRegex(SystemExit, "raw ELF SHA-256"):
            run_hardware.load_build(root)

    def test_raw_and_safe_build_identity_must_differ(self):
        root = self.artifact_dir()
        path = root / "build-manifest.json"
        manifest = json.loads(path.read_text())
        manifest["binaries"]["safe"]["build_id"] = "a" * 64
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(SystemExit, "must differ"):
            run_hardware.load_build(root)

    def test_capture_command_selects_one_probe_and_has_two_timeouts(self):
        args = types.SimpleNamespace(
            openocd="/usr/bin/openocd",
            board_config="board/st_nucleo_f4.cfg",
            device_serial="REAL-SERIAL",
            timeout_seconds=17,
        )
        command = run_hardware.capture_command(args, "/evidence/raw.elf")
        self.assertIn("adapter serial REAL-SERIAL", command)
        self.assertIn("program /evidence/raw.elf verify", command)
        self.assertIn("wait_halt 17000", command)
        self.assertEqual(command.count("program /evidence/raw.elf verify"), 1)


if __name__ == "__main__":
    unittest.main()
