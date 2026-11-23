from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PhraseMatch:
    matched: bool
    matched_phrase: str | None
    normalized_text: str


def normalize_ocr_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def match_add_to_cart(text: str, phrases: list[str]) -> PhraseMatch:
    normalized_text = normalize_ocr_text(text)
    compact_text = normalized_text.replace(" ", "")
    for phrase in phrases:
        normalized_phrase = normalize_ocr_text(phrase)
        if not normalized_phrase:
            continue
        if normalized_phrase in normalized_text or normalized_phrase.replace(" ", "") in compact_text:
            return PhraseMatch(
                matched=True,
                matched_phrase=phrase,
                normalized_text=normalized_text,
            )
    return PhraseMatch(matched=False, matched_phrase=None, normalized_text=normalized_text)


class PhraseSetError(ValueError):
    pass


class JsonPhraseSetLoader:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self, country: str, platform: str, page_type: str, *, unavailable: bool = False) -> list[str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PhraseSetError(f"failed to load phrase sets: {self.path}") from exc

        phrase_sets = data.get("phrase_sets") if isinstance(data, dict) else data
        if not isinstance(phrase_sets, list):
            raise PhraseSetError("phrase set file must contain a phrase_sets list")
        for item in phrase_sets:
            if not isinstance(item, dict):
                continue
            if (
                str(item.get("country", "")).upper() == country.upper()
                and str(item.get("platform", "")).lower() == platform.lower()
                and str(item.get("page_type", "")) == page_type
            ):
                phrases = item.get("unavailable_phrases", []) if unavailable else item.get("phrases")
                if not isinstance(phrases, list) or not all(isinstance(value, str) for value in phrases):
                    raise PhraseSetError("phrases must be a list of strings")
                return list(phrases)
        raise PhraseSetError(
            f"phrase set not found: {country}/{platform}/{page_type}"
        )
