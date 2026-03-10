from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_archive_site  # noqa: E402


class TodayCurationTests(unittest.TestCase):
    def test_today_picks_use_latest_sent_batch(self) -> None:
        items = [
            {"id": "a", "sent_at": "2026-03-10T02:48:40+00:00"},
            {"id": "b", "sent_at": "2026-03-10T02:48:40+00:00"},
            {"id": "c", "sent_at": "2026-03-09T22:00:00+00:00"},
        ]

        picks = build_archive_site.derive_today_picks(items)

        self.assertEqual([item["id"] for item in picks], ["a", "b"])


class RelatedItemsTests(unittest.TestCase):
    def test_same_slot_beats_same_source(self) -> None:
        base_item = {
            "id": "base",
            "primary_slot": "tools_agents",
            "source": "AI Weekly",
            "matched_terms": ["agent", "workflow"],
        }
        same_slot = {
            "id": "slot",
            "primary_slot": "tools_agents",
            "source": "TechCrunch",
            "matched_terms": [],
            "sent_at": "2026-03-10T01:00:00+00:00",
        }
        same_source = {
            "id": "source",
            "primary_slot": "industry_business",
            "source": "AI Weekly",
            "matched_terms": [],
            "sent_at": "2026-03-10T01:10:00+00:00",
        }

        ranked = build_archive_site.derive_related_items(base_item, [same_source, same_slot])

        self.assertEqual([item["id"] for item in ranked], ["slot", "source"])


class BuildSiteTests(unittest.TestCase):
    def test_build_site_generates_detail_pages_and_safe_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            dist_dir = tmp_root / "dist"
            news_path = tmp_root / "news.json"
            last_run_path = tmp_root / "last_run.json"
            allowlist_path = tmp_root / "lazy_detail_allowlist.json"

            payload = {
                "items": [
                    {
                        "id": "eng1",
                        "source": "TechCrunch",
                        "title": "OpenAI ships a faster workflow",
                        "translated_title": "오픈AI, 더 빠른 워크플로 공개",
                        "short_summary": "목록용 짧은 요약",
                        "detailed_summary": (
                            "상세 페이지 첫 문단입니다.\n\n"
                            "- **핵심 변화**를 먼저 짚는다\n"
                            "- 읽기 흐름을 더 빠르게 만든다\n\n"
                            "마지막 문단에서 의미를 정리합니다."
                        ),
                        "summary": "raw source text",
                        "link": "https://example.com/eng1",
                        "sent_at": "2026-03-10T02:48:40+00:00",
                    },
                    {
                        "id": "kor1",
                        "source": "GeekNews",
                        "title": "긱뉴스 한국어 기사",
                        "summary": "긱뉴스 RSS에서 제공하는 한국어 요약 미리보기입니다. 원문 전체를 복제하면 안 되지만 핵심 흐름은 보여줄 수 있습니다.",
                        "link": "https://news.hada.io/topic?id=1",
                        "sent_at": "2026-03-10T02:48:40+00:00",
                    },
                    {
                        "id": "legacy-eng",
                        "source": "TechCrunch",
                        "title": "Legacy English story",
                        "short_summary": "기존 짧은 요약",
                        "summary": "legacy feed snippet",
                        "link": "https://techcrunch.com/2026/03/01/legacy-english-story/",
                        "sent_at": "2026-03-09T22:30:00+00:00",
                    },
                    {
                        "id": "hn-safe",
                        "source": "Hacker News Frontpage (HN RSS)",
                        "title": "An opinionated take on how to do important research that matters",
                        "short_summary": "HN 원문 후보",
                        "summary": "essay feed snippet",
                        "link": "https://nicholas.carlini.com/writing/2026/how-to-win-a-best-paper-award.html",
                        "hn_story_id": "47317132",
                        "hn_story_type": "story",
                        "hn_points": "45",
                        "hn_comments_count": "9",
                        "sent_at": "2026-03-09T22:15:00+00:00",
                    },
                    {
                        "id": "dup-gn",
                        "source": "GeekNews",
                        "title": "Go 표준 라이브러리에 UUID 패키지 추가 제안",
                        "summary": "긱뉴스 중복 기사",
                        "link": "https://news.hada.io/topic?id=27299",
                        "sent_at": "2026-03-08T08:47:14+00:00",
                    },
                    {
                        "id": "dup-hn",
                        "source": "Hacker News Frontpage (HN RSS)",
                        "title": "UUID package coming to Go standard library",
                        "translated_title": "Go 표준 라이브러리에 UUID 패키지 추가 예정",
                        "short_summary": "HN 중복 기사",
                        "link": "https://github.com/golang/go/issues/62026",
                        "sent_at": "2026-03-07T05:06:29+00:00",
                    },
                    {
                        "id": "old1",
                        "source": "TechCrunch",
                        "title": "Older story",
                        "short_summary": "오래된 기사",
                        "link": "https://example.com/old1",
                        "sent_at": "2026-03-09T22:00:00+00:00",
                    },
                ]
            }
            news_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            last_run_path.write_text(
                json.dumps({"executed_at": "2026-03-10T02:48:40+00:00"}, ensure_ascii=False),
                encoding="utf-8",
            )
            allowlist_path.write_text(
                json.dumps(
                    {
                        "allowed_sources": ["TechCrunch"],
                        "excluded_sources": ["GeekNews"],
                        "allowed_domains": ["techcrunch.com"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with (
                patch.object(build_archive_site, "NEWS_PATH", news_path),
                patch.object(build_archive_site, "LAST_RUN_PATH", last_run_path),
                patch.object(build_archive_site, "DIST_DIR", dist_dir),
                patch.object(build_archive_site, "SITE_DATA_PATH", dist_dir / "data" / "news-archive.json"),
                patch.object(build_archive_site, "LAZY_DETAIL_ALLOWLIST_PATH", allowlist_path),
                patch.dict("os.environ", {"LAZY_DETAIL_API_URL": "https://detail-api.example.com/api/lazy-detail"}),
            ):
                build_archive_site.build_site()

            archive_payload = json.loads((dist_dir / "data" / "news-archive.json").read_text(encoding="utf-8"))
            self.assertEqual(len(archive_payload["today_picks"]), 2)
            self.assertTrue((dist_dir / "news" / "eng1" / "index.html").exists())
            self.assertTrue((dist_dir / "news" / "kor1" / "index.html").exists())
            self.assertTrue((dist_dir / "news" / "legacy-eng" / "index.html").exists())
            self.assertTrue((dist_dir / "news" / "hn-safe" / "index.html").exists())
            self.assertTrue((dist_dir / "about.html").exists())
            self.assertTrue((dist_dir / "editorial-policy.html").exists())
            self.assertTrue((dist_dir / "privacy.html").exists())
            self.assertTrue((dist_dir / "contact.html").exists())

            english_detail = (dist_dir / "news" / "eng1" / "index.html").read_text(encoding="utf-8")
            korean_detail = (dist_dir / "news" / "kor1" / "index.html").read_text(encoding="utf-8")
            legacy_detail = (dist_dir / "news" / "legacy-eng" / "index.html").read_text(encoding="utf-8")
            hn_detail = (dist_dir / "news" / "hn-safe" / "index.html").read_text(encoding="utf-8")
            about_page = (dist_dir / "about.html").read_text(encoding="utf-8")
            contact_page = (dist_dir / "contact.html").read_text(encoding="utf-8")

            self.assertIn("<ul class='detail-summary-list'>", english_detail)
            self.assertIn("<strong>핵심 변화</strong>", english_detail)
            self.assertIn("data-summary-markdown=", english_detail)
            self.assertIn("../../about.html", english_detail)
            self.assertIn("../../contact.html", english_detail)
            self.assertIn("긱뉴스 RSS에서 제공하는 한국어 요약 미리보기입니다.", korean_detail)
            self.assertNotIn("원문 전체를 복제하면 안 됩니다.", korean_detail)
            self.assertNotIn("with AI", korean_detail)
            self.assertIn("class=\"detail-hero-actions\"", english_detail)
            self.assertIn('data-item-id="legacy-eng"', legacy_detail)
            self.assertIn('data-lazy-detail-supported="true"', legacy_detail)
            self.assertIn("https://detail-api.example.com/api/lazy-detail", legacy_detail)
            self.assertIn('data-hn-story-id="47317132"', hn_detail)
            self.assertIn("href=\"../", english_detail)
            self.assertNotIn("href=\"./news/", english_detail)
            self.assertIn("./contact.html", about_page)
            self.assertIn("GitHub Issues", contact_page)

            by_id = {item["id"]: item for item in archive_payload["items"]}
            self.assertEqual(by_id["kor1"]["detail_url"], "https://news.hada.io/topic?id=1")
            self.assertFalse(by_id["eng1"]["lazy_detail_supported"])
            self.assertEqual(by_id["eng1"]["lazy_detail_reason"], "already_present")
            self.assertFalse(by_id["kor1"]["lazy_detail_supported"])
            self.assertEqual(by_id["kor1"]["lazy_detail_reason"], "not_english")
            self.assertTrue(by_id["legacy-eng"]["lazy_detail_supported"])
            self.assertEqual(by_id["legacy-eng"]["lazy_detail_reason"], "supported")
            self.assertTrue(by_id["hn-safe"]["lazy_detail_supported"])
            self.assertEqual(by_id["hn-safe"]["lazy_detail_reason"], "hn_api")
            self.assertEqual(by_id["hn-safe"]["hn_story_id"], "47317132")
            self.assertIn("dup-hn", by_id)
            self.assertNotIn("dup-gn", by_id)


if __name__ == "__main__":
    unittest.main()
