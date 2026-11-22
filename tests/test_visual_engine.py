import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import Video_Studyosu_V5_Arayuz_Onizleme as app


class _Response:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class VisualEngineTests(unittest.TestCase):
    @patch("Video_Studyosu_V5_Arayuz_Onizleme.urllib.request.urlopen")
    def test_auto_workflow_uses_first_installed_checkpoint(self, mocked_open):
        mocked_open.return_value = _Response(["cinematicXL.safetensors", "other.safetensors"])
        with tempfile.TemporaryDirectory() as tmp:
            with patch("Video_Studyosu_V5_Arayuz_Onizleme.tempfile.gettempdir", return_value=tmp):
                path, checkpoint = app.create_default_comfyui_workflow(
                    "http://127.0.0.1:8188", 1024, 1792
                )
            self.assertEqual(checkpoint, "cinematicXL.safetensors")
            workflow = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(workflow["1"]["inputs"]["ckpt_name"], checkpoint)
            self.assertEqual(workflow["4"]["inputs"]["width"], 1024)
            self.assertEqual(workflow["4"]["inputs"]["height"], 1792)
            self.assertEqual(workflow["5"]["inputs"]["denoise"], 1.0)
            self.assertEqual(workflow["7"]["class_type"], "SaveImage")

    @patch("Video_Studyosu_V5_Arayuz_Onizleme.urllib.request.urlopen")
    def test_auto_workflow_reports_missing_checkpoint(self, mocked_open):
        mocked_open.return_value = _Response([])
        with self.assertRaisesRegex(RuntimeError, "checkpoint modeli bulunamadı"):
            app.create_default_comfyui_workflow("http://127.0.0.1:8188")

    def test_character_prompt_preserves_identity_and_wardrobe_cues(self):
        prompt = app.build_character_consistency_prompt(
            {"character_ids": [0]},
            [{"name": "Cansu", "description": "long blonde hair", "wardrobe": "black sweater"}],
        )
        self.assertIn("Cansu", prompt)
        self.assertIn("long blonde hair", prompt)
        self.assertIn("black sweater", prompt)


if __name__ == "__main__":
    unittest.main()
