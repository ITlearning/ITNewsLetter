#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import feedparser
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
STATE_PATH = ROOT / "data" / "state.json"
NEWS_PATH = ROOT / "data" / "news.json"
LAST_RUN_PATH = ROOT / "data" / "last_run.json"

USER_AGENT = "ITNewsLetterBot/1.0 (+https://github.com/)"


@dataclass
class Source:
    name: str
    feed_url: str
    enabled: bool
    max_items: int


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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

        if not name or not feed_url:
            continue

        sources.append(
            Source(
                name=name,
                feed_url=feed_url,
                enabled=enabled,
                max_items=max(1, max_items),
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


def normalize_entry(source_name: str, entry: dict[str, Any], fetched_at: str) -> dict[str, str]:
    title = normalize_text(entry.get("title"), "(no title)")
    link = normalize_text(entry.get("link") or entry.get("id"))
    published_at = parse_entry_time(entry)

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
        "fetched_at": fetched_at,
    }


def fetch_source(source: Source, fetched_at: str) -> list[dict[str, str]]:
    feed = feedparser.parse(
        source.feed_url,
        request_headers={"User-Agent": USER_AGENT},
    )

    if getattr(feed, "bozo", False) and not feed.entries:
        reason = str(getattr(feed, "bozo_exception", "unknown feed parse error"))
        raise RuntimeError(reason)

    items: list[dict[str, str]] = []
    for entry in feed.entries[: source.max_items]:
        item = normalize_entry(source.name, entry, fetched_at)
        if not item["link"]:
            continue
        items.append(item)

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


def build_discord_content(item: dict[str, str], mention: str) -> str:
    title = item["title"]
    if len(title) > 220:
        title = title[:217] + "..."

    date_suffix = f" ({item['published_at']})" if item.get("published_at") else ""
    header = f"**[{item['source']}]** {title}{date_suffix}"

    if mention:
        return f"{mention}\n{header}\n{item['link']}"
    return f"{header}\n{item['link']}"


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

    ttl_days = max(1, safe_int(os.getenv("STATE_TTL_DAYS"), 14))
    max_state_ids = max(100, safe_int(os.getenv("MAX_STATE_IDS"), 3000))
    max_news_items = max(100, safe_int(os.getenv("MAX_NEWS_ITEMS"), 2000))
    max_new_items_per_run = max(1, safe_int(os.getenv("MAX_NEW_ITEMS_PER_RUN"), 30))

    mention = os.getenv("DISCORD_MENTION", "").strip()
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

    candidates.sort(key=lambda item: item.get("published_at", ""), reverse=True)

    seen_links: set[str] = set()
    seen_title_hashes: set[str] = set()
    new_items: list[dict[str, str]] = []

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
        new_items.append(item)

        if len(new_items) >= max_new_items_per_run:
            break

    sent_items: list[dict[str, str]] = []
    send_failures: list[dict[str, str]] = []

    for item in new_items:
        if dry_run:
            item["sent_at"] = fetched_at
            sent_items.append(item)
            continue

        content = build_discord_content(item, mention=mention)
        ok, err = post_discord(
            webhook_url=webhook_url,
            content=content,
            timeout_sec=timeout_sec,
            retries=retries,
            user_agent=discord_user_agent,
        )

        if ok:
            item["sent_at"] = now_utc().isoformat()
            sent_items.append(item)
            sent_ids[item["id"]] = now_ts
        else:
            send_failures.append(
                {
                    "source": item["source"],
                    "title": item["title"],
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
        "new_items_total": len(new_items),
        "sent_total": len(sent_items),
        "send_failures": send_failures,
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
