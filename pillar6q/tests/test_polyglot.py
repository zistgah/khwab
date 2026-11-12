from __future__ import annotations

import unittest

from crowd_cinema.polyglot_dubbing import (
    LANGUAGES,
    LanguageMetadata,
    ScriptMetadata,
    ShotWindow,
    SubtitleCue,
    export_webvtt,
    get_language_metadata,
    validate_cues,
)


class PolyglotDubbingTests(unittest.TestCase):
    def test_language_manifest_covers_scheduled_indian_and_global_languages(self) -> None:
        scheduled = {
            code for code, language in LANGUAGES.items() if language.indian_scheduled
        }
        self.assertEqual(len(scheduled), 22)
        self.assertTrue(
            {
                "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai",
                "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta",
                "te", "ur",
            }.issubset(scheduled)
        )
        self.assertEqual(get_language_metadata("zh_hans").scripts[0].iso_15924, "Hans")
        self.assertEqual(get_language_metadata("mni").scripts[0].name, "Meitei Mayek")
        self.assertTrue(all(language.scripts for language in LANGUAGES.values()))

    def test_script_and_language_records_are_structured_metadata(self) -> None:
        self.assertIsInstance(get_language_metadata("hi"), LanguageMetadata)
        self.assertIsInstance(get_language_metadata("hi").scripts[0], ScriptMetadata)

    def test_exports_unicode_supplied_translation_and_sorts_cues(self) -> None:
        shot = ShotWindow("scene-1", start_ms=12_000, duration_ms=12_000)
        shots = {shot.shot_id: shot}
        cues = [
            SubtitleCue("scene-1", 20_000, 22_000, "தமிழ் — नमस्ते"),
            SubtitleCue("scene-1", 12_000, 13_500, "你好 & <friends>"),
        ]
        output = export_webvtt("zh-Hans", cues, shots)
        self.assertIn("NOTE language: zh-Hans", output)
        self.assertLess(output.index("00:00:12.000"), output.index("00:00:20.000"))
        self.assertIn("你好 &amp; &lt;friends&gt;", output)
        self.assertIn("தமிழ் — नमस्ते", output)

    def test_rejects_cues_outside_their_10_to_15_second_shot(self) -> None:
        shot = ShotWindow("scene-1", start_ms=5_000, duration_ms=10_000)
        with self.assertRaisesRegex(ValueError, "fit within"):
            validate_cues(
                "en",
                [SubtitleCue("scene-1", 4_999, 6_000, "too early")],
                {"scene-1": shot},
            )
        with self.assertRaisesRegex(ValueError, "fit within"):
            validate_cues(
                "en",
                [SubtitleCue("scene-1", 14_000, 15_001, "too late")],
                {"scene-1": shot},
            )

    def test_rejects_invalid_shot_windows_and_unknown_languages_or_shots(self) -> None:
        for duration in (9_999, 15_001):
            with self.subTest(duration=duration), self.assertRaisesRegex(
                ValueError, "shot duration"
            ):
                ShotWindow("scene-1", 0, duration)
        with self.assertRaisesRegex(ValueError, "unsupported language"):
            export_webvtt("xx", [], {})
        with self.assertRaisesRegex(ValueError, "unknown shot"):
            validate_cues(
                "en",
                [SubtitleCue("missing", 0, 1_000, "text")],
                {},
            )

    def test_rejects_non_unicode_scalar_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid Unicode"):
            SubtitleCue("scene-1", 0, 1_000, "\ud800")


if __name__ == "__main__":
    unittest.main()
