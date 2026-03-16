#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
TAXONOMY_PATH = ROOT / "config" / "taxonomy.yaml"
STATE_PATH = ROOT / "data" / "state.json"
NEWS_PATH = ROOT / "data" / "news.json"
LAST_RUN_PATH = ROOT / "data" / "last_run.json"

USER_AGENT = "ITNewsLetterBot/1.0 (+https://github.com/)"
HN_ITEM_ID_RE = re.compile(r"news\.ycombinator\.com/item\?id=(\d+)", re.IGNORECASE)
HN_POINTS_RE = re.compile(r"\bPoints:\s*(\d+)\b", re.IGNORECASE)
HN_COMMENTS_RE = re.compile(r"(?:#\s*Comments:|Comments:)\s*(\d+)\b", re.IGNORECASE)
BRIEFING_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

HUMANIZER_PROMPT_GUIDANCE = """- 한국어 문장을 사람이 쓴 것처럼 자연스럽게 써라.
- 쉼표를 과하게 쓰지 말고, 필요하면 문장을 나눠라.
- 영어 번역투를 줄이고 한국어다운 어순과 호흡을 사용하라.
- '핵심적이다', '효과적이다', '혁신적이다', '중요하다', '다양하다' 같은 상투적 표현을 반복하지 말라.
- 문장 길이와 리듬을 조금씩 다르게 써라.
- 불필요한 대명사, 지시어, 복수형 '-들' 남발을 피하라.
- 의미와 사실은 바꾸지 말고, 설명은 더 읽기 쉽게 재구성하라."""

DEFAULT_SOURCE_PRIORITY_BOOST: dict[str, int] = {
    "GeekNews": 45,
    "iOS Dev Weekly": 24,
    "Swift Weekly Brief": 22,
    "Hacker News Frontpage (HN RSS)": 18,
    "TLDR Tech": 10,
    "TechCrunch": 6,
}

DEFAULT_TAXONOMY_WEIGHTS: dict[str, int] = {
    "strong_term": 5,
    "support_term": 2,
    "negative_term": -4,
    "phrase_rule": 6,
    "domain_hint": 3,
    "no_signal_penalty": -8,
}

SLOT_BUCKETS: dict[str, str] = {
    "practical_tech": "technical",
    "tools_agents": "technical",
    "strategy_insight": "general",
    "industry_business": "general",
}

DISCORD_PREVIEW_ITEMS_LIMIT = 3
DISCORD_PREVIEW_TITLE_LIMIT = 52
TOPIC_DIGEST_WINDOWS: tuple[tuple[str, str, int], ...] = (
    ("weekly", "이번 주", 7),
    ("monthly", "이번 달", 30),
)
TOPIC_DIGEST_MIN_ITEMS = 2
TOPIC_DIGEST_MAX_ITEMS_PER_DIGEST = 5
TOPIC_DIGEST_MAX_SLOTS_PER_PERIOD = 3


@dataclass
class Source:
    name: str
    feed_url: str
    enabled: bool
    max_items: int
    priority_boost: int
    source_type: str
    path_prefix: str


@dataclass
class BatchContentResult:
    content: str
    mode: str
    truncated: bool


@dataclass
class BatchSelection:
    content: str
    items: list[dict[str, str]]
    mode: str
    truncated: bool
    selection_reason: str | None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def read_bounded_int_env(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc

    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}, got {value}")
    return value


def default_source_priority_boost(source_name: str) -> int:
    return DEFAULT_SOURCE_PRIORITY_BOOST.get(source_name, 0)


def count_keyword_hits(text: str, keywords: list[str]) -> int:
    total = 0
    for keyword in keywords:
        if keyword and keyword in text:
            total += 1
    return total


def unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def normalize_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []

    values: list[str] = []
    for item in raw:
        text = normalize_text(item).lower()
        if text:
            values.append(text)
    return unique_preserving_order(values)


def normalize_phrase_rules(raw: Any) -> list[list[str]]:
    if not isinstance(raw, list):
        return []

    rules: list[list[str]] = []
    for item in raw:
        if not isinstance(item, list):
            continue
        terms = normalize_string_list(item)
        if len(terms) >= 2:
            rules.append(terms)
    return rules


def normalize_taxonomy_slot(raw: Any) -> dict[str, Any]:
    slot = raw if isinstance(raw, dict) else {}
    return {
        "label": normalize_text(slot.get("label")),
        "strong_terms": normalize_string_list(slot.get("strong_terms")),
        "support_terms": normalize_string_list(slot.get("support_terms")),
        "negative_terms": normalize_string_list(slot.get("negative_terms")),
        "phrase_rules": normalize_phrase_rules(slot.get("phrase_rules")),
        "domain_hints": normalize_string_list(slot.get("domain_hints")),
    }


def merge_taxonomy_slot(base_slot: dict[str, Any], overlay_slot: dict[str, Any]) -> dict[str, Any]:
    merged = {
        "label": normalize_text(overlay_slot.get("label") or base_slot.get("label")),
        "strong_terms": unique_preserving_order(
            [*base_slot.get("strong_terms", []), *overlay_slot.get("strong_terms", [])]
        ),
        "support_terms": unique_preserving_order(
            [*base_slot.get("support_terms", []), *overlay_slot.get("support_terms", [])]
        ),
        "negative_terms": unique_preserving_order(
            [*base_slot.get("negative_terms", []), *overlay_slot.get("negative_terms", [])]
        ),
        "phrase_rules": [*base_slot.get("phrase_rules", []), *overlay_slot.get("phrase_rules", [])],
        "domain_hints": unique_preserving_order(
            [*base_slot.get("domain_hints", []), *overlay_slot.get("domain_hints", [])]
        ),
    }
    return merged


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def normalize_text(raw: Any, fallback: str = "") -> str:
    text = str(raw or fallback).replace("\n", " ").strip()
    return " ".join(text.split())


def normalize_briefing_markdown(raw: Any, fallback: str = "") -> str:
    text = str(raw or fallback).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    normalized_lines: list[str] = []
    previous_blank = False
    for raw_line in text.split("\n"):
        line = " ".join(str(raw_line).strip().split())
        if not line:
            if normalized_lines and not previous_blank:
                normalized_lines.append("")
            previous_blank = True
            continue

        if line.startswith("* "):
            line = "- " + line[2:].strip()
        elif line.startswith("- "):
            line = "- " + line[2:].strip()
        normalized_lines.append(line)
        previous_blank = False

    return "\n".join(normalized_lines).strip()


def briefing_looks_like_markdown(raw: Any) -> bool:
    text = str(raw or "")
    normalized = normalize_briefing_markdown(text)
    if not normalized:
        return False

    lines = [line for line in normalized.split("\n") if line.strip()]
    if any(line.startswith("- ") for line in lines):
        return True
    if "**" in text:
        return True
    return len(lines) >= 2 and "\n\n" in normalized


def render_inline_briefing_markdown(text: str) -> str:
    escaped = html.escape(text)
    return BRIEFING_BOLD_RE.sub(lambda match: f"<strong>{match.group(1)}</strong>", escaped)


def render_briefing_markdown_html(text: str) -> str:
    normalized = normalize_briefing_markdown(text)
    if not normalized:
        return "<p class='detail-summary-empty'>요약이 없습니다. 원문에서 자세히 확인하세요.</p>"

    lines = normalized.split("\n")
    html_blocks: list[str] = []
    paragraph_lines: list[str] = []
    list_items: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if not paragraph_lines:
            return
        paragraph = " ".join(paragraph_lines).strip()
        if paragraph:
            html_blocks.append(f"<p>{render_inline_briefing_markdown(paragraph)}</p>")
        paragraph_lines = []

    def flush_list() -> None:
        nonlocal list_items
        if not list_items:
            return
        items_html = "".join(
            f"<li>{render_inline_briefing_markdown(item)}</li>" for item in list_items if item
        )
        if items_html:
            html_blocks.append(f"<ul class='detail-summary-list'>{items_html}</ul>")
        list_items = []

    for line in lines:
        if not line:
            flush_paragraph()
            flush_list()
            continue

        if line.startswith("- "):
            flush_paragraph()
            list_items.append(line[2:].strip())
            continue

        flush_list()
        paragraph_lines.append(line)

    flush_paragraph()
    flush_list()
    return "\n".join(html_blocks)


def truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def strip_html(raw: Any, fallback: str = "") -> str:
    text = html.unescape(str(raw or fallback))
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize_text(text)


def fetch_json_url(url: str, timeout_sec: int = 15) -> Any:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    with urlopen(req, timeout=timeout_sec) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def to_multiline_preview(text: str, max_lines: int = 4, line_width: int = 44, max_chars: int = 280) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return ""

    clipped = truncate_text(normalized, max_chars)
    wrapped = textwrap.wrap(
        clipped,
        width=max(16, line_width),
        break_long_words=False,
        break_on_hyphens=False,
    )
    if not wrapped:
        return clipped

    if len(wrapped) > max_lines:
        wrapped = wrapped[:max_lines]
        wrapped[-1] = truncate_text(wrapped[-1], max(8, line_width))
        if not wrapped[-1].endswith("..."):
            wrapped[-1] = wrapped[-1].rstrip(".") + "..."

    return "\n".join(wrapped)


def is_likely_english(text: str) -> bool:
    ascii_letters = re.findall(r"[A-Za-z]", text)
    hangul_letters = re.findall(r"[가-힣]", text)
    if not ascii_letters:
        return False
    if hangul_letters and len(hangul_letters) >= len(ascii_letters):
        return False
    ratio = len(ascii_letters) / max(1, len(text))
    return len(ascii_letters) >= 6 and ratio >= 0.2


def is_korean_dominant(text: str) -> bool:
    hangul_letters = re.findall(r"[가-힣]", text)
    if not hangul_letters:
        return False
    ascii_letters = re.findall(r"[A-Za-z]", text)
    return len(hangul_letters) >= max(2, len(ascii_letters))


def extract_hn_story_id(item: dict[str, Any]) -> str:
    existing = normalize_text(item.get("hn_story_id"))
    if existing:
        return existing

    for candidate in (
        normalize_text(item.get("hn_discussion_url")),
        normalize_text(item.get("summary")),
        normalize_text(item.get("link")),
    ):
        match = HN_ITEM_ID_RE.search(candidate)
        if match:
            return normalize_text(match.group(1))
    return ""


def extract_hn_metric(text: str, pattern: re.Pattern[str]) -> str:
    match = pattern.search(normalize_text(text))
    if not match:
        return ""
    return normalize_text(match.group(1))


def duplicate_compare_title(item: dict[str, Any]) -> str:
    source = normalize_text(item.get("source"))
    if source == "Hacker News Frontpage (HN RSS)":
        return normalize_text(item.get("translated_title") or item.get("title"))
    return normalize_text(item.get("title") or item.get("translated_title"))


def title_tokens_for_dedupe(text: str) -> set[str]:
    normalized = normalize_text(text).lower()
    if not normalized:
        return set()
    tokens = re.findall(r"[a-z0-9]+|[가-힣]+", normalized)
    stopwords = {
        "the",
        "a",
        "an",
        "to",
        "for",
        "of",
        "in",
        "on",
        "and",
        "or",
        "is",
        "are",
        "with",
        "using",
        "guide",
        "how",
        "show",
        "hn",
    }
    return {token for token in tokens if len(token) >= 2 and token not in stopwords}


def geeknews_hn_duplicate_preference(item: dict[str, Any]) -> tuple[int, int, str]:
    source = normalize_text(item.get("source"))
    if source == "Hacker News Frontpage (HN RSS)":
        source_rank = 3
    elif source == "GeekNews":
        source_rank = 2
    else:
        source_rank = 0

    time_rank = sort_time_rank(item)
    score_rank = safe_int(item.get("priority_score"), 0)
    return (source_rank, score_rank, time_rank)


def are_geeknews_hn_duplicates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    sources = {normalize_text(left.get("source")), normalize_text(right.get("source"))}
    if sources != {"GeekNews", "Hacker News Frontpage (HN RSS)"}:
        return False

    left_title = duplicate_compare_title(left)
    right_title = duplicate_compare_title(right)
    if not left_title or not right_title:
        return False

    normalized_left = re.sub(r"[^a-z0-9가-힣]+", " ", left_title.lower()).strip()
    normalized_right = re.sub(r"[^a-z0-9가-힣]+", " ", right_title.lower()).strip()
    if normalized_left and normalized_left == normalized_right:
        return True

    left_tokens = title_tokens_for_dedupe(left_title)
    right_tokens = title_tokens_for_dedupe(right_title)
    if len(left_tokens) < 4 or len(right_tokens) < 4:
        return False

    overlap = len(left_tokens & right_tokens)
    min_size = min(len(left_tokens), len(right_tokens))
    return overlap >= 4 and (overlap / max(1, min_size)) >= 0.7


def collapse_geeknews_hn_duplicates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []

    for item in items:
        duplicate_index = next(
            (index for index, existing in enumerate(kept) if are_geeknews_hn_duplicates(item, existing)),
            None,
        )
        if duplicate_index is None:
            kept.append(item)
            continue

        existing = kept[duplicate_index]
        if geeknews_hn_duplicate_preference(item) > geeknews_hn_duplicate_preference(existing):
            kept[duplicate_index] = item

    return kept


def slugify_archive_item(item: dict[str, Any]) -> str:
    item_id = normalize_text(item.get("id"))
    if item_id:
        return item_id

    raw_title = normalize_text(item.get("translated_title") or item.get("title"))
    title_slug = re.sub(r"[^a-z0-9]+", "-", raw_title.lower()).strip("-")[:48]
    raw_date = normalize_text(item.get("sent_at") or item.get("published_at") or item.get("fetched_at"))[:10]
    raw_source = re.sub(r"[^a-z0-9]+", "-", normalize_text(item.get("source")).lower()).strip("-")
    parts = [part for part in [raw_source, title_slug, raw_date] if part]
    if parts:
        return "-".join(parts)

    fallback = json.dumps(item, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(fallback.encode("utf-8")).hexdigest()


def is_english_item(item: dict[str, Any]) -> bool:
    if normalize_text(item.get("source")).lower() == "geeknews":
        return False

    title = normalize_text(item.get("title"))
    summary = strip_html(item.get("summary"))
    combined = normalize_text(" ".join(filter(None, [title, summary])))
    if is_korean_dominant(combined):
        return False
    return is_likely_english(title) or is_likely_english(summary)


def ensure_archive_detail_fields(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    enriched["detail_slug"] = normalize_text(enriched.get("detail_slug")) or slugify_archive_item(enriched)
    enriched["is_english_source"] = is_english_item(enriched)
    if normalize_text(enriched.get("source")) == "Hacker News Frontpage (HN RSS)":
        hn_story_id = extract_hn_story_id(enriched)
        if hn_story_id:
            enriched["hn_story_id"] = hn_story_id
            enriched["hn_discussion_url"] = normalize_text(
                enriched.get("hn_discussion_url")
            ) or build_hn_discussion_url(hn_story_id)
        summary_text = normalize_text(enriched.get("summary"))
        hn_points = normalize_text(enriched.get("hn_points")) or extract_hn_metric(summary_text, HN_POINTS_RE)
        hn_comments_count = normalize_text(enriched.get("hn_comments_count")) or extract_hn_metric(
            summary_text,
            HN_COMMENTS_RE,
        )
        if hn_points:
            enriched["hn_points"] = hn_points
        if hn_comments_count:
            enriched["hn_comments_count"] = hn_comments_count
        if normalize_text(enriched.get("hn_story_type")) == "":
            enriched["hn_story_type"] = "story"
    return enriched


def parse_json_from_text(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s*```$", "", candidate)

    first = candidate.find("{")
    last = candidate.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return {}

    fragment = candidate[first : last + 1]
    try:
        parsed = json.loads(fragment)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return {}
    return {}


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def load_sources(config_path: Path) -> list[Source]:
    if not config_path.exists():
        raise FileNotFoundError(f"Missing config file: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    defaults = config.get("defaults") or {}
    default_limit = safe_int(defaults.get("max_items_per_source"), 20)

    sources: list[Source] = []
    for raw in config.get("sources", []):
        if not isinstance(raw, dict):
            continue

        name = normalize_text(raw.get("name"))
        feed_url = normalize_text(raw.get("feed_url") or raw.get("url"))
        enabled = bool(raw.get("enabled", True))
        max_items = safe_int(raw.get("max_items"), default_limit)
        source_type = normalize_text(raw.get("source_type"), "rss").lower()
        path_prefix = normalize_text(raw.get("path_prefix"))
        priority_boost = safe_int(
            raw.get("priority_boost"),
            default_source_priority_boost(name),
        )

        if not name or not feed_url:
            continue

        sources.append(
            Source(
                name=name,
                feed_url=feed_url,
                enabled=enabled,
                max_items=max(1, max_items),
                priority_boost=priority_boost,
                source_type=source_type if source_type in {"rss", "sitemap", "hn_api"} else "rss",
                path_prefix=path_prefix,
            )
        )

    return sources


def load_taxonomy(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Missing taxonomy file: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    weights_raw = config.get("weights") or {}
    weights = {
        key: safe_int(weights_raw.get(key), default)
        for key, default in DEFAULT_TAXONOMY_WEIGHTS.items()
    }

    slots_raw = config.get("slots") or {}
    slot_order: list[str] = []
    slots: dict[str, dict[str, Any]] = {}
    for slot_name, slot_config in slots_raw.items():
        normalized_name = normalize_text(slot_name).lower()
        if not normalized_name:
            continue
        normalized_slot = normalize_taxonomy_slot(slot_config)
        normalized_slot["label"] = normalized_slot["label"] or normalized_name
        slot_order.append(normalized_name)
        slots[normalized_name] = normalized_slot

    if not slots:
        raise ValueError(f"Taxonomy file has no slots: {config_path}")

    sources_raw = config.get("sources") or {}
    sources: dict[str, dict[str, Any]] = {}
    for source_name, source_config in sources_raw.items():
        normalized_source = normalize_text(source_name)
        if not normalized_source or not isinstance(source_config, dict):
            continue

        slot_boosts_raw = source_config.get("slot_boosts") or {}
        slot_boosts = {
            normalize_text(slot_name).lower(): safe_int(value, 0)
            for slot_name, value in slot_boosts_raw.items()
            if normalize_text(slot_name)
        }

        slot_overlays_raw = source_config.get("slot_overlays") or {}
        slot_overlays: dict[str, dict[str, Any]] = {}
        for slot_name, slot_overlay in slot_overlays_raw.items():
            normalized_slot = normalize_text(slot_name).lower()
            if not normalized_slot:
                continue
            slot_overlays[normalized_slot] = normalize_taxonomy_slot(slot_overlay)

        sources[normalized_source] = {
            "default_slot": normalize_text(source_config.get("default_slot")).lower() or None,
            "slot_boosts": slot_boosts,
            "slot_overlays": slot_overlays,
        }

    return {
        "weights": weights,
        "slot_order": slot_order,
        "slots": slots,
        "sources": sources,
    }


def parse_entry_time(entry: dict[str, Any]) -> str:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            dt = datetime(*parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except (TypeError, ValueError):
            pass

    published = normalize_text(entry.get("published") or entry.get("updated"))
    return published


def parse_published_datetime(raw: str) -> datetime | None:
    published = normalize_text(raw)
    if not published:
        return None

    iso_candidates = [published]
    if published.endswith("Z"):
        iso_candidates.append(f"{published[:-1]}+00:00")

    for candidate in iso_candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue

    try:
        parsed = parsedate_to_datetime(published)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None


def normalize_entry(
    source_name: str,
    entry: dict[str, Any],
    fetched_at: str,
    source_priority_boost: int,
) -> dict[str, str]:
    title = normalize_text(entry.get("title"), "(no title)")
    link = normalize_text(entry.get("link") or entry.get("id"))
    published_at = parse_entry_time(entry)
    summary = strip_html(entry.get("summary") or entry.get("description"))

    identity = normalize_text(entry.get("id")) or link or f"{source_name}|{title}|{published_at}"
    entry_id = sha1_text(identity)
    title_hash = sha1_text(f"{source_name}|{title}")

    return {
        "id": entry_id,
        "title_hash": title_hash,
        "source": source_name,
        "title": title,
        "link": link,
        "published_at": published_at,
        "summary": summary,
        "fetched_at": fetched_at,
        "source_priority_boost": str(source_priority_boost),
    }


def fetch_source(source: Source, fetched_at: str) -> list[dict[str, str]]:
    if source.source_type == "sitemap":
        return fetch_sitemap_source(source, fetched_at)
    if source.source_type == "hn_api":
        return fetch_hn_api_source(source, fetched_at)

    import feedparser

    feed = feedparser.parse(
        source.feed_url,
        request_headers={"User-Agent": USER_AGENT},
    )

    if getattr(feed, "bozo", False) and not feed.entries:
        reason = str(getattr(feed, "bozo_exception", "unknown feed parse error"))
        raise RuntimeError(reason)

    items: list[dict[str, str]] = []
    for entry in feed.entries[: source.max_items]:
        item = normalize_entry(
            source.name,
            entry,
            fetched_at,
            source.priority_boost,
        )
        if not item["link"]:
            continue
        items.append(item)

    return items


def slug_to_title(path: str) -> str:
    slug = path.strip("/").split("/")[-1]
    if not slug:
        return "(no title)"
    return " ".join(part.capitalize() for part in slug.split("-") if part) or "(no title)"


def fetch_sitemap_source(source: Source, fetched_at: str) -> list[dict[str, str]]:
    req = Request(
        source.feed_url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8"},
        method="GET",
    )
    with urlopen(req, timeout=15) as resp:
        xml_text = resp.read().decode("utf-8", errors="replace")

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RuntimeError(f"sitemap parse error: {exc}") from exc

    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    raw_items: list[dict[str, str]] = []
    prefix = source.path_prefix.rstrip("/")

    for node in root.findall("sm:url", namespace):
        loc_node = node.find("sm:loc", namespace)
        if loc_node is None or not loc_node.text:
            continue

        link = normalize_text(loc_node.text)
        path = normalize_text(urlparse(link).path)
        if prefix:
            if not path.startswith(prefix):
                continue
            if path.rstrip("/") == prefix:
                continue

        lastmod_node = node.find("sm:lastmod", namespace)
        published = normalize_text(lastmod_node.text if lastmod_node is not None else "")
        title = slug_to_title(path)

        pseudo_entry = {
            "id": link,
            "title": title,
            "link": link,
            "published": published,
            "summary": "",
        }
        raw_items.append(
            normalize_entry(
                source.name,
                pseudo_entry,
                fetched_at,
                source.priority_boost,
            )
        )

    raw_items.sort(key=lambda item: item.get("published_at", ""), reverse=True)
    return raw_items[: source.max_items]


def build_hn_discussion_url(story_id: int | str) -> str:
    return f"https://news.ycombinator.com/item?id={story_id}"


def parse_hn_story_time(raw: Any) -> str:
    try:
        ts = int(raw)
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def normalize_hn_comment_text(raw: Any) -> str:
    text = strip_html(raw)
    return truncate_text(text, 420)


def fetch_hn_comment_preview(base_url: str, story: dict[str, Any], max_comments: int = 3) -> str:
    comment_ids = story.get("kids")
    if not isinstance(comment_ids, list) or not comment_ids:
        return ""

    previews: list[str] = []
    for comment_id in comment_ids[:12]:
        try:
            payload = fetch_json_url(f"{base_url}/item/{comment_id}.json")
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            continue

        if not isinstance(payload, dict):
            continue
        if payload.get("deleted") or payload.get("dead"):
            continue
        if normalize_text(payload.get("type")).lower() != "comment":
            continue

        comment_text = normalize_hn_comment_text(payload.get("text"))
        if len(comment_text) < 40:
            continue

        author = normalize_text(payload.get("by"))
        if author:
            previews.append(f"{author}: {comment_text}")
        else:
            previews.append(comment_text)

        if len(previews) >= max_comments:
            break

    return "\n".join(previews)


def build_hn_summary(story: dict[str, Any], comment_preview: str) -> str:
    story_text = truncate_text(strip_html(story.get("text")), 1200)
    points = safe_int(story.get("score"), 0)
    comments_count = safe_int(story.get("descendants"), 0)
    story_type = normalize_text(story.get("type"), "story")

    parts: list[str] = [
        f"HN story type: {story_type}",
        f"HN points: {points}",
        f"HN comments: {comments_count}",
    ]

    if story_text:
        parts.append(f"HN post text: {story_text}")
    if comment_preview:
        parts.append(f"HN top comments:\n{comment_preview}")

    return "\n".join(parts)


def normalize_hn_entry(
    source_name: str,
    story: dict[str, Any],
    fetched_at: str,
    source_priority_boost: int,
    base_url: str,
) -> dict[str, str] | None:
    try:
        story_id = int(story.get("id"))
    except (TypeError, ValueError):
        return None

    if story.get("deleted") or story.get("dead"):
        return None

    story_type = normalize_text(story.get("type"), "story").lower()
    if story_type not in {"story", "job", "poll"}:
        return None

    title = normalize_text(story.get("title"), "(no title)")
    if not title:
        return None

    published_at = parse_hn_story_time(story.get("time"))
    outbound_url = normalize_text(story.get("url"))
    link = outbound_url or build_hn_discussion_url(story_id)
    comment_preview = fetch_hn_comment_preview(base_url, story)
    summary = build_hn_summary(story, comment_preview)

    pseudo_entry = {
        "id": str(story_id),
        "title": title,
        "link": link,
        "published": published_at,
        "summary": summary,
    }
    item = normalize_entry(
        source_name,
        pseudo_entry,
        fetched_at,
        source_priority_boost,
    )
    item["hn_story_id"] = str(story_id)
    item["hn_story_type"] = story_type
    item["hn_points"] = str(safe_int(story.get("score"), 0))
    item["hn_comments_count"] = str(safe_int(story.get("descendants"), 0))
    item["hn_discussion_url"] = build_hn_discussion_url(story_id)
    item["hn_item_text"] = truncate_text(strip_html(story.get("text")), 1200)
    item["hn_comment_preview"] = truncate_text(comment_preview, 1200)
    return item


def fetch_hn_api_source(source: Source, fetched_at: str) -> list[dict[str, str]]:
    base_url = source.feed_url.rstrip("/")
    story_ids = fetch_json_url(f"{base_url}/topstories.json")
    if not isinstance(story_ids, list):
        raise RuntimeError("hn api topstories payload is not a list")

    items: list[dict[str, str]] = []
    fetch_limit = max(source.max_items * 3, source.max_items)
    for story_id in story_ids[:fetch_limit]:
        try:
            story = fetch_json_url(f"{base_url}/item/{story_id}.json")
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"hn item fetch failed ({story_id}): {exc}") from exc

        if not isinstance(story, dict):
            continue

        item = normalize_hn_entry(
            source.name,
            story,
            fetched_at,
            source.priority_boost,
            base_url,
        )
        if not item or not item.get("link"):
            continue

        items.append(item)
        if len(items) >= source.max_items:
            break

    return items


def trim_sent_ids(sent_ids: dict[str, int], ttl_days: int, max_ids: int) -> dict[str, int]:
    threshold_ts = int((now_utc() - timedelta(days=ttl_days)).timestamp())

    filtered: dict[str, int] = {}
    for key, value in sent_ids.items():
        ts = safe_int(value, 0)
        if ts >= threshold_ts:
            filtered[key] = ts

    ordered = sorted(filtered.items(), key=lambda kv: kv[1], reverse=True)
    trimmed = ordered[:max_ids]
    return {k: v for k, v in trimmed}


def get_taxonomy_source_config(taxonomy: dict[str, Any], source_name: str) -> dict[str, Any]:
    sources = taxonomy.get("sources", {})
    return sources.get(source_name) or sources.get("default") or {}


def build_source_taxonomy_slots(taxonomy: dict[str, Any], source_name: str) -> dict[str, dict[str, Any]]:
    source_config = get_taxonomy_source_config(taxonomy, source_name)
    slot_overlays = source_config.get("slot_overlays", {})

    slots: dict[str, dict[str, Any]] = {}
    for slot_name, base_slot in taxonomy.get("slots", {}).items():
        overlay_slot = slot_overlays.get(slot_name, {})
        slots[slot_name] = merge_taxonomy_slot(base_slot, overlay_slot)
    return slots


def match_terms_in_text(text: str, terms: list[str]) -> list[str]:
    matched: list[str] = []
    for term in sorted(terms, key=len, reverse=True):
        if term and term in text and not any(term in existing for existing in matched):
            matched.append(term)
    return matched


def match_phrase_rules(text: str, phrase_rules: list[list[str]]) -> list[str]:
    matched: list[str] = []
    for rule in phrase_rules:
        if rule and all(term in text for term in rule):
            matched.append(" + ".join(rule))
    return matched


def match_domain_hints(domain: str, hints: list[str]) -> list[str]:
    return [hint for hint in hints if hint and hint in domain]


def build_item_analysis_text(item: dict[str, Any]) -> tuple[str, str]:
    link = normalize_text(item.get("link", ""))
    parsed = urlparse(link)
    domain = normalize_text(parsed.netloc).lower()
    path = normalize_text(parsed.path).lower()
    text = normalize_text(
        " ".join(
            [
                normalize_text(item.get("title", "")),
                normalize_text(item.get("translated_title", "")),
                normalize_text(item.get("summary", "")),
                normalize_text(item.get("short_summary", "")),
                normalize_text(item.get("hn_item_text", "")),
                normalize_text(item.get("hn_comment_preview", "")),
                normalize_text(item.get("hn_story_type", "")),
                domain,
                path,
            ]
        )
    ).lower()
    return text, domain


def score_slot(
    text: str,
    domain: str,
    slot_name: str,
    slot_config: dict[str, Any],
    source_slot_boost: int,
    weights: dict[str, int],
) -> tuple[int, dict[str, Any]]:
    strong_hits = match_terms_in_text(text, slot_config.get("strong_terms", []))
    support_hits = match_terms_in_text(text, slot_config.get("support_terms", []))
    negative_hits = match_terms_in_text(text, slot_config.get("negative_terms", []))
    phrase_hits = match_phrase_rules(text, slot_config.get("phrase_rules", []))
    domain_hits = match_domain_hints(domain, slot_config.get("domain_hints", []))

    score = (
        len(strong_hits) * weights["strong_term"]
        + len(support_hits) * weights["support_term"]
        + len(negative_hits) * weights["negative_term"]
        + len(phrase_hits) * weights["phrase_rule"]
        + len(domain_hits) * weights["domain_hint"]
        + source_slot_boost
    )

    return score, {
        "slot": slot_name,
        "label": slot_config.get("label", slot_name),
        "score": score,
        "strong_hits": strong_hits,
        "support_hits": support_hits,
        "negative_hits": negative_hits,
        "phrase_hits": phrase_hits,
        "domain_hits": domain_hits,
    }


def pick_primary_slot(
    slot_scores: dict[str, int],
    slot_order: list[str],
    default_slot: str | None,
) -> str:
    if not slot_scores:
        return default_slot or "industry_business"

    ranked = sorted(
        slot_scores.items(),
        key=lambda kv: (
            kv[1],
            -slot_order.index(kv[0]) if kv[0] in slot_order else 0,
        ),
        reverse=True,
    )
    best_slot, best_score = ranked[0]
    if best_score <= 0 and default_slot:
        return default_slot
    return best_slot


def score_and_tag_item_priority(item: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    source = normalize_text(item.get("source", ""))
    source_boost = safe_int(
        item.get("source_priority_boost"),
        default_source_priority_boost(source),
    )
    source_config = get_taxonomy_source_config(taxonomy, source)
    source_slots = build_source_taxonomy_slots(taxonomy, source)
    source_slot_boosts = source_config.get("slot_boosts", {})
    default_slot = source_config.get("default_slot")
    weights = taxonomy.get("weights", DEFAULT_TAXONOMY_WEIGHTS)
    slot_order = taxonomy.get("slot_order", [])

    text, domain = build_item_analysis_text(item)
    slot_scores: dict[str, int] = {}
    slot_matches: dict[str, Any] = {}

    for slot_name, slot_config in source_slots.items():
        score, details = score_slot(
            text=text,
            domain=domain,
            slot_name=slot_name,
            slot_config=slot_config,
            source_slot_boost=safe_int(source_slot_boosts.get(slot_name), 0),
            weights=weights,
        )
        slot_scores[slot_name] = score
        slot_matches[slot_name] = details

    primary_slot = pick_primary_slot(slot_scores, slot_order, default_slot)
    max_slot_score = slot_scores.get(primary_slot, 0)
    final_score = source_boost + max_slot_score
    if max_slot_score <= 0:
        final_score += weights["no_signal_penalty"]

    bucket = SLOT_BUCKETS.get(primary_slot, "general")

    tagged = dict(item)
    tagged["primary_slot"] = primary_slot
    tagged["primary_slot_label"] = source_slots.get(primary_slot, {}).get("label", primary_slot)
    tagged["priority_bucket"] = bucket
    tagged["priority_score"] = str(final_score)
    tagged["priority_signal"] = (
        f"slot={primary_slot},boost={source_boost},slot_score={max_slot_score},"
        + ",".join(f"{slot}={slot_scores.get(slot, 0)}" for slot in slot_order)
    )
    tagged["slot_scores"] = slot_scores
    tagged["slot_matches"] = slot_matches
    tagged["matched_terms"] = unique_preserving_order(
        [
            *slot_matches.get(primary_slot, {}).get("strong_hits", []),
            *slot_matches.get(primary_slot, {}).get("support_hits", []),
            *slot_matches.get(primary_slot, {}).get("phrase_hits", []),
            *slot_matches.get(primary_slot, {}).get("domain_hits", []),
        ]
    )
    return tagged


def priority_sort_key(item: dict[str, str]) -> tuple[int, str]:
    return (
        safe_int(item.get("priority_score"), 0),
        normalize_text(item.get("published_at", "")),
    )


def sort_time_rank(item: dict[str, Any]) -> int:
    raw = normalize_text(item.get("sent_at") or item.get("published_at") or item.get("fetched_at"))
    parsed = parse_published_datetime(raw)
    return int(parsed.timestamp()) if parsed else 0


def select_diverse_items(items: list[dict[str, Any]], target_count: int) -> list[dict[str, Any]]:
    if target_count <= 0:
        return []

    remaining = list(items)
    selected: list[dict[str, Any]] = []
    seen_slots: set[str] = set()

    while remaining and len(selected) < target_count:
        pick_index = 0
        for idx, item in enumerate(remaining):
            slot = normalize_text(item.get("primary_slot"))
            if slot and slot not in seen_slots:
                pick_index = idx
                break

        picked = remaining.pop(pick_index)
        selected.append(picked)
        slot = normalize_text(picked.get("primary_slot"))
        if slot:
            seen_slots.add(slot)

    return selected


def dynamic_geeknews_cap_for_count(selected_count: int, configured_cap: int) -> int:
    if selected_count <= 0:
        return 0
    batch_cap = 2 if selected_count <= 5 else 3
    return min(max(0, configured_cap), batch_cap)


def count_items_by_slot(items: list[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for item in items:
        slot = normalize_text(item.get("primary_slot"), "unknown")
        totals[slot] = totals.get(slot, 0) + 1
    return totals


def enforce_geeknews_batch_cap(
    pool_items: list[dict[str, Any]],
    selected_items: list[dict[str, Any]],
    configured_cap: int,
) -> tuple[list[dict[str, Any]], str | None]:
    if not selected_items:
        return selected_items, None

    effective_cap = dynamic_geeknews_cap_for_count(len(selected_items), configured_cap)
    geeknews_count = sum(1 for item in selected_items if item.get("source") == "GeekNews")
    if geeknews_count <= effective_cap:
        return selected_items, None

    kept_ids: set[str] = set()
    adjusted: list[dict[str, Any]] = []
    kept_geeknews = 0
    for item in selected_items:
        if item.get("source") != "GeekNews":
            adjusted.append(item)
            kept_ids.add(item["id"])
            continue
        if kept_geeknews < effective_cap:
            adjusted.append(item)
            kept_ids.add(item["id"])
            kept_geeknews += 1

    for item in pool_items:
        if len(adjusted) >= len(selected_items):
            break
        if item["id"] in kept_ids:
            continue
        if item.get("source") == "GeekNews" and kept_geeknews >= effective_cap:
            continue
        if item.get("source") == "GeekNews":
            kept_geeknews += 1
        adjusted.append(item)
        kept_ids.add(item["id"])

    order = {item["id"]: idx for idx, item in enumerate(pool_items)}
    adjusted.sort(key=lambda item: order.get(item["id"], 10**9))
    return adjusted[: len(selected_items)], "geeknews_cap"


def prioritize_items(
    items: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    max_items: int,
    technical_quota: int,
    geeknews_cap: int,
) -> list[dict[str, Any]]:
    if max_items <= 0:
        return []

    tagged_items = [score_and_tag_item_priority(item, taxonomy=taxonomy) for item in items]
    geeknews_items = [item for item in tagged_items if item.get("source") == "GeekNews"]
    non_geeknews_items = [item for item in tagged_items if item.get("source") != "GeekNews"]

    geeknews_items.sort(key=priority_sort_key, reverse=True)
    geeknews_cap = min(max_items, max(0, geeknews_cap), 3)
    selected = select_diverse_items(geeknews_items, geeknews_cap)
    selected_ids = {item["id"] for item in selected}

    technical_items = [
        item for item in non_geeknews_items if item.get("priority_bucket") == "technical"
    ]
    general_items = [
        item for item in non_geeknews_items if item.get("priority_bucket") != "technical"
    ]
    technical_items.sort(key=priority_sort_key, reverse=True)
    general_items.sort(key=priority_sort_key, reverse=True)

    remaining_slots = max_items - len(selected)
    tech_take = min(remaining_slots, max(0, technical_quota), len(technical_items))
    selected.extend(select_diverse_items(technical_items, tech_take))
    selected_ids.update(item["id"] for item in selected)

    general_take = min(max_items - len(selected), len(general_items))
    selected.extend(select_diverse_items(general_items, general_take))
    selected_ids.update(item["id"] for item in selected)

    if len(selected) < max_items:
        remaining = [
            item
            for item in (technical_items + general_items + geeknews_items)
            if item["id"] not in selected_ids
        ]
        remaining.sort(key=priority_sort_key, reverse=True)
        selected.extend(select_diverse_items(remaining, max_items - len(selected)))

    return selected[:max_items]


def build_discord_item_block(
    item: dict[str, str],
    *,
    include_summary: bool = True,
    compact_summary: bool = False,
) -> str:
    title = truncate_text(normalize_text(item.get("translated_title") or item.get("title")), 220)
    lines: list[str] = [f"[{item['source']}]", f"**{title}**"]

    if item.get("translated_title") and item["translated_title"] != item["title"]:
        lines.append(f"원제: **{truncate_text(item['title'], 220)}**")

    summary_text = normalize_text(item.get("short_summary"))
    if not summary_text and item.get("source") == "GeekNews":
        summary_text = to_multiline_preview(item.get("summary", ""))

    if include_summary and summary_text:
        lines.append("**요약**")
        if compact_summary:
            lines.append(truncate_text(summary_text.replace("\n", " "), 120))
        elif "\n" in summary_text:
            lines.append(summary_text)
        else:
            lines.append(truncate_text(summary_text, 260))

    lines.append("")
    lines.append(item["link"])
    return "\n".join(lines)


def build_discord_title_preview(
    items: list[dict[str, str]],
    *,
    max_items: int = DISCORD_PREVIEW_ITEMS_LIMIT,
    title_limit: int = DISCORD_PREVIEW_TITLE_LIMIT,
) -> list[str]:
    preview_lines: list[str] = []
    for item in items[: max(0, max_items)]:
        title = normalize_text(item.get("translated_title") or item.get("title"), "(제목 없음)")
        preview_lines.append(f"- {truncate_text(title, title_limit)}")
    return preview_lines


def build_discord_batch_content(
    items: list[dict[str, str]],
    mention: str,
    max_chars: int = 1900,
    modes: tuple[str, ...] = ("full_summary", "compact_summary", "titles_only"),
    allow_truncate_fallback: bool = True,
) -> BatchContentResult:
    if not items:
        return BatchContentResult(content=mention if mention else "", mode="empty", truncated=False)

    def compose(include_summary: bool, compact_summary: bool) -> str:
        header = f"이번 배치 뉴스 {len(items)}건"
        lines: list[str] = []
        if mention:
            lines.append(mention)
        lines.append(header)
        lines.extend(build_discord_title_preview(items))
        for idx, item in enumerate(items, start=1):
            block = build_discord_item_block(
                item,
                include_summary=include_summary,
                compact_summary=compact_summary,
            )
            lines.append("")
            lines.append(f"{idx}. {block}")
        return "\n".join(lines)

    mode_options = {
        "full_summary": (True, False),
        "compact_summary": (True, True),
        "titles_only": (False, False),
    }

    last_mode = modes[-1]
    last_content = ""

    for mode in modes:
        include_summary, compact_summary = mode_options[mode]
        content = compose(include_summary=include_summary, compact_summary=compact_summary)
        last_content = content
        if len(content) <= max_chars:
            return BatchContentResult(content=content, mode=mode, truncated=False)

    if not allow_truncate_fallback:
        return BatchContentResult(content=last_content, mode=f"{last_mode}_overflow", truncated=True)

    return BatchContentResult(
        content=truncate_text(last_content, max_chars),
        mode=f"{last_mode}_truncated",
        truncated=True,
    )


def select_discord_batch(
    items: list[dict[str, str]],
    mention: str,
    min_items: int,
    max_items: int,
    max_chars: int = 1900,
) -> BatchSelection:
    if not items:
        return BatchSelection(
            content=mention if mention else "",
            items=[],
            mode="empty",
            truncated=False,
            selection_reason=None,
        )

    upper_bound = min(len(items), max_items)
    lower_bound = min(upper_bound, min_items)
    fallback: BatchSelection | None = None

    for count in range(upper_bound, lower_bound - 1, -1):
        selected_items = items[:count]
        batch = build_discord_batch_content(
            selected_items,
            mention=mention,
            max_chars=max_chars,
            modes=("full_summary",) if count > lower_bound else ("full_summary", "compact_summary", "titles_only"),
            allow_truncate_fallback=count == lower_bound,
        )

        if batch.truncated and count > lower_bound:
            continue

        reason: str | None = None
        if count < upper_bound:
            reason = "message_too_long"
        if batch.truncated:
            reason = "message_too_long_min_floor"

        selection = BatchSelection(
            content=batch.content,
            items=selected_items,
            mode=batch.mode,
            truncated=batch.truncated,
            selection_reason=reason,
        )

        if not batch.truncated:
            return selection
        fallback = selection

    if fallback is not None:
        return fallback

    batch = build_discord_batch_content(items[:upper_bound], mention=mention, max_chars=max_chars)
    return BatchSelection(
        content=batch.content,
        items=items[:upper_bound],
        mode=batch.mode,
        truncated=batch.truncated,
        selection_reason="message_too_long_min_floor" if batch.truncated else None,
    )


def enrich_item_with_codex_cli(
    item: dict[str, str],
    model: str,
    timeout_sec: int,
    sandbox: str,
    extra_args: str,
    retries: int,
) -> tuple[dict[str, str], str | None]:
    item = ensure_archive_detail_fields(item)
    if not item.get("is_english_source"):
        return item, None
    codex_bin = shutil.which("codex")
    if not codex_bin:
        return item, None

    source_name = normalize_text(item.get("source"))
    is_hn_item = source_name == "Hacker News Frontpage (HN RSS)"
    snippet_limit = 2200 if is_hn_item else 800
    snippet_parts = [normalize_text(item.get("summary", ""))]
    if is_hn_item:
        hn_meta_parts: list[str] = []
        if normalize_text(item.get("hn_story_type")):
            hn_meta_parts.append(f"HN type: {normalize_text(item.get('hn_story_type'))}")
        if normalize_text(item.get("hn_points")):
            hn_meta_parts.append(f"HN points: {normalize_text(item.get('hn_points'))}")
        if normalize_text(item.get("hn_comments_count")):
            hn_meta_parts.append(f"HN comments: {normalize_text(item.get('hn_comments_count'))}")
        if hn_meta_parts:
            snippet_parts.append(" / ".join(hn_meta_parts))
        if normalize_text(item.get("hn_item_text")):
            snippet_parts.append(f"HN post text: {normalize_text(item.get('hn_item_text'))}")
        if normalize_text(item.get("hn_comment_preview")):
            snippet_parts.append(f"HN comments preview: {normalize_text(item.get('hn_comment_preview'))}")
    snippet = truncate_text("\n".join(part for part in snippet_parts if part), snippet_limit)
    source_note = ""
    if is_hn_item:
        source_note = (
            "- 이 항목은 Hacker News 프론트페이지 스토리다.\n"
            "- 외부 원문 전체가 아니라 HN 스토리 메타데이터, 본문, 댓글 맥락을 기준으로 정리해도 된다.\n"
            "- 댓글에서 드러난 쟁점이나 반론이 있으면 요약에 반영해라.\n"
        )
    extra_schema = ""
    extra_instruction = ""
    if is_hn_item:
        extra_schema = ', "hn_reaction_summary":""'
        extra_instruction = (
            "- hn_reaction_summary: HN 댓글/반응 카드용 짧은 한국어 브리핑. 1개 도입 문단 + '- ' bullet 2~3개\n"
            "- 댓글 분위기, 반복된 찬반 포인트, 실무자가 읽을 만한 논점을 중심으로 정리\n\n"
        )

    user_prompt = (
        "아래 IT 뉴스 정보를 한국어로 정리해줘.\n"
        "반드시 JSON만 출력해.\n"
        f'스키마: {{"translated_title":"", "short_summary":"", "why_it_matters":""{extra_schema}}}\n'
        "- translated_title: 자연스러운 한국어 제목(40자 내외)\n"
        "- short_summary: 1~2문장 요약(총 120자 내외)\n\n"
        "- why_it_matters: 상세 페이지 카드용 짧은 한국어 브리핑. 1개 도입 문단 + '- ' bullet 2~3개\n"
        "- 왜 지금 봐야 하는지, 실무적으로 어떤 변화가 생기는지를 중심으로 정리\n\n"
        f"{extra_instruction}"
        f"{HUMANIZER_PROMPT_GUIDANCE}\n\n"
        f"{source_note}"
        f"Title: {item.get('title', '')}\n"
        f"Source: {source_name}\n"
        f"Snippet: {snippet}\n"
    )
    last_error: str | None = None

    base_command = [
        codex_bin,
        "exec",
        "--full-auto",
        "--sandbox",
        sandbox or "read-only",
        "-C",
        str(ROOT),
    ]
    if model:
        base_command.extend(["--model", model])

    for attempt in range(retries):
        with tempfile.TemporaryDirectory(prefix="codex-summary-") as tmp_dir:
            last_message_path = Path(tmp_dir) / "last-message.md"
            command = [*base_command, "--output-last-message", str(last_message_path)]
            if extra_args:
                command.extend(shlex.split(extra_args))
            command.append("-")

            try:
                result = subprocess.run(
                    command,
                    input=user_prompt,
                    text=True,
                    capture_output=True,
                    timeout=timeout_sec,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
                last_error = str(exc)
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                continue

            if result.returncode != 0:
                stderr = normalize_text(result.stderr)
                stdout = normalize_text(result.stdout)
                last_error = stderr or stdout or f"codex exec exited with status {result.returncode}"
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                continue

            try:
                content = last_message_path.read_text(encoding="utf-8")
            except OSError as exc:
                last_error = f"failed to read codex output: {exc}"
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                continue

            parsed = parse_json_from_text(content)
            translated_title = normalize_text(parsed.get("translated_title"))
            short_summary = normalize_text(parsed.get("short_summary"))
            why_it_matters = normalize_briefing_markdown(parsed.get("why_it_matters"))
            hn_reaction_summary = normalize_briefing_markdown(parsed.get("hn_reaction_summary"))

            if translated_title:
                item["translated_title"] = translated_title
            if short_summary:
                item["short_summary"] = short_summary
            if why_it_matters:
                item["why_it_matters"] = why_it_matters
            if is_hn_item and hn_reaction_summary:
                item["hn_reaction_summary"] = hn_reaction_summary
            if translated_title or short_summary or why_it_matters or hn_reaction_summary:
                item["ai_model"] = normalize_text(model) or "codex-cli"
                return item, None
            last_error = "codex response did not include translated_title, short_summary, why_it_matters, or hn_reaction_summary"

    return item, last_error


def topic_digest_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    raw = normalize_text(item.get("sent_at") or item.get("published_at") or item.get("fetched_at"))
    parsed = parse_published_datetime(raw)
    return (int(parsed.timestamp()) if parsed else 0, raw)


def build_topic_digest_prompt(period_label: str, slot_label: str, items: list[dict[str, Any]]) -> str:
    item_lines: list[str] = []
    for index, item in enumerate(items[:TOPIC_DIGEST_MAX_ITEMS_PER_DIGEST], start=1):
        title = normalize_text(item.get("translated_title") or item.get("title"), "(제목 없음)")
        source = normalize_text(item.get("source"), "Unknown")
        summary = normalize_text(item.get("short_summary")) or normalize_text(to_multiline_preview(item.get("summary", "")))
        summary = truncate_text(summary.replace("\n", " "), 180) if summary else ""
        line_parts = [f"{index}. {title}", f"Source: {source}"]
        if summary:
            line_parts.append(f"Summary: {summary}")
        item_lines.append("\n".join(line_parts))

    items_block = "\n\n".join(item_lines)
    return (
        f"아래 {period_label} {slot_label} 기사 묶음을 한국어로 정리해줘.\n"
        "반드시 JSON만 출력해.\n"
        '스키마: {"headline":"", "summary":""}\n'
        f'- headline: "{period_label} {slot_label}" 형태의 짧은 제목\n'
        "- summary: Markdown 허용. 짧은 도입 문단 1개 + '- ' bullet 2~3개, 총 240자 내외\n"
        "- 이 주제 묶음에서 반복된 흐름과 지금 볼 이유를 중심으로 정리\n\n"
        f"{HUMANIZER_PROMPT_GUIDANCE}\n\n"
        f"Period: {period_label}\n"
        f"Slot: {slot_label}\n\n"
        f"Items:\n{items_block}\n"
    )


def generate_topic_digest_with_codex(
    items: list[dict[str, Any]],
    *,
    period_label: str,
    slot_label: str,
    model: str,
    timeout_sec: int,
    sandbox: str,
    extra_args: str,
    retries: int,
) -> dict[str, str] | None:
    if not items:
        return None

    codex_bin = shutil.which("codex")
    if not codex_bin:
        return None

    user_prompt = build_topic_digest_prompt(period_label, slot_label, items)
    last_error: str | None = None
    base_command = [
        codex_bin,
        "exec",
        "--full-auto",
        "--sandbox",
        sandbox or "read-only",
        "-C",
        str(ROOT),
    ]
    if model:
        base_command.extend(["--model", model])

    for attempt in range(retries):
        with tempfile.TemporaryDirectory(prefix="codex-topic-digest-") as tmp_dir:
            last_message_path = Path(tmp_dir) / "last-message.md"
            command = [*base_command, "--output-last-message", str(last_message_path)]
            if extra_args:
                command.extend(shlex.split(extra_args))
            command.append("-")

            try:
                result = subprocess.run(
                    command,
                    input=user_prompt,
                    text=True,
                    capture_output=True,
                    timeout=timeout_sec,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
                last_error = str(exc)
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                continue

            if result.returncode != 0:
                stderr = normalize_text(result.stderr)
                stdout = normalize_text(result.stdout)
                last_error = stderr or stdout or f"codex exec exited with status {result.returncode}"
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                continue

            try:
                content = last_message_path.read_text(encoding="utf-8")
            except OSError as exc:
                last_error = f"failed to read codex output: {exc}"
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                continue

            parsed = parse_json_from_text(content)
            headline = normalize_text(parsed.get("headline"), f"{period_label} {slot_label}")
            summary = normalize_briefing_markdown(parsed.get("summary"))
            if summary:
                return {
                    "headline": headline,
                    "summary": summary,
                    "ai_model": normalize_text(model) or "codex-cli",
                }
            last_error = "codex response did not include topic digest summary"

    return None


def generate_topic_digests(
    items: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    model: str,
    timeout_sec: int,
    sandbox: str,
    extra_args: str,
    retries: int,
    *,
    now_iso: str = "",
) -> dict[str, list[dict[str, Any]]]:
    slot_order = taxonomy.get("slot_order", [])
    slot_labels = {
        slot_name: normalize_text(taxonomy.get("slots", {}).get(slot_name, {}).get("label"), slot_name)
        for slot_name in slot_order
    }
    now_dt = parse_published_datetime(now_iso) or now_utc()
    tagged_items = [score_and_tag_item_priority(ensure_archive_detail_fields(dict(item)), taxonomy=taxonomy) for item in items]
    tagged_items.sort(key=topic_digest_sort_key, reverse=True)

    payload: dict[str, list[dict[str, Any]]] = {"weekly": [], "monthly": []}

    for period_key, period_label, window_days in TOPIC_DIGEST_WINDOWS:
        cutoff_dt = now_dt - timedelta(days=window_days)
        grouped_items: dict[str, list[dict[str, Any]]] = {}

        for item in tagged_items:
            slot_name = normalize_text(item.get("primary_slot")).lower()
            if not slot_name:
                continue
            item_dt = parse_published_datetime(item.get("sent_at") or item.get("published_at") or item.get("fetched_at"))
            if not item_dt or item_dt < cutoff_dt:
                continue
            grouped_items.setdefault(slot_name, []).append(item)

        ordered_slots = sorted(
            grouped_items,
            key=lambda slot_name: (
                -len(grouped_items[slot_name]),
                slot_order.index(slot_name) if slot_name in slot_order else len(slot_order),
                slot_name,
            ),
        )

        for slot_name in ordered_slots[:TOPIC_DIGEST_MAX_SLOTS_PER_PERIOD]:
            slot_items = grouped_items[slot_name]
            if len(slot_items) < TOPIC_DIGEST_MIN_ITEMS:
                continue

            slot_label = normalize_text(slot_labels.get(slot_name), slot_name)
            digest = generate_topic_digest_with_codex(
                slot_items[:TOPIC_DIGEST_MAX_ITEMS_PER_DIGEST],
                period_label=period_label,
                slot_label=slot_label,
                model=model,
                timeout_sec=timeout_sec,
                sandbox=sandbox,
                extra_args=extra_args,
                retries=retries,
            )
            if not digest:
                continue

            payload[period_key].append(
                {
                    "period": period_key,
                    "slot": slot_name,
                    "slot_label": slot_label,
                    "headline": normalize_text(digest.get("headline"), f"{period_label} {slot_label}"),
                    "summary": normalize_briefing_markdown(digest.get("summary")),
                    "item_ids": [normalize_text(item.get("id")) for item in slot_items if normalize_text(item.get("id"))],
                    "total_items": len(slot_items),
                    "generated_at": now_dt.isoformat(),
                    "ai_model": normalize_text(digest.get("ai_model"), normalize_text(model) or "codex-cli"),
                }
            )

    return payload


def post_discord(
    webhook_url: str,
    content: str,
    timeout_sec: int,
    retries: int,
    user_agent: str,
) -> tuple[bool, str | None]:
    payload = json.dumps({"content": content}).encode("utf-8")
    error_msg: str | None = None

    for attempt in range(retries):
        req = Request(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": user_agent,
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=timeout_sec) as resp:
                code = resp.getcode()
                if code in (200, 204):
                    return True, None
                error_msg = f"unexpected status code: {code}"
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:  # noqa: BLE001
                body = ""

            if body:
                error_msg = f"HTTP Error {exc.code}: {body}"
            else:
                error_msg = str(exc)
        except (URLError, TimeoutError) as exc:
            error_msg = str(exc)

        if attempt < retries - 1:
            time.sleep(2**attempt)

    return False, error_msg


def merge_news(existing: list[dict[str, Any]], new_sent: list[dict[str, str]], max_items: int) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in existing:
        item_id = normalize_text(item.get("id"))
        if item_id:
            by_id[item_id] = item

    for item in new_sent:
        by_id[item["id"]] = dict(item)

    merged = list(by_id.values())
    merged = collapse_geeknews_hn_duplicates(merged)

    def sort_key(item: dict[str, Any]) -> str:
        return normalize_text(item.get("sent_at") or item.get("published_at") or item.get("fetched_at"))

    merged.sort(key=sort_key, reverse=True)
    return merged[:max_items]


def main() -> int:
    run_started = now_utc()
    fetched_at = run_started.isoformat()
    now_ts = int(run_started.timestamp())

    dry_run = os.getenv("DRY_RUN", "0") == "1"
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

    timeout_sec = safe_int(os.getenv("REQUEST_TIMEOUT_SEC"), 15)
    retries = max(1, safe_int(os.getenv("DISCORD_RETRY"), 3))
    send_delay_sec = float(os.getenv("SEND_DELAY_SEC", "0.6"))
    batch_max_chars = max(500, safe_int(os.getenv("DISCORD_BATCH_MAX_CHARS"), 1900))

    ttl_days = max(1, safe_int(os.getenv("STATE_TTL_DAYS"), 14))
    max_state_ids = max(100, safe_int(os.getenv("MAX_STATE_IDS"), 3000))
    max_news_items = max(100, safe_int(os.getenv("MAX_NEWS_ITEMS"), 2000))
    try:
        min_new_items_per_run = read_bounded_int_env(
            "MIN_NEW_ITEMS_PER_RUN",
            5,
            minimum=1,
            maximum=15,
        )
        max_new_items_per_run = read_bounded_int_env(
            "MAX_NEW_ITEMS_PER_RUN",
            7,
            minimum=1,
            maximum=15,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if min_new_items_per_run > max_new_items_per_run:
        print("ERROR: MIN_NEW_ITEMS_PER_RUN must be less than or equal to MAX_NEW_ITEMS_PER_RUN", file=sys.stderr)
        return 2
    max_item_age_days = max(1, safe_int(os.getenv("MAX_ITEM_AGE_DAYS"), 3))
    technical_priority_quota = max(0, safe_int(os.getenv("TECH_PRIORITY_QUOTA"), 3))
    geeknews_max_per_run = max(0, safe_int(os.getenv("GEEKNEWS_MAX_PER_RUN"), 3))
    technical_priority_quota = min(technical_priority_quota, max_new_items_per_run)
    geeknews_max_per_run = min(geeknews_max_per_run, max_new_items_per_run)

    mention = os.getenv("DISCORD_MENTION", "").strip()
    codex_summary_model = os.getenv("CODEX_SUMMARY_MODEL", "").strip()
    codex_summary_timeout_sec = max(15, safe_int(os.getenv("CODEX_SUMMARY_TIMEOUT_SEC"), 120))
    codex_summary_sandbox = normalize_text(os.getenv("CODEX_SUMMARY_SANDBOX", "read-only"), "read-only")
    codex_summary_extra_args = os.getenv("CODEX_SUMMARY_EXTRA_ARGS", "").strip()
    dispatch_origin = normalize_text(os.getenv("NEWSLETTER_DISPATCH_ORIGIN"), "unknown")
    discord_user_agent = os.getenv(
        "DISCORD_USER_AGENT",
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        ),
    ).strip()

    if not dry_run and not webhook_url:
        print("ERROR: DISCORD_WEBHOOK_URL is required unless DRY_RUN=1", file=sys.stderr)
        return 2

    sources = load_sources(CONFIG_PATH)
    try:
        taxonomy = load_taxonomy(TAXONOMY_PATH)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    enabled_sources = [s for s in sources if s.enabled]

    state_raw = load_json(STATE_PATH, {"sent_ids": {}})
    sent_ids_raw = state_raw.get("sent_ids", {}) if isinstance(state_raw, dict) else {}
    sent_ids: dict[str, int] = sent_ids_raw if isinstance(sent_ids_raw, dict) else {}
    sent_ids = trim_sent_ids(sent_ids, ttl_days=ttl_days, max_ids=max_state_ids)

    source_failures: list[dict[str, str]] = []
    candidates: list[dict[str, str]] = []

    for source in enabled_sources:
        try:
            entries = fetch_source(source, fetched_at=fetched_at)
            candidates.extend(entries)
        except Exception as exc:  # noqa: BLE001
            source_failures.append({"source": source.name, "error": str(exc)})

    cutoff_dt = run_started - timedelta(days=max_item_age_days)
    aged_out_total = 0
    fresh_candidates: list[dict[str, str]] = []
    for item in candidates:
        published_dt = parse_published_datetime(item.get("published_at", ""))
        if published_dt and published_dt < cutoff_dt:
            aged_out_total += 1
            continue
        fresh_candidates.append(item)
    candidates = fresh_candidates

    candidates.sort(key=lambda item: item.get("published_at", ""), reverse=True)

    seen_links: set[str] = set()
    seen_title_hashes: set[str] = set()
    deduped_items: list[dict[str, str]] = []

    for item in candidates:
        item_id = item["id"]
        link = item.get("link", "")
        title_hash = item["title_hash"]

        if item_id in sent_ids:
            continue
        if link and link in seen_links:
            continue
        if title_hash in seen_title_hashes:
            continue

        if link:
            seen_links.add(link)
        seen_title_hashes.add(title_hash)
        deduped_items.append(item)

    new_items = prioritize_items(
        deduped_items,
        taxonomy=taxonomy,
        max_items=max_new_items_per_run,
        technical_quota=technical_priority_quota,
        geeknews_cap=geeknews_max_per_run,
    )

    sent_items: list[dict[str, str]] = []
    enriched_items: list[dict[str, str]] = []
    send_failures: list[dict[str, str]] = []
    briefing_failures: list[dict[str, str]] = []
    briefing_enriched_total = 0
    discord_messages_sent = 0
    prioritized_geeknews_total = sum(1 for item in new_items if item.get("source") == "GeekNews")
    prioritized_technical_total = sum(1 for item in new_items if item.get("priority_bucket") == "technical")
    prioritized_general_total = sum(1 for item in new_items if item.get("priority_bucket") != "technical")
    prioritized_slot_totals = count_items_by_slot(new_items)

    for item in new_items:
        enriched_item, briefing_err = enrich_item_with_codex_cli(
            item=dict(item),
            model=codex_summary_model,
            timeout_sec=codex_summary_timeout_sec,
            sandbox=codex_summary_sandbox,
            extra_args=codex_summary_extra_args,
            retries=retries,
        )
        if briefing_err:
            briefing_failures.append(
                {
                    "source": item["source"],
                    "title": item["title"],
                    "error": briefing_err,
                }
            )
        if enriched_item.get("translated_title") or enriched_item.get("short_summary"):
            briefing_enriched_total += 1

        enriched_items.append(enriched_item)

    enriched_items = collapse_geeknews_hn_duplicates(enriched_items)

    batch_selection = select_discord_batch(
        enriched_items,
        mention=mention,
        min_items=min_new_items_per_run,
        max_items=max_new_items_per_run,
        max_chars=batch_max_chars,
    )
    batch_items, geeknews_batch_reason = enforce_geeknews_batch_cap(
        pool_items=enriched_items,
        selected_items=batch_selection.items,
        configured_cap=geeknews_max_per_run,
    )
    if geeknews_batch_reason:
        combined_reason = batch_selection.selection_reason
        if combined_reason:
            combined_reason = f"{combined_reason}+{geeknews_batch_reason}"
        else:
            combined_reason = geeknews_batch_reason
        rebuilt_batch = build_discord_batch_content(
            batch_items,
            mention=mention,
            max_chars=batch_max_chars,
            modes=("full_summary", "compact_summary", "titles_only"),
            allow_truncate_fallback=True,
        )
        batch_selection = BatchSelection(
            content=rebuilt_batch.content,
            items=batch_items,
            mode=rebuilt_batch.mode,
            truncated=rebuilt_batch.truncated,
            selection_reason=combined_reason,
        )
    selected_geeknews_total = sum(1 for item in batch_items if item.get("source") == "GeekNews")
    selected_technical_total = sum(1 for item in batch_items if item.get("priority_bucket") == "technical")
    selected_general_total = sum(1 for item in batch_items if item.get("priority_bucket") != "technical")
    selected_slot_totals = count_items_by_slot(batch_items)

    if dry_run:
        for enriched_item in batch_items:
            enriched_item["sent_at"] = fetched_at
            sent_items.append(enriched_item)
    elif batch_items:
        ok, err = post_discord(
            webhook_url=webhook_url,
            content=batch_selection.content,
            timeout_sec=timeout_sec,
            retries=retries,
            user_agent=discord_user_agent,
        )

        if ok:
            sent_at = now_utc().isoformat()
            discord_messages_sent = 1
            for enriched_item in batch_items:
                enriched_item["sent_at"] = sent_at
                sent_items.append(enriched_item)
                sent_ids[enriched_item["id"]] = now_ts
            # Persist immediately to prevent duplicate sends on cancellation/re-run.
            sent_ids = trim_sent_ids(sent_ids, ttl_days=ttl_days, max_ids=max_state_ids)
            write_json(STATE_PATH, {"sent_ids": sent_ids})
        else:
            for enriched_item in batch_items:
                send_failures.append(
                    {
                        "source": enriched_item["source"],
                        "title": enriched_item["title"],
                        "error": err or "unknown error",
                    }
                )
        time.sleep(send_delay_sec)

    if not dry_run:
        sent_ids = trim_sent_ids(sent_ids, ttl_days=ttl_days, max_ids=max_state_ids)
        write_json(STATE_PATH, {"sent_ids": sent_ids})

        news_raw = load_json(NEWS_PATH, {"items": []})
        existing_news = news_raw.get("items", []) if isinstance(news_raw, dict) else []
        existing_topic_digests = news_raw.get("topic_digests", {}) if isinstance(news_raw, dict) else {}
        if not isinstance(existing_news, list):
            existing_news = []
        if not isinstance(existing_topic_digests, dict):
            existing_topic_digests = {}

        merged_news = merge_news(existing=existing_news, new_sent=sent_items, max_items=max_news_items)
        topic_digests = generate_topic_digests(
            items=merged_news,
            taxonomy=taxonomy,
            model=codex_summary_model,
            timeout_sec=codex_summary_timeout_sec,
            sandbox=codex_summary_sandbox,
            extra_args=codex_summary_extra_args,
            retries=retries,
            now_iso=fetched_at,
        )
        if not any(topic_digests.get(period) for period in ("weekly", "monthly")) and existing_topic_digests:
            topic_digests = existing_topic_digests
        write_json(NEWS_PATH, {"items": merged_news, "topic_digests": topic_digests})

    summary = {
        "executed_at": fetched_at,
        "dispatch_origin": dispatch_origin,
        "dry_run": dry_run,
        "sources_total": len(sources),
        "sources_enabled": len(enabled_sources),
        "source_failures": source_failures,
        "candidates_total": len(candidates),
        "max_item_age_days": max_item_age_days,
        "aged_out_total": aged_out_total,
        "deduped_total": len(deduped_items),
        "min_new_items_per_run": min_new_items_per_run,
        "max_new_items_per_run": max_new_items_per_run,
        "priority_technical_quota": technical_priority_quota,
        "geeknews_max_per_run": geeknews_max_per_run,
        "taxonomy_slots": taxonomy.get("slot_order", []),
        "prioritized_geeknews_total": prioritized_geeknews_total,
        "prioritized_technical_total": prioritized_technical_total,
        "prioritized_general_total": prioritized_general_total,
        "prioritized_slot_totals": prioritized_slot_totals,
        "selected_geeknews_total": selected_geeknews_total,
        "selected_technical_total": selected_technical_total,
        "selected_general_total": selected_general_total,
        "selected_slot_totals": selected_slot_totals,
        "new_items_total": len(new_items),
        "batch_selected_total": len(batch_items),
        "batch_trimmed_total": max(0, len(new_items) - len(batch_items)),
        "batch_selection_reason": batch_selection.selection_reason,
        "batch_content_mode": batch_selection.mode,
        "batch_content_truncated": batch_selection.truncated,
        "sent_total": len(sent_items),
        "discord_messages_sent": discord_messages_sent,
        "discord_batch_max_chars": batch_max_chars,
        "send_failures": send_failures,
        "briefing_enriched_total": briefing_enriched_total,
        "briefing_failures": briefing_failures,
        "topic_digest_total": (
            sum(len(topic_digests.get(period, [])) for period in ("weekly", "monthly")) if not dry_run else 0
        ),
    }
    write_json(LAST_RUN_PATH, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if enabled_sources and len(source_failures) == len(enabled_sources):
        return 1

    if new_items and not sent_items and send_failures and not dry_run:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
