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
    """把 OCR 文本和词库条目归一化到可比较的形式。

    这一步的重点是**剥离附加符号**。西班牙语的 "Añadir"、德语的
    "Warenkorb"、意大利语的 "però" 等都带重音或变音符号，OCR 未必能
    准确还原；NFKD 分解后去掉组合记号，"Añadir" 就变成 "anadir"，两边
    就能对齐。反之，如果词库里带符号而 OCR 读不出，就会永远匹配不上。

    步骤：
      1. NFKC 归一化 —— 统一全角/半角、兼容字符；
      2. 转小写；
      3. NFKD 分解并去掉组合记号 —— 剥离 ñ/é/ü 等附加符号；
      4. 下划线换成空格；
      5. 非单词字符换成空格；
      6. 合并连续空白。
    """
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def match_add_to_cart(text: str, phrases: list[str]) -> PhraseMatch:
    """在 OCR 文本中查找是否包含词库里的任一条目。

    匹配两种形态：
      1. 归一化后的短语作为子串出现在归一化文本里；
      2. 去掉所有空格后再匹配 —— 覆盖 OCR 把词内换行或多余空格打乱的情况。

    返回首个命中的词库条目（matched_phrase 是词库里的原文，便于人工核对）。
    """
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
        """按「站点 + 平台 + 页面类型」取出词库条目。

        词库文件是 config/phrase_sets.json，结构是 phrase_sets 数组，每项形如：
            {
              "country": "ES",              站点国家码，对应 markets.py 的九站
              "platform": "amazon",          平台
              "page_type": "product_detail", 页面类型
              "phrases": [...],              加购文案（能买的标志）
              "unavailable_phrases": [...]   不可购买文案（买不了的佐证）
            }

        unavailable=True 取不可购词库，否则取加购词库。两套词分开维护，因为
        它们的用途不同：加购词用来确认「能买」，不可购词用来佐证「买不了」。

        每个站点独立配置是必要的 —— DOM 结构可以跨站通用（同样的 id），
        但显示文案必须按站点语言给。词库里通常也附上英语写法作为兜底。

        词库不存在时抛 PhraseSetError 而不是返回空列表：空词库会让所有商品
        都判不出结果，问题会被推迟到判定阶段才暴露，排查成本更高。
        """
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
