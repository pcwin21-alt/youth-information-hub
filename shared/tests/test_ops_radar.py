from __future__ import annotations

import sys
import unittest
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.ops_radar import annotate_ops_radar  # noqa: E402


def make_article(
    *,
    title: str,
    lead_text: str,
    published_date: str = "2026-04-21T09:00:00+09:00",
    selected: bool = False,
    drop_reason: str | None = "selection_cutoff:youth_issue:score=9",
    editorial_decision: str = "default",
) -> dict:
    return {
        "url": "https://example.com/article",
        "title": title,
        "source": "테스트신문",
        "source_name": "테스트신문",
        "published_date": published_date,
        "lead_text": lead_text,
        "body_text": lead_text,
        "source_kind": "news",
        "region": "서울",
        "categories": ["청년은 지금"],
        "issue_tags": ["청년센터 운영"],
        "location_tags": ["서울"],
        "pipeline_flags": {"selected": selected},
        "drop_reason": drop_reason if not selected else None,
        "editorial_decision": editorial_decision,
        "is_noise": False,
        "importance_score": 8,
    }


class OpsRadarTests(unittest.TestCase):
    def test_ops_radar_surfaces_overlooked_center_campaign_risk_article(self) -> None:
        articles, payload = annotate_ops_radar(
            [
                make_article(
                    title="부산 청년센터장 공약 논란 커진다",
                    lead_text="청년센터 위탁 운영과 예산, 후보 공약을 두고 갑질 논란과 감사 요구가 이어졌다.",
                )
            ],
            generated_at="2026-04-21T10:00:00+09:00",
        )

        article = articles[0]
        self.assertTrue(article["ops_radar_overlooked"])
        self.assertGreater(article["ops_radar_score"], 0)
        self.assertIn("청년센터 운영", article["ops_radar_labels"])
        self.assertIn("정치·공약", article["ops_radar_labels"])
        self.assertIn("리스크·논란", article["ops_radar_labels"])
        self.assertEqual(payload["summary"]["overlooked_count"], 1)
        self.assertEqual(payload["items"][0]["ops_radar_priority"], "critical")

    def test_editorially_excluded_article_does_not_enter_ops_radar(self) -> None:
        articles, payload = annotate_ops_radar(
            [
                make_article(
                    title="청년센터 프로그램 모집 시작",
                    lead_text="청년센터가 참여자 모집 공고를 냈다.",
                    editorial_decision="exclude",
                )
            ]
        )

        article = articles[0]
        self.assertEqual(article["ops_radar_labels"], [])
        self.assertEqual(article["ops_radar_matches"], [])
        self.assertEqual(payload["summary"]["total_matched"], 0)
        self.assertEqual(payload["items"], [])


if __name__ == "__main__":
    unittest.main()
