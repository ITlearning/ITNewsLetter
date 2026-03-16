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
    truncate_text,
)

ROOT = Path(__file__).resolve().parent.parent
SITE_SRC = ROOT / "site"
DIST_DIR = ROOT / "dist"
SITE_DATA_PATH = DIST_DIR / "data" / "news-archive.json"
DETAIL_TEMPLATE_PATH = SITE_SRC / "templates" / "detail.html"
TOPIC_TEMPLATE_PATH = SITE_SRC / "templates" / "topic.html"
LAZY_DETAIL_ALLOWLIST_PATH = ROOT / "config" / "lazy_detail_allowlist.json"
DEFAULT_SITE_BASE_URL = "https://itnewsletter.vercel.app"
DEFAULT_ADSENSE_CLIENT = "ca-pub-3668470088067384"


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


def normalize_site_base_url(raw: Any) -> str:
    url = normalize_text(raw, DEFAULT_SITE_BASE_URL)
    return url.rstrip("/")


def build_absolute_detail_url(detail_slug: str, site_base_url: str) -> str:
    return f"{normalize_site_base_url(site_base_url)}/news/{detail_slug}/"


def build_absolute_asset_url(asset_path: str, site_base_url: str) -> str:
    base_url = normalize_site_base_url(site_base_url)
    normalized_path = "/" + asset_path.lstrip("/")
    return f"{base_url}{normalized_path}"


def build_topic_url(period: str, slot: str) -> str:
    return f"./topics/{period}/{slot}/"


def build_nested_topic_url(period: str, slot: str) -> str:
    return f"./{period}/{slot}/"


def build_absolute_topic_url(period: str, slot: str, site_base_url: str) -> str:
    return f"{normalize_site_base_url(site_base_url)}/topics/{period}/{slot}/"


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
        why_it_matters = normalize_briefing_markdown(tagged.get("why_it_matters"))
        hn_reaction_summary = normalize_briefing_markdown(tagged.get("hn_reaction_summary"))
        lazy_detail_supported, lazy_detail_reason = evaluate_lazy_detail_support(tagged, lazy_detail_config)
        archive_items.append(
            {
                "id": item_id,
                "source": tagged.get("source"),
                "title": tagged.get("title"),
                "translated_title": tagged.get("translated_title"),
                "short_summary": tagged.get("short_summary"),
                "why_it_matters": why_it_matters,
                "hn_reaction_summary": hn_reaction_summary,
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
                "hn_discussion_url": normalize_text(tagged.get("hn_discussion_url")),
                "lazy_detail_supported": lazy_detail_supported,
                "lazy_detail_reason": lazy_detail_reason,
            }
        )

    archive_items.sort(key=sort_key, reverse=True)
    return collapse_geeknews_hn_duplicates(archive_items)


def normalize_topic_digests(raw: Any, taxonomy: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    slot_labels = {
        slot_name: normalize_text(taxonomy.get("slots", {}).get(slot_name, {}).get("label"), slot_name)
        for slot_name in taxonomy.get("slot_order", [])
    }
    normalized: dict[str, list[dict[str, Any]]] = {"weekly": [], "monthly": []}

    if not isinstance(raw, dict):
        return normalized

    for period in ("weekly", "monthly"):
        entries = raw.get(period, [])
        if not isinstance(entries, list):
            continue

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            slot = normalize_text(entry.get("slot")).lower()
            if not slot:
                continue
            item_ids = [normalize_text(item_id) for item_id in entry.get("item_ids", []) if normalize_text(item_id)]
            if not item_ids:
                continue
            slot_label = normalize_text(entry.get("slot_label"), slot_labels.get(slot, slot))
            headline = normalize_text(entry.get("headline"), f"{'이번 주' if period == 'weekly' else '이번 달'} {slot_label}")
            summary = normalize_briefing_markdown(entry.get("summary"))
            total_items = int(entry.get("total_items") or len(item_ids))
            normalized[period].append(
                {
                    "period": period,
                    "slot": slot,
                    "slot_label": slot_label,
                    "headline": headline,
                    "summary": summary,
                    "item_ids": item_ids,
                    "total_items": total_items,
                    "generated_at": normalize_text(entry.get("generated_at")),
                    "ai_model": normalize_text(entry.get("ai_model")),
                    "url": build_topic_url(period, slot),
                }
            )

    return normalized


def build_payload(items: list[dict[str, Any]], taxonomy: dict[str, Any], topic_digests: dict[str, Any]) -> dict[str, Any]:
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
        "topic_digests": normalize_topic_digests(topic_digests, taxonomy),
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


def load_topic_template() -> Template:
    if not TOPIC_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Missing topic template: {TOPIC_TEMPLATE_PATH}")
    return Template(TOPIC_TEMPLATE_PATH.read_text(encoding="utf-8"))


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


def build_meta_description(item: dict[str, Any]) -> str:
    summary_text = summary_for_detail(item)
    summary_text = summary_text.replace("**", "").replace("\n- ", " ").replace("\n", " ")
    normalized = normalize_text(summary_text)
    if normalized:
        return truncate_text(normalized, 180)
    fallback = normalize_text(item.get("translated_title") or item.get("title"))
    if fallback:
        return f"{truncate_text(fallback, 110)} 브리핑 페이지."
    return "보낸 IT 뉴스를 원문 읽기 전 브리핑 형태로 정리한 상세 페이지."


def render_detail_banner_ad_html() -> str:
    ad_slot = normalize_text(os.getenv("DETAIL_BANNER_AD_SLOT"))
    if not ad_slot:
        return ""

    ad_client = normalize_text(os.getenv("DETAIL_BANNER_AD_CLIENT"), DEFAULT_ADSENSE_CLIENT)
    return (
        "<section class='detail-ad-section' aria-label='advertisement'>"
        "<div class='detail-ad-label'>Advertisement</div>"
        "<div class='detail-ad-shell'>"
        "<ins class='adsbygoogle detail-ad-unit' "
        "style='display:block' "
        f"data-ad-client='{html.escape(ad_client, quote=True)}' "
        f"data-ad-slot='{html.escape(ad_slot, quote=True)}' "
        "data-ad-format='auto' "
        "data-full-width-responsive='true'></ins>"
        "</div>"
        "<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>"
        "</section>"
    )


def render_why_it_matters_html(item: dict[str, Any]) -> str:
    why_text = normalize_briefing_markdown(item.get("why_it_matters"))
    if not why_text:
        return ""

    return (
        "<section class='detail-section detail-why-card'>"
        "<div class='section-head'>"
        "<h2>왜 중요한가</h2>"
        "<p>이 기사를 지금 볼 이유와 실무적 맥락만 짧게 정리했습니다.</p>"
        "</div>"
        f"<div class='detail-summary'>{render_summary_html(why_text)}</div>"
        "</section>"
    )


def render_hn_reaction_html(item: dict[str, Any]) -> str:
    reaction_text = normalize_briefing_markdown(item.get("hn_reaction_summary"))
    if not reaction_text:
        return ""

    return (
        "<section class='detail-section detail-hn-card'>"
        "<div class='section-head'>"
        "<h2>HN 반응</h2>"
        "<p>Hacker News 댓글에서 반복된 분위기와 논점을 짧게 묶었습니다.</p>"
        "</div>"
        f"<div class='detail-summary'>{render_summary_html(reaction_text)}</div>"
        "</section>"
    )


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


def topic_period_meta(period: str) -> tuple[str, str]:
    if period == "monthly":
        return ("Monthly Topic", "이번 달")
    return ("Weekly Topic", "이번 주")


def topic_page_item_url(item: dict[str, Any]) -> str:
    if is_geeknews_item(item):
        return normalize_text(item.get("link"), "#")
    detail_slug = normalize_text(item.get("detail_slug"))
    if not detail_slug:
        return "#"
    return f"../../../news/{detail_slug}/"


def render_topic_item_cards_html(items: list[dict[str, Any]]) -> str:
    if not items:
        return (
            "<section class='empty-state'>"
            "<h2>연결된 기사가 없습니다.</h2>"
            "<p>다음 배치에서 다시 생성해 주세요.</p>"
            "</section>"
        )

    cards: list[str] = []
    for item in items:
        slot_name = html.escape(normalize_text(item.get("primary_slot"), "unknown"))
        source = html.escape(normalize_text(item.get("source"), "Unknown"))
        slot = html.escape(normalize_text(item.get("primary_slot_label"), "미분류"))
        date = html.escape(format_date(item.get("sent_at") or item.get("published_at") or item.get("fetched_at")))
        title = html.escape(normalize_text(item.get("translated_title") or item.get("title"), "(제목 없음)"))
        original = normalize_text(item.get("title"))
        summary = html.escape(normalize_text(item.get("short_summary")) or normalize_text(item.get("summary")) or "요약 없음")
        detail_url = html.escape(topic_page_item_url(item))
        source_url = html.escape(normalize_text(item.get("link"), "#"))
        original_html = ""
        if original and original != normalize_text(item.get("translated_title")):
            original_html = f"<p class='card-original'>원제: {html.escape(original)}</p>"

        cards.append(
            "<article class='news-card' data-slot='{slot_name}'>"
            "<div class='card-meta'>"
            "<time class='card-date'>{date}</time>"
            "<div class='card-topline'>"
            "<span class='badge badge-source'>{source}</span>"
            "<span class='badge badge-slot'>{slot}</span>"
            "</div>"
            "</div>"
            "<div class='card-body'>"
            "<h3 class='card-title'><a class='card-title-link' href='{detail_url}'>{title}</a></h3>"
            "{original_html}"
            "<p class='card-summary'>{summary}</p>"
            "<div class='card-actions'>"
            "<a class='card-link' href='{detail_url}'>브리핑 보기</a>"
            "<a class='card-link' href='{source_url}' target='_blank' rel='noreferrer'>원문 보기</a>"
            "</div>"
            "</div>"
            "</article>".format(
                slot_name=slot_name,
                date=date,
                source=source,
                slot=slot,
                detail_url=detail_url,
                title=title,
                original_html=original_html,
                summary=summary,
                source_url=source_url,
            )
        )

    return "<section class='news-list'>{cards}</section>".format(cards="".join(cards))


def render_topic_hub_cards_html(topic_digests: dict[str, list[dict[str, Any]]]) -> str:
    cards: list[str] = []
    for period in ("weekly", "monthly"):
        period_tag, _ = topic_period_meta(period)
        for digest in topic_digests.get(period, []):
            cards.append(
                "<a class='topic-card' href='{url}'>"
                "<span class='topic-period'>{period_tag}</span>"
                "<strong class='topic-headline'>{headline}</strong>"
                "<span class='topic-meta'>{slot_label} · 기사 {total_items}건</span>"
                "<p class='topic-summary'>{summary}</p>"
                "</a>".format(
                    url=html.escape(build_nested_topic_url(period, normalize_text(digest.get("slot")))),
                    period_tag=html.escape(period_tag),
                    headline=html.escape(normalize_text(digest.get("headline"))),
                    slot_label=html.escape(normalize_text(digest.get("slot_label"))),
                    total_items=html.escape(str(digest.get("total_items") or 0)),
                    summary=html.escape(normalize_text(digest.get("summary"))),
                )
            )

    if not cards:
        return (
            "<section class='empty-state'>"
            "<h2>토픽 브리핑이 아직 없습니다.</h2>"
            "<p>다음 배치에서 Codex digest가 생성되면 여기에 표시됩니다.</p>"
            "</section>"
        )

    return "<section class='topic-list topic-list-hub'>{cards}</section>".format(cards="".join(cards))


def render_topic_hub_page(topic_digests: dict[str, list[dict[str, Any]]], site_base_url: str) -> str:
    og_image_url = build_absolute_asset_url("img.icons8.png", site_base_url)
    canonical_url = f"{normalize_site_base_url(site_base_url)}/topics/"
    cards_html = render_topic_hub_cards_html(topic_digests)
    return """<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>주간·월간 토픽 | IT Dispatch Archive</title>
    <meta name="description" content="최근 아카이브를 슬롯별로 묶어 한 번에 훑어보는 토픽 브리핑입니다." />
    <link rel="canonical" href="{canonical_url}" />
    <meta property="og:locale" content="ko_KR" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="IT Dispatch Archive" />
    <meta property="og:title" content="주간·월간 토픽" />
    <meta property="og:description" content="최근 아카이브를 슬롯별로 묶어 한 번에 훑어보는 토픽 브리핑입니다." />
    <meta property="og:url" content="{canonical_url}" />
    <meta property="og:image" content="{og_image_url}" />
    <meta name="twitter:card" content="summary" />
    <meta name="twitter:title" content="주간·월간 토픽" />
    <meta name="twitter:description" content="최근 아카이브를 슬롯별로 묶어 한 번에 훑어보는 토픽 브리핑입니다." />
    <meta name="twitter:image" content="{og_image_url}" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet" />
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ad_client}" crossorigin="anonymous"></script>
    <link rel="stylesheet" href="../styles.css" />
  </head>
  <body>
    <div class="page-shell topic-page-shell">
      <header class="topbar">
        <div class="brand-lockup">
          <span class="brand-dot" aria-hidden="true"></span>
          <strong class="brand-name"><a class="brand-link" href="../">IT Dispatch Archive</a></strong>
        </div>
      </header>
      <main class="topic-main">
        <section class="topic-hero">
          <p class="section-kicker">Topic Briefings</p>
          <h1>주간·월간 토픽</h1>
          <p class="section-description">최근 아카이브에서 반복된 흐름만 슬롯별로 다시 묶었습니다.</p>
        </section>
        {cards_html}
      </main>
      <footer class="site-footer" aria-label="사이트 정보">
        <p class="site-footer-copy">이 사이트는 IT 뉴스 브리핑과 큐레이션을 제공합니다. 원문은 각 출처에서 확인하세요.</p>
        <nav class="site-footer-nav" aria-label="정책 링크">
          <a href="../about.html">About</a>
          <a href="../editorial-policy.html">Editorial Policy</a>
          <a href="../privacy.html">Privacy</a>
          <a href="../contact.html">Contact</a>
        </nav>
      </footer>
    </div>
  </body>
</html>
""".format(
        canonical_url=html.escape(canonical_url, quote=True),
        og_image_url=html.escape(og_image_url, quote=True),
        cards_html=cards_html,
        ad_client=html.escape(DEFAULT_ADSENSE_CLIENT, quote=True),
    )


def render_topic_page(
    digest: dict[str, Any],
    *,
    items: list[dict[str, Any]],
    template: Template,
    site_base_url: str,
) -> str:
    period = normalize_text(digest.get("period"), "weekly")
    period_tag, period_label = topic_period_meta(period)
    slot_label = normalize_text(digest.get("slot_label"), "미분류")
    headline = normalize_text(digest.get("headline"), f"{period_label} {slot_label}")
    summary = normalize_briefing_markdown(digest.get("summary"))
    summary_text = truncate_text(summary.replace("\n", " "), 180) or headline
    summary_html = render_summary_html(summary) if summary else "<p>요약이 아직 없습니다.</p>"
    canonical_url = build_absolute_topic_url(period, normalize_text(digest.get("slot")), site_base_url)
    og_image_url = build_absolute_asset_url("img.icons8.png", site_base_url)

    return template.substitute(
        page_title=html.escape(f"{headline} | IT Dispatch Archive"),
        meta_description=html.escape(summary_text, quote=True),
        canonical_url=html.escape(canonical_url, quote=True),
        og_title=html.escape(headline, quote=True),
        og_description=html.escape(summary_text, quote=True),
        og_url=html.escape(canonical_url, quote=True),
        og_image_url=html.escape(og_image_url, quote=True),
        stylesheet_path="../../../styles.css",
        home_url="../../../",
        topics_home_url="../../",
        period_tag=html.escape(period_tag),
        period_label=html.escape(period_label),
        slot_label=html.escape(slot_label),
        headline=html.escape(headline),
        summary_html=summary_html,
        cards_html=render_topic_item_cards_html(items),
    )


def render_detail_page(
    item: dict[str, Any],
    *,
    related_items: list[dict[str, Any]],
    previous_item: dict[str, Any] | None,
    next_item: dict[str, Any] | None,
    template: Template,
    lazy_detail_api_url: str,
    site_base_url: str,
) -> str:
    translated_title = normalize_text(item.get("translated_title") or item.get("title"), "(제목 없음)")
    original_title = normalize_text(item.get("title"))
    original_block = ""
    if original_title and original_title != translated_title:
        original_block = f"<p class='detail-original-title'>원제: {html.escape(original_title)}</p>"

    summary_html = render_summary_html(summary_for_detail(item))
    summary_markdown = summary_for_detail(item)
    meta_description = build_meta_description(item)
    detail_slug = normalize_text(item.get("detail_slug"))
    canonical_url = build_absolute_detail_url(detail_slug, site_base_url) if detail_slug else normalize_site_base_url(
        site_base_url
    )
    og_image_url = build_absolute_asset_url("img.icons8.png", site_base_url)
    matched_terms_html = render_matched_terms_html(item.get("matched_terms", []))
    related_html = render_related_items_html(related_items)
    pager_html = render_pager_html(previous_item, next_item)
    detail_banner_ad_html = render_detail_banner_ad_html()
    why_it_matters_html = render_why_it_matters_html(item)
    hn_reaction_html = render_hn_reaction_html(item)
    hn_discussion_button_html = ""
    hn_discussion_url = normalize_text(item.get("hn_discussion_url"))
    if hn_discussion_url:
        hn_discussion_button_html = (
            f"<a class='source-button secondary' href='{html.escape(hn_discussion_url, quote=True)}' "
            "target='_blank' rel='noreferrer'>HN 토론 보기</a>"
        )
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
        page_title=html.escape(f"{translated_title} | IT Dispatch Archive"),
        meta_description=html.escape(meta_description, quote=True),
        canonical_url=html.escape(canonical_url, quote=True),
        og_title=html.escape(translated_title, quote=True),
        og_description=html.escape(meta_description, quote=True),
        og_url=html.escape(canonical_url, quote=True),
        og_image_url=html.escape(og_image_url, quote=True),
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
        hn_discussion_button_html=hn_discussion_button_html,
        detail_banner_ad_html=detail_banner_ad_html,
        why_it_matters_html=why_it_matters_html,
        hn_reaction_html=hn_reaction_html,
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
    site_base_url = normalize_site_base_url(os.getenv("SITE_BASE_URL", DEFAULT_SITE_BASE_URL))
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
            site_base_url=site_base_url,
        )
        (output_dir / "index.html").write_text(page_html, encoding="utf-8")


def write_topic_pages(items: list[dict[str, Any]], topic_digests: dict[str, list[dict[str, Any]]]) -> None:
    site_base_url = normalize_site_base_url(os.getenv("SITE_BASE_URL", DEFAULT_SITE_BASE_URL))
    topic_root = DIST_DIR / "topics"
    topic_root.mkdir(parents=True, exist_ok=True)
    (topic_root / "index.html").write_text(render_topic_hub_page(topic_digests, site_base_url), encoding="utf-8")

    template = load_topic_template()
    items_by_id = {normalize_text(item.get("id")): item for item in items if normalize_text(item.get("id"))}

    for period in ("weekly", "monthly"):
        for digest in topic_digests.get(period, []):
            slot = normalize_text(digest.get("slot"))
            if not slot:
                continue
            topic_items = [items_by_id[item_id] for item_id in digest.get("item_ids", []) if item_id in items_by_id]
            output_dir = topic_root / period / slot
            output_dir.mkdir(parents=True, exist_ok=True)
            page_html = render_topic_page(digest, items=topic_items, template=template, site_base_url=site_base_url)
            (output_dir / "index.html").write_text(page_html, encoding="utf-8")


def build_site() -> None:
    if not SITE_SRC.exists():
        raise FileNotFoundError(f"Missing site source directory: {SITE_SRC}")

    raw_news = load_json(NEWS_PATH, {"items": []})
    raw_items = raw_news.get("items", []) if isinstance(raw_news, dict) else []
    raw_topic_digests = raw_news.get("topic_digests", {}) if isinstance(raw_news, dict) else {}
    if not isinstance(raw_items, list):
        raw_items = []

    taxonomy = load_taxonomy(TAXONOMY_PATH)
    lazy_detail_config = load_lazy_detail_config(LAZY_DETAIL_ALLOWLIST_PATH)
    archive_items = build_archive_items(raw_items, taxonomy=taxonomy, lazy_detail_config=lazy_detail_config)
    payload = build_payload(archive_items, taxonomy=taxonomy, topic_digests=raw_topic_digests)
    lazy_detail_api_url = os.getenv("LAZY_DETAIL_API_URL", "").strip()

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    shutil.copytree(SITE_SRC, DIST_DIR)
    (DIST_DIR / "data").mkdir(parents=True, exist_ok=True)
    SITE_DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_detail_pages(archive_items, lazy_detail_api_url)
    write_topic_pages(archive_items, payload.get("topic_digests", {}))
    (DIST_DIR / ".nojekyll").write_text("", encoding="utf-8")


if __name__ == "__main__":
    build_site()
