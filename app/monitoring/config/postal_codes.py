from __future__ import annotations

import re


_POSTAL_FORMATTING = str.maketrans("", "", "-\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad")


def normalize_postal(value: str | None) -> str:
    if not value:
        return ""
    return "".join(value.split()).translate(_POSTAL_FORMATTING).upper().strip()


def postal_matches(readback: str | None, target: str | None) -> bool:
    expected = normalize_postal(target)
    if not expected or not readback:
        return False

    # 保留页头的空白作为词边界，否则邮编会与城市名粘连。
    # 候选内部允许排版空白，两端必须完整，以免把 101150 认成 10115。
    text = readback.translate(_POSTAL_FORMATTING).upper()
    candidate = r"\s*".join(re.escape(character) for character in expected)
    return re.search(r"(?<![^\W_])" + candidate + r"(?![^\W_])", text) is not None


def postal_values_equal(left: str | None, right: str | None) -> bool:
    return normalize_postal(left) == normalize_postal(right)
