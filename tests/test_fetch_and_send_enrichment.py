from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_and_send  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def build_fake_urlopen(payload_by_suffix):
    def fake_urlopen(request, timeout=0):
        url = getattr(request, "full_url", str(request))
        for suffix, payload in payload_by_suffix.items():
            if url.endswith(suffix):
                return FakeResponse(payload)
        raise AssertionError(f"Unexpected URL: {url}")

    return fake_urlopen


class EnrichmentTests(unittest.TestCase):
    def test_briefing_looks_like_markdown_detects_supported_shapes(self) -> None:
        self.assertFalse(fetch_and_send.briefing_looks_like_markdown("한 줄 평문 요약입니다."))
        self.assertTrue(fetch_and_send.briefing_looks_like_markdown("도입\n\n- 항목 하나\n\n마무리"))
        self.assertTrue(fetch_and_send.briefing_looks_like_markdown("도입 **강조** 문장"))
        self.assertTrue(fetch_and_send.briefing_looks_like_markdown("첫 문단\n\n둘째 문단"))

    def test_normalize_briefing_markdown_preserves_structure(self) -> None:
        raw = "  도입 문장  \n\n* 첫 항목  \n- 둘째   항목\n\n  마무리 문장  "

        normalized = fetch_and_send.normalize_briefing_markdown(raw)

        self.assertEqual(normalized, "도입 문장\n\n- 첫 항목\n- 둘째 항목\n\n마무리 문장")

    def test_render_briefing_markdown_html_supports_safe_subset(self) -> None:
        rendered = fetch_and_send.render_briefing_markdown_html(
            "도입 **강조** 문장\n\n- 첫 <항목>\n- 둘째 항목\n\n마무리"
        )

        self.assertIn("<p>도입 <strong>강조</strong> 문장</p>", rendered)
        self.assertIn("<ul class='detail-summary-list'>", rendered)
        self.assertIn("<li>첫 &lt;항목&gt;</li>", rendered)
        self.assertIn("<p>마무리</p>", rendered)

    def test_english_item_stores_detail_fields(self) -> None:
        item = {
            "id": "abc123",
            "source": "AI Weekly",
            "title": "OpenAI ships a faster coding workflow",
            "summary": "A new coding workflow improves code review and automation for teams.",
        }
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "translated_title": "오픈AI, 더 빠른 코딩 워크플로 공개",
                                "short_summary": "코드 리뷰와 자동화를 개선하는 워크플로를 공개했다.",
                                "detailed_summary": (
                                    "새 코딩 워크플로가 공개됐다.\n\n"
                                    "* 코드 리뷰 흐름을 더 짧게 만든다\n"
                                    "- 자동화 연결이 자연스럽다\n"
                                    "- 팀 협업 병목을 줄인다\n\n"
                                    "반복 업무를 덜어주는 변화로 볼 수 있다."
                                ),
                            }
                        )
                    }
                }
            ]
        }

        with patch.object(fetch_and_send, "urlopen", return_value=FakeResponse(response_payload)) as mocked:
            enriched, err = fetch_and_send.enrich_item_with_openai(
                item=item,
                api_key="test-key",
                models=["gpt-test"],
                timeout_sec=1,
                retries=1,
            )

        self.assertIsNone(err)
        self.assertEqual(enriched["detail_slug"], "abc123")
        self.assertTrue(enriched["is_english_source"])
        self.assertIn("translated_title", enriched)
        self.assertIn("short_summary", enriched)
        self.assertIn("detailed_summary", enriched)
        self.assertEqual(
            enriched["detailed_summary"],
            (
                "새 코딩 워크플로가 공개됐다.\n\n"
                "- 코드 리뷰 흐름을 더 짧게 만든다\n"
                "- 자동화 연결이 자연스럽다\n"
                "- 팀 협업 병목을 줄인다\n\n"
                "반복 업무를 덜어주는 변화로 볼 수 있다."
            ),
        )
        self.assertEqual(enriched["ai_model"], "gpt-test")
        mocked.assert_called_once()

    def test_geeknews_item_skips_openai_but_keeps_detail_slug(self) -> None:
        item = {
            "id": "gn001",
            "source": "GeekNews",
            "title": "OpenAI expands agent workflows",
            "summary": "긱뉴스 등록자가 작성한 한국어 요약이 이미 존재합니다.",
        }

        with patch.object(fetch_and_send, "urlopen") as mocked:
            enriched, err = fetch_and_send.enrich_item_with_openai(
                item=item,
                api_key="test-key",
                models=["gpt-test"],
                timeout_sec=1,
                retries=1,
            )

        self.assertIsNone(err)
        self.assertEqual(enriched["detail_slug"], "gn001")
        self.assertFalse(enriched["is_english_source"])
        self.assertNotIn("detailed_summary", enriched)
        mocked.assert_not_called()

    def test_fetch_hn_api_source_collects_story_and_comment_context(self) -> None:
        source = fetch_and_send.Source(
            name="Hacker News Frontpage (HN RSS)",
            feed_url="https://hacker-news.firebaseio.com/v0",
            enabled=True,
            max_items=2,
            priority_boost=24,
            source_type="hn_api",
            path_prefix="",
        )
        payloads = {
            "/topstories.json": [101, 102],
            "/item/101.json": {
                "id": 101,
                "type": "story",
                "title": "Show HN: Fast local agents",
                "url": "https://example.com/agents",
                "time": 1773120000,
                "score": 120,
                "descendants": 18,
                "text": "I built a fast local agent workflow for macOS development.",
                "kids": [1001, 1002],
            },
            "/item/1001.json": {
                "id": 1001,
                "type": "comment",
                "by": "alice",
                "text": "This looks much faster than the usual agent loop and the worktree isolation is practical.",
            },
            "/item/1002.json": {
                "id": 1002,
                "type": "comment",
                "by": "bob",
                "text": "The implementation details are useful, especially the local-first workflow decisions.",
            },
            "/item/102.json": {
                "id": 102,
                "type": "story",
                "title": "An opinionated take on research workflows",
                "url": "https://example.com/research",
                "time": 1773120300,
                "score": 75,
                "descendants": 4,
                "kids": [],
            },
        }

        with patch.object(fetch_and_send, "urlopen", side_effect=build_fake_urlopen(payloads)):
            items = fetch_and_send.fetch_hn_api_source(source, "2026-03-10T00:00:00+00:00")

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["hn_story_id"], "101")
        self.assertEqual(items[0]["hn_story_type"], "story")
        self.assertEqual(items[0]["hn_points"], "120")
        self.assertEqual(items[0]["hn_comments_count"], "18")
        self.assertIn("HN post text:", items[0]["summary"])
        self.assertIn("HN top comments:", items[0]["summary"])
        self.assertIn("alice:", items[0]["summary"])
        self.assertEqual(items[1]["hn_story_id"], "102")

    def test_legacy_hn_item_derives_story_id_from_summary(self) -> None:
        item = {
            "id": "legacy",
            "source": "Hacker News Frontpage (HN RSS)",
            "title": "No, it doesn't cost Anthropic $5k per Claude Code user",
            "summary": (
                "Article URL: https://martinalderson.com/posts/example "
                "Comments URL: https://news.ycombinator.com/item?id=47317132 "
                "Points: 45 # Comments: 9"
            ),
            "link": "https://martinalderson.com/posts/example",
        }

        enriched = fetch_and_send.ensure_archive_detail_fields(item)

        self.assertEqual(enriched["hn_story_id"], "47317132")
        self.assertEqual(enriched["hn_points"], "45")
        self.assertEqual(enriched["hn_comments_count"], "9")
        self.assertEqual(
            enriched["hn_discussion_url"],
            "https://news.ycombinator.com/item?id=47317132",
        )

    def test_hn_duplicate_beats_geeknews_duplicate(self) -> None:
        items = [
            {
                "id": "gn-1",
                "source": "GeekNews",
                "title": "Go 표준 라이브러리에 UUID 패키지 추가 제안",
                "sent_at": "2026-03-08T08:47:14+00:00",
            },
            {
                "id": "hn-1",
                "source": "Hacker News Frontpage (HN RSS)",
                "title": "UUID package coming to Go standard library",
                "translated_title": "Go 표준 라이브러리에 UUID 패키지 추가 예정",
                "sent_at": "2026-03-07T05:06:29+00:00",
            },
        ]

        collapsed = fetch_and_send.collapse_geeknews_hn_duplicates(items)

        self.assertEqual(len(collapsed), 1)
        self.assertEqual(collapsed[0]["id"], "hn-1")

    def test_discord_batch_content_prepends_top_three_titles_only(self) -> None:
        items = [
            {
                "id": "1",
                "source": "AI Weekly",
                "title": "First original title",
                "translated_title": "첫 번째 기사 제목",
                "link": "https://example.com/1",
            },
            {
                "id": "2",
                "source": "AI Weekly",
                "title": "Second original title",
                "translated_title": "두 번째 기사 제목",
                "link": "https://example.com/2",
            },
            {
                "id": "3",
                "source": "AI Weekly",
                "title": "Third original title",
                "translated_title": "세 번째 기사 제목",
                "link": "https://example.com/3",
            },
            {
                "id": "4",
                "source": "AI Weekly",
                "title": "Fourth original title",
                "translated_title": "네 번째 기사 제목",
                "link": "https://example.com/4",
            },
        ]

        batch = fetch_and_send.build_discord_batch_content(items, mention="", max_chars=1900)
        preview_section, _ = batch.content.split("\n\n1. ", 1)

        self.assertIn("- 첫 번째 기사 제목", preview_section)
        self.assertIn("- 두 번째 기사 제목", preview_section)
        self.assertIn("- 세 번째 기사 제목", preview_section)
        self.assertNotIn("- 네 번째 기사 제목", preview_section)

    def test_discord_batch_content_keeps_existing_detail_blocks_below_preview(self) -> None:
        items = [
            {
                "id": "1",
                "source": "AI Weekly",
                "title": "Original title",
                "translated_title": "번역된 제목",
                "short_summary": "짧은 요약입니다.",
                "link": "https://example.com/1",
            }
        ]

        batch = fetch_and_send.build_discord_batch_content(items, mention="", max_chars=1900)

        self.assertIn("이번 배치 뉴스 1건\n- 번역된 제목", batch.content)
        self.assertIn("\n\n1. [AI Weekly]\n**번역된 제목**", batch.content)
        self.assertIn("원제: **Original title**", batch.content)
        self.assertIn("**요약**\n짧은 요약입니다.", batch.content)


if __name__ == "__main__":
    unittest.main()
