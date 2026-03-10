#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from fetch_and_send import (
    LAST_RUN_PATH,
    NEWS_PATH,
    TAXONOMY_PATH,
    load_json,
    load_taxonomy,
    normalize_text,
    now_utc,
    parse_published_datetime,
    score_and_tag_item_priority,
)

ROOT = Path(__file__).resolve().parent.parent
SITE_SRC = ROOT / "site"
DIST_DIR = ROOT / "dist"
SITE_DATA_PATH = DIST_DIR / "data" / "news-archive.json"


def sort_key(item: dict[str, Any]) -> tuple[int, str]:
    raw = (
        normalize_text(item.get("sent_at"))
        or normalize_text(item.get("published_at"))
        or normalize_text(item.get("fetched_at"))
    )
    parsed = parse_published_datetime(raw)
    return (int(parsed.timestamp()) if parsed else 0, raw)


def build_archive_items(items: list[dict[str, Any]], taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    archive_items: list[dict[str, Any]] = []

    for item in items:
        tagged = score_and_tag_item_priority(dict(item), taxonomy=taxonomy)
        archive_items.append(
            {
                "id": tagged.get("id"),
                "source": tagged.get("source"),
                "title": tagged.get("title"),
                "translated_title": tagged.get("translated_title"),
                "short_summary": tagged.get("short_summary"),
                "summary": tagged.get("summary"),
                "link": tagged.get("link"),
                "published_at": tagged.get("published_at"),
                "sent_at": tagged.get("sent_at"),
                "fetched_at": tagged.get("fetched_at"),
                "ai_model": tagged.get("ai_model"),
                "priority_bucket": tagged.get("priority_bucket"),
                "priority_score": tagged.get("priority_score"),
                "priority_signal": tagged.get("priority_signal"),
                "primary_slot": tagged.get("primary_slot"),
                "primary_slot_label": tagged.get("primary_slot_label"),
                "slot_scores": tagged.get("slot_scores", {}),
                "matched_terms": tagged.get("matched_terms", []),
            }
        )

    archive_items.sort(key=sort_key, reverse=True)
    return archive_items


def build_payload(items: list[dict[str, Any]], taxonomy: dict[str, Any]) -> dict[str, Any]:
    slot_order = taxonomy.get("slot_order", [])
    slot_labels = {
        slot_name: taxonomy.get("slots", {}).get(slot_name, {}).get("label", slot_name)
        for slot_name in slot_order
    }
    source_counts = Counter(str(item.get("source") or "").strip() for item in items)
    slot_counts = Counter(normalize_text(item.get("primary_slot")) for item in items)
    last_run = load_json(LAST_RUN_PATH, {})

    return {
        "generated_at": now_utc().isoformat(),
        "archive_total": len(items),
        "last_dispatch_at": last_run.get("executed_at"),
        "sources": [
            {"name": source, "count": count}
            for source, count in sorted(source_counts.items(), key=lambda entry: (-entry[1], entry[0]))
            if source
        ],
        "slots": [
            {
                "name": slot_name,
                "label": slot_labels.get(slot_name, slot_name),
                "count": slot_counts.get(slot_name, 0),
            }
            for slot_name in slot_order
        ],
        "items": items,
    }


def build_site() -> None:
    if not SITE_SRC.exists():
        raise FileNotFoundError(f"Missing site source directory: {SITE_SRC}")

    raw_news = load_json(NEWS_PATH, {"items": []})
    raw_items = raw_news.get("items", []) if isinstance(raw_news, dict) else []
    if not isinstance(raw_items, list):
        raw_items = []

    taxonomy = load_taxonomy(TAXONOMY_PATH)
    archive_items = build_archive_items(raw_items, taxonomy=taxonomy)
    payload = build_payload(archive_items, taxonomy=taxonomy)

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    shutil.copytree(SITE_SRC, DIST_DIR)
    (DIST_DIR / "data").mkdir(parents=True, exist_ok=True)
    SITE_DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DIST_DIR / ".nojekyll").write_text("", encoding="utf-8")


if __name__ == "__main__":
    build_site()
