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


class EnrichmentTests(unittest.TestCase):
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
                                    "OpenAI가 팀 생산성을 높이는 새로운 코딩 워크플로를 공개했다. "
                                    "이번 변화는 코드 리뷰와 자동화 흐름을 더 자연스럽게 연결하는 데 초점을 둔다. "
                                    "팀 협업과 반복 업무 감소 측면에서 의미가 크다."
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


if __name__ == "__main__":
    unittest.main()
