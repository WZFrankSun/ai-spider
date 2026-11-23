import json
from typing import Any


def parse_json_response(text: str | None) -> Any:
    if not text:
        raise ValueError("empty LLM response")

    text = text.strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()

    return json.loads(text)
