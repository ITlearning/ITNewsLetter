#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from build_archive_site import (
    LAZY_DETAIL_ALLOWLIST_PATH,
    evaluate_lazy_detail_support,
    load_lazy_detail_config,
)
from fetch_and_send import (
    NEWS_PATH,
    briefing_looks_like_markdown,
    ensure_archive_detail_fields,
    load_json,
    normalize_briefing_markdown,
    normalize_text,
    write_json,
)


def build_reset_candidates(items: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []

    for item in items:
        enriched = ensure_archive_detail_fields(dict(item))
        detailed_summary = normalize_briefing_markdown(enriched.get("detailed_summary"))
        if not detailed_summary:
            continue
        if briefing_looks_like_markdown(detailed_summary):
            continue

        candidate = dict(enriched)
        candidate.pop("detailed_summary", None)
        supported, reason = evaluate_lazy_detail_support(candidate, config)
        if not supported:
            continue

        candidates.append(
            {
                "id": normalize_text(enriched.get("id")),
                "source": normalize_text(enriched.get("source")),
                "title": normalize_text(enriched.get("translated_title") or enriched.get("title")),
                "reason": reason,
            }
        )

    return candidates


def reset_legacy_briefings(
    items: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    candidates = build_reset_candidates(items, config)
    candidate_ids = {candidate["id"] for candidate in candidates if candidate.get("id")}
    updated_items: list[dict[str, Any]] = []

    for item in items:
        item_id = normalize_text(item.get("id"))
        if item_id and item_id in candidate_ids:
            updated = dict(item)
            updated.pop("detailed_summary", None)
            updated_items.append(updated)
            continue
        updated_items.append(item)

    return updated_items, candidates


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset legacy plain-text detailed_summary fields that can be regenerated lazily."
    )
    parser.add_argument("--apply", action="store_true", help="Write changes back to the archive JSON.")
    parser.add_argument("--news-path", type=Path, default=NEWS_PATH, help="Path to archive JSON.")
    parser.add_argument(
        "--allowlist-path",
        type=Path,
        default=LAZY_DETAIL_ALLOWLIST_PATH,
        help="Path to lazy detail allowlist JSON.",
    )
    parser.add_argument("--sample-limit", type=int, default=12, help="How many candidate rows to print.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    payload = load_json(args.news_path, {"items": []})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        print("ERROR: archive payload is not a list of items.", file=sys.stderr)
        return 2

    config = load_lazy_detail_config(args.allowlist_path)
    updated_items, candidates = reset_legacy_briefings(items, config)

    print(json.dumps(
        {
            "news_path": str(args.news_path),
            "apply": bool(args.apply),
            "items_total": len(items),
            "reset_candidates": len(candidates),
            "sample": candidates[: max(0, args.sample_limit)],
        },
        ensure_ascii=False,
        indent=2,
    ))

    if not args.apply or not candidates:
        return 0

    write_json(args.news_path, {"items": updated_items})
    print(f"Applied: cleared detailed_summary for {len(candidates)} item(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
