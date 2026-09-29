"""Ensure the NanoJev adapter rejects a different native checkpoint."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "inference" / "nanojev" / "bridge.py"
SPEC = importlib.util.spec_from_file_location("nanojev_bridge", MODULE_PATH)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class NanoJevBridgeTests(unittest.TestCase):
    def test_native_checkpoint_directory_must_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            expected = Path(temporary) / "expected"
            other = Path(temporary) / "other"
            native = {
                "checkpoint": {"directory": str(other), "base_revision": bridge.BASE_REVISION,
                               "set_head": "attention"},
                "states": [{"id": "case", "answers": {"next": {
                    "type": "choice", "value": "no_tool", "probabilities": {"no_tool": 1.0}}}}],
                "execution": {"server_evaluation_seconds": 0.01},
            }
            with self.assertRaisesRegex(ValueError, "different checkpoint directory"):
                bridge.systemone_response(native, expected)
            native["checkpoint"]["directory"] = str(expected)
            self.assertEqual(bridge.systemone_response(native, expected)["answers"]["next"]["value"], "no_tool")


if __name__ == "__main__":
    unittest.main()
