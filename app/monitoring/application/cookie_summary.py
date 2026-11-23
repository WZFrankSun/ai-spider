from __future__ import annotations

import hashlib
from collections.abc import Iterable


def summarize_cookies(cookies: Iterable[dict]) -> list[dict]:
    summaries = []
    for cookie in cookies:
        value = cookie.get("value")
        has_value = isinstance(value, str) and bool(value)
        summaries.append(
            {
                "name": str(cookie.get("name", "")),
                "domain": str(cookie.get("domain", "")),
                "path": str(cookie.get("path", "/")),
                "expires": cookie.get("expires"),
                "secure": bool(cookie.get("secure", False)),
                "http_only": bool(cookie.get("httpOnly", False)),
                "same_site": cookie.get("sameSite"),
                "present": has_value,
                "value_hash": hashlib.sha256(value.encode("utf-8")).hexdigest()
                if has_value
                else None,
            }
        )
    return summaries
