#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
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

import feedparser
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
STATE_PATH = ROOT / "data" / "state.json"
NEWS_PATH = ROOT / "data" / "news.json"
LAST_RUN_PATH = ROOT / "data" / "last_run.json"

USER_AGENT = "ITNewsLetterBot/1.0 (+https://github.com/)"

DEFAULT_SOURCE_PRIORITY_BOOST: dict[str, int] = {
    "GeekNews": 45,
    "iOS Dev Weekly": 24,
    "Swift Weekly Brief": 22,
    "Hacker News Frontpage (HN RSS)": 18,
    "TLDR Tech": 10,
    "TechCrunch": 6,
}

TECHNICAL_KEYWORDS = [
    "github",
    "repo",
    "open source",
    "opensource",
    "오픈소스",
    "개발기",
    "사용기",
    "실전",
    "how to",
    "tutorial",
    "guide",
    "pattern",
    "architecture",
    "sdk",
    "cli",
    "library",
    "framework",
    "api",
    "implementation",
    "show hn",
    "build",
    "built",
    "swift",
    "ios",
    "web",
    "oss",
    "ai agent",
    "ai agents",
    "agentic",
    "agent",
    "multi-agent",
    "autonomous agent",
    "mcp",
    "model context protocol",
    "llm",
    "vlm",
    "rag",
    "retrieval-augmented generation",
    "prompt engineering",
    "prompt",
    "tool calling",
    "function calling",
    "tool use",
    "context window",
    "vector db",
    "vector database",
    "embedding",
    "fine-tuning",
    "finetuning",
    "reasoning model",
    "inference",
    "copilot",
    "cursor",
    "claude code",
    "codex",
    "vibe coding",
    "에이전트",
    "ai 에이전트",
    "에이전틱",
    "멀티 에이전트",
    "멀티에이전트",
    "프롬프트 엔지니어링",
    "프롬프트",
    "툴 콜링",
    "함수 호출",
    "임베딩",
    "벡터 db",
    "벡터 데이터베이스",
    "파인튜닝",
    "추론",
    "에이전트 활용",
    "에이전트 워크플로우",
    "에이전트 자동화",
]

GENERAL_NEWS_KEYWORDS = [
    "acquire",
    "acquisition",
    "merger",
    "funding",
    "ipo",
    "earnings",
    "settles",
    "lawsuit",
    "regulation",
    "antitrust",
    "deal",
    "announces",
    "reported",
    "reports",
    "인수",
    "투자",
    "실적",
    "소송",
    "규제",
    "주가",
    "합병",
    "파트너십",
    "협약",
]


@dataclass
class Source:
    name: str
    feed_url: str
    enabled: bool
    max_items: int
    priority_boost: int
    source_type: str
    path_prefix: str


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def default_source_priority_boost(source_name: str) -> int:
    return DEFAULT_SOURCE_PRIORITY_BOOST.get(source_name, 0)


def count_keyword_hits(text: str, keywords: list[str]) -> int:
    total = 0
    for keyword in keywords:
        if keyword and keyword in text:
            total += 1
    return total


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


def truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def strip_html(raw: Any, fallback: str = "") -> str:
    text = html.unescape(str(raw or fallback))
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize_text(text)


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


def build_model_candidates(primary: str, fallback_csv: str) -> list[str]:
    models: list[str] = []
    for token in [primary, *fallback_csv.split(",")]:
        model = normalize_text(token)
        if model and model not in models:
            models.append(model)
    return models


def is_openai_model_access_error(body_text: str) -> bool:
    lowered = body_text.lower()
    if "model_not_found" in lowered or "does not have access to model" in lowered:
        return True

    try:
        payload = json.loads(body_text)
        err = payload.get("error", {}) if isinstance(payload, dict) else {}
        code = str(err.get("code", "")).lower()
        msg = str(err.get("message", "")).lower()
        if code == "model_not_found":
            return True
        if "does not have access to model" in msg:
            return True
    except json.JSONDecodeError:
        return False
    return False


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
                source_type=source_type if source_type in {"rss", "sitemap"} else "rss",
                path_prefix=path_prefix,
            )
        )

    return sources


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


def score_and_tag_item_priority(item: dict[str, str]) -> dict[str, str]:
    source = item.get("source", "")
    source_boost = safe_int(
        item.get("source_priority_boost"),
        default_source_priority_boost(source),
    )

    text = normalize_text(f"{item.get('title', '')} {item.get('summary', '')}").lower()
    tech_hits = count_keyword_hits(text, TECHNICAL_KEYWORDS)
    news_hits = count_keyword_hits(text, GENERAL_NEWS_KEYWORDS)

    if tech_hits > news_hits:
        bucket = "technical"
    elif news_hits > tech_hits:
        bucket = "general"
    else:
        bucket = "technical" if source_boost >= 20 else "general"

    score = source_boost + (tech_hits * 9) - (news_hits * 8)
    if bucket == "technical":
        score += 10
    else:
        score -= 4

    tagged = dict(item)
    tagged["priority_bucket"] = bucket
    tagged["priority_score"] = str(score)
    tagged["priority_signal"] = f"boost={source_boost},tech={tech_hits},news={news_hits}"
    return tagged


def priority_sort_key(item: dict[str, str]) -> tuple[int, str]:
    return (
        safe_int(item.get("priority_score"), 0),
        normalize_text(item.get("published_at", "")),
    )


def prioritize_items(
    items: list[dict[str, str]],
    max_items: int,
    technical_quota: int,
    geeknews_cap: int,
) -> list[dict[str, str]]:
    if max_items <= 0:
        return []

    tagged_items = [score_and_tag_item_priority(item) for item in items]
    geeknews_items = [item for item in tagged_items if item.get("source") == "GeekNews"]
    non_geeknews_items = [item for item in tagged_items if item.get("source") != "GeekNews"]

    geeknews_items.sort(key=priority_sort_key, reverse=True)
    geeknews_cap = min(max_items, max(0, geeknews_cap))
    selected = geeknews_items[:geeknews_cap]

    technical_items = [item for item in non_geeknews_items if item.get("priority_bucket") == "technical"]
    general_items = [item for item in non_geeknews_items if item.get("priority_bucket") != "technical"]
    technical_items.sort(key=priority_sort_key, reverse=True)
    general_items.sort(key=priority_sort_key, reverse=True)

    remaining_slots = max_items - len(selected)
    tech_take = min(remaining_slots, max(0, technical_quota), len(technical_items))
    selected.extend(technical_items[:tech_take])

    general_take = min(max_items - len(selected), len(general_items))
    selected.extend(general_items[:general_take])

    if len(selected) < max_items:
        # Keep feed diversity first; if non-GeekNews runs out, backfill from remaining GeekNews.
        remaining = (
            technical_items[tech_take:]
            + general_items[general_take:]
            + geeknews_items[geeknews_cap:]
        )
        remaining.sort(key=priority_sort_key, reverse=True)
        selected.extend(remaining[: max_items - len(selected)])

    return selected[:max_items]


def build_discord_item_block(
    item: dict[str, str],
    *,
    include_summary: bool = True,
    compact_summary: bool = False,
) -> str:
    title = item.get("translated_title") or item["title"]
    title = truncate_text(title, 220)
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


def build_discord_batch_content(
    items: list[dict[str, str]],
    mention: str,
    max_chars: int = 1900,
) -> str:
    if not items:
        return mention if mention else ""

    def compose(include_summary: bool, compact_summary: bool) -> str:
        header = f"이번 배치 뉴스 {len(items)}건"
        lines: list[str] = []
        if mention:
            lines.append(mention)
        lines.append(header)
        for idx, item in enumerate(items, start=1):
            block = build_discord_item_block(
                item,
                include_summary=include_summary,
                compact_summary=compact_summary,
            )
            lines.append("")
            lines.append(f"{idx}. {block}")
        return "\n".join(lines)

    for include_summary, compact_summary in [
        (True, False),
        (True, True),
        (False, False),
    ]:
        content = compose(include_summary=include_summary, compact_summary=compact_summary)
        if len(content) <= max_chars:
            return content

    return truncate_text(compose(include_summary=False, compact_summary=False), max_chars)


def enrich_item_with_openai(
    item: dict[str, str],
    api_key: str,
    models: list[str],
    timeout_sec: int,
    retries: int,
) -> tuple[dict[str, str], str | None]:
    if not api_key:
        return item, None
    if is_korean_dominant(item.get("title", "")):
        return item, None
    if not is_likely_english(item.get("title", "")):
        return item, None
    if not models:
        return item, "openai model list is empty"

    snippet = truncate_text(item.get("summary", ""), 800)
    user_prompt = (
        "아래 IT 뉴스 정보를 한국어로 정리해줘.\n"
        "반드시 JSON만 출력해.\n"
        '스키마: {"translated_title":"", "short_summary":""}\n'
        "- translated_title: 자연스러운 한국어 제목(40자 내외)\n"
        "- short_summary: 1~2문장 요약(총 120자 내외)\n\n"
        f"Title: {item.get('title', '')}\n"
        f"Snippet: {snippet}\n"
    )
    last_error: str | None = None
    denied_models: list[str] = []

    for model in models:
        payload = {
            "model": model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a precise Korean translator and tech news summarizer. "
                        "Output strictly valid JSON."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
        }

        body = json.dumps(payload).encode("utf-8")
        model_access_error = False

        for attempt in range(retries):
            req = Request(
                "https://api.openai.com/v1/chat/completions",
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
                method="POST",
            )

            try:
                with urlopen(req, timeout=timeout_sec) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                    choices = data.get("choices", [])
                    if not choices:
                        return item, f"openai choices is empty (model={model})"

                    content = choices[0].get("message", {}).get("content", "")
                    if isinstance(content, list):
                        content = " ".join(
                            normalize_text(part.get("text", ""))
                            for part in content
                            if isinstance(part, dict)
                        )

                    parsed = parse_json_from_text(str(content))
                    translated_title = normalize_text(parsed.get("translated_title"))
                    short_summary = normalize_text(parsed.get("short_summary"))

                    if translated_title:
                        item["translated_title"] = translated_title
                    if short_summary:
                        item["short_summary"] = short_summary
                    if translated_title or short_summary:
                        item["ai_model"] = model
                    return item, None
            except HTTPError as exc:
                body_text = ""
                try:
                    body_text = exc.read().decode("utf-8", errors="replace").strip()
                except Exception:  # noqa: BLE001
                    body_text = ""

                if body_text and is_openai_model_access_error(body_text):
                    last_error = f"model access denied: {model}"
                    denied_models.append(model)
                    model_access_error = True
                    break

                last_error = (
                    f"HTTP Error {exc.code} (model={model}): {body_text}" if body_text else str(exc)
                )
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = f"{exc} (model={model})"

            if attempt < retries - 1:
                time.sleep(2**attempt)

        if model_access_error:
            continue

    if denied_models:
        return item, f"model access denied (tried: {', '.join(denied_models)})"
    return item, last_error


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
    max_new_items_per_run = max(1, safe_int(os.getenv("MAX_NEW_ITEMS_PER_RUN"), 3))
    max_item_age_days = max(1, safe_int(os.getenv("MAX_ITEM_AGE_DAYS"), 3))
    technical_priority_quota = max(0, safe_int(os.getenv("TECH_PRIORITY_QUOTA"), 2))
    geeknews_max_per_run = max(0, safe_int(os.getenv("GEEKNEWS_MAX_PER_RUN"), 1))
    technical_priority_quota = min(technical_priority_quota, max_new_items_per_run)
    geeknews_max_per_run = min(geeknews_max_per_run, max_new_items_per_run)

    mention = os.getenv("DISCORD_MENTION", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini-2025-04-14").strip()
    openai_fallback_models = os.getenv(
        "OPENAI_FALLBACK_MODELS",
        "gpt-4.1-mini,gpt-4.1-nano-2025-04-14,gpt-4.1-nano,gpt-4o-mini-2024-07-18,gpt-4o-mini",
    ).strip()
    openai_models = build_model_candidates(openai_model, openai_fallback_models)
    openai_timeout_sec = max(5, safe_int(os.getenv("OPENAI_TIMEOUT_SEC"), 20))
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
        max_items=max_new_items_per_run,
        technical_quota=technical_priority_quota,
        geeknews_cap=geeknews_max_per_run,
    )

    sent_items: list[dict[str, str]] = []
    enriched_items: list[dict[str, str]] = []
    send_failures: list[dict[str, str]] = []
    ai_failures: list[dict[str, str]] = []
    ai_enriched_total = 0
    discord_messages_sent = 0
    selected_geeknews_total = sum(1 for item in new_items if item.get("source") == "GeekNews")
    selected_technical_total = sum(1 for item in new_items if item.get("priority_bucket") == "technical")
    selected_general_total = sum(1 for item in new_items if item.get("priority_bucket") != "technical")

    for item in new_items:
        enriched_item, ai_err = enrich_item_with_openai(
            item=dict(item),
            api_key=openai_api_key,
            models=openai_models,
            timeout_sec=openai_timeout_sec,
            retries=retries,
        )
        if ai_err:
            ai_failures.append(
                {
                    "source": item["source"],
                    "title": item["title"],
                    "error": ai_err,
                }
            )
        if enriched_item.get("translated_title") or enriched_item.get("short_summary"):
            ai_enriched_total += 1

        enriched_items.append(enriched_item)

    if dry_run:
        for enriched_item in enriched_items:
            enriched_item["sent_at"] = fetched_at
            sent_items.append(enriched_item)
    elif enriched_items:
        content = build_discord_batch_content(
            enriched_items,
            mention=mention,
            max_chars=batch_max_chars,
        )
        ok, err = post_discord(
            webhook_url=webhook_url,
            content=content,
            timeout_sec=timeout_sec,
            retries=retries,
            user_agent=discord_user_agent,
        )

        if ok:
            sent_at = now_utc().isoformat()
            discord_messages_sent = 1
            for enriched_item in enriched_items:
                enriched_item["sent_at"] = sent_at
                sent_items.append(enriched_item)
                sent_ids[enriched_item["id"]] = now_ts
            # Persist immediately to prevent duplicate sends on cancellation/re-run.
            sent_ids = trim_sent_ids(sent_ids, ttl_days=ttl_days, max_ids=max_state_ids)
            write_json(STATE_PATH, {"sent_ids": sent_ids})
        else:
            for enriched_item in enriched_items:
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
        if not isinstance(existing_news, list):
            existing_news = []

        merged_news = merge_news(existing=existing_news, new_sent=sent_items, max_items=max_news_items)
        write_json(NEWS_PATH, {"items": merged_news})

    summary = {
        "executed_at": fetched_at,
        "dry_run": dry_run,
        "sources_total": len(sources),
        "sources_enabled": len(enabled_sources),
        "source_failures": source_failures,
        "candidates_total": len(candidates),
        "max_item_age_days": max_item_age_days,
        "aged_out_total": aged_out_total,
        "deduped_total": len(deduped_items),
        "priority_technical_quota": technical_priority_quota,
        "geeknews_max_per_run": geeknews_max_per_run,
        "selected_geeknews_total": selected_geeknews_total,
        "selected_technical_total": selected_technical_total,
        "selected_general_total": selected_general_total,
        "new_items_total": len(new_items),
        "sent_total": len(sent_items),
        "discord_messages_sent": discord_messages_sent,
        "discord_batch_max_chars": batch_max_chars,
        "send_failures": send_failures,
        "ai_enriched_total": ai_enriched_total,
        "ai_failures": ai_failures,
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
