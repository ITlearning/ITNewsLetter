from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import reset_legacy_briefings  # noqa: E402


class ResetLegacyBriefingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "allowed_sources": {"techcrunch"},
            "excluded_sources": {"geeknews"},
            "allowed_domains": {"techcrunch.com"},
            "source_domain_overrides": {},
        }

    def test_build_reset_candidates_only_selects_lazy_regenerable_plain_text(self) -> None:
        items = [
            {
                "id": "legacy-plain",
                "source": "TechCrunch",
                "title": "Legacy English item",
                "summary": "English summary snippet",
                "detailed_summary": "예전 방식의 평문 상세 요약입니다. 여러 문장으로 이어집니다.",
                "link": "https://techcrunch.com/2026/03/10/example",
            },
            {
                "id": "already-markdown",
                "source": "TechCrunch",
                "title": "Already refreshed",
                "summary": "English summary snippet",
                "detailed_summary": "도입\n\n- 항목 하나\n\n마무리",
                "link": "https://techcrunch.com/2026/03/10/example-2",
            },
            {
                "id": "geeknews",
                "source": "GeekNews",
                "title": "긱뉴스 기사",
                "summary": "한국어 요약",
                "detailed_summary": "예전 방식 평문입니다.",
                "link": "https://news.hada.io/topic?id=1",
            },
        ]

        candidates = reset_legacy_briefings.build_reset_candidates(items, self.config)

        self.assertEqual([candidate["id"] for candidate in candidates], ["legacy-plain"])

    def test_reset_legacy_briefings_clears_only_candidates(self) -> None:
        items = [
            {
                "id": "legacy-plain",
                "source": "TechCrunch",
                "title": "Legacy English item",
                "summary": "English summary snippet",
                "detailed_summary": "예전 방식의 평문 상세 요약입니다. 여러 문장으로 이어집니다.",
                "link": "https://techcrunch.com/2026/03/10/example",
            },
            {
                "id": "already-markdown",
                "source": "TechCrunch",
                "title": "Already refreshed",
                "summary": "English summary snippet",
                "detailed_summary": "도입\n\n- 항목 하나\n\n마무리",
                "link": "https://techcrunch.com/2026/03/10/example-2",
            },
        ]

        updated_items, candidates = reset_legacy_briefings.reset_legacy_briefings(items, self.config)

        self.assertEqual([candidate["id"] for candidate in candidates], ["legacy-plain"])
        self.assertNotIn("detailed_summary", updated_items[0])
        self.assertEqual(updated_items[1]["detailed_summary"], "도입\n\n- 항목 하나\n\n마무리")


if __name__ == "__main__":
    unittest.main()
