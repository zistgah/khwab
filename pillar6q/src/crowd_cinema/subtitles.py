"""WebVTT cue generation for supplied translations."""

from __future__ import annotations


def _timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{millis:03}"


def make_webvtt(language: str, text: str, duration_sec: int) -> str:
    if not language.strip():
        raise ValueError("language must not be empty")
    if not text.strip():
        raise ValueError("subtitle text must not be empty")
    if isinstance(duration_sec, bool) or not isinstance(duration_sec, int) or duration_sec <= 0:
        raise ValueError("duration_sec must be a positive integer")
    return (
        "WEBVTT\n\n"
        f"NOTE language: {language.strip()}\n\n"
        f"00:00:00.000 --> {_timestamp(duration_sec * 1000)}\n"
        f"{text.strip()}\n"
    )
