#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import logging
import os
import re
import shutil
from collections import Counter
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any
from urllib.parse import urlparse

try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError:
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageFont = None  # type: ignore[assignment]

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
    safe_float,
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
SPOTLIGHT_KIND_ORDER: tuple[str, ...] = ("quiet_riser", "hn_split", "anomaly_signal")
DEFAULT_OG_IMAGE_PATH = "img.icons8.png"
DEFAULT_OG_IMAGE_WIDTH = 200
DEFAULT_OG_IMAGE_HEIGHT = 200
HN_SOURCE_NAME = "Hacker News Frontpage (HN RSS)"
HN_OG_ASSET_DIR = "og/hn"
HN_OG_IMAGE_WIDTH = 1200
HN_OG_IMAGE_HEIGHT = 630
HN_OG_FONT_DIR = ROOT / "scripts" / "assets" / "fonts"
HN_OG_FONT_PATHS = {
    "regular": (
        HN_OG_FONT_DIR / "IBMPlexSansKR-Regular.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    ),
    "bold": (
        HN_OG_FONT_DIR / "IBMPlexSansKR-Bold.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    ),
}
LOGGER = logging.getLogger(__name__)


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


def is_hn_item(item: dict[str, Any]) -> bool:
    return normalize_text(item.get("source")) == HN_SOURCE_NAME


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


def normalize_spotlight_modules(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    modules_by_kind: dict[str, dict[str, Any]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        kind = normalize_text(entry.get("kind")).lower()
        if kind not in SPOTLIGHT_KIND_ORDER:
            continue

        raw_related_item_ids = entry.get("related_item_ids", [])
        if not isinstance(raw_related_item_ids, list):
            raw_related_item_ids = []
        related_item_ids = [normalize_text(item_id) for item_id in raw_related_item_ids if normalize_text(item_id)]
        module: dict[str, Any] = {
            "id": normalize_text(entry.get("id"), kind),
            "kind": kind,
            "label": normalize_text(entry.get("label"), "AI Spotlight" if kind != "anomaly_signal" else "Labs"),
            "title": normalize_text(entry.get("title")),
            "cta_label": normalize_text(entry.get("cta_label"), "관련 기사 보기"),
            "related_item_ids": related_item_ids,
            "score": max(0.0, min(1.0, safe_float(entry.get("score"), 0.0))),
            "generated_at": normalize_text(entry.get("generated_at")),
            "ai_model": normalize_text(entry.get("ai_model")),
        }

        if kind == "quiet_riser":
            raw_signals = entry.get("signals", [])
            if not isinstance(raw_signals, list):
                raw_signals = []
            module["topic_name"] = normalize_text(entry.get("topic_name"))
            module["summary_line"] = normalize_text(entry.get("summary_line"))
            module["signals"] = [normalize_text(signal) for signal in raw_signals if normalize_text(signal)][:3]
            if not module["topic_name"] or not module["summary_line"]:
                continue
        elif kind == "hn_split":
            module["headline"] = normalize_text(entry.get("headline"))
            module["issue_title"] = normalize_text(entry.get("issue_title"))
            module["opposition_summary"] = normalize_text(entry.get("opposition_summary"))
            module["support_summary"] = normalize_text(entry.get("support_summary"))
            if (
                not module["headline"]
                or not module["issue_title"]
                or not module["opposition_summary"]
                or not module["support_summary"]
            ):
                continue
        elif kind == "anomaly_signal":
            raw_signals = entry.get("signals", [])
            if not isinstance(raw_signals, list):
                raw_signals = []
            module["signal_title"] = normalize_text(entry.get("signal_title"))
            module["summary_line"] = normalize_text(entry.get("summary_line"))
            module["signals"] = [normalize_text(signal) for signal in raw_signals if normalize_text(signal)][:3]
            if not module["signal_title"] or not module["summary_line"]:
                continue

        modules_by_kind.setdefault(kind, module)

    return [modules_by_kind[kind] for kind in SPOTLIGHT_KIND_ORDER if kind in modules_by_kind]


def normalize_featured_spotlight(raw: Any, modules: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not modules:
        return None

    featured_id = normalize_text(raw.get("id")) if isinstance(raw, dict) else ""
    featured = next((module for module in modules if module.get("id") == featured_id), None)
    if not featured:
        featured = max(modules, key=lambda module: float(module.get("score") or 0.0))
    return dict(featured)


def build_payload(
    items: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    topic_digests: dict[str, Any],
    spotlight_modules_raw: Any,
    featured_spotlight_raw: Any,
) -> dict[str, Any]:
    slot_order = taxonomy.get("slot_order", [])
    slot_labels = {
        slot_name: taxonomy.get("slots", {}).get(slot_name, {}).get("label", slot_name)
        for slot_name in slot_order
    }
    source_counts = Counter(str(item.get("source") or "").strip() for item in items)
    slot_counts = Counter(normalize_text(item.get("primary_slot")) for item in items)
    last_run = load_json(LAST_RUN_PATH, {})
    today_picks = derive_today_picks(items)
    spotlight_modules = normalize_spotlight_modules(spotlight_modules_raw)
    featured_spotlight = normalize_featured_spotlight(featured_spotlight_raw, spotlight_modules)

    return {
        "generated_at": now_utc().isoformat(),
        "archive_total": len(items),
        "last_dispatch_at": last_run.get("executed_at"),
        "today_picks": today_picks,
        "topic_digests": normalize_topic_digests(topic_digests, taxonomy),
        "spotlight_modules": spotlight_modules,
        "featured_spotlight": featured_spotlight,
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


def build_default_social_metadata(site_base_url: str) -> dict[str, str]:
    og_image_url = build_absolute_asset_url(DEFAULT_OG_IMAGE_PATH, site_base_url)
    return {
        "og_image_url": og_image_url,
        "twitter_image_url": og_image_url,
        "twitter_card": "summary",
        "og_image_width": str(DEFAULT_OG_IMAGE_WIDTH),
        "og_image_height": str(DEFAULT_OG_IMAGE_HEIGHT),
    }


def is_hn_og_eligible(item: dict[str, Any]) -> bool:
    if not is_hn_item(item):
        return False
    if not normalize_text(item.get("detail_slug")):
        return False
    return bool(build_hn_primary_title(item))


def build_hn_primary_title(item: dict[str, Any]) -> str:
    return normalize_text(item.get("translated_title") or item.get("title"))


def build_hn_secondary_title(item: dict[str, Any], primary_title: str) -> str:
    original_title = normalize_text(item.get("title"))
    if not original_title or original_title == primary_title:
        return ""
    return original_title


def measure_text_width(font: Any, text: str) -> int:
    if not text:
        return 0
    bbox = font.getbbox(text)
    return max(0, bbox[2] - bbox[0])


def measure_line_height(font: Any, *, multiplier: float = 1.18) -> int:
    bbox = font.getbbox("한Ag")
    height = max(1, bbox[3] - bbox[1])
    return max(1, int(height * multiplier))


def ellipsize_text(text: str, font: Any, max_width: int) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return ""
    if measure_text_width(font, normalized) <= max_width:
        return normalized

    trimmed = normalized.rstrip()
    while trimmed and measure_text_width(font, f"{trimmed}...") > max_width:
        trimmed = trimmed[:-1].rstrip()
    return f"{trimmed}..." if trimmed else "..."


def clamp_text_lines(text: str, font: Any, *, max_width: int, max_lines: int) -> list[str]:
    normalized = re.sub(r"\s+", " ", normalize_text(text))
    if not normalized:
        return []

    lines: list[str] = []
    current = ""
    index = 0
    while index < len(normalized):
        char = normalized[index]
        candidate = current + char
        if not current or measure_text_width(font, candidate) <= max_width:
            current = candidate
            index += 1
            continue

        split_at = current.rfind(" ")
        if split_at > int(len(current) * 0.45):
            lines.append(current[:split_at].rstrip())
            current = current[split_at + 1 :] + char
            index += 1
        else:
            lines.append(current.rstrip())
            current = char.lstrip()
            index += 1

        if len(lines) == max_lines:
            remaining = current + normalized[index:]
            lines[-1] = ellipsize_text(f"{lines[-1]} {remaining}".strip(), font, max_width)
            return [line for line in lines if line]

    if current.strip():
        lines.append(current.rstrip())

    if len(lines) <= max_lines:
        return [line for line in lines if line]

    trimmed = lines[:max_lines]
    overflow = " ".join(line for line in lines[max_lines - 1 :] if line)
    trimmed[-1] = ellipsize_text(overflow, font, max_width)
    return [line for line in trimmed if line]


@lru_cache(maxsize=None)
def load_hn_og_font(role: str, size: int) -> Any:
    if ImageFont is None:
        raise RuntimeError("Pillow is not installed")

    for path in HN_OG_FONT_PATHS.get(role, ()):
        if not path.exists():
            continue
        try:
            return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def interpolate_color(start: tuple[int, int, int], end: tuple[int, int, int], ratio: float) -> tuple[int, int, int]:
    return tuple(int(start[index] + (end[index] - start[index]) * ratio) for index in range(3))


def draw_vertical_gradient(draw: Any, width: int, height: int) -> None:
    top = (244, 239, 230)
    bottom = (255, 255, 255)
    for y in range(height):
        ratio = y / max(1, height - 1)
        draw.line((0, y, width, y), fill=interpolate_color(top, bottom, ratio))


def render_hn_og_image(item: dict[str, Any]) -> Any:
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is not installed")

    width = HN_OG_IMAGE_WIDTH
    height = HN_OG_IMAGE_HEIGHT
    image = Image.new("RGBA", (width, height), (252, 250, 244, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    draw_vertical_gradient(draw, width, height)

    draw.ellipse((-140, -90, 450, 420), fill=(37, 99, 235, 28))
    draw.ellipse((780, -120, 1320, 360), fill=(249, 115, 22, 26))
    draw.ellipse((860, 310, 1290, 760), fill=(129, 140, 248, 22))

    surface_box = (56, 46, width - 56, height - 46)
    draw.rounded_rectangle(surface_box, radius=34, fill=(255, 255, 255, 228), outline=(255, 255, 255, 170), width=2)
    draw.rounded_rectangle((80, 70, 96, height - 70), radius=8, fill=(37, 99, 235, 255))

    brand_font = load_hn_og_font("bold", 30)
    chip_font = load_hn_og_font("bold", 28)
    eyebrow_font = load_hn_og_font("regular", 23)
    primary_font = load_hn_og_font("bold", 78)
    secondary_font = load_hn_og_font("regular", 40)

    primary_title = build_hn_primary_title(item)
    secondary_title = build_hn_secondary_title(item, primary_title)
    primary_lines = clamp_text_lines(
        primary_title,
        primary_font,
        max_width=952,
        max_lines=3 if secondary_title else 4,
    )
    secondary_lines = clamp_text_lines(secondary_title, secondary_font, max_width=952, max_lines=2)

    brand_label = "IT Dispatch Archive"
    brand_width = measure_text_width(brand_font, brand_label)
    draw.rounded_rectangle((112, 94, 112 + brand_width + 42, 146), radius=18, fill=(255, 255, 255, 188))
    draw.text((132, 107), brand_label, font=brand_font, fill=(26, 31, 39, 255))
    draw.text((112, 171), "EDITORIAL LINK PREVIEW", font=eyebrow_font, fill=(95, 107, 120, 255))

    chip_label = "Hacker News"
    chip_width = measure_text_width(chip_font, chip_label)
    chip_x = width - 112 - chip_width - 42
    draw.rounded_rectangle((chip_x, 94, width - 112, 146), radius=18, fill=(255, 241, 232, 255), outline=(249, 115, 22, 96), width=2)
    draw.text((chip_x + 20, 107), chip_label, font=chip_font, fill=(194, 65, 12, 255))

    text_x = 130
    text_y = 234
    primary_line_height = measure_line_height(primary_font, multiplier=1.12)
    secondary_line_height = measure_line_height(secondary_font, multiplier=1.18)
    for line in primary_lines:
        draw.text((text_x, text_y), line, font=primary_font, fill=(26, 31, 39, 255))
        text_y += primary_line_height

    if secondary_lines:
        text_y += 22
        for line in secondary_lines:
            draw.text((text_x, text_y), line, font=secondary_font, fill=(95, 107, 120, 255))
            text_y += secondary_line_height

    return image.convert("RGB")


def write_hn_og_image(item: dict[str, Any], site_base_url: str) -> str:
    detail_slug = normalize_text(item.get("detail_slug"))
    if not detail_slug:
        raise RuntimeError("missing detail slug")

    asset_rel_path = f"{HN_OG_ASSET_DIR}/{detail_slug}.png"
    output_path = DIST_DIR / asset_rel_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = render_hn_og_image(item)
    image.save(output_path, format="PNG")
    return build_absolute_asset_url(asset_rel_path, site_base_url)


def build_detail_social_metadata(item: dict[str, Any], site_base_url: str) -> dict[str, str]:
    metadata = build_default_social_metadata(site_base_url)
    if not is_hn_og_eligible(item):
        return metadata

    item_id = normalize_text(item.get("id"), "(missing-id)")
    detail_slug = normalize_text(item.get("detail_slug"), "(missing-slug)")
    try:
        og_image_url = write_hn_og_image(item, site_base_url)
    except Exception as exc:
        LOGGER.warning("HN OG render failed for item=%s slug=%s reason=%s", item_id, detail_slug, exc)
        return metadata

    return {
        "og_image_url": og_image_url,
        "twitter_image_url": og_image_url,
        "twitter_card": "summary_large_image",
        "og_image_width": str(HN_OG_IMAGE_WIDTH),
        "og_image_height": str(HN_OG_IMAGE_HEIGHT),
    }


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


def build_spotlight_context_map(spotlight_modules: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    context_map: dict[str, list[dict[str, Any]]] = {}
    for module in spotlight_modules:
        for item_id in module.get("related_item_ids", []):
            normalized_item_id = normalize_text(item_id)
            if not normalized_item_id:
                continue
            context_map.setdefault(normalized_item_id, []).append(module)
    return context_map


def render_spotlight_context_html(item: dict[str, Any], spotlight_modules: list[dict[str, Any]]) -> str:
    if not spotlight_modules:
        return ""

    module = spotlight_modules[0]
    kind = normalize_text(module.get("kind"))
    kicker = html.escape(normalize_text(module.get("label"), "AI Spotlight"))
    home_url = "../../#spotlight-section"

    if kind == "quiet_riser":
        headline = html.escape(normalize_text(module.get("topic_name"), "조용히 커지는 흐름"))
        body = html.escape(
            normalize_text(module.get("summary_line"), "최근 기사 안에서 반복되며 조금씩 커지는 흐름으로 묶였습니다.")
        )
    elif kind == "hn_split":
        headline = html.escape(normalize_text(module.get("issue_title") or module.get("headline"), "논쟁 포인트"))
        body = html.escape(
            normalize_text(
                module.get("headline"),
                "이번 주 HN 반응이 가장 선명하게 갈린 기사 카드에 포함됐습니다.",
            )
        )
    else:
        headline = html.escape(normalize_text(module.get("signal_title"), "이번 주 이상 신호"))
        body = html.escape(
            normalize_text(module.get("summary_line"), "메인스트림은 아니지만 반복해서 감지된 신호입니다.")
        )

    return (
        f"<section class='detail-section detail-spotlight-context detail-spotlight-context-{html.escape(kind)}'>"
        "<div class='section-head'>"
        f"<p class='detail-spotlight-kicker'>{kicker}</p>"
        f"<h2>{html.escape(normalize_text(module.get('title'), 'AI Spotlight'))}</h2>"
        "</div>"
        "<div class='detail-spotlight-copy'>"
        f"<strong>{headline}</strong>"
        f"<p>{body}</p>"
        "</div>"
        f"<a class='card-link' href='{home_url}'>홈 Spotlight 보기</a>"
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
    spotlight_context_html: str,
    previous_item: dict[str, Any] | None,
    next_item: dict[str, Any] | None,
    social_metadata: dict[str, str],
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
        og_image_url=html.escape(social_metadata["og_image_url"], quote=True),
        twitter_image_url=html.escape(social_metadata["twitter_image_url"], quote=True),
        twitter_card=html.escape(social_metadata["twitter_card"], quote=True),
        og_image_width=html.escape(social_metadata["og_image_width"], quote=True),
        og_image_height=html.escape(social_metadata["og_image_height"], quote=True),
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
        spotlight_context_html=spotlight_context_html,
        briefing_badge_html=briefing_badge_html,
        summary_markdown=html.escape(summary_markdown, quote=True),
        summary_html=summary_html,
        matched_terms_html=matched_terms_html,
        original_link=html.escape(normalize_text(item.get("link"), "#")),
        pager_html=pager_html,
        related_html=related_html,
    )


def write_detail_pages(
    items: list[dict[str, Any]],
    lazy_detail_api_url: str,
    spotlight_modules: list[dict[str, Any]],
) -> None:
    template = load_detail_template()
    site_base_url = normalize_site_base_url(os.getenv("SITE_BASE_URL", DEFAULT_SITE_BASE_URL))
    spotlight_context_map = build_spotlight_context_map(spotlight_modules)
    for index, item in enumerate(items):
        detail_slug = normalize_text(item.get("detail_slug"))
        if not detail_slug:
            continue

        previous_item = items[index + 1] if index + 1 < len(items) else None
        next_item = items[index - 1] if index - 1 >= 0 else None
        related_items = derive_related_items(item, items)
        spotlight_context_html = render_spotlight_context_html(
            item,
            spotlight_context_map.get(normalize_text(item.get("id")), []),
        )
        output_dir = DIST_DIR / "news" / detail_slug
        output_dir.mkdir(parents=True, exist_ok=True)
        social_metadata = build_detail_social_metadata(item, site_base_url)
        page_html = render_detail_page(
            item,
            related_items=related_items,
            spotlight_context_html=spotlight_context_html,
            previous_item=previous_item,
            next_item=next_item,
            social_metadata=social_metadata,
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
    raw_spotlight_modules = raw_news.get("spotlight_modules", []) if isinstance(raw_news, dict) else []
    raw_featured_spotlight = raw_news.get("featured_spotlight") if isinstance(raw_news, dict) else None
    if not isinstance(raw_items, list):
        raw_items = []

    taxonomy = load_taxonomy(TAXONOMY_PATH)
    lazy_detail_config = load_lazy_detail_config(LAZY_DETAIL_ALLOWLIST_PATH)
    archive_items = build_archive_items(raw_items, taxonomy=taxonomy, lazy_detail_config=lazy_detail_config)
    payload = build_payload(
        archive_items,
        taxonomy=taxonomy,
        topic_digests=raw_topic_digests,
        spotlight_modules_raw=raw_spotlight_modules,
        featured_spotlight_raw=raw_featured_spotlight,
    )
    lazy_detail_api_url = os.getenv("LAZY_DETAIL_API_URL", "").strip()

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    shutil.copytree(SITE_SRC, DIST_DIR)
    (DIST_DIR / "data").mkdir(parents=True, exist_ok=True)
    SITE_DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_detail_pages(archive_items, lazy_detail_api_url, payload.get("spotlight_modules", []))
    write_topic_pages(archive_items, payload.get("topic_digests", {}))
    (DIST_DIR / ".nojekyll").write_text("", encoding="utf-8")


if __name__ == "__main__":
    build_site()
