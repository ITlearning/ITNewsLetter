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
                        "why_it_matters": (
                            "이 변화는 단순 기능 추가보다, 팀 단위 개발 흐름을 다시 설계하게 만든다는 점이 더 중요하다.\n\n"
                            "- 코드 리뷰와 자동화가 같은 흐름 안으로 들어온다\n"
                            "- 도구 선택보다 워크플로 설계가 중요해진다"
                        ),
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
                        "hn_reaction_summary": (
                            "댓글 반응은 논문을 잘 쓰는 법 자체보다, 무엇을 연구 가치로 볼지에 더 쏠렸다.\n\n"
                            "- 실험의 난도보다 문제 선택과 타이밍이 더 중요하다는 의견이 많았다\n"
                            "- 현실 조언인지 자기합리화인지에 대한 반론도 함께 붙었다"
                        ),
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
                ],
                "topic_digests": {
                    "weekly": [
                        {
                            "period": "weekly",
                            "slot": "tools_agents",
                            "slot_label": "도구·에이전트",
                            "headline": "이번 주 도구·에이전트",
                            "summary": "로컬 실행과 워크플로 설계가 중심 주제였다.",
                            "item_ids": ["eng1", "legacy-eng"],
                            "total_items": 2,
                        }
                    ],
                    "monthly": [
                        {
                            "period": "monthly",
                            "slot": "practical_tech",
                            "slot_label": "실무 기술",
                            "headline": "이번 달 실무 기술",
                            "summary": "성능, 데이터베이스, 운영 맥락이 많이 묶였다.",
                            "item_ids": ["hn-safe", "old1"],
                            "total_items": 2,
                        }
                    ],
                },
                "spotlight_modules": [
                    {
                        "id": "quiet-riser",
                        "kind": "quiet_riser",
                        "label": "AI Spotlight",
                        "title": "조용히 커지는 주제",
                        "topic_name": "에이전트 워크플로",
                        "summary_line": "이번 주 기사에서 조용히 반복되며 커지기 시작한 흐름이다.",
                        "signals": ["로컬 실행", "팀 워크플로", "자동화 재설계"],
                        "related_item_ids": ["eng1", "legacy-eng"],
                        "cta_label": "관련 기사 보기",
                        "score": 0.82,
                    },
                    {
                        "id": "hn-split",
                        "kind": "hn_split",
                        "label": "AI Spotlight",
                        "title": "HN 댓글이 가장 갈린 기사",
                        "headline": "An opinionated take on how to do important research that matters",
                        "issue_title": "문제 선택이 더 중요한가",
                        "opposition_summary": "현실 조언이라기보다 결과론적 해석에 가깝다는 반론이 있었다.",
                        "support_summary": "문제 선택과 타이밍을 보는 관점 자체는 실무에도 도움이 된다는 의견이 많았다.",
                        "related_item_ids": ["hn-safe"],
                        "cta_label": "쟁점 읽기",
                        "score": 0.76,
                    },
                    {
                        "id": "anomaly-signal",
                        "kind": "anomaly_signal",
                        "label": "Labs",
                        "title": "이번 주 이상 신호",
                        "signal_title": "로컬 추론 도구",
                        "summary_line": "메인 토픽은 아니지만 서로 다른 기사에서 같은 결로 감지된 신호다.",
                        "signals": ["CPU 추론", "경량 워크플로", "로컬 도구 체인"],
                        "related_item_ids": ["legacy-eng", "old1"],
                        "cta_label": "신호 보기",
                        "score": 0.7,
                    },
                ],
                "featured_spotlight": {
                    "id": "quiet-riser",
                    "kind": "quiet_riser",
                },
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
                patch.dict(
                    "os.environ",
                    {
                        "LAZY_DETAIL_API_URL": "https://detail-api.example.com/api/lazy-detail",
                        "SITE_BASE_URL": "https://itnewsletter.vercel.app",
                        "DETAIL_BANNER_AD_SLOT": "1234567890",
                    },
                ),
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
            self.assertTrue((dist_dir / "ads.txt").exists())
            self.assertTrue((dist_dir / "robots.txt").exists())
            self.assertTrue((dist_dir / "topics" / "index.html").exists())
            self.assertTrue((dist_dir / "topics" / "weekly" / "tools_agents" / "index.html").exists())

            english_detail = (dist_dir / "news" / "eng1" / "index.html").read_text(encoding="utf-8")
            korean_detail = (dist_dir / "news" / "kor1" / "index.html").read_text(encoding="utf-8")
            legacy_detail = (dist_dir / "news" / "legacy-eng" / "index.html").read_text(encoding="utf-8")
            hn_detail = (dist_dir / "news" / "hn-safe" / "index.html").read_text(encoding="utf-8")
            about_page = (dist_dir / "about.html").read_text(encoding="utf-8")
            contact_page = (dist_dir / "contact.html").read_text(encoding="utf-8")
            index_page = (dist_dir / "index.html").read_text(encoding="utf-8")
            topics_hub_page = (dist_dir / "topics" / "index.html").read_text(encoding="utf-8")
            topic_page = (dist_dir / "topics" / "weekly" / "tools_agents" / "index.html").read_text(encoding="utf-8")
            ads_txt = (dist_dir / "ads.txt").read_text(encoding="utf-8")
            robots_txt = (dist_dir / "robots.txt").read_text(encoding="utf-8")

            self.assertIn("<ul class='detail-summary-list'>", english_detail)
            self.assertIn("<strong>핵심 변화</strong>", english_detail)
            self.assertIn("data-summary-markdown=", english_detail)
            self.assertIn('property="og:title"', english_detail)
            self.assertIn('property="og:description"', english_detail)
            self.assertIn('property="og:url"', english_detail)
            self.assertIn('property="og:image"', english_detail)
            self.assertIn('name="twitter:card"', english_detail)
            self.assertIn('rel="canonical"', english_detail)
            self.assertIn("https://itnewsletter.vercel.app/news/eng1/", english_detail)
            self.assertIn("https://itnewsletter.vercel.app/img.icons8.png", english_detail)
            self.assertIn("../../about.html", english_detail)
            self.assertIn("../../contact.html", english_detail)
            self.assertIn("ca-pub-3668470088067384", english_detail)
            self.assertIn("detail-ad-section", english_detail)
            self.assertIn("data-ad-slot='1234567890'", english_detail)
            self.assertLess(english_detail.index("detail-ad-section"), english_detail.index("detail-briefing"))
            self.assertIn("detail-why-card", english_detail)
            self.assertIn("왜 중요한가", english_detail)
            self.assertGreater(english_detail.index("detail-why-card"), english_detail.index("detail-briefing"))
            self.assertIn("detail-spotlight-context", english_detail)
            self.assertIn("조용히 커지는 주제", english_detail)
            self.assertGreater(english_detail.index("detail-spotlight-context"), english_detail.index("detail-why-card"))
            self.assertIn("detail-hn-card", hn_detail)
            self.assertGreater(hn_detail.index("detail-hn-card"), hn_detail.index("detail-briefing"))
            self.assertIn("detail-spotlight-context", hn_detail)
            self.assertIn("HN 댓글이 가장 갈린 기사", hn_detail)
            self.assertIn("긱뉴스 RSS에서 제공하는 한국어 요약 미리보기입니다.", korean_detail)
            self.assertNotIn("원문 전체를 복제하면 안 됩니다.", korean_detail)
            self.assertNotIn("with AI", korean_detail)
            self.assertIn("class=\"detail-hero-actions\"", english_detail)
            self.assertIn('data-item-id="legacy-eng"', legacy_detail)
            self.assertIn('data-lazy-detail-supported="true"', legacy_detail)
            self.assertIn("https://detail-api.example.com/api/lazy-detail", legacy_detail)
            self.assertIn('data-hn-story-id="47317132"', hn_detail)
            self.assertIn("HN 반응", hn_detail)
            self.assertIn("댓글 반응은 논문을 잘 쓰는 법 자체보다", hn_detail)
            self.assertIn("HN 토론 보기", hn_detail)
            self.assertIn("https://news.ycombinator.com/item?id=47317132", hn_detail)
            self.assertIn("href=\"../", english_detail)
            self.assertNotIn("href=\"./news/", english_detail)
            self.assertIn('id="spotlight-section"', index_page)
            self.assertIn('id="spotlight-stage"', index_page)
            self.assertNotIn("주간·월간 토픽", index_page)
            self.assertNotIn("토픽 허브 열기", index_page)
            self.assertIn("이번 주 도구·에이전트", topics_hub_page)
            self.assertIn("로컬 실행과 워크플로 설계가 중심 주제였다.", topic_page)
            self.assertIn("오픈AI, 더 빠른 워크플로 공개", topic_page)
            self.assertIn("./contact.html", about_page)
            self.assertIn("GitHub Issues", contact_page)
            self.assertIn("ca-pub-3668470088067384", index_page)
            self.assertIn("pub-3668470088067384", ads_txt)
            self.assertIn("User-agent: *", robots_txt)
            self.assertIn("Allow: /", robots_txt)

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
            self.assertEqual(
                by_id["hn-safe"]["hn_discussion_url"],
                "https://news.ycombinator.com/item?id=47317132",
            )
            self.assertTrue(by_id["hn-safe"]["hn_reaction_summary"].startswith("댓글 반응은 논문을 잘 쓰는 법"))
            self.assertIn("dup-hn", by_id)
            self.assertNotIn("dup-gn", by_id)
            self.assertIn("topic_digests", archive_payload)
            self.assertEqual(archive_payload["topic_digests"]["weekly"][0]["url"], "./topics/weekly/tools_agents/")
            self.assertIn("spotlight_modules", archive_payload)
            self.assertEqual(len(archive_payload["spotlight_modules"]), 3)
            self.assertEqual(archive_payload["featured_spotlight"]["id"], "quiet-riser")


if __name__ == "__main__":
    unittest.main()
