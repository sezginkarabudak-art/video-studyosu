import io
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


class _RawResponse(_Response):
    def __init__(self, payload):
        self.payload = payload
    def read(self):
        return self.payload


class VisualEngineTests(unittest.TestCase):
    @patch("Video_Studyosu_V5_Arayuz_Onizleme.urllib.request.urlopen")
    def test_auto_workflow_prefers_realistic_sdxl_checkpoint(self, mocked_open):
        mocked_open.return_value = _Response(["anime_model.safetensors", "realvisXL_sdxl.safetensors", "base.safetensors"])
        with tempfile.TemporaryDirectory() as tmp:
            with patch("Video_Studyosu_V5_Arayuz_Onizleme.tempfile.gettempdir", return_value=tmp):
                path, checkpoint = app.create_default_comfyui_workflow(
                    "http://127.0.0.1:8188", 1024, 1792
                )
            self.assertEqual(checkpoint, "realvisXL_sdxl.safetensors")
            workflow = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(workflow["1"]["inputs"]["ckpt_name"], checkpoint)
            self.assertEqual(workflow["4"]["inputs"]["width"], 768)
            self.assertEqual(workflow["4"]["inputs"]["height"], 1344)
            self.assertIn("photorealistic", workflow["2"]["inputs"]["text"])
            self.assertIn("stick figure", workflow["3"]["inputs"]["text"])
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

    def test_ipadapter_chain_expands_for_multiple_character_angles(self):
        workflow = {
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "positive"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "negative"}},
            "5": {"class_type": "KSampler", "inputs": {
                "model": ["9", 0], "positive": ["2", 0], "negative": ["3", 0], "seed": 1
            }},
            "8": {"class_type": "IPAdapterUnifiedLoader", "inputs": {"model": ["1", 0], "preset": "PLUS"}},
            "9": {"class_type": "IPAdapter", "inputs": {
                "model": ["8", 0], "ipadapter": ["8", 1], "image": None, "weight": 0.85
            }},
        }
        nodes = app.expand_ipadapter_workflow_for_references(workflow, 3)
        self.assertEqual([node_id for node_id, _ in nodes], ["9", "10", "11"])
        self.assertEqual(workflow["10"]["inputs"]["model"], ["9", 0])
        self.assertEqual(workflow["11"]["inputs"]["model"], ["10", 0])
        self.assertEqual(workflow["5"]["inputs"]["model"], ["11", 0])
        self.assertEqual(len(nodes), 3)

    @patch("Video_Studyosu_V5_Arayuz_Onizleme.time.sleep")
    @patch("Video_Studyosu_V5_Arayuz_Onizleme.urllib.request.urlopen")
    def test_generation_preserves_sdxl_optimized_latent_dimensions(self, mocked_open, _sleep):
        with tempfile.TemporaryDirectory() as tmp:
            workflow = {
                "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "positive"}},
                "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "negative"}},
                "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 1344}},
                "5": {"class_type": "KSampler", "inputs": {
                    "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "seed": 1
                }},
                "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "test", "images": ["6", 0]}},
            }
            workflow_path = Path(tmp) / "workflow.json"
            workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
            captured = {}
            def fake_open(request, timeout=30):
                url = request.full_url if hasattr(request, "full_url") else request
                if url.endswith("/prompt"):
                    captured["workflow"] = json.loads(request.data.decode("utf-8"))["prompt"]
                    return _Response({"prompt_id": "test-prompt"})
                if "/history/test-prompt" in url:
                    return _Response({"test-prompt": {"outputs": {
                        "7": {"images": [{"filename": "generated.png", "type": "output"}]}
                    }}})
                if "/view?" in url:
                    buffer = io.BytesIO()
                    app.Image.new("RGB", (2, 2)).save(buffer, format="PNG")
                    return _RawResponse(buffer.getvalue())
                raise AssertionError("Unexpected URL: " + url)
            mocked_open.side_effect = fake_open
            app.comfyui_generate_image(
                "http://127.0.0.1:8188", str(workflow_path), "A cinematic scene",
                tmp, width=1024, height=1792, seed=42
            )
            latent = captured["workflow"]["4"]["inputs"]
            self.assertEqual(latent["width"], 768)
            self.assertEqual(latent["height"], 1344)

    @patch("Video_Studyosu_V5_Arayuz_Onizleme.time.sleep")
    @patch("Video_Studyosu_V5_Arayuz_Onizleme.urllib.request.urlopen")
    def test_generation_uploads_all_character_reference_angles(self, mocked_open, _sleep):
        with tempfile.TemporaryDirectory() as tmp:
            refs = []
            for name in ("front.png", "side.png"):
                path = Path(tmp) / name
                path.write_bytes(b"reference-image")
                refs.append(str(path))
            workflow = {
                "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "positive"}},
                "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "negative"}},
                "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 1344}},
                "5": {"class_type": "KSampler", "inputs": {
                    "model": ["9", 0], "positive": ["2", 0], "negative": ["3", 0], "seed": 1
                }},
                "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "test", "images": ["6", 0]}},
                "8": {"class_type": "IPAdapterUnifiedLoader", "inputs": {"model": ["1", 0], "preset": "PLUS"}},
                "9": {"class_type": "IPAdapter", "inputs": {
                    "model": ["8", 0], "ipadapter": ["8", 1], "image": None, "weight": 0.85
                }},
            }
            workflow_path = Path(tmp) / "workflow.json"
            workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
            captured = {}
            upload_count = [0]
            def fake_open(request, timeout=30):
                url = request.full_url if hasattr(request, "full_url") else request
                if url.endswith("/upload/image"):
                    upload_count[0] += 1
                    return _Response({"name": f"reference_{upload_count[0]}.png"})
                if url.endswith("/prompt"):
                    captured["workflow"] = json.loads(request.data.decode("utf-8"))["prompt"]
                    return _Response({"prompt_id": "test-prompt"})
                if "/history/test-prompt" in url:
                    return _Response({"test-prompt": {"outputs": {
                        "7": {"images": [{"filename": "generated.png", "type": "output"}]}
                    }}})
                if "/view?" in url:
                    return _RawResponse(b"fake-png")
                raise AssertionError("Unexpected URL: " + url)
            mocked_open.side_effect = fake_open
            app.comfyui_generate_image(
                "http://127.0.0.1:8188", str(workflow_path), "A cinematic scene",
                tmp, width=1024, height=1792, reference_images=refs, seed=42
            )
            submitted = captured["workflow"]
            self.assertEqual(upload_count[0], 2)
            self.assertEqual(submitted["9"]["inputs"]["image"], ["11", 0])
            self.assertEqual(submitted["10"]["inputs"]["model"], ["9", 0])
            self.assertEqual(submitted["10"]["inputs"]["image"], ["12", 0])
            self.assertEqual(submitted["5"]["inputs"]["model"], ["10", 0])


if __name__ == "__main__":
    unittest.main()
