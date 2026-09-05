import importlib.util
import json
import pathlib
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "tools" / "fingerprint.py"
SPEC = importlib.util.spec_from_file_location("fingerprint", MODULE_PATH)
fingerprint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fingerprint)


def corpus(reference_pass=True):
    return {
        "schema": 1,
        "seed": "0x514f2701",
        "taps": 31,
        "block": 64,
        "blocks": 8,
        "samples": 512,
        "coeff_digest": "1111111111111111",
        "input_digest": "2222222222222222",
        "expected_digest": "3333333333333333",
        "reference_pass": reference_pass,
    }


class FingerprintTests(unittest.TestCase):
    def host_report(self, value):
        temporary = tempfile.NamedTemporaryFile(mode="w", delete=False)
        json.dump({"hardware_corpus": value}, temporary)
        temporary.close()
        self.addCleanup(pathlib.Path(temporary.name).unlink)
        return temporary.name

    def test_corpus_identity_is_stable(self):
        path = self.host_report(corpus())
        self.assertEqual(fingerprint.corpus_identity(path), fingerprint.corpus_identity(path))
        self.assertEqual(len(fingerprint.corpus_identity(path)), 64)

    def test_reference_pass_is_strict_boolean(self):
        for value in ("false", 1, 0, None, False):
            with self.subTest(value=value), self.assertRaises(SystemExit):
                fingerprint.require_hardware_corpus(self.host_report(corpus(value)))

    def test_corpus_shape_is_exact(self):
        value = corpus()
        value["blocks"] = 7
        with self.assertRaises(SystemExit):
            fingerprint.require_hardware_corpus(self.host_report(value))


if __name__ == "__main__":
    unittest.main()
