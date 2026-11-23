import re


def filter_links(raw_links: list[dict], pattern_config: dict, limit: int) -> list[dict]:
    if not pattern_config:
        return [
            {"url": item.get("href"), "text": item.get("text", "")}
            for item in raw_links[:limit]
            if item.get("href")
        ]

    match_re = re.compile(pattern_config["match_regex"])
    exclude = pattern_config.get("exclude_if_contains", [])
    id_field = pattern_config.get("id_field", "id")
    id_group = int(pattern_config.get("id_group", 1))
    url_template = pattern_config.get("url_template")

    seen = set()
    results = []

    for link in raw_links:
        href = link.get("href") or link.get("url") or ""
        if not href:
            continue

        clean_href = href.split("?")[0].split("#")[0]
        if "/ref=" in clean_href:
            clean_href = clean_href.split("/ref=")[0]

        if exclude and any(part in clean_href for part in exclude):
            continue

        match = match_re.search(clean_href)
        if not match:
            continue

        item_id = match.group(id_group)
        if item_id in seen:
            continue

        seen.add(item_id)

        item = {
            "text": link.get("text", ""),
            id_field: item_id,
        }

        if url_template:
            item["url"] = url_template.format(**{id_field: item_id})
        else:
            item["url"] = clean_href

        results.append(item)

        if len(results) >= limit:
            break

    return results


def merge_links(primary: list, secondary: list, limit: int) -> list:
    seen = set()
    merged = []

    for link in primary + secondary:
        url = (link.get("url") or link.get("href") or "").split("?")[0].split("#")[0].rstrip("/")
        if not url or url in seen:
            continue

        seen.add(url)
        merged.append(link)

        if len(merged) >= limit:
            break

    return merged
