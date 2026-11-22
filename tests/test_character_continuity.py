import tempfile
import unittest
from pathlib import Path

import Video_Studyosu_V5_Arayuz_Onizleme as app


class CharacterContinuityTests(unittest.TestCase):
    def test_delete_character_remaps_multi_and_legacy_links(self):
        scenes = [
            {"character_ids": [0, 2, 3], "character_id": 0},
            {"character_id": 3},
            {"character_ids": [1], "character_id": 1},
            {"character_ids": [2], "character_id": 2},
        ]
        app.remap_character_scene_links(scenes, 1)
        self.assertEqual(scenes[0]["character_ids"], [0, 1, 2])
        self.assertEqual(scenes[0]["character_id"], 0)
        self.assertEqual(scenes[1]["character_id"], 2)
        self.assertNotIn("character_ids", scenes[2])
        self.assertNotIn("character_id", scenes[2])
        self.assertEqual(scenes[3]["character_ids"], [1])

    def test_collects_unique_existing_reference_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "front.png"
            side = Path(tmp) / "side.png"
            first.write_bytes(b"front")
            side.write_bytes(b"side")
            characters = [
                {"image": str(first), "reference_images": [str(side), str(first)]},
                {"image": str(side), "reference_images": []},
            ]
            images = app.collect_character_reference_images(
                {"character_ids": [0, 1]}, characters
            )
            self.assertEqual(images, [str(first), str(side)])

    def test_wardrobe_is_included_in_character_prompt(self):
        prompt = app.build_character_consistency_prompt(
            {"character_ids": [0]},
            [{"name": "Ahmet", "description": "short dark hair", "wardrobe": "red coat"}],
        )
        self.assertIn("red coat", prompt)
        self.assertIn("LOCKED COSTUME", prompt)

    def test_scene_continuity_uses_previous_scene_and_allows_change(self):
        scenes = [
            {"text": "Ahmet is in the old house", "visual_request": "warm light"},
            {"text": "Ahmet walks into the garden"},
        ]
        prompt = app.build_scene_continuity_prompt(scenes[1], 1, scenes)
        self.assertIn("old house", prompt)
        self.assertIn("warm light", prompt)
        self.assertIn("explicitly establishes a change", prompt)
        self.assertEqual(app.build_scene_continuity_prompt(scenes[0], 0, scenes), "")


if __name__ == "__main__":
    unittest.main()
