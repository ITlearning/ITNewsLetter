#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from string import Template
from typing import Any
from urllib.parse import urlparse

from fetch_and_send import (
    LAST_RUN_PATH,
    NEWS_PATH,
    TAXONOMY_PATH,
    collapse_geeknews_hn_duplicates,
    ensure_archive_detail_fields,
    load_json,
    load_taxonomy,
    normalize_briefing_markdown,
    normalize_text,
    now_utc,
    parse_published_datetime,
    render_briefing_markdown_html,
    score_and_tag_item_priority,
    to_multiline_preview,
)

ROOT = Path(__file__).resolve().parent.parent
SITE_SRC = ROOT / "site"
DIST_DIR = ROOT / "dist"
SITE_DATA_PATH = DIST_DIR / "data" / "news-archive.json"
DETAIL_TEMPLATE_PATH = SITE_SRC / "templates" / "detail.html"
LAZY_DETAIL_ALLOWLIST_PATH = ROOT / "config" / "lazy_detail_allowlist.json"


def sort_key(item: dict[str, Any]) -> tuple[int, str]:
    raw = (
        normalize_text(item.get("sent_at"))
        or normalize_text(item.get("published_at"))
        or normalize_text(item.get("fetched_at"))
    )
    parsed = parse_published_datetime(raw)
    return (int(parsed.timestamp()) if parsed else 0, raw)


def build_detail_url(detail_slug: str) -> str:
    return f"./news/{detail_slug}/"


def build_nested_detail_url(detail_slug: str) -> str:
    return f"../{detail_slug}/"


def is_geeknews_item(item: dict[str, Any]) -> bool:
    return normalize_text(item.get("source")) == "GeekNews"


def detail_target_url(item: dict[str, Any], *, nested: bool) -> str:
    if is_geeknews_item(item):
        return normalize_text(item.get("link"), "#")

    detail_slug = normalize_text(item.get("detail_slug"))
    if not detail_slug:
        return "#"
    return build_nested_detail_url(detail_slug) if nested else build_detail_url(detail_slug)


def normalize_string_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {normalize_text(value).lower() for value in values if normalize_text(value)}


def normalize_source_domain_overrides(raw: Any) -> dict[str, set[str]]:
    if not isinstance(raw, dict):
        return {}

    overrides: dict[str, set[str]] = {}
    for source_name, domains in raw.items():
        normalized_source = normalize_text(source_name).lower()
        if not normalized_source:
            continue
        normalized_domains = normalize_string_set(domains)
        if normalized_domains:
            overrides[normalized_source] = normalized_domains
    return overrides


def load_lazy_detail_config(path: Path) -> dict[str, Any]:
    raw = load_json(path, {})
    if not isinstance(raw, dict):
        raw = {}

    return {
        "allowed_sources": normalize_string_set(raw.get("allowed_sources")),
        "excluded_sources": normalize_string_set(raw.get("excluded_sources")),
        "allowed_domains": normalize_string_set(raw.get("allowed_domains")),
        "source_domain_overrides": normalize_source_domain_overrides(raw.get("source_domain_overrides")),
    }


def extract_link_domain(url: Any) -> str:
    parsed = urlparse(normalize_text(url))
    return normalize_text(parsed.netloc).lower()


def domain_is_allowlisted(domain: str, allowlist: set[str]) -> bool:
    if not domain:
        return False
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowlist)


def evaluate_lazy_detail_support(item: dict[str, Any], config: dict[str, Any]) -> tuple[bool, str]:
    if normalize_briefing_markdown(item.get("detailed_summary")):
        return False, "already_present"

    if not item.get("is_english_source"):
        return False, "not_english"

    source = normalize_text(item.get("source")).lower()
    if source == "hacker news frontpage (hn rss)" and normalize_text(item.get("hn_story_id")):
        return True, "hn_api"

    domain = extract_link_domain(item.get("link"))
    if not domain:
        return False, "missing_domain"

    source_domain_overrides = config.get("source_domain_overrides", {})
    override_domains = source_domain_overrides.get(source, set())
    if override_domains:
        if domain_is_allowlisted(domain, override_domains):
            return True, "supported"
        return False, "source_domain_not_allowlisted"

    if source in config.get("excluded_sources", set()):
        return False, "source_excluded"

    allowed_sources = config.get("allowed_sources", set())
    if allowed_sources and source not in allowed_sources:
        return False, "source_not_allowlisted"

    allowed_domains = config.get("allowed_domains", set())
    if allowed_domains and not domain_is_allowlisted(domain, allowed_domains):
        return False, "domain_not_allowlisted"

    return True, "supported"


def build_archive_items(
    items: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    lazy_detail_config: dict[str, Any],
) -> list[dict[str, Any]]:
    archive_items: list[dict[str, Any]] = []

    for item in items:
        tagged = score_and_tag_item_priority(ensure_archive_detail_fields(dict(item)), taxonomy=taxonomy)
        detail_slug = normalize_text(tagged.get("detail_slug"))
        item_id = normalize_text(tagged.get("id")) or detail_slug
        detailed_summary = normalize_briefing_markdown(tagged.get("detailed_summary"))
        lazy_detail_supported, lazy_detail_reason = evaluate_lazy_detail_support(tagged, lazy_detail_config)
        archive_items.append(
            {
                "id": item_id,
                "source": tagged.get("source"),
                "title": tagged.get("title"),
                "translated_title": tagged.get("translated_title"),
                "short_summary": tagged.get("short_summary"),
                "detailed_summary": detailed_summary,
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
                "detail_slug": detail_slug,
                "detail_url": detail_target_url(tagged, nested=False),
                "has_detailed_summary": bool(detailed_summary),
                "is_english_source": bool(tagged.get("is_english_source")),
                "hn_story_id": normalize_text(tagged.get("hn_story_id")),
                "hn_story_type": normalize_text(tagged.get("hn_story_type")),
                "hn_points": normalize_text(tagged.get("hn_points")),
                "hn_comments_count": normalize_text(tagged.get("hn_comments_count")),
                "lazy_detail_supported": lazy_detail_supported,
                "lazy_detail_reason": lazy_detail_reason,
            }
        )

    archive_items.sort(key=sort_key, reverse=True)
    return collapse_geeknews_hn_duplicates(archive_items)


def build_payload(items: list[dict[str, Any]], taxonomy: dict[str, Any]) -> dict[str, Any]:
    slot_order = taxonomy.get("slot_order", [])
    slot_labels = {
        slot_name: taxonomy.get("slots", {}).get(slot_name, {}).get("label", slot_name)
        for slot_name in slot_order
    }
    source_counts = Counter(str(item.get("source") or "").strip() for item in items)
    slot_counts = Counter(normalize_text(item.get("primary_slot")) for item in items)
    last_run = load_json(LAST_RUN_PATH, {})
    today_picks = derive_today_picks(items)

    return {
        "generated_at": now_utc().isoformat(),
        "archive_total": len(items),
        "last_dispatch_at": last_run.get("executed_at"),
        "today_picks": today_picks,
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


def derive_today_picks(items: list[dict[str, Any]], limit: int = 7) -> list[dict[str, Any]]:
    if not items:
        return []

    latest_sent_at = next((normalize_text(item.get("sent_at")) for item in items if item.get("sent_at")), "")
    if latest_sent_at:
        picks = [item for item in items if normalize_text(item.get("sent_at")) == latest_sent_at]
    else:
        picks = items[: min(len(items), limit)]
    picks.sort(key=sort_key, reverse=True)
    return picks[:limit]


def score_related_item(base_item: dict[str, Any], candidate: dict[str, Any]) -> int:
    if normalize_text(base_item.get("id")) == normalize_text(candidate.get("id")):
        return -1

    score = 0
    if normalize_text(base_item.get("primary_slot")) == normalize_text(candidate.get("primary_slot")):
        score += 6

    base_terms = {normalize_text(term).lower() for term in base_item.get("matched_terms", []) if normalize_text(term)}
    candidate_terms = {
        normalize_text(term).lower() for term in candidate.get("matched_terms", []) if normalize_text(term)
    }
    score += len(base_terms & candidate_terms) * 2

    if normalize_text(base_item.get("source")) == normalize_text(candidate.get("source")):
        score += 1

    return score


def derive_related_items(
    base_item: dict[str, Any],
    items: list[dict[str, Any]],
    limit: int = 3,
) -> list[dict[str, Any]]:
    ranked: list[tuple[int, tuple[int, str], dict[str, Any]]] = []
    for candidate in items:
        score = score_related_item(base_item, candidate)
        if score <= 0:
            continue
        ranked.append((score, sort_key(candidate), candidate))

    ranked.sort(key=lambda entry: (entry[0], entry[1][0], entry[1][1]), reverse=True)
    return [entry[2] for entry in ranked[:limit]]


def load_detail_template() -> Template:
    if not DETAIL_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Missing detail template: {DETAIL_TEMPLATE_PATH}")
    return Template(DETAIL_TEMPLATE_PATH.read_text(encoding="utf-8"))


def summary_for_detail(item: dict[str, Any]) -> str:
    detailed = normalize_briefing_markdown(item.get("detailed_summary"))
    if detailed:
        return detailed

    short_summary = normalize_text(item.get("short_summary"))
    if short_summary:
        return short_summary

    if is_geeknews_item(item):
        return to_multiline_preview(item.get("summary", ""), max_lines=5, line_width=52, max_chars=420)

    return ""


def render_summary_html(text: str) -> str:
    return render_briefing_markdown_html(text)


def render_matched_terms_html(terms: list[str]) -> str:
    cleaned = [normalize_text(term) for term in terms if normalize_text(term)]
    if not cleaned:
        return ""
    chips = "".join(f"<span>{html.escape(term)}</span>" for term in cleaned[:6])
    return (
        "<section class='detail-section detail-terms'>"
        "<h2>분류 태그</h2>"
        f"<div class='detail-chip-row'>{chips}</div>"
        "</section>"
    )


def render_related_items_html(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""

    cards: list[str] = []
    for item in items:
        title = html.escape(normalize_text(item.get("translated_title") or item.get("title"), "(제목 없음)"))
        slot = html.escape(normalize_text(item.get("primary_slot_label"), "미분류"))
        source = html.escape(normalize_text(item.get("source"), "Unknown"))
        date = html.escape(format_date(item.get("sent_at") or item.get("published_at") or item.get("fetched_at")))
        url = html.escape(detail_target_url(item, nested=True))
        cards.append(
            "<a class='related-card' href='{url}'>"
            "<span class='related-source'>{source}</span>"
            "<strong>{title}</strong>"
            "<span class='related-meta'>{slot} · {date}</span>"
            "</a>".format(url=url, source=source, title=title, slot=slot, date=date)
        )

    return (
        "<section class='detail-section related-section'>"
        "<div class='section-head'>"
        "<h2>관련 기사</h2>"
        "<p>같은 슬롯이나 비슷한 맥락의 기사입니다.</p>"
        "</div>"
        "<div class='related-list'>"
        + "".join(cards)
        + "</div></section>"
    )


def render_pager_link(item: dict[str, Any] | None, label: str) -> str:
    if not item:
        return ""

    url = html.escape(detail_target_url(item, nested=True))
    title = html.escape(normalize_text(item.get("translated_title") or item.get("title"), "(제목 없음)"))
    return (
        "<a class='pager-link' href='{url}'>"
        "<span class='pager-label'>{label}</span>"
        "<strong>{title}</strong>"
        "</a>".format(url=url, label=html.escape(label), title=title)
    )


def render_pager_html(previous_item: dict[str, Any] | None, next_item: dict[str, Any] | None) -> str:
    previous_html = render_pager_link(previous_item, "이전 기사")
    next_html = render_pager_link(next_item, "다음 기사")
    if not previous_html and not next_html:
        return ""

    return (
        "<nav class='detail-section detail-pager'>"
        f"{previous_html}"
        f"{next_html}"
        "</nav>"
    )


def format_date(value: Any) -> str:
    raw = normalize_text(value)
    if not raw:
        return "날짜 없음"
    parsed = parse_published_datetime(raw)
    if not parsed:
        return raw
    return parsed.astimezone().strftime("%Y.%m.%d %H:%M")


def render_detail_page(
    item: dict[str, Any],
    *,
    related_items: list[dict[str, Any]],
    previous_item: dict[str, Any] | None,
    next_item: dict[str, Any] | None,
    template: Template,
    lazy_detail_api_url: str,
) -> str:
    translated_title = normalize_text(item.get("translated_title") or item.get("title"), "(제목 없음)")
    original_title = normalize_text(item.get("title"))
    original_block = ""
    if original_title and original_title != translated_title:
        original_block = f"<p class='detail-original-title'>원제: {html.escape(original_title)}</p>"

    summary_html = render_summary_html(summary_for_detail(item))
    summary_markdown = summary_for_detail(item)
    matched_terms_html = render_matched_terms_html(item.get("matched_terms", []))
    related_html = render_related_items_html(related_items)
    pager_html = render_pager_html(previous_item, next_item)
    show_ai_badge = normalize_text(item.get("source")) != "GeekNews"
    briefing_badge_html = ""
    if show_ai_badge:
        briefing_badge_html = (
            "<span class='ai-briefing-badge'>"
            "<img src='../../img.icons8.png' alt='' aria-hidden='true' />"
            "<span>with AI</span>"
            "</span>"
        )

    return template.substitute(
        page_title=html.escape(translated_title),
        translated_title=html.escape(translated_title),
        original_title_block=original_block,
        item_id=html.escape(normalize_text(item.get("id"), item.get("detail_slug"))),
        hn_story_id=html.escape(normalize_text(item.get("hn_story_id"))),
        has_detailed_summary=str(bool(item.get("has_detailed_summary"))).lower(),
        lazy_detail_supported=str(bool(item.get("lazy_detail_supported"))).lower(),
        lazy_detail_reason=html.escape(normalize_text(item.get("lazy_detail_reason"))),
        lazy_detail_api_url=html.escape(normalize_text(lazy_detail_api_url)),
        source=html.escape(normalize_text(item.get("source"), "Unknown")),
        sent_date=html.escape(format_date(item.get("sent_at") or item.get("published_at") or item.get("fetched_at"))),
        slot_label=html.escape(normalize_text(item.get("primary_slot_label"), "미분류")),
        briefing_badge_html=briefing_badge_html,
        summary_markdown=html.escape(summary_markdown, quote=True),
        summary_html=summary_html,
        matched_terms_html=matched_terms_html,
        original_link=html.escape(normalize_text(item.get("link"), "#")),
        pager_html=pager_html,
        related_html=related_html,
    )


def write_detail_pages(items: list[dict[str, Any]], lazy_detail_api_url: str) -> None:
    template = load_detail_template()
    for index, item in enumerate(items):
        detail_slug = normalize_text(item.get("detail_slug"))
        if not detail_slug:
            continue

        previous_item = items[index + 1] if index + 1 < len(items) else None
        next_item = items[index - 1] if index - 1 >= 0 else None
        related_items = derive_related_items(item, items)
        output_dir = DIST_DIR / "news" / detail_slug
        output_dir.mkdir(parents=True, exist_ok=True)
        page_html = render_detail_page(
            item,
            related_items=related_items,
            previous_item=previous_item,
            next_item=next_item,
            template=template,
            lazy_detail_api_url=lazy_detail_api_url,
        )
        (output_dir / "index.html").write_text(page_html, encoding="utf-8")


def build_site() -> None:
    if not SITE_SRC.exists():
        raise FileNotFoundError(f"Missing site source directory: {SITE_SRC}")

    raw_news = load_json(NEWS_PATH, {"items": []})
    raw_items = raw_news.get("items", []) if isinstance(raw_news, dict) else []
    if not isinstance(raw_items, list):
        raw_items = []

    taxonomy = load_taxonomy(TAXONOMY_PATH)
    lazy_detail_config = load_lazy_detail_config(LAZY_DETAIL_ALLOWLIST_PATH)
    archive_items = build_archive_items(raw_items, taxonomy=taxonomy, lazy_detail_config=lazy_detail_config)
    payload = build_payload(archive_items, taxonomy=taxonomy)
    lazy_detail_api_url = os.getenv("LAZY_DETAIL_API_URL", "").strip()

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    shutil.copytree(SITE_SRC, DIST_DIR)
    (DIST_DIR / "data").mkdir(parents=True, exist_ok=True)
    SITE_DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_detail_pages(archive_items, lazy_detail_api_url)
    (DIST_DIR / ".nojekyll").write_text("", encoding="utf-8")


if __name__ == "__main__":
    build_site()
