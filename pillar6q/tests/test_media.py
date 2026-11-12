from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from crowd_cinema import media


def clips() -> list[dict[str, object]]:
    return [
        {
            "shot_id": "shot-a",
            "media_uri": "first.mp4",
            "pts": 0,
            "duration_pts": 48,
            "time_base": {"numerator": 1, "denominator": 24},
        },
        {
            "shot_id": "shot-b",
            "media_uri": "second.mp4",
            "pts": 48,
            "duration_pts": 24,
            "time_base": {"numerator": 1, "denominator": 24},
        },
    ]


class MediaTimelineTests(unittest.TestCase):
    def test_continuity_report_preserves_exact_duration(self) -> None:
        result = media.check_continuity(clips())
        self.assertTrue(result["continuous"])
        self.assertEqual(result["clip_count"], 2)
        self.assertEqual(result["total_duration_pts"], 72)
        self.assertEqual(result["total_duration_seconds"], {"numerator": 3, "denominator": 1})

    def test_timeline_json_is_deterministic_valid_otio_structure(self) -> None:
        first = media.assemble_otio_json(clips(), name="Local cut")
        second = media.assemble_otio_json(clips(), name="Local cut")
        self.assertEqual(first, second)
        self.assertEqual(first["OTIO_SCHEMA"], "Timeline.1")
        track = first["tracks"]["children"][0]
        self.assertEqual(track["OTIO_SCHEMA"], "Track.1")
        self.assertEqual([item["name"] for item in track["children"]], ["shot-a", "shot-b"])
        self.assertEqual(
            track["children"][0]["media_reference"]["target_url"], "first.mp4"
        )
        self.assertEqual(track["children"][0]["source_range"]["duration"]["value"], 48)
        self.assertEqual(
            track["children"][1]["metadata"]["crowd_cinema"]["pts"], 48
        )

    def test_rejects_gaps_overlaps_duplicate_shots_and_timebase_mismatch(self) -> None:
        for pts in (47, 49):
            malformed = clips()
            malformed[1]["pts"] = pts
            with self.subTest(pts=pts), self.assertRaisesRegex(ValueError, "discontinuity"):
                media.check_continuity(malformed)

        malformed = clips()
        malformed[1]["shot_id"] = "shot-a"
        with self.assertRaisesRegex(ValueError, "duplicate shot_id"):
            media.assemble_otio_json(malformed)

        malformed = clips()
        malformed[1]["time_base"] = {"numerator": 1, "denominator": 25}
        with self.assertRaisesRegex(ValueError, "same time_base"):
            media.check_continuity(malformed)

    def test_rejects_boolean_integers_and_invalid_order(self) -> None:
        malformed = clips()
        malformed[0]["pts"] = True
        with self.assertRaisesRegex(ValueError, "pts must be an integer"):
            media.validate_ordered_clips(malformed)
        malformed = clips()
        malformed[1]["order"] = 0
        with self.assertRaisesRegex(ValueError, "presentation position"):
            media.validate_ordered_clips(malformed)


class FFmpegAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.input_path = Path(__file__).resolve()
        self.output_path = Path(__file__).with_name("_media_test_output.mkv")
        if self.output_path.exists():
            self.output_path.unlink()
        self.probe_stream = {
            "codec_type": "video",
            "codec_name": "h264",
            "profile": "High",
            "width": 16,
            "height": 16,
            "pix_fmt": "yuv420p",
            "time_base": "1/24",
            "duration_ts": "48",
            "r_frame_rate": "24/1",
            "avg_frame_rate": "24/1",
            "sample_aspect_ratio": "1:1",
            "field_order": "progressive",
        }

    def tearDown(self) -> None:
        if self.output_path.exists():
            self.output_path.unlink()

    def _local_clips(self) -> list[dict[str, object]]:
        result = clips()
        for clip in result:
            clip["media_uri"] = str(self.input_path)
        result[1]["duration_pts"] = 48
        return result

    def _mock_probe(self, command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe.exe":
            stream = dict(self.probe_stream)
            return subprocess.CompletedProcess(command, 0, json.dumps({"streams": [stream]}), "")
        self.output_path.write_bytes(b"stitched")
        return subprocess.CompletedProcess(command, 0, "", "")

    @patch("crowd_cinema.media.shutil.which", side_effect=lambda name: f"{name}.exe")
    @patch("crowd_cinema.media.subprocess.run")
    def test_stitches_compatible_video_with_argument_list_and_checks_output(
        self, run: object, _which: object
    ) -> None:
        run.side_effect = self._mock_probe
        result = media.assemble_with_ffmpeg(
            self._local_clips(),
            self.output_path,
            ffmpeg_executable="ffmpeg",
            ffprobe_executable="ffprobe",
        )
        self.assertEqual(result, self.output_path.resolve())
        self.assertEqual(self.output_path.read_bytes(), b"stitched")
        ffmpeg_call = run.call_args_list[-1]
        self.assertIsInstance(ffmpeg_call.args[0], list)
        self.assertFalse(ffmpeg_call.kwargs["shell"])

    @patch("crowd_cinema.media.shutil.which", return_value=None)
    def test_unavailable_ffmpeg_is_an_explicit_capability_error(self, _which: object) -> None:
        with self.assertRaisesRegex(media.FFmpegCapabilityError, "unavailable"):
            media.assemble_with_ffmpeg(self._local_clips(), self.output_path)

    @patch("crowd_cinema.media.shutil.which", side_effect=lambda name: f"{name}.exe")
    @patch("crowd_cinema.media.subprocess.run")
    def test_rejects_audio_and_timebase_mismatch_before_stitching(
        self, run: object, _which: object
    ) -> None:
        audio_probe = dict(self.probe_stream, codec_type="audio")
        run.return_value = subprocess.CompletedProcess(
            ["ffprobe.exe"], 0, json.dumps({"streams": [self.probe_stream, audio_probe]}), ""
        )
        with self.assertRaisesRegex(media.FFmpegCapabilityError, "A/V synchronization"):
            media.assemble_with_ffmpeg(self._local_clips(), self.output_path)

        run.return_value = subprocess.CompletedProcess(
            ["ffprobe.exe"], 0, json.dumps({"streams": [dict(self.probe_stream, time_base="1/25")]}), ""
        )
        with self.assertRaisesRegex(media.FFmpegCapabilityError, "time-base mismatch"):
            media.assemble_with_ffmpeg(self._local_clips(), self.output_path)

        run.return_value = subprocess.CompletedProcess(
            ["ffprobe.exe"],
            0,
            json.dumps({"streams": [dict(self.probe_stream, codec_name="vp9")]}),
            "",
        )
        with self.assertRaisesRegex(media.FFmpegCapabilityError, "only H.264"):
            media.assemble_with_ffmpeg(self._local_clips(), self.output_path)

    @patch("crowd_cinema.media.shutil.which", side_effect=lambda name: f"{name}.exe")
    @patch("crowd_cinema.media.subprocess.run")
    def test_reports_ffmpeg_exit_failure_and_missing_output(
        self, run: object, _which: object
    ) -> None:
        run.side_effect = [
            subprocess.CompletedProcess(
                ["ffprobe.exe"], 0, json.dumps({"streams": [self.probe_stream]}), ""
            ),
            subprocess.CompletedProcess(
                ["ffprobe.exe"], 0, json.dumps({"streams": [self.probe_stream]}), ""
            ),
            subprocess.CompletedProcess(["ffmpeg.exe"], 1, "", "codec error"),
        ]
        with self.assertRaisesRegex(media.FFmpegExecutionError, "status 1.*codec error"):
            media.assemble_with_ffmpeg(self._local_clips(), self.output_path)

        run.side_effect = [
            subprocess.CompletedProcess(
                ["ffprobe.exe"], 0, json.dumps({"streams": [self.probe_stream]}), ""
            ),
            subprocess.CompletedProcess(
                ["ffprobe.exe"], 0, json.dumps({"streams": [self.probe_stream]}), ""
            ),
            subprocess.CompletedProcess(["ffmpeg.exe"], 0, "", ""),
        ]
        with self.assertRaisesRegex(media.FFmpegExecutionError, "did not create"):
            media.assemble_with_ffmpeg(self._local_clips(), self.output_path)

    def test_reports_missing_media_input(self) -> None:
        unavailable = clips()
        unavailable[0]["media_uri"] = "missing-input-for-media-test.mp4"
        with patch(
            "crowd_cinema.media.shutil.which", side_effect=lambda name: f"{name}.exe"
        ):
            with self.assertRaisesRegex(media.FFmpegCapabilityError, "does not exist"):
                media.assemble_with_ffmpeg(unavailable, self.output_path)

    def test_rejects_line_breaks_in_ffconcat_media_paths(self) -> None:
        malformed = clips()
        malformed[0]["media_uri"] = "safe.mp4\nfile '/unexpected.mp4'"
        with self.assertRaisesRegex(ValueError, "line breaks"):
            media.assemble_with_ffmpeg(malformed, self.output_path)

    @unittest.skipUnless(
        shutil.which("ffmpeg")
        and shutil.which("ffprobe")
        and (Path(__file__).parent / "fixtures" / "tiny.mp4").is_file(),
        "requires FFmpeg, ffprobe, and tests/fixtures/tiny.mp4",
    )
    def test_real_ffmpeg_integration_when_fixture_and_binaries_exist(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "tiny.mp4"
        probe = subprocess.run(
            [
                shutil.which("ffprobe") or "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=time_base,duration_ts",
                "-select_streams",
                "v:0",
                "-of",
                "json",
                str(fixture),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        stream = json.loads(probe.stdout)["streams"][0]
        numerator, denominator = map(int, stream["time_base"].split("/"))
        duration_pts = int(stream["duration_ts"])
        sequence = [
            {
                "shot_id": "fixture",
                "media_uri": str(fixture),
                "pts": 0,
                "duration_pts": duration_pts,
                "time_base": {"numerator": numerator, "denominator": denominator},
            }
        ]
        result = media.assemble_with_ffmpeg(sequence, self.output_path)
        self.assertTrue(result.is_file())
        self.assertGreater(result.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
