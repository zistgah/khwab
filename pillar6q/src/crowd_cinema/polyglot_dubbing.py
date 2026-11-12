"""Language metadata and shot-bounded WebVTT export for supplied translations.

This module validates subtitle text and timing only. It does not translate,
synthesize audio, run Praat, or measure or guarantee lip synchronization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping
import unicodedata


@dataclass(frozen=True)
class ScriptMetadata:
    name: str
    iso_15924: str


@dataclass(frozen=True)
class LanguageMetadata:
    code: str
    name: str
    scripts: tuple[ScriptMetadata, ...]
    indian_scheduled: bool = False


def _script(name: str, code: str) -> ScriptMetadata:
    return ScriptMetadata(name, code)


_LANGUAGES = (
    LanguageMetadata("as", "Assamese", (_script("Bengali-Assamese", "Beng"),), True),
    LanguageMetadata("bn", "Bengali", (_script("Bengali-Assamese", "Beng"),), True),
    LanguageMetadata("brx", "Bodo", (_script("Devanagari", "Deva"),), True),
    LanguageMetadata("doi", "Dogri", (_script("Devanagari", "Deva"),), True),
    LanguageMetadata("gu", "Gujarati", (_script("Gujarati", "Gujr"),), True),
    LanguageMetadata("hi", "Hindi", (_script("Devanagari", "Deva"),), True),
    LanguageMetadata("kn", "Kannada", (_script("Kannada", "Knda"),), True),
    LanguageMetadata(
        "ks",
        "Kashmiri",
        (_script("Arabic", "Arab"), _script("Devanagari", "Deva")),
        True,
    ),
    LanguageMetadata("kok", "Konkani", (_script("Devanagari", "Deva"),), True),
    LanguageMetadata("mai", "Maithili", (_script("Devanagari", "Deva"),), True),
    LanguageMetadata("ml", "Malayalam", (_script("Malayalam", "Mlym"),), True),
    LanguageMetadata(
        "mni",
        "Manipuri (Meitei)",
        (_script("Meitei Mayek", "Mtei"), _script("Bengali-Assamese", "Beng")),
        True,
    ),
    LanguageMetadata("mr", "Marathi", (_script("Devanagari", "Deva"),), True),
    LanguageMetadata("ne", "Nepali", (_script("Devanagari", "Deva"),), True),
    LanguageMetadata("or", "Odia", (_script("Odia", "Orya"),), True),
    LanguageMetadata(
        "pa",
        "Punjabi",
        (_script("Gurmukhi", "Guru"), _script("Arabic (Shahmukhi)", "Arab")),
        True,
    ),
    LanguageMetadata("sa", "Sanskrit", (_script("Devanagari", "Deva"),), True),
    LanguageMetadata(
        "sat",
        "Santali",
        (_script("Ol Chiki", "Olck"), _script("Devanagari", "Deva")),
        True,
    ),
    LanguageMetadata(
        "sd",
        "Sindhi",
        (_script("Arabic", "Arab"), _script("Devanagari", "Deva")),
        True,
    ),
    LanguageMetadata("ta", "Tamil", (_script("Tamil", "Taml"),), True),
    LanguageMetadata("te", "Telugu", (_script("Telugu", "Telu"),), True),
    LanguageMetadata("ur", "Urdu", (_script("Arabic (Nastaliq)", "Arab"),), True),
    LanguageMetadata("ar", "Arabic", (_script("Arabic", "Arab"),)),
    LanguageMetadata("de", "German", (_script("Latin", "Latn"),)),
    LanguageMetadata("en", "English", (_script("Latin", "Latn"),)),
    LanguageMetadata("es", "Spanish", (_script("Latin", "Latn"),)),
    LanguageMetadata("fr", "French", (_script("Latin", "Latn"),)),
    LanguageMetadata("id", "Indonesian", (_script("Latin", "Latn"),)),
    LanguageMetadata("it", "Italian", (_script("Latin", "Latn"),)),
    LanguageMetadata("ja", "Japanese", (_script("Japanese", "Jpan"),)),
    LanguageMetadata("ko", "Korean", (_script("Hangul", "Hang"),)),
    LanguageMetadata("pt", "Portuguese", (_script("Latin", "Latn"),)),
    LanguageMetadata("ru", "Russian", (_script("Cyrillic", "Cyrl"),)),
    LanguageMetadata("sw", "Swahili", (_script("Latin", "Latn"),)),
    LanguageMetadata("tr", "Turkish", (_script("Latin", "Latn"),)),
    LanguageMetadata("vi", "Vietnamese", (_script("Latin", "Latn"),)),
    LanguageMetadata("zh-Hans", "Chinese (Simplified)", (_script("Han, Simplified", "Hans"),)),
    LanguageMetadata("zh-Hant", "Chinese (Traditional)", (_script("Han, Traditional", "Hant"),)),
)

LANGUAGES: Mapping[str, LanguageMetadata] = {
    language.code: language for language in _LANGUAGES
}


def get_language_metadata(language_code: str) -> LanguageMetadata:
    """Return registered language/script metadata for a BCP 47-style code."""
    if not isinstance(language_code, str) or not language_code.strip():
        raise ValueError("language code must not be empty")
    normalized = "-".join(
        part.lower() if index == 0 else part.title()
        for index, part in enumerate(language_code.strip().replace("_", "-").split("-"))
    )
    try:
        return LANGUAGES[normalized]
    except KeyError as error:
        raise ValueError(f"unsupported language code: {language_code}") from error


@dataclass(frozen=True)
class ShotWindow:
    """A shot's absolute timeline start and permitted 10–15 second duration."""

    shot_id: str
    start_ms: int
    duration_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.shot_id, str) or not self.shot_id.strip():
            raise ValueError("shot_id must not be empty")
        _require_integer(self.start_ms, "start_ms")
        _require_integer(self.duration_ms, "duration_ms")
        if self.start_ms < 0:
            raise ValueError("start_ms must not be negative")
        if not 10_000 <= self.duration_ms <= 15_000:
            raise ValueError("shot duration must be between 10000 and 15000 milliseconds")

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms


@dataclass(frozen=True)
class SubtitleCue:
    """A caller-supplied subtitle cue with absolute timeline timestamps."""

    shot_id: str
    start_ms: int
    end_ms: int
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.shot_id, str) or not self.shot_id.strip():
            raise ValueError("shot_id must not be empty")
        _require_integer(self.start_ms, "start_ms")
        _require_integer(self.end_ms, "end_ms")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("cue end_ms must be greater than a nonnegative start_ms")
        _validate_subtitle_text(self.text)


def _require_integer(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")


def _validate_subtitle_text(text: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("subtitle text must not be empty")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("subtitle text must contain valid Unicode scalar values") from error
    for character in text:
        if unicodedata.category(character) == "Cc" and character not in "\r\n\t":
            raise ValueError("subtitle text contains an unsupported control character")


def validate_cues(
    language_code: str,
    cues: Iterable[SubtitleCue],
    shots: Mapping[str, ShotWindow],
) -> tuple[SubtitleCue, ...]:
    """Validate supplied cues against known shot windows and return them in order."""
    get_language_metadata(language_code)
    if not isinstance(shots, Mapping):
        raise ValueError("shots must map shot IDs to ShotWindow values")
    for shot_id, shot in shots.items():
        if not isinstance(shot, ShotWindow) or shot_id != shot.shot_id:
            raise ValueError("each shots entry must be keyed by its ShotWindow shot_id")
    try:
        cue_list = tuple(cues)
    except TypeError as error:
        raise ValueError("cues must be an iterable of SubtitleCue values") from error
    if any(not isinstance(cue, SubtitleCue) for cue in cue_list):
        raise ValueError("cues must contain only SubtitleCue values")
    for cue in cue_list:
        shot = shots.get(cue.shot_id)
        if shot is None:
            raise ValueError(f"cue references unknown shot: {cue.shot_id}")
        if cue.start_ms < shot.start_ms or cue.end_ms > shot.end_ms:
            raise ValueError(
                f"cue for shot {cue.shot_id} must fit within "
                f"{shot.start_ms}..{shot.end_ms} milliseconds"
            )
    return tuple(sorted(cue_list, key=lambda cue: (cue.start_ms, cue.end_ms, cue.shot_id)))


def _timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{millis:03}"


def _vtt_text(text: str) -> str:
    normalized = text.strip().replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def export_webvtt(
    language_code: str,
    cues: Iterable[SubtitleCue],
    shots: Mapping[str, ShotWindow],
) -> str:
    """Export validated, caller-supplied translations as a WebVTT document."""
    language = get_language_metadata(language_code)
    ordered_cues = validate_cues(language.code, cues, shots)
    lines = ["WEBVTT", "", f"NOTE language: {language.code}", ""]
    for cue in ordered_cues:
        lines.extend(
            (
                f"{_timestamp(cue.start_ms)} --> {_timestamp(cue.end_ms)}",
                _vtt_text(cue.text),
                "",
            )
        )
    return "\n".join(lines)
