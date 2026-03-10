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

            payload = {
                "items": [
                    {
                        "id": "eng1",
                        "source": "AI Weekly",
                        "title": "OpenAI ships a faster workflow",
                        "translated_title": "오픈AI, 더 빠른 워크플로 공개",
                        "short_summary": "목록용 짧은 요약",
                        "detailed_summary": "상세 페이지에서 보여줄 충분한 브리핑 요약입니다.",
                        "summary": "raw source text",
                        "link": "https://example.com/eng1",
                        "sent_at": "2026-03-10T02:48:40+00:00",
                    },
                    {
                        "id": "kor1",
                        "source": "GeekNews",
                        "title": "긱뉴스 한국어 기사",
                        "short_summary": "한국어 브리핑 요약",
                        "summary": "원문 전체를 복제하면 안 됩니다.",
                        "link": "https://news.hada.io/topic?id=1",
                        "sent_at": "2026-03-10T02:48:40+00:00",
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

            with (
                patch.object(build_archive_site, "NEWS_PATH", news_path),
                patch.object(build_archive_site, "LAST_RUN_PATH", last_run_path),
                patch.object(build_archive_site, "DIST_DIR", dist_dir),
                patch.object(build_archive_site, "SITE_DATA_PATH", dist_dir / "data" / "news-archive.json"),
            ):
                build_archive_site.build_site()

            archive_payload = json.loads((dist_dir / "data" / "news-archive.json").read_text(encoding="utf-8"))
            self.assertEqual(len(archive_payload["today_picks"]), 2)
            self.assertTrue((dist_dir / "news" / "eng1" / "index.html").exists())
            self.assertTrue((dist_dir / "news" / "kor1" / "index.html").exists())

            english_detail = (dist_dir / "news" / "eng1" / "index.html").read_text(encoding="utf-8")
            korean_detail = (dist_dir / "news" / "kor1" / "index.html").read_text(encoding="utf-8")

            self.assertIn("상세 페이지에서 보여줄 충분한 브리핑 요약입니다.", english_detail)
            self.assertIn("한국어 브리핑 요약", korean_detail)
            self.assertNotIn("원문 전체를 복제하면 안 됩니다.", korean_detail)


if __name__ == "__main__":
    unittest.main()
