import unittest

from video_effects import VIDEO_EFFECT_PRESETS, get_video_effect_filter


class VideoEffectPresetTests(unittest.TestCase):
    def test_all_presets_are_strings(self):
        self.assertGreaterEqual(len(VIDEO_EFFECT_PRESETS), 7)
        self.assertTrue(all(isinstance(value, str) for value in VIDEO_EFFECT_PRESETS.values()))

    def test_disabled_preset_is_empty(self):
        self.assertEqual(get_video_effect_filter("Kapalı"), "")

    def test_known_presets_return_filter_chains(self):
        for name in ("Sinematik", "Korku", "Vintage", "Siyah-beyaz", "Rüya", "Keskin ve canlı"):
            with self.subTest(name=name):
                value = get_video_effect_filter(name)
                self.assertTrue(value)
                self.assertNotIn(";", value)
                self.assertNotIn("\n", value)

    def test_unknown_preset_fails_closed(self):
        self.assertEqual(get_video_effect_filter("arbitrary-input"), "")


if __name__ == "__main__":
    unittest.main()
