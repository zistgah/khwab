"""Local OTIO timeline assembly and a conservative FFmpeg stream-copy adapter."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

try:
    import opentimelineio as _otio
except ImportError:
    _otio = None


class FFmpegError(RuntimeError):
    """Base error for local FFmpeg assembly failures."""


class FFmpegCapabilityError(FFmpegError):
    """Required executables or supported media capabilities are unavailable."""


class FFmpegExecutionError(FFmpegError):
    """A probe or FFmpeg process failed."""


def _integer(value: Any, label: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def validate_ordered_clips(clips: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate ordered clips and return normalized values with gapless integer PTS."""
    if not isinstance(clips, Sequence) or isinstance(clips, (str, bytes)) or not clips:
        raise ValueError("clips must be a non-empty ordered sequence")

    normalized: list[dict[str, Any]] = []
    seen_shots: set[str] = set()
    expected_pts = 0
    common_time_base: Fraction | None = None

    for index, clip in enumerate(clips):
        if not isinstance(clip, Mapping):
            raise ValueError(f"clips[{index}] must be a mapping")
        shot_id = clip.get("shot_id")
        if not isinstance(shot_id, str) or not shot_id.strip():
            raise ValueError(f"clips[{index}].shot_id must be a non-empty string")
        shot_id = shot_id.strip()
        if shot_id in seen_shots:
            raise ValueError(f"duplicate shot_id: {shot_id}")
        seen_shots.add(shot_id)

        media_uri = clip.get("media_uri")
        if not isinstance(media_uri, str) or not media_uri.strip():
            raise ValueError(f"clips[{index}].media_uri must be a non-empty string")
        media_uri = media_uri.strip()
        if "\n" in media_uri or "\r" in media_uri:
            raise ValueError(f"clips[{index}].media_uri cannot contain line breaks")
        pts = _integer(clip.get("pts"), f"clips[{index}].pts", 0)
        duration_pts = _integer(clip.get("duration_pts"), f"clips[{index}].duration_pts", 1)
        time_base = clip.get("time_base")
        if not isinstance(time_base, Mapping):
            raise ValueError(f"clips[{index}].time_base must be a mapping")
        numerator = _integer(time_base.get("numerator"), f"clips[{index}].time_base.numerator", 1)
        denominator = _integer(time_base.get("denominator"), f"clips[{index}].time_base.denominator", 1)
        normalized_time_base = Fraction(numerator, denominator)
        if common_time_base is None:
            common_time_base = normalized_time_base
        elif normalized_time_base != common_time_base:
            raise ValueError("all clips must use the same time_base")

        if "order" in clip and _integer(clip["order"], f"clips[{index}].order", 0) != index:
            raise ValueError(f"clips[{index}].order must match its presentation position")
        if pts != expected_pts:
            raise ValueError(
                f"timeline discontinuity at {shot_id}: expected pts {expected_pts}, got {pts}"
            )

        normalized.append(
            {
                "shot_id": shot_id,
                "media_uri": media_uri,
                "pts": pts,
                "duration_pts": duration_pts,
                "time_base": {
                    "numerator": normalized_time_base.numerator,
                    "denominator": normalized_time_base.denominator,
                },
            }
        )
        expected_pts += duration_pts

    return normalized


def check_continuity(clips: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return checked timeline continuity and an exact rational total duration."""
    normalized = validate_ordered_clips(clips)
    total_pts = sum(clip["duration_pts"] for clip in normalized)
    time_base = normalized[0]["time_base"]
    seconds = Fraction(total_pts * time_base["numerator"], time_base["denominator"])
    return {
        "continuous": True,
        "clip_count": len(normalized),
        "total_duration_pts": total_pts,
        "time_base": time_base,
        "total_duration_seconds": {
            "numerator": seconds.numerator,
            "denominator": seconds.denominator,
        },
    }


def _rational_time(value: int, rate: float) -> dict[str, Any]:
    return {"OTIO_SCHEMA": "RationalTime.1", "value": value, "rate": rate}


def _fallback_timeline(clips: list[dict[str, Any]], name: str) -> dict[str, Any]:
    numerator = clips[0]["time_base"]["numerator"]
    denominator = clips[0]["time_base"]["denominator"]
    rate = denominator / numerator
    children = []
    for clip in clips:
        children.append(
            {
                "OTIO_SCHEMA": "Clip.2",
                "metadata": {
                    "crowd_cinema": {
                        "shot_id": clip["shot_id"],
                        "pts": clip["pts"],
                        "duration_pts": clip["duration_pts"],
                        "time_base": clip["time_base"],
                    }
                },
                "name": clip["shot_id"],
                "media_reference": {
                    "OTIO_SCHEMA": "ExternalReference.1",
                    "metadata": {},
                    "name": "",
                    "target_url": clip["media_uri"],
                    "available_range": None,
                },
                "source_range": {
                    "OTIO_SCHEMA": "TimeRange.1",
                    "start_time": _rational_time(0, rate),
                    "duration": _rational_time(clip["duration_pts"], rate),
                },
                "effects": [],
                "markers": [],
                "enabled": True,
                "color": None,
            }
        )
    return {
        "OTIO_SCHEMA": "Timeline.1",
        "metadata": {},
        "name": name,
        "global_start_time": None,
        "tracks": {
            "OTIO_SCHEMA": "Stack.1",
            "metadata": {},
            "name": "Tracks",
            "children": [
                {
                    "OTIO_SCHEMA": "Track.1",
                    "metadata": {},
                    "name": "Picture",
                    "children": children,
                    "kind": "Video",
                    "effects": [],
                    "markers": [],
                }
            ],
            "effects": [],
            "markers": [],
        },
    }


def assemble_otio_json(
    clips: Sequence[Mapping[str, Any]], name: str = "Crowd Cinema"
) -> dict[str, Any]:
    """Build deterministic OTIO JSON from validated, gapless ordered clips.

    Source ranges begin at zero because the input contract has no source-in field.
    This constructs timeline metadata; it does not claim decoded-frame accuracy.
    """
    normalized = validate_ordered_clips(clips)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    if _otio is None:
        return _fallback_timeline(normalized, name.strip())

    rate = normalized[0]["time_base"]["denominator"] / normalized[0]["time_base"]["numerator"]
    track = _otio.schema.Track(name="Picture", kind=_otio.schema.TrackKind.Video)
    for clip in normalized:
        external = _otio.schema.ExternalReference(target_url=clip["media_uri"])
        item = _otio.schema.Clip(
            name=clip["shot_id"],
            media_reference=external,
            source_range=_otio.opentime.TimeRange(
                start_time=_otio.opentime.RationalTime(0, rate),
                duration=_otio.opentime.RationalTime(clip["duration_pts"], rate),
            ),
        )
        item.metadata["crowd_cinema"] = {
            "shot_id": clip["shot_id"],
            "pts": clip["pts"],
            "duration_pts": clip["duration_pts"],
            "time_base": clip["time_base"],
        }
        track.append(item)
    timeline = _otio.schema.Timeline(name=name.strip())
    timeline.tracks.append(track)
    encoded = _otio.adapters.write_to_string(timeline, adapter_name="otio_json")
    return json.loads(encoded)


def ffmpeg_availability(
    ffmpeg_executable: str = "ffmpeg", ffprobe_executable: str = "ffprobe"
) -> dict[str, Any]:
    """Report executable availability without attempting media work."""
    ffmpeg_path = shutil.which(ffmpeg_executable)
    ffprobe_path = shutil.which(ffprobe_executable)
    return {
        "available": bool(ffmpeg_path and ffprobe_path),
        "ffmpeg": ffmpeg_path,
        "ffprobe": ffprobe_path,
    }


def _local_media_path(media_uri: str) -> Path:
    if "\n" in media_uri or "\r" in media_uri:
        raise FFmpegCapabilityError("media paths cannot contain line breaks")
    is_windows_drive_path = len(media_uri) >= 2 and media_uri[1] == ":"
    parsed = urlparse(media_uri) if not is_windows_drive_path else None
    if parsed is not None and parsed.scheme and parsed.scheme.lower() != "file":
        raise FFmpegCapabilityError(f"only local media paths and file:// URIs are supported: {media_uri}")
    if parsed is not None and parsed.scheme.lower() == "file":
        if parsed.netloc not in ("", "localhost"):
            raise FFmpegCapabilityError("UNC file:// media URIs are not supported")
        path_text = url2pathname(unquote(parsed.path))
        if len(path_text) >= 3 and path_text[0] == "/" and path_text[2] == ":":
            path_text = path_text[1:]
        path = Path(path_text)
    else:
        path = Path(media_uri)
    if not path.exists() or not path.is_file():
        raise FFmpegCapabilityError(f"media input does not exist or is not a file: {path}")
    return path.resolve()


def _probe_video(
    ffprobe_path: str, path: Path, timeout: float
) -> dict[str, Any]:
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,codec_name,codec_tag_string,profile,level,width,height,pix_fmt,time_base,duration_ts,r_frame_rate,avg_frame_rate,sample_aspect_ratio,field_order,bits_per_raw_sample,chroma_location,color_range,color_space,color_transfer,color_primaries,extradata_hash",
        "-show_data_hash",
        "sha256",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise FFmpegExecutionError(f"ffprobe failed for {path}: {error}") from error
    if result.returncode != 0:
        raise FFmpegExecutionError(
            f"ffprobe exited with status {result.returncode} for {path}: "
            f"{result.stderr.strip() or 'no diagnostic output'}"
        )
    try:
        probe_document = json.loads(result.stdout)
        streams = probe_document["streams"]
    except (ValueError, KeyError, TypeError) as error:
        raise FFmpegExecutionError(f"ffprobe returned invalid stream data for {path}") from error
    if not isinstance(streams, list) or not all(isinstance(stream, dict) for stream in streams):
        raise FFmpegExecutionError(f"ffprobe returned invalid stream data for {path}")
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    if len(videos) != 1 or len(streams) != 1:
        raise FFmpegCapabilityError(
            f"{path} must contain exactly one video stream and no audio or other streams; "
            "A/V synchronization is not implemented"
        )
    stream = videos[0]
    required = ("codec_name", "width", "height", "pix_fmt", "time_base", "duration_ts")
    missing = [field for field in required if stream.get(field) in (None, "")]
    if missing:
        raise FFmpegCapabilityError(f"{path} lacks required probe fields: {', '.join(missing)}")
    try:
        actual_time_base = Fraction(stream["time_base"])
        duration_ts = int(stream["duration_ts"])
    except (ValueError, TypeError, ZeroDivisionError) as error:
        raise FFmpegCapabilityError(f"{path} has invalid time-base or duration metadata") from error
    if duration_ts <= 0:
        raise FFmpegCapabilityError(f"{path} has no positive video duration")
    return {"stream": stream, "time_base": actual_time_base, "duration_ts": duration_ts}


def assemble_with_ffmpeg(
    clips: Sequence[Mapping[str, Any]],
    output_path: str | Path,
    *,
    ffmpeg_executable: str = "ffmpeg",
    ffprobe_executable: str = "ffprobe",
    timeout: float = 120.0,
) -> Path:
    """Concatenate compatible local video-only files using FFmpeg stream copy.

    This deliberately rejects audio and differing stream/timeline time bases.
    No codec conversion, frame-rate conversion, or A/V synchronization is implied.
    """
    normalized = validate_ordered_clips(clips)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive")
    ffmpeg_path = shutil.which(ffmpeg_executable)
    ffprobe_path = shutil.which(ffprobe_executable)
    if not ffmpeg_path or not ffprobe_path:
        missing = []
        if not ffmpeg_path:
            missing.append(ffmpeg_executable)
        if not ffprobe_path:
            missing.append(ffprobe_executable)
        raise FFmpegCapabilityError(f"required executable(s) unavailable: {', '.join(missing)}")

    output = Path(output_path).expanduser().resolve()
    if output.exists():
        raise FFmpegCapabilityError(f"output already exists; refusing to overwrite: {output}")
    if not output.parent.exists() or not output.parent.is_dir():
        raise FFmpegCapabilityError(f"output directory does not exist: {output.parent}")
    if output.suffix.lower() not in {".mp4", ".mov", ".mkv"}:
        raise FFmpegCapabilityError("stream-copy output supports only .mp4, .mov, and .mkv")

    probed: list[tuple[Path, dict[str, Any]]] = []
    for clip in normalized:
        path = _local_media_path(clip["media_uri"])
        metadata = _probe_video(ffprobe_path, path, timeout)
        if metadata["stream"].get("codec_name") != "h264":
            raise FFmpegCapabilityError(
                f"unsupported video codec in {path}: {metadata['stream'].get('codec_name')}; "
                "only H.264 stream copy is supported"
            )
        expected_tb = Fraction(
            clip["time_base"]["numerator"], clip["time_base"]["denominator"]
        )
        if metadata["time_base"] != expected_tb:
            raise FFmpegCapabilityError(
                f"time-base mismatch for {path}: timeline uses {expected_tb}, "
                f"media uses {metadata['time_base']}"
            )
        if metadata["duration_ts"] != clip["duration_pts"]:
            raise FFmpegCapabilityError(
                f"duration mismatch for {path}: timeline declares {clip['duration_pts']} "
                f"ticks, media has {metadata['duration_ts']}"
            )
        probed.append((path, metadata))

    baseline = probed[0][1]["stream"]
    signature_fields = (
        "codec_name",
        "codec_tag_string",
        "profile",
        "level",
        "width",
        "height",
        "pix_fmt",
        "time_base",
        "r_frame_rate",
        "avg_frame_rate",
        "sample_aspect_ratio",
        "field_order",
        "bits_per_raw_sample",
        "chroma_location",
        "color_range",
        "color_space",
        "color_transfer",
        "color_primaries",
        "extradata_hash",
    )
    for path, metadata in probed[1:]:
        current = metadata["stream"]
        differences = [
            field
            for field in signature_fields
            if baseline.get(field) != current.get(field)
        ]
        if differences:
            raise FFmpegCapabilityError(
                f"incompatible video streams in {path}; mismatched: {', '.join(differences)}"
            )

    manifest_lines = ["ffconcat version 1.0"]
    for path, _ in probed:
        escaped = str(path).replace("\\", "\\\\").replace("'", "\\'")
        manifest_lines.append(f"file '{escaped}'")
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-v",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        "-",
        "-map",
        "0:v:0",
        "-c:v",
        "copy",
        "-an",
        "-n",
        str(output),
    ]
    try:
        result = subprocess.run(
            command,
            input="\n".join(manifest_lines) + "\n",
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise FFmpegExecutionError(f"FFmpeg execution failed: {error}") from error
    if result.returncode != 0:
        raise FFmpegExecutionError(
            f"FFmpeg exited with status {result.returncode}: "
            f"{result.stderr.strip() or 'no diagnostic output'}"
        )
    if not output.exists() or not output.is_file() or output.stat().st_size == 0:
        raise FFmpegExecutionError(
            f"FFmpeg reported success but did not create a non-empty output: {output}"
        )
    return output
