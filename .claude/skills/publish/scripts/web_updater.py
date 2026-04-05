from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youth_info_platform.contact_config import load_contact_settings
from youth_info_platform.io_utils import read_json

NEWS_WINDOW_DAYS = 7
NEWS_WINDOW_HOURS = NEWS_WINDOW_DAYS * 24
HOME_UPDATE_SNAPSHOT = ROOT / "output" / "home_update_snapshot.json"

YOUTH_METRICS = [
    {
        "label": "청년 인구",
        "value": "1,040.4만명",
        "basis": "2024 · 19~34세",
        "source": "청년 삶의 질 2025",
        "url": "https://mods.go.kr/board.es?act=view&bid=246&list_no=442421&mainXml=Y&mid=a10301010000",
    },
    {
        "label": "전체 인구 비중",
        "value": "20.1%",
        "basis": "2024 · 19~34세",
        "source": "청년 삶의 질 2025",
        "url": "https://mods.go.kr/board.es?act=view&bid=246&list_no=442421&mainXml=Y&mid=a10301010000",
    },
    {
        "label": "삶의 만족도",
        "value": "6.7점",
        "basis": "2024 · 19~34세",
        "source": "청년 삶의 질 2025",
        "url": "https://mods.go.kr/board.es?act=view&bid=12316&list_no=442459&mid=a90106000000&nPage=1&ref_bid=&tag=",
    },
    {
        "label": "청년 실업률",
        "value": "7.7%",
        "basis": "2026.02 · 15~29세",
        "source": "2026년 2월 고용동향",
        "url": "https://sri.kostat.go.kr/board.es?act=view&bid=210&list_no=444083&mid=a10301030200&ref_bid=&tag=",
    },
    {
        "label": "쉬었음 청년",
        "value": "40.2만명",
        "basis": "2023.07 · 15~29세",
        "source": "복지부 지원방안",
        "url": "https://www.mohw.go.kr/board.es?act=view&bid=0027&list_no=1479278&mid=a10503000000&nPage=112&tag=",
    },
    {
        "label": "고립·은둔 위기청년",
        "value": "최대 54만명",
        "basis": "2022 조사 기반 · 19~34세",
        "source": "복지부·보사연 추정",
        "url": "https://www.mohw.go.kr/board.es?act=view&bid=0027&list_no=1479278&mid=a10503000000&nPage=112&tag=",
    },
]

LOCAL_POLICY_CORE_KEYWORDS = (
    "청년정책",
    "정책 발표",
    "정책 공약",
    "공약 발표",
    "시행계획",
    "종합계획",
    "기본계획",
    "지원정책",
    "지원사업",
    "청년 공약",
)

LOCAL_POLICY_ACTION_KEYWORDS = (
    "발표",
    "추진",
    "시행",
    "출범",
    "확대",
    "확정",
    "수립",
    "제시",
    "발의",
    "공약",
)

LOCAL_POLICY_STRONG_KEYWORDS = (
    "공약",
    "시행계획",
    "종합계획",
    "기본계획",
    "정책 발표",
    "정책 공약",
    "공약 발표",
)

LOCAL_POLICY_EXCLUDE_KEYWORDS = (
    "청년정책 네트워크",
    "청년정책네트워크",
    "청년정책 참여단",
    "청년정책참여단",
    "청년참여단",
    "청년위원회",
    "청년정책위원회",
    "청년정책조정위원회",
    "청년정책 발굴단",
    "청년정책발굴단",
)

LOCAL_GOVERNMENT_ACTOR_KEYWORDS = (
    "지자체",
    "시청",
    "도청",
    "군청",
    "구청",
    "시장",
    "도지사",
    "군수",
    "구청장",
    "서울시",
    "부산시",
    "대구시",
    "인천시",
    "광주시",
    "대전시",
    "울산시",
    "세종시",
    "경기도",
    "강원도",
    "충청북도",
    "충청남도",
    "전북특별자치도",
    "전라남도",
    "경상북도",
    "경상남도",
    "제주특별자치도",
)


BASE_CSS = """
  :root {
    --page-bg: #e8e1d8;
    --app-bg: #fcfaf6;
    --panel: #ffffff;
    --panel-soft: #f3ede6;
    --text: #1f2a33;
    --muted: #66717b;
    --line: rgba(31, 42, 51, 0.1);
    --accent: #395677;
    --accent-soft: rgba(57, 86, 119, 0.12);
    --accent-strong: #172536;
    --home-apricot: #dd9367;
    --home-apricot-soft: rgba(221, 147, 103, 0.18);
    --home-teal: #5f9188;
    --home-teal-soft: rgba(95, 145, 136, 0.18);
    --shadow: 0 18px 42px rgba(31, 42, 51, 0.08);
    --shadow-soft: 0 8px 20px rgba(31, 42, 51, 0.05);
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  [hidden] { display: none !important; }
  body {
    margin: 0;
    color: var(--text);
    background: linear-gradient(180deg, #f2eee8 0%, var(--page-bg) 100%);
    font-family: "Noto Sans KR", sans-serif;
    overflow-x: hidden;
  }
  a { color: inherit; text-decoration: none; }
  .shell {
    position: relative;
    max-width: 430px;
    min-height: 100vh;
    margin: 0 auto;
    padding: 16px 16px 98px;
    border: 1px solid rgba(31, 42, 51, 0.05);
    background: linear-gradient(180deg, rgba(252, 251, 247, 0.98) 0%, rgba(248, 246, 241, 0.98) 100%);
    box-shadow: var(--shadow);
  }
  .topbar {
    position: sticky;
    top: 0;
    z-index: 20;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    margin: -16px -16px 18px;
    padding: 16px;
    border-bottom: 1px solid var(--line);
    background: rgba(252, 251, 247, 0.92);
    backdrop-filter: blur(12px);
    box-shadow: 0 6px 18px rgba(31, 42, 51, 0.04);
    box-sizing: border-box;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }
  .brand-mark {
    position: relative;
    width: 42px;
    height: 42px;
    border-radius: 12px;
    border: 1px solid rgba(31, 42, 51, 0.12);
    background: linear-gradient(180deg, #ffffff 0%, #f2eee7 100%);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
  }
  .brand-mark::before,
  .brand-mark::after {
    content: "";
    position: absolute;
    left: 8px;
    right: 8px;
    border-radius: 999px;
    background: rgba(23, 33, 49, 0.18);
  }
  .brand-mark::before {
    top: 10px;
    height: 12px;
    border-radius: 4px;
    background: linear-gradient(180deg, #8fa6c2 0%, #304b68 100%);
  }
  .brand-mark::after {
    top: 26px;
    height: 2px;
    box-shadow: 0 -6px 0 rgba(23, 33, 49, 0.18), 0 6px 0 rgba(23, 33, 49, 0.12);
  }
  .brand-title {
    display: block;
    font-size: 1.52rem;
    font-weight: 800;
    letter-spacing: -0.04em;
  }
  .brand-sub {
    display: block;
    margin-top: 2px;
    color: var(--muted);
    font-size: 0.81rem;
    line-height: 1.3;
  }
  .header-side {
    display: grid;
    gap: 4px;
    justify-items: end;
    text-align: right;
    flex-shrink: 0;
    min-width: 0;
  }
  .topbar-side {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-left: auto;
    min-width: 0;
  }
  .header-side strong {
    font-size: 0.98rem;
    font-weight: 800;
    letter-spacing: -0.03em;
  }
  .header-side span {
    font-size: 0.72rem;
    color: var(--muted);
  }
  .guide-link {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 8px 12px;
    border-radius: 999px;
    border: 1px solid rgba(57, 86, 119, 0.14);
    background: rgba(57, 86, 119, 0.08);
    color: var(--accent);
    font-size: 0.78rem;
    font-weight: 800;
    white-space: nowrap;
  }
  .guide-link:hover {
    border-color: rgba(57, 86, 119, 0.22);
    background: rgba(57, 86, 119, 0.12);
    color: var(--accent-strong);
  }
  .guide-link.active {
    background: var(--accent-strong);
    border-color: transparent;
    color: white;
  }
  .nav { display: none; }
  .hero {
    display: grid;
    grid-template-columns: 1fr;
    gap: 14px;
    margin-bottom: 24px;
  }
  .hero-card, .status-card, .section-card, .article-card, .info-card, .list-card, .menu-update-card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 22px;
    box-shadow: 0 1px 0 rgba(255, 255, 255, 0.82), var(--shadow-soft);
  }
  .hero-card {
    padding: 24px;
    background: linear-gradient(180deg, rgba(244, 239, 233, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 7px 11px;
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent);
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: -0.01em;
  }
  h1, h2, h3 {
    margin: 0;
    line-height: 1.2;
    letter-spacing: -0.04em;
  }
  h1 {
    margin-top: 14px;
    font-size: 1.82rem;
    font-weight: 800;
  }
  h2 {
    font-size: 1.32rem;
    font-weight: 800;
  }
  h3 {
    font-size: 1.04rem;
    font-weight: 800;
  }
  .hero-feature-meta {
    margin-top: 12px;
    color: var(--muted);
    font-size: 0.78rem;
    line-height: 1.5;
  }
  .hero-copy {
    margin-top: 12px;
    color: var(--muted);
    font-size: 0.98rem;
    line-height: 1.72;
  }
  .page-intro-card {
    display: grid;
    gap: 10px;
    padding: 18px 20px;
    margin-bottom: 20px;
    border: 1px solid rgba(23, 37, 54, 0.14);
    border-radius: 22px;
    background:
      radial-gradient(circle at top right, rgba(143, 166, 194, 0.18), transparent 34%),
      linear-gradient(180deg, rgba(28, 40, 58, 0.98) 0%, rgba(23, 37, 54, 1) 100%);
    box-shadow: 0 18px 34px rgba(23, 37, 54, 0.16);
  }
  .page-intro-top {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .page-intro-badge {
    display: inline-flex;
    align-items: center;
    padding: 7px 12px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.12);
    color: rgba(255, 255, 255, 0.92);
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: -0.01em;
  }
  .page-intro-copy {
    margin: 0;
    color: rgba(240, 245, 251, 0.88);
    font-size: 0.96rem;
    line-height: 1.7;
    letter-spacing: -0.01em;
  }
  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 18px;
  }
  .button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 11px 14px;
    border-radius: 14px;
    border: 1px solid var(--line);
    background: var(--panel);
    font-size: 0.92rem;
    font-weight: 800;
  }
  .button.primary {
    background: var(--accent-strong);
    color: white;
    border-color: transparent;
  }
  .status-card {
    padding: 18px 18px 16px;
    display: grid;
    gap: 12px;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 245, 239, 0.94) 100%);
  }
  .status-grid, .overview-grid, .feature-grid, .article-grid, .menu-update-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 14px;
  }
  .stat {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    padding-top: 10px;
    border-top: 1px solid var(--line);
  }
  .stat:first-child {
    padding-top: 0;
    border-top: 0;
  }
  .stat-label {
    display: block;
    color: var(--muted);
    font-size: 0.76rem;
    font-weight: 600;
  }
  .stat-value {
    display: block;
    text-align: right;
    font-size: 0.9rem;
    font-weight: 700;
    line-height: 1.45;
  }
  .stat-value.meta {
    color: var(--muted);
    font-size: 0.8rem;
    font-weight: 600;
  }
  .stat-value.state-pill {
    padding: 6px 10px;
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent-strong);
    font-size: 0.8rem;
  }
  .status-note {
    margin: 0;
    color: var(--muted);
    font-size: 0.74rem;
    line-height: 1.5;
  }
  .section {
    margin-top: 26px;
  }
  .section-head {
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 12px;
    margin-bottom: 14px;
  }
  .section-head p {
    margin: 6px 0 0;
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.62;
  }
  .feature-grid, .article-grid, .menu-update-grid, .overview-grid {
    grid-template-columns: 1fr;
  }
  .section-card, .article-card, .info-card, .list-card {
    padding: 18px;
  }
  .section-card h3, .info-card h3, .list-card h3 {
    margin-bottom: 8px;
  }
  .section-card p, .info-card p, .list-card p {
    color: rgba(31, 42, 51, 0.7);
    line-height: 1.68;
    font-size: 0.91rem;
  }
  .mini-link {
    display: inline-flex;
    margin-top: 2px;
    color: var(--accent-strong);
    font-size: 0.88rem;
    font-weight: 800;
  }
  .article-title-link,
  .article-summary-link,
  .article-list-link {
    color: inherit;
    text-decoration: none;
  }
  .article-title-link:hover,
  .article-summary-link:hover,
  .article-list-link:hover strong,
  .article-list-link:hover span {
    color: var(--accent);
  }
  .article-list-item {
    display: grid;
    gap: 10px;
  }
  .article-list-link {
    display: grid;
    gap: 6px;
  }
  .article-list-overline {
    color: var(--accent);
    font-size: 0.74rem;
    font-style: normal;
    font-weight: 800;
    line-height: 1.35;
  }
  .article-actions,
  .article-list-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }
  .article-actions {
    margin-top: 14px;
  }
  .action-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 8px 12px;
    border: 1px solid rgba(31, 42, 51, 0.08);
    border-radius: 999px;
    background: rgba(249, 247, 242, 0.96);
    color: var(--accent-strong);
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
  }
  .action-button:hover {
    border-color: rgba(57, 86, 119, 0.18);
    background: rgba(57, 86, 119, 0.08);
    color: var(--accent);
  }
  .article-feedback {
    min-height: 1.2em;
    color: var(--muted);
    font-size: 0.75rem;
    line-height: 1.4;
  }
  .article-feedback.error {
    color: #b45309;
  }
  .filter-panel {
    display: grid;
    gap: 14px;
    background: linear-gradient(180deg, rgba(248, 245, 239, 0.96) 0%, rgba(255, 255, 255, 0.98) 100%);
  }
  .filter-stack {
    display: grid;
    gap: 16px;
  }
  .filter-group {
    display: grid;
    gap: 8px;
  }
  .filter-group-label {
    color: var(--accent-strong);
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.01em;
  }
  .filter-head {
    display: grid;
    gap: 8px;
  }
  .filter-head h3 {
    font-size: 1.02rem;
  }
  .filter-head p {
    margin: 0;
    color: var(--muted);
    font-size: 0.88rem;
    line-height: 1.6;
  }
  .filter-controls {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .filter-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 8px 12px;
    border: 1px solid rgba(31, 42, 51, 0.09);
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.92);
    color: var(--accent-strong);
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
  }
  .filter-button.active {
    border-color: transparent;
    background: var(--accent-strong);
    color: white;
  }
  .filter-status {
    color: var(--muted);
    font-size: 0.8rem;
    line-height: 1.55;
  }
  .date-picker-row {
    display: grid;
    gap: 10px;
  }
  .date-range-fields {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: stretch;
  }
  .date-input-wrap {
    display: grid;
    gap: 6px;
    min-width: min(100%, 220px);
    flex: 1 1 220px;
    padding: 12px 14px;
    border: 1px solid rgba(31, 42, 51, 0.08);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.96);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.78);
    cursor: pointer;
  }
  .date-picker-label {
    color: var(--muted);
    font-size: 0.72rem;
    font-weight: 700;
    line-height: 1;
  }
  .date-input {
    width: 100%;
    border: 0;
    background: transparent;
    color: var(--text);
    font: inherit;
    font-size: 0.92rem;
    font-weight: 700;
    padding: 0;
  }
  .date-input:focus {
    outline: none;
  }
  .news-intro-card {
    display: grid;
    gap: 10px;
    padding: 18px 20px;
  }
  .news-intro-copy {
    margin: 0;
    color: var(--muted);
    font-size: 0.95rem;
    line-height: 1.65;
  }
  .menu-update-card {
    padding: 18px;
    display: grid;
    gap: 12px;
  }
  .menu-update-top {
    display: grid;
    gap: 8px;
  }
  .menu-update-head {
    display: grid;
    gap: 8px;
  }
  .menu-update-card h3 {
    margin-top: 0;
    font-size: 1.2rem;
  }
  .menu-update-copy {
    margin: 0;
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.58;
  }
  .menu-meta-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 12px;
  }
  .menu-meta {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--muted);
  }
  .menu-meta strong {
    margin-bottom: 0;
    font-size: 0.74rem;
    font-weight: 600;
  }
  .menu-meta span {
    font-size: 0.78rem;
    font-weight: 500;
    line-height: 1.4;
  }
  .menu-links {
    display: flex;
  }
  .menu-links .button {
    width: 100%;
  }
  .article-card {
    display: grid;
    align-content: start;
    gap: 14px;
  }
  .article-meta {
    display: grid;
    gap: 8px;
  }
  .article-meta-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .meta-pill {
    display: inline-flex;
    align-items: center;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 800;
    line-height: 1;
  }
  .meta-pill.primary {
    background: var(--accent-soft);
    color: var(--accent-strong);
  }
  .meta-pill.subtle {
    background: rgba(245, 241, 234, 0.96);
    color: var(--muted);
  }
  .article-byline {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    color: var(--muted);
    font-size: 0.77rem;
    line-height: 1.5;
  }
  .article-byline .meta-divider {
    opacity: 0.45;
  }
  .article-byline .meta-item {
    display: inline-flex;
    align-items: center;
  }
  .badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 0;
  }
  .badge {
    display: inline-flex;
    padding: 5px 8px;
    border-radius: 999px;
    background: rgba(245, 241, 234, 0.96);
    color: var(--accent);
    font-size: 0.72rem;
    font-weight: 700;
  }
  .article-summary {
    margin: 0;
    color: rgba(31, 42, 51, 0.8);
    font-size: 0.95rem;
    line-height: 1.68;
    white-space: pre-wrap;
  }
  .list {
    display: grid;
    gap: 10px;
    margin-top: 0;
  }
  .list-item {
    padding: 14px 16px;
    border-radius: 18px;
    border: 1px solid rgba(31, 42, 51, 0.08);
    background: linear-gradient(180deg, rgba(250, 248, 244, 0.96) 0%, rgba(255, 255, 255, 0.98) 100%);
  }
  .list-item strong {
    display: block;
    margin-bottom: 5px;
    font-size: 0.98rem;
    line-height: 1.38;
  }
  .list-item span {
    display: block;
    color: var(--muted);
    font-size: 0.84rem;
    line-height: 1.55;
  }
  .footer-note {
    margin-top: 28px;
    color: var(--muted);
    font-size: 0.84rem;
    text-align: center;
  }
  .home-section-card {
    padding: 18px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 24px;
    box-shadow: var(--shadow-soft);
    display: grid;
    align-content: start;
  }
  .home-section-card.featured {
    background: linear-gradient(180deg, rgba(221, 147, 103, 0.08) 0%, rgba(255, 255, 255, 1) 100%);
  }
  .home-briefing-grid {
    display: grid;
    gap: 18px;
    margin-top: 10px;
  }
  .home-briefing-card {
    padding: 24px;
    border-radius: 26px;
    border: 1px solid var(--line);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.99) 0%, rgba(249, 246, 241, 0.97) 100%);
    box-shadow: 0 1px 0 rgba(255, 255, 255, 0.82), var(--shadow-soft);
    display: grid;
    align-content: start;
    gap: 18px;
    position: relative;
    isolation: isolate;
    overflow: hidden;
  }
  .home-briefing-card > * {
    position: relative;
    z-index: 1;
  }
  .home-briefing-card::before,
  .home-briefing-card::after {
    content: "";
    position: absolute;
    pointer-events: none;
    z-index: 0;
  }
  .home-briefing-card.lead-arch {
    border-color: rgba(23, 37, 54, 0.18);
    border-radius: 40px 108px 40px 50px;
    background:
      radial-gradient(circle at top left, rgba(95, 145, 136, 0.18), transparent 30%),
      radial-gradient(circle at top right, rgba(221, 147, 103, 0.18), transparent 28%),
      linear-gradient(180deg, rgba(28, 40, 58, 0.98) 0%, rgba(23, 37, 54, 1) 100%);
    box-shadow: 0 22px 42px rgba(23, 37, 54, 0.18);
  }
  .home-briefing-card.lead-arch::before {
    top: -62px;
    right: -28px;
    width: 190px;
    height: 190px;
    border-radius: 0 0 0 170px;
    background: radial-gradient(circle, rgba(221, 147, 103, 0.28) 0%, rgba(221, 147, 103, 0) 72%);
  }
  .home-briefing-card.lead-arch::after {
    left: -64px;
    bottom: -88px;
    width: 180px;
    height: 180px;
    border-radius: 999px;
    background: radial-gradient(circle, rgba(95, 145, 136, 0.18) 0%, rgba(95, 145, 136, 0) 74%);
  }
  .home-briefing-card.digest-organic {
    border-color: var(--home-apricot-soft);
    border-radius: 34px 30px 88px 34px;
    background:
      radial-gradient(circle at top right, rgba(221, 147, 103, 0.2), transparent 30%),
      radial-gradient(circle at bottom left, rgba(95, 145, 136, 0.12), transparent 28%),
      linear-gradient(180deg, rgba(252, 245, 239, 0.99) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-briefing-card.digest-organic::before {
    top: -38px;
    right: -26px;
    width: 132px;
    height: 132px;
    border-radius: 58% 42% 54% 46% / 42% 60% 40% 58%;
    background: rgba(255, 255, 255, 0.72);
  }
  .home-briefing-card.support-pill {
    border-color: var(--home-teal-soft);
    border-radius: 86px 30px 42px 86px;
    background:
      radial-gradient(circle at top left, rgba(95, 145, 136, 0.22), transparent 26%),
      radial-gradient(circle at bottom right, rgba(221, 147, 103, 0.12), transparent 30%),
      linear-gradient(180deg, rgba(250, 247, 241, 0.99) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-briefing-card.support-pill::after {
    left: -58px;
    bottom: -82px;
    width: 210px;
    height: 210px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.42);
  }
  .home-briefing-card.footer-warm {
    padding: 0;
    gap: 0;
    border-color: var(--home-apricot-soft);
    border-radius: 36px 36px 110px 44px;
    background:
      radial-gradient(circle at top right, rgba(221, 147, 103, 0.22), transparent 28%),
      radial-gradient(circle at bottom left, rgba(95, 145, 136, 0.1), transparent 30%),
      linear-gradient(180deg, rgba(249, 240, 233, 0.99) 0%, rgba(255, 255, 255, 0.99) 100%);
    color: var(--text);
  }
  .home-briefing-card.footer-warm::after {
    right: -44px;
    bottom: -70px;
    width: 150px;
    height: 150px;
    border-radius: 999px;
    background: rgba(221, 147, 103, 0.16);
  }
  .home-briefing-date {
    color: var(--accent-strong);
    font-size: 0.82rem;
    font-weight: 800;
    letter-spacing: 0.01em;
  }
  .home-briefing-title {
    margin: 0;
    font-size: clamp(2.5rem, 8vw, 4.8rem);
    line-height: 0.95;
    letter-spacing: -0.07em;
    max-width: none;
    white-space: nowrap;
  }
  .home-briefing-copy {
    margin: 0;
    color: var(--text);
    font-size: 1rem;
    line-height: 1.72;
    max-width: 42ch;
    word-break: keep-all;
    overflow-wrap: normal;
  }
  .home-briefing-card.lead-arch .home-briefing-date {
    color: rgba(255, 255, 255, 0.74);
  }
  .home-briefing-card.lead-arch .home-briefing-title {
    color: white;
  }
  .home-briefing-card.lead-arch .home-briefing-copy {
    color: rgba(240, 245, 251, 0.9);
  }
  .home-briefing-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 14px;
    padding-top: 14px;
    border-top: 1px solid rgba(23, 33, 49, 0.08);
    color: var(--muted);
    font-size: 0.78rem;
    line-height: 1.5;
  }
  .home-briefing-head {
    display: grid;
    gap: 6px;
  }
  .home-briefing-head h2 {
    margin: 0;
    font-size: 1.16rem;
    letter-spacing: -0.03em;
  }
  .home-briefing-head p {
    margin: 0;
    color: var(--muted);
    font-size: 0.88rem;
    line-height: 1.58;
  }
  .home-glance-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }
  .home-glance-item {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 8px;
    min-height: 110px;
    aspect-ratio: 1 / 1;
    padding: 16px 12px;
    border-radius: 999px;
    border: 1px solid rgba(23, 33, 49, 0.08);
    background:
      linear-gradient(180deg, rgba(250, 248, 243, 0.96) 0%, rgba(255, 255, 255, 0.99) 100%);
    text-align: center;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.88);
  }
  .home-glance-item.warm {
    border-color: var(--home-apricot-soft);
    background:
      radial-gradient(circle at top, rgba(221, 147, 103, 0.2), transparent 44%),
      linear-gradient(180deg, rgba(251, 241, 233, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-glance-item.neutral {
    background:
      radial-gradient(circle at top, rgba(57, 86, 119, 0.12), transparent 44%),
      linear-gradient(180deg, rgba(247, 243, 239, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-glance-item.teal {
    border-color: var(--home-teal-soft);
    background:
      radial-gradient(circle at top, rgba(95, 145, 136, 0.2), transparent 44%),
      linear-gradient(180deg, rgba(238, 247, 244, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-glance-label {
    color: var(--muted);
    font-size: 0.75rem;
    font-weight: 800;
    line-height: 1.3;
  }
  .home-glance-value {
    font-size: 1.72rem;
    font-weight: 800;
    letter-spacing: -0.05em;
    line-height: 1;
    color: var(--accent-strong);
  }
  .home-glance-links {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }
  .home-glance-links .mini-link {
    margin-top: 0;
    padding: 10px 14px;
    border-radius: 999px;
    border: 1px solid rgba(23, 33, 49, 0.08);
    background: rgba(255, 255, 255, 0.88);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82);
  }
  .home-glance-links .mini-link:nth-child(1) {
    border-color: var(--home-apricot-soft);
    background: rgba(251, 235, 224, 0.96);
  }
  .home-glance-links .mini-link:nth-child(2) {
    border-color: rgba(57, 86, 119, 0.14);
    background: rgba(241, 245, 250, 0.96);
  }
  .home-glance-links .mini-link:nth-child(3) {
    border-color: var(--home-teal-soft);
    background: rgba(233, 244, 240, 0.96);
  }
  .home-briefing-divider {
    height: 1px;
    background: rgba(23, 33, 49, 0.08);
  }
  .home-briefing-card.digest-organic .home-briefing-divider {
    background: rgba(221, 147, 103, 0.16);
  }
  .home-briefing-card.digest-organic .home-urgent-list,
  .home-briefing-card.digest-organic .home-urgent-item {
    border-color: rgba(221, 147, 103, 0.16);
  }
  .home-briefing-subhead {
    display: grid;
    gap: 6px;
  }
  .home-briefing-subhead h3 {
    margin: 0;
    font-size: 1.02rem;
    letter-spacing: -0.02em;
  }
  .home-briefing-subhead p {
    margin: 0;
    color: var(--muted);
    font-size: 0.84rem;
    line-height: 1.58;
  }
  .home-urgent-list {
    display: grid;
    gap: 0;
    border-top: 1px solid rgba(23, 33, 49, 0.08);
  }
  .home-urgent-item {
    padding: 16px 0;
    border-bottom: 1px solid rgba(23, 33, 49, 0.08);
  }
  .home-urgent-link {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 14px;
    align-items: start;
  }
  .home-urgent-rank {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: 999px;
    background: rgba(221, 147, 103, 0.16);
    color: var(--accent-strong);
    font-size: 0.8rem;
    font-weight: 800;
    line-height: 1;
  }
  .home-urgent-text {
    display: grid;
    gap: 5px;
  }
  .home-urgent-text strong {
    font-size: 1rem;
    line-height: 1.48;
    letter-spacing: -0.02em;
  }
  .home-urgent-meta {
    color: var(--muted);
    font-size: 0.82rem;
    line-height: 1.5;
  }
  .home-support-version {
    display: inline-flex;
    align-items: center;
    width: fit-content;
    padding: 7px 12px;
    border-radius: 999px;
    border: 1px solid transparent;
    background: rgba(23, 37, 54, 0.94);
    color: rgba(255, 255, 255, 0.96);
    font-size: 0.78rem;
    font-weight: 800;
  }
  .home-support-footer {
    display: grid;
    gap: 14px;
    padding: 22px;
    color: var(--text);
  }
  .home-support-copy {
    margin: 0;
    color: var(--text);
    font-size: 0.95rem;
    line-height: 1.78;
  }
  .home-support-copy.secondary {
    color: var(--muted);
    font-size: 0.86rem;
  }
  .home-support-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 14px;
    padding-top: 14px;
    border-top: 1px solid rgba(23, 33, 49, 0.08);
    color: var(--muted);
    font-size: 0.78rem;
    line-height: 1.5;
  }
  .home-support-links {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }
  .home-support-links a {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 10px 14px;
    border-radius: 999px;
    border: 1px solid rgba(23, 33, 49, 0.08);
    background: rgba(255, 255, 255, 0.74);
    color: var(--accent-strong);
    font-size: 0.84rem;
    font-weight: 700;
    text-decoration: none;
  }
  .home-support-links a:first-child {
    background: rgba(241, 245, 250, 0.92);
    border-color: rgba(57, 86, 119, 0.14);
  }
  .home-support-links a:last-child {
    background: rgba(251, 235, 224, 0.94);
    border-color: var(--home-apricot-soft);
  }
  .home-support-credit {
    margin: 2px 0 0;
    color: rgba(102, 113, 123, 0.9);
    font-size: 0.77rem;
    line-height: 1.55;
    text-align: right;
  }
  .home-support-metrics {
    display: grid;
    gap: 12px;
  }
  .home-support-metrics h3 {
    margin: 0;
    font-size: 1.08rem;
    letter-spacing: -0.02em;
    color: var(--accent-strong);
  }
  .home-support-metrics-grid {
    display: grid;
    gap: 10px;
  }
  .home-support-metric-item {
    display: grid;
    gap: 8px;
    padding: 14px 16px;
    border-radius: 20px;
    border: 1px solid rgba(23, 33, 49, 0.08);
    background: rgba(255, 255, 255, 0.92);
    box-shadow: 0 6px 16px rgba(23, 33, 49, 0.04);
  }
  .home-support-metric-label {
    color: var(--muted);
    font-size: 0.74rem;
    font-weight: 800;
    line-height: 1.3;
  }
  .home-support-metric-value {
    font-size: 1.32rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    line-height: 1;
    color: var(--accent-strong);
  }
  .home-support-metric-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 10px;
    color: var(--muted);
    font-size: 0.74rem;
    line-height: 1.5;
  }
  .home-support-metric-meta a {
    color: var(--accent-strong);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .home-support-note {
    margin: 0;
    color: var(--muted);
    font-size: 0.74rem;
    line-height: 1.55;
  }
  .home-support-metric-item:nth-child(1) {
    background:
      linear-gradient(180deg, rgba(250, 238, 229, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-support-metric-item:nth-child(2) {
    background:
      linear-gradient(180deg, rgba(236, 246, 242, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-support-metric-item:nth-child(3) {
    background:
      linear-gradient(180deg, rgba(244, 243, 239, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-support-metric-item:nth-child(4) {
    background:
      linear-gradient(180deg, rgba(251, 239, 231, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-support-metric-item:nth-child(5) {
    background:
      linear-gradient(180deg, rgba(236, 246, 242, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-support-metric-item:nth-child(6) {
    background:
      linear-gradient(180deg, rgba(245, 243, 239, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .youth-metrics-card {
    display: none;
  }
  .youth-metrics-head {
    display: grid;
    gap: 8px;
    margin-bottom: 16px;
  }
  .youth-metrics-head h2 {
    margin: 0;
    font-size: 1.22rem;
    letter-spacing: -0.03em;
  }
  .youth-metrics-head p {
    margin: 0;
    color: var(--muted);
    font-size: 0.9rem;
    line-height: 1.62;
  }
  .youth-metrics-grid {
    display: grid;
    gap: 12px;
  }
  .youth-metric-item {
    display: grid;
    gap: 10px;
    padding: 16px;
    border-radius: 22px;
    border: 1px solid rgba(23, 33, 49, 0.08);
    background: rgba(255, 255, 255, 0.9);
  }
  .youth-metric-label {
    color: var(--muted);
    font-size: 0.78rem;
    font-weight: 800;
    line-height: 1.3;
  }
  .youth-metric-value {
    font-size: 1.54rem;
    font-weight: 800;
    letter-spacing: -0.05em;
    line-height: 1;
  }
  .youth-metric-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 10px;
    color: var(--muted);
    font-size: 0.76rem;
    line-height: 1.5;
  }
  .youth-metric-source {
    color: var(--accent-strong);
    font-weight: 700;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .youth-metrics-note {
    margin: 14px 0 0;
    color: var(--muted);
    font-size: 0.76rem;
    line-height: 1.55;
  }
  .home-welcome-card {
    background:
      radial-gradient(circle at top left, rgba(57, 86, 119, 0.08), transparent 32%),
      linear-gradient(180deg, rgba(250, 247, 241, 0.99) 0%, rgba(255, 255, 255, 0.99) 100%);
    overflow: hidden;
  }
  .home-section-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 10px;
  }
  .home-news-card .home-section-head,
  .home-highlight-card .home-section-head {
    margin-bottom: 12px;
  }
  .home-section-title {
    display: grid;
    gap: 8px;
  }
  .home-section-title h2,
  .home-section-title h3 {
    margin: 0;
  }
  .home-section-copy {
    margin: 0;
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.6;
  }
  .home-meta-line {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 12px;
    margin: 10px 0 0;
    color: var(--muted);
    font-size: 0.76rem;
    line-height: 1.45;
  }
  .home-meta-line span {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .home-meta-line.home-meta-footer {
    margin-top: 18px;
    padding-top: 12px;
    border-top: 1px solid rgba(23, 33, 49, 0.08);
  }
  .home-section-card .list {
    margin-top: 12px;
  }
  .home-actions {
    margin-top: 14px;
  }
  .home-actions .button {
    width: auto;
  }
  .home-news-card .list-item span,
  .home-highlight-card .list-item span {
    font-size: 0.82rem;
  }
  .home-highlight-card {
    background: linear-gradient(180deg, rgba(57, 86, 119, 0.06) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-highlight-card .list-item {
    background: rgba(255, 255, 255, 0.96);
  }
  .home-spotlight-card {
    background:
      radial-gradient(circle at top left, rgba(57, 86, 119, 0.08), transparent 34%),
      linear-gradient(180deg, rgba(250, 247, 241, 0.99) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-spotlight-layout {
    display: grid;
    grid-template-columns: 1fr;
    gap: 22px;
    margin-top: 10px;
  }
  .hero.home-hero {
    grid-template-columns: 1fr;
  }
  .spotlight-main {
    display: grid;
    gap: 20px;
    align-content: start;
  }
  .spotlight-main .home-section-head {
    margin: 0;
    padding-bottom: 18px;
    border-bottom: 1px solid rgba(23, 33, 49, 0.08);
  }
  .spotlight-focus {
    display: grid;
    gap: 14px;
    padding: 0;
    border: 0;
    background: none;
  }
  .spotlight-stories {
    display: grid;
    gap: 0;
    border-top: 1px solid rgba(23, 33, 49, 0.08);
  }
  .spotlight-story {
    padding: 16px 0;
    border-bottom: 1px solid rgba(23, 33, 49, 0.08);
  }
  .spotlight-story-link {
    display: grid;
    gap: 5px;
  }
  .spotlight-story-kicker {
    color: var(--accent-strong);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }
  .spotlight-story strong {
    display: block;
    font-size: 1.04rem;
    line-height: 1.42;
    letter-spacing: -0.03em;
  }
  .spotlight-story span {
    color: var(--muted);
    font-size: 0.84rem;
    line-height: 1.55;
  }
  .spotlight-story:first-child strong {
    font-size: 1.24rem;
    line-height: 1.34;
  }
  .spotlight-story:hover strong {
    color: var(--accent-strong);
  }
  .spotlight-panel-title {
    display: block;
    margin-bottom: 0;
    color: var(--accent-strong);
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }
  .spotlight-notes {
    display: grid;
    gap: 16px;
    position: relative;
    padding-left: 22px;
  }
  .spotlight-notes::before {
    content: "";
    position: absolute;
    left: 5px;
    top: 6px;
    bottom: 6px;
    width: 1px;
    background: linear-gradient(180deg, rgba(57, 86, 119, 0.32) 0%, rgba(23, 33, 49, 0.08) 100%);
  }
  .spotlight-note {
    position: relative;
    padding: 0 0 0 12px;
    border: 0;
    background: none;
  }
  .spotlight-note::before {
    content: "";
    position: absolute;
    left: -22px;
    top: 7px;
    width: 12px;
    height: 12px;
    border-radius: 999px;
    background: linear-gradient(180deg, rgba(110, 139, 173, 0.96) 0%, rgba(23, 37, 54, 0.96) 100%);
    box-shadow: 0 0 0 5px rgba(57, 86, 119, 0.08);
  }
  .spotlight-note strong {
    display: block;
    font-size: 1rem;
    line-height: 1.35;
    letter-spacing: -0.02em;
  }
  .spotlight-note span {
    display: block;
    margin-top: 5px;
    color: var(--muted);
    font-size: 0.84rem;
    line-height: 1.6;
  }
  .spotlight-side {
    display: grid;
    gap: 18px;
    align-content: start;
  }
  .spotlight-panel {
    display: grid;
    gap: 18px;
    padding: 22px 0 0;
    border: 0;
    border-top: 1px solid rgba(23, 33, 49, 0.08);
    background: none;
  }
  .spotlight-panel-title.secondary {
    margin-top: 4px;
  }
  .spotlight-routes {
    display: grid;
    gap: 0;
    border-top: 1px solid rgba(23, 33, 49, 0.08);
  }
  .spotlight-route {
    display: grid;
    gap: 4px;
    position: relative;
    padding: 14px 0 14px 22px;
    border: 0;
    border-bottom: 1px solid rgba(23, 33, 49, 0.08);
    background: none;
    transition: transform 0.18s ease, color 0.18s ease;
  }
  .spotlight-route::before {
    content: ">";
    position: absolute;
    left: 0;
    top: 14px;
    color: rgba(57, 86, 119, 0.8);
    font-size: 0.88rem;
    font-weight: 700;
  }
  .spotlight-route:hover {
    transform: translateX(3px);
  }
  .spotlight-route strong {
    font-size: 0.98rem;
    line-height: 1.35;
    letter-spacing: -0.02em;
  }
  .spotlight-route span {
    color: var(--muted);
    font-size: 0.82rem;
    line-height: 1.5;
  }
  .spotlight-lead-title {
    margin: 0;
    font-size: 2.35rem;
    line-height: 1.08;
    letter-spacing: -0.05em;
    max-width: 12ch;
  }
  .spotlight-lead-title span {
    display: block;
  }
  .spotlight-lead-summary {
    margin: 0;
    color: var(--muted);
    font-size: 1rem;
    line-height: 1.7;
    max-width: 54ch;
  }
  .spotlight-update-inline {
    display: grid;
    gap: 4px;
    margin-top: 16px;
    padding: 14px 16px 0 0;
    border-top: 1px solid rgba(23, 33, 49, 0.08);
    max-width: 68ch;
  }
  .spotlight-update-label {
    color: var(--accent-strong);
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.01em;
  }
  .spotlight-update-copy {
    margin: 0;
    color: var(--text);
    font-size: 0.94rem;
    font-weight: 700;
    line-height: 1.55;
    letter-spacing: -0.01em;
  }
  .spotlight-update-meta {
    margin: 0;
    color: var(--muted);
    font-size: 0.8rem;
    line-height: 1.5;
  }
  .highlight-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
    gap: 12px;
    margin-top: 0;
  }
  .highlight-stat {
    aspect-ratio: 1 / 1;
    min-height: 112px;
    padding: 14px;
    border-radius: 999px;
    border: 1px solid rgba(23, 33, 49, 0.08);
    background:
      radial-gradient(circle at 30% 30%, rgba(143, 166, 194, 0.18), transparent 48%),
      linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(245, 243, 239, 0.96) 100%);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
  }
  .highlight-stat-label {
    display: block;
    color: var(--muted);
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.01em;
  }
  .highlight-stat-value {
    display: block;
    margin-top: 6px;
    font-size: 1.4rem;
    font-weight: 800;
    letter-spacing: -0.04em;
  }
  .welcome-kicker {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 7px 12px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid rgba(23, 33, 49, 0.08);
    color: var(--accent-strong);
    font-size: 0.78rem;
    font-weight: 800;
  }
  .welcome-kicker::before {
    content: "";
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: linear-gradient(180deg, #8fa6c2 0%, #304b68 100%);
    box-shadow: 0 0 0 4px rgba(57, 86, 119, 0.12);
  }
  .welcome-copy {
    margin: 0;
    color: var(--muted);
    font-size: 0.95rem;
    line-height: 1.72;
    max-width: 58ch;
  }
  .welcome-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 12px;
    margin-top: 16px;
  }
  .welcome-panel {
    display: grid;
    gap: 6px;
    padding: 16px 16px 15px;
    border-radius: 20px;
    border: 1px solid rgba(23, 33, 49, 0.08);
    background: rgba(255, 255, 255, 0.84);
    box-shadow: 0 10px 24px rgba(23, 33, 49, 0.06);
  }
  .welcome-panel-label {
    color: var(--accent);
    font-size: 0.73rem;
    font-weight: 800;
    letter-spacing: 0.01em;
    text-transform: uppercase;
  }
  .welcome-panel strong {
    display: block;
    font-size: 1rem;
    line-height: 1.38;
    letter-spacing: -0.02em;
  }
  .welcome-panel span {
    display: block;
    color: var(--muted);
    font-size: 0.84rem;
    line-height: 1.58;
  }
  .welcome-note {
    margin-top: 16px;
    padding: 16px 18px;
    border-radius: 20px;
    background: linear-gradient(180deg, rgba(28, 39, 54, 0.96) 0%, rgba(23, 33, 49, 1) 100%);
    color: rgba(255, 255, 255, 0.92);
  }
  .welcome-note strong {
    display: block;
    margin-bottom: 6px;
    font-size: 0.96rem;
  }
  .welcome-note p {
    margin: 0;
    color: rgba(255, 255, 255, 0.74);
    font-size: 0.84rem;
    line-height: 1.58;
  }
  .home-footer {
    padding: 16px 18px;
    background: linear-gradient(180deg, rgba(28, 39, 54, 0.98) 0%, rgba(23, 33, 49, 1) 100%);
    border-radius: 24px;
    color: rgba(255, 255, 255, 0.94);
    box-shadow: var(--shadow-soft);
  }
  .home-status-note {
    margin: 8px 2px 0;
    color: var(--muted);
    font-size: 0.75rem;
    line-height: 1.6;
    text-align: center;
  }
  .guide-overlay {
    position: fixed;
    inset: 0;
    z-index: 80;
    display: grid;
    place-items: center;
    padding: 20px;
    background: rgba(31, 42, 51, 0.36);
    backdrop-filter: blur(8px);
  }
  .guide-dialog {
    width: min(100%, 560px);
    padding: 22px;
    border-radius: 26px;
    border: 1px solid rgba(255, 255, 255, 0.5);
    background:
      radial-gradient(circle at top left, rgba(57, 86, 119, 0.08), transparent 30%),
      linear-gradient(180deg, rgba(252, 251, 247, 0.99) 0%, rgba(248, 245, 239, 0.99) 100%);
    box-shadow: 0 24px 56px rgba(31, 42, 51, 0.16);
  }
  .guide-dialog h2 {
    margin-top: 14px;
    font-size: 1.62rem;
  }
  .guide-dialog p {
    margin: 12px 0 0;
    color: var(--muted);
    font-size: 0.95rem;
    line-height: 1.7;
  }
  .guide-dialog .list {
    margin-top: 16px;
  }
  .guide-dialog .hero-actions {
    margin-top: 18px;
  }
  .home-footer h3 {
    margin: 0 0 6px;
    font-size: 1rem;
    color: white;
  }
  .home-footer p {
    margin: 0;
    color: rgba(255, 255, 255, 0.72);
    font-size: 0.84rem;
    line-height: 1.55;
  }
  .home-footer-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 12px;
    margin-top: 12px;
    font-size: 0.78rem;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.82);
  }
  .home-footer a {
    color: white;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .bottom-nav {
    position: fixed;
    left: 50%;
    bottom: 0;
    transform: translateX(-50%);
    z-index: 30;
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 4px;
    width: min(100%, 430px);
    padding: 10px 10px calc(10px + env(safe-area-inset-bottom));
    border-top: 1px solid var(--line);
    background: rgba(252, 251, 247, 0.98);
    box-shadow: 0 -12px 28px rgba(31, 42, 51, 0.06);
    box-sizing: border-box;
  }
  .bottom-nav a {
    display: grid;
    justify-items: center;
    gap: 5px;
    padding: 4px 0;
    color: var(--muted);
    font-size: 0.64rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    min-width: 0;
  }
  .bottom-nav a span {
    white-space: nowrap;
  }
  .bottom-nav a::before {
    content: attr(data-icon);
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 999px;
    background: var(--panel-soft);
    color: var(--accent-strong);
    font-size: 0.72rem;
    font-weight: 800;
  }
  .bottom-nav a.active {
    color: var(--accent-strong);
  }
  .bottom-nav a.active::before {
    background: var(--accent-strong);
    color: white;
  }
  body.is-guide-open {
    overflow: hidden;
  }
  @media (min-width: 560px) {
    body {
      padding: 18px 0 112px;
    }
    .shell {
      min-height: calc(100vh - 36px);
      border-radius: 30px;
    }
    .bottom-nav {
      bottom: 18px;
      border: 1px solid var(--line);
      border-radius: 24px;
    }
  }
  @media (min-width: 980px) {
    body {
      padding: 0;
      background: linear-gradient(180deg, #efe9e1 0%, #e8e1d8 100%);
    }
    .shell {
      max-width: min(100vw, 1440px);
      min-height: 100vh;
      padding: 28px 32px 56px;
      border-radius: 0;
      box-shadow: none;
      background:
        radial-gradient(circle at top left, rgba(57, 86, 119, 0.07), transparent 28%),
        linear-gradient(180deg, #fcfaf6 0%, #f6f2eb 100%);
    }
    .topbar {
      margin: -28px -32px 24px;
      padding: 18px 32px;
    }
    .section {
      margin-top: 42px;
    }
    .section-head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 18px;
      margin-bottom: 20px;
      padding: 0 4px;
    }
    .section-head > div {
      max-width: 72ch;
    }
    .section-head p {
      margin-top: 10px;
    }
    .section-head .mini-link {
      margin-top: 0;
      padding: 10px 14px;
      border-radius: 999px;
      border: 1px solid rgba(57, 86, 119, 0.16);
      background: rgba(57, 86, 119, 0.08);
      white-space: nowrap;
    }
    .topbar-side {
      gap: 18px;
    }
    .nav {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .nav a {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 14px;
      border-radius: 999px;
      color: var(--muted);
      font-size: 0.88rem;
      font-weight: 700;
      border: 1px solid transparent;
    }
    .nav a:hover {
      background: var(--panel-soft);
      color: var(--text);
    }
    .nav a.active {
      background: var(--accent-strong);
      color: white;
    }
    .hero {
      grid-template-columns: 1.6fr 0.95fr;
      align-items: start;
      gap: 22px;
      margin-bottom: 32px;
    }
    .hero-card,
    .status-card,
    .home-section-card,
    .section-card,
    .article-card,
    .info-card,
    .list-card,
    .menu-update-card {
      padding: 24px 26px;
    }
    .home-meta-line {
      margin: 14px 0 2px;
      gap: 8px 18px;
    }
    .welcome-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .highlight-stats {
      grid-template-columns: repeat(3, minmax(96px, 1fr));
      gap: 12px;
    }
    .home-briefing-grid {
      grid-template-columns: minmax(0, 1.06fr) minmax(320px, 0.94fr);
      grid-template-areas:
        "lead digest"
        "support digest"
        "footer footer";
      align-items: stretch;
    }
    .home-briefing-card.lead {
      grid-area: lead;
      min-height: 320px;
    }
    .home-briefing-card.digest {
      grid-area: digest;
    }
    .home-briefing-card.support {
      grid-area: support;
    }
    .home-briefing-card.footer {
      grid-area: footer;
    }
    .home-briefing-card.lead-arch {
      border-radius: 46px 132px 44px 58px;
    }
    .home-briefing-card.digest-organic {
      border-radius: 40px 34px 104px 40px;
    }
    .home-briefing-card.support-pill {
      border-radius: 96px 34px 46px 96px;
    }
    .home-briefing-card.footer-warm {
      border-radius: 38px 38px 128px 48px;
    }
    .home-spotlight-layout {
      grid-template-columns: minmax(0, 1.24fr) minmax(280px, 0.82fr);
      gap: 18px;
    }
    .spotlight-notes {
      grid-template-columns: 1fr;
    }
    .list {
      gap: 14px;
      margin-top: 16px;
    }
    .list-item {
      padding: 18px 22px;
    }
    .article-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }
    .feature-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 18px;
    }
    .youth-metrics-grid {
      grid-template-columns: repeat(5, minmax(0, 1fr));
    }
    .home-support-metrics-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .home-dual-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 28px;
      align-items: start;
      margin-top: 28px;
    }
    .home-dual-grid .section {
      margin-top: 0;
      display: grid;
      align-content: start;
    }
    .home-footer {
      padding: 20px 24px;
      margin-top: 6px;
    }
    .bottom-nav {
      display: none;
    }
  }
  @media (max-width: 559px) {
    .topbar {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: start;
      gap: 12px;
    }
    .topbar-side {
      display: grid;
      justify-items: end;
      align-content: start;
      gap: 8px;
      margin-left: 0;
    }
    .header-side strong {
      font-size: 0.9rem;
      line-height: 1.15;
      white-space: nowrap;
    }
    .header-side span {
      font-size: 0.68rem;
      line-height: 1.2;
      white-space: nowrap;
    }
    .home-briefing-grid,
    .home-briefing-card,
    .home-glance-grid,
    .home-urgent-link {
      min-width: 0;
    }
    .home-briefing-card {
      padding: 20px;
      border-radius: 24px;
    }
    .home-briefing-card.lead-arch {
      border-radius: 32px 78px 32px 38px;
    }
    .home-briefing-card.digest-organic {
      border-radius: 28px 24px 64px 28px;
    }
    .home-briefing-card.support-pill {
      border-radius: 58px 24px 32px 58px;
    }
    .home-briefing-card.footer-warm {
      border-radius: 28px 28px 72px 34px;
    }
    .home-briefing-title {
      font-size: clamp(2.05rem, 9.8vw, 3.25rem);
      letter-spacing: -0.05em;
    }
    .home-briefing-copy {
      max-width: 100%;
      font-size: 0.98rem;
    }
    .home-glance-item {
      min-height: 96px;
      padding: 14px 10px;
    }
    .bottom-nav {
      width: calc(100% - 8px);
      padding-left: 8px;
      padding-right: 8px;
      gap: 2px;
    }
    .bottom-nav a {
      font-size: 0.58rem;
    }
    .bottom-nav a span {
      white-space: normal;
      text-align: center;
      line-height: 1.1;
    }
  }
  @media (max-width: 380px) {
    .brand-title {
      font-size: 1.38rem;
    }
    .brand-sub {
      font-size: 0.75rem;
    }
    .header-side strong {
      font-size: 0.88rem;
    }
    .guide-link {
      padding: 7px 10px;
      font-size: 0.72rem;
    }
    .hero-actions .button {
      width: 100%;
    }
    .bottom-nav {
      width: calc(100% - 6px);
      padding-left: 6px;
      padding-right: 6px;
    }
    .bottom-nav a {
      font-size: 0.58rem;
    }
    .bottom-nav a::before {
      width: 24px;
      height: 24px;
      font-size: 0.64rem;
    }
  }
"""


PAGE_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{page_title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;800&display=swap" rel="stylesheet">
  <style>{styles}</style>
</head>
<body data-page="{active_page}">
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark"></div>
        <div>
          <span class="brand-title">청년 투게더</span>
          <span class="brand-sub">오늘 기준 청년 정책과 이슈를 한곳에 모아 봅니다</span>
        </div>
      </div>
      <div class="topbar-side">
        {guide_link}
        {header_meta}
        <nav class="nav">{nav}</nav>
      </div>
    </header>
    {content}
  </div>
  <nav class="bottom-nav">{bottom_nav}</nav>
  {guide_overlay}
  <script>{script}</script>
</body>
</html>
"""


BASE_SCRIPT = """
(() => {
  function setFeedback(card, message, isError) {
    const feedback = card && card.querySelector('[data-article-feedback]');
    if (!feedback) {
      return;
    }
    if (feedback._timer) {
      clearTimeout(feedback._timer);
    }
    feedback.textContent = message;
    feedback.classList.toggle('error', Boolean(isError));
    feedback._timer = window.setTimeout(() => {
      feedback.textContent = '';
      feedback.classList.remove('error');
    }, 2200);
  }

  function fallbackCopy(text) {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'absolute';
    area.style.left = '-9999px';
    document.body.appendChild(area);
    area.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(area);
    if (!copied) {
      throw new Error('copy_failed');
    }
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    fallbackCopy(text);
  }

  function normalizeNewsDateRange(startValue, endValue) {
    let startDate = startValue || '';
    let endDate = endValue || '';
    if (startDate && endDate && startDate > endDate) {
      const swappedStart = endDate;
      endDate = startDate;
      startDate = swappedStart;
    }
    return { startDate, endDate };
  }

  function formatNewsDateRange(startDate, endDate) {
    if (startDate && endDate) {
      return `${startDate} - ${endDate}`;
    }
    if (startDate) {
      return `${startDate}부터`;
    }
    if (endDate) {
      return `${endDate}까지`;
    }
    return '전체';
  }

  function openNewsDatePicker(input) {
    if (!input) {
      return;
    }
    input.focus({ preventScroll: true });
    if (typeof input.showPicker === 'function') {
      try {
        input.showPicker();
      } catch (error) {
        // Some browsers limit showPicker; keep focus fallback.
      }
    }
  }

  function applyNewsFilters(root, selectedDateStart, selectedDateEnd, selectedRegion) {
    const normalizedDates = normalizeNewsDateRange(
      selectedDateStart ?? root.dataset.selectedDateStart ?? root.getAttribute('data-default-date-start') ?? '',
      selectedDateEnd ?? root.dataset.selectedDateEnd ?? root.getAttribute('data-default-date-end') ?? '',
    );
    const activeDateStart = normalizedDates.startDate;
    const activeDateEnd = normalizedDates.endDate;
    const hasDateRange = Boolean(activeDateStart || activeDateEnd);
    const activeRegion = selectedRegion || root.dataset.selectedRegion || root.getAttribute('data-default-region') || 'all';
    root.dataset.selectedDateStart = activeDateStart;
    root.dataset.selectedDateEnd = activeDateEnd;
    root.dataset.selectedRegion = activeRegion;

    const articleCards = Array.from(root.querySelectorAll('[data-article-date]'));
    let visibleCount = 0;

    articleCards.forEach((card) => {
      const articleDate = card.getAttribute('data-article-date') || '';
      const articleRegion = card.getAttribute('data-article-region') || '중앙';
      const isAfterStart = !activeDateStart || (articleDate && articleDate >= activeDateStart);
      const isBeforeEnd = !activeDateEnd || (articleDate && articleDate <= activeDateEnd);
      const dateMatch = !hasDateRange || (isAfterStart && isBeforeEnd);
      const regionMatch = activeRegion === 'all' || articleRegion === activeRegion;
      const isMatch = dateMatch && regionMatch;
      card.hidden = !isMatch;
      if (isMatch) {
        visibleCount += 1;
      }
    });

    root.querySelectorAll('[data-news-filter]').forEach((button) => {
      const group = button.getAttribute('data-filter-group') || 'date';
      const value = button.getAttribute('data-filter-value') || 'all';
      const isActive = group === 'region' ? value === activeRegion : (value === 'all' && !hasDateRange);
      button.classList.toggle('active', isActive);
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    root.querySelectorAll('[data-news-date-input]').forEach((dateInput) => {
      const role = dateInput.getAttribute('data-date-role') || 'start';
      const nextValue = role === 'end' ? activeDateEnd : activeDateStart;
      if (dateInput.value !== nextValue) {
        dateInput.value = nextValue;
      }
    });

    const status = root.querySelector('[data-news-filter-status]');
    if (status) {
      const dateLabel = formatNewsDateRange(activeDateStart, activeDateEnd);
      if (!hasDateRange && activeRegion === 'all') {
        status.textContent = `전체 ${visibleCount}건을 보고 있습니다.`;
      } else if (!hasDateRange) {
        status.textContent = `${activeRegion} 기사 ${visibleCount}건을 보고 있습니다.`;
      } else if (activeRegion === 'all') {
        status.textContent = `${dateLabel} 기사 ${visibleCount}건을 보고 있습니다.`;
      } else {
        status.textContent = `${activeRegion} · ${dateLabel} 기사 ${visibleCount}건을 보고 있습니다.`;
      }
    }

    const emptyState = root.querySelector('[data-news-empty-state]');
    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }
  }

  function getPolicyRegionAvailability(articleCards, activeGroup, activeType, activeDateStart, activeDateEnd, hasDateRange) {
    const availableRegions = new Set();

    articleCards.forEach((card) => {
      const articleGroup = card.getAttribute('data-policy-group') || 'official';
      const articleRegion = card.getAttribute('data-article-region') || '중앙';
      const articleType = card.getAttribute('data-policy-type') || '기타';
      const articleDate = card.getAttribute('data-article-date') || '';
      const groupMatch = activeGroup === 'all' || articleGroup === activeGroup;
      const typeMatch = activeType === 'all' || articleType === activeType;
      const isAfterStart = !activeDateStart || (articleDate && articleDate >= activeDateStart);
      const isBeforeEnd = !activeDateEnd || (articleDate && articleDate <= activeDateEnd);
      const dateMatch = !hasDateRange || (isAfterStart && isBeforeEnd);

      if (groupMatch && typeMatch && dateMatch) {
        availableRegions.add(articleRegion);
      }
    });

    return availableRegions;
  }

  function formatPolicyGroup(value) {
    if (value === 'official') {
      return '정부 공식 발표';
    }
    if (value === 'local') {
      return '지자체 발표 소식';
    }
    if (value === 'related') {
      return '참고 기록';
    }
    return '전체';
  }

  function applyPolicyFilters(root, selectedGroup, selectedRegion, selectedType, selectedDateStart, selectedDateEnd) {
    const normalizedDates = normalizeNewsDateRange(
      selectedDateStart ?? root.dataset.selectedDateStart ?? root.getAttribute('data-default-date-start') ?? '',
      selectedDateEnd ?? root.dataset.selectedDateEnd ?? root.getAttribute('data-default-date-end') ?? '',
    );
    const activeGroup = selectedGroup || root.dataset.selectedPolicyGroup || root.getAttribute('data-default-policy-group') || 'all';
    let activeRegion = selectedRegion || root.dataset.selectedPolicyRegion || root.getAttribute('data-default-policy-region') || 'all';
    const activeType = selectedType || root.dataset.selectedPolicyType || root.getAttribute('data-default-policy-type') || 'all';
    const activeDateStart = normalizedDates.startDate;
    const activeDateEnd = normalizedDates.endDate;
    const hasDateRange = Boolean(activeDateStart || activeDateEnd);
    root.dataset.selectedPolicyGroup = activeGroup;
    root.dataset.selectedPolicyRegion = activeRegion;
    root.dataset.selectedPolicyType = activeType;
    root.dataset.selectedDateStart = activeDateStart;
    root.dataset.selectedDateEnd = activeDateEnd;

    const articleCards = Array.from(root.querySelectorAll('[data-policy-card="true"]'));
    const availableRegions = getPolicyRegionAvailability(
      articleCards,
      activeGroup,
      activeType,
      activeDateStart,
      activeDateEnd,
      hasDateRange,
    );
    if (activeRegion !== 'all' && !availableRegions.has(activeRegion)) {
      activeRegion = 'all';
    }
    root.dataset.selectedPolicyRegion = activeRegion;

    const visibleByGroup = { official: 0, local: 0, related: 0 };
    let visibleCount = 0;

    articleCards.forEach((card) => {
      const articleGroup = card.getAttribute('data-policy-group') || 'official';
      const articleRegion = card.getAttribute('data-article-region') || '중앙';
      const articleType = card.getAttribute('data-policy-type') || '기타';
      const articleDate = card.getAttribute('data-article-date') || '';
      const groupMatch = activeGroup === 'all' || articleGroup === activeGroup;
      const regionMatch = activeRegion === 'all' || articleRegion === activeRegion;
      const typeMatch = activeType === 'all' || articleType === activeType;
      const isAfterStart = !activeDateStart || (articleDate && articleDate >= activeDateStart);
      const isBeforeEnd = !activeDateEnd || (articleDate && articleDate <= activeDateEnd);
      const dateMatch = !hasDateRange || (isAfterStart && isBeforeEnd);
      const isMatch = groupMatch && regionMatch && typeMatch && dateMatch;
      card.hidden = !isMatch;
      if (isMatch) {
        visibleCount += 1;
        visibleByGroup[articleGroup] = (visibleByGroup[articleGroup] || 0) + 1;
      }
    });

    root.querySelectorAll('[data-policy-filter]').forEach((button) => {
      const group = button.getAttribute('data-filter-group') || 'group';
      const value = button.getAttribute('data-filter-value') || 'all';
      const isActive =
        group === 'group' ? value === activeGroup :
        group === 'region' ? value === activeRegion :
        group === 'type' ? value === activeType :
        value === 'all' && !hasDateRange;
      if (group === 'region' && value !== 'all') {
        button.hidden = !availableRegions.has(value);
      }
      button.classList.toggle('active', isActive);
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    root.querySelectorAll('[data-policy-date-input]').forEach((dateInput) => {
      const role = dateInput.getAttribute('data-date-role') || 'start';
      const nextValue = role === 'end' ? activeDateEnd : activeDateStart;
      if (dateInput.value !== nextValue) {
        dateInput.value = nextValue;
      }
    });

    root.querySelectorAll('[data-policy-section]').forEach((section) => {
      const sectionGroup = section.getAttribute('data-policy-section') || 'official';
      const visibleInSection = visibleByGroup[sectionGroup] || 0;
      section.hidden = visibleInSection === 0;
      const count = section.querySelector('[data-policy-section-count]');
      if (count) {
        count.textContent = `${visibleInSection}건`;
      }
    });

    const status = root.querySelector('[data-policy-filter-status]');
    if (status) {
      const parts = [];
      if (activeGroup !== 'all') {
        parts.push(formatPolicyGroup(activeGroup));
      }
      if (activeRegion !== 'all') {
        parts.push(activeRegion);
      }
      if (activeType !== 'all') {
        parts.push(activeType);
      }
      if (hasDateRange) {
        parts.push(formatNewsDateRange(activeDateStart, activeDateEnd));
      }
      if (parts.length === 0) {
        status.textContent = `전체 ${visibleCount}건을 보고 있습니다.`;
      } else {
        status.textContent = `${parts.join(' · ')} ${visibleCount}건을 보고 있습니다.`;
      }
    }

    const emptyState = root.querySelector('[data-policy-empty-state]');
    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }
  }

  function markGuideSeen() {
    try {
      localStorage.setItem('youthTogetherGuideSeen-v1', '1');
    } catch (error) {
      // ignore storage errors
    }
  }

  function closeGuideOverlay(overlay, shouldPersist) {
    if (!overlay) {
      return;
    }
    if (shouldPersist) {
      markGuideSeen();
    }
    overlay.hidden = true;
    document.body.classList.remove('is-guide-open');
  }

  document.addEventListener('click', async (event) => {
    const guideDismiss = event.target.closest('[data-guide-dismiss]');
    if (guideDismiss) {
      event.preventDefault();
      closeGuideOverlay(document.querySelector('[data-guide-overlay]'), true);
      return;
    }

    const guideOpenLink = event.target.closest('[data-guide-open-link]');
    if (guideOpenLink) {
      markGuideSeen();
      return;
    }

    if (event.target.matches('[data-guide-overlay]')) {
      closeGuideOverlay(event.target, true);
      return;
    }

    const dateLaunch = event.target.closest('[data-news-date-launch], [data-policy-date-launch]');
    if (dateLaunch) {
      const dateInput = dateLaunch.querySelector('[data-news-date-input], [data-policy-date-input]');
      if (dateInput) {
        event.preventDefault();
        openNewsDatePicker(dateInput);
      }
      return;
    }

    const filterButton = event.target.closest('[data-news-filter]');
    if (filterButton) {
      const root = filterButton.closest('[data-news-filter-root]');
      if (root) {
        const group = filterButton.getAttribute('data-filter-group') || 'date';
        const value = filterButton.getAttribute('data-filter-value') || 'all';
        applyNewsFilters(
          root,
          group === 'date' ? '' : (root.dataset.selectedDateStart || root.getAttribute('data-default-date-start') || ''),
          group === 'date' ? '' : (root.dataset.selectedDateEnd || root.getAttribute('data-default-date-end') || ''),
          group === 'region' ? value : (root.dataset.selectedRegion || root.getAttribute('data-default-region') || 'all'),
        );
      }
      return;
    }

    const policyFilterButton = event.target.closest('[data-policy-filter]');
    if (policyFilterButton) {
      const root = policyFilterButton.closest('[data-policy-filter-root]');
      if (root) {
        const filterGroup = policyFilterButton.getAttribute('data-filter-group') || 'group';
        const filterValue = policyFilterButton.getAttribute('data-filter-value') || 'all';
        applyPolicyFilters(
          root,
          filterGroup === 'group' ? filterValue : (root.dataset.selectedPolicyGroup || root.getAttribute('data-default-policy-group') || 'all'),
          filterGroup === 'region' ? filterValue : (root.dataset.selectedPolicyRegion || root.getAttribute('data-default-policy-region') || 'all'),
          filterGroup === 'type' ? filterValue : (root.dataset.selectedPolicyType || root.getAttribute('data-default-policy-type') || 'all'),
          filterGroup === 'date' ? '' : (root.dataset.selectedDateStart || root.getAttribute('data-default-date-start') || ''),
          filterGroup === 'date' ? '' : (root.dataset.selectedDateEnd || root.getAttribute('data-default-date-end') || ''),
        );
      }
      return;
    }

    const button = event.target.closest('[data-article-action]');
    if (!button) {
      return;
    }

    event.preventDefault();
    const card = button.closest('[data-article-card]');
    const url = button.getAttribute('data-article-url') || (card && card.getAttribute('data-article-url')) || '';
    const title = button.getAttribute('data-share-title') || (card && card.getAttribute('data-article-title')) || document.title;
    const action = button.getAttribute('data-article-action');

    if (!url) {
      setFeedback(card, '링크 정보를 찾지 못했습니다.', true);
      return;
    }

    try {
      if (action === 'share' && typeof navigator.share === 'function') {
        await navigator.share({ title, url });
        setFeedback(card, '공유 창을 열었습니다.', false);
        return;
      }

      await copyText(url);
      setFeedback(card, action === 'share' ? '공유 링크를 복사했습니다.' : '링크를 복사했습니다.', false);
    } catch (error) {
      if (error && error.name === 'AbortError') {
        return;
      }
      setFeedback(card, '링크 복사에 실패했습니다.', true);
    }
  });

  document.querySelectorAll('[data-news-filter-root]').forEach((root) => {
    applyNewsFilters(
      root,
      root.getAttribute('data-default-date-start') || '',
      root.getAttribute('data-default-date-end') || '',
      root.getAttribute('data-default-region') || 'all',
    );
  });

  document.querySelectorAll('[data-policy-filter-root]').forEach((root) => {
    applyPolicyFilters(
      root,
      root.getAttribute('data-default-policy-group') || 'all',
      root.getAttribute('data-default-policy-region') || 'all',
      root.getAttribute('data-default-policy-type') || 'all',
      root.getAttribute('data-default-date-start') || '',
      root.getAttribute('data-default-date-end') || '',
    );
  });

  document.addEventListener('change', (event) => {
    const dateInput = event.target.closest('[data-news-date-input]');
    if (dateInput) {
      const root = dateInput.closest('[data-news-filter-root]');
      if (!root) {
        return;
      }
      const startInput = root.querySelector('[data-news-date-input][data-date-role="start"]');
      const endInput = root.querySelector('[data-news-date-input][data-date-role="end"]');
      applyNewsFilters(
        root,
        startInput ? startInput.value : '',
        endInput ? endInput.value : '',
        root.dataset.selectedRegion || root.getAttribute('data-default-region') || 'all',
      );
      return;
    }

    const policyDateInput = event.target.closest('[data-policy-date-input]');
    if (!policyDateInput) {
      return;
    }
    const policyRoot = policyDateInput.closest('[data-policy-filter-root]');
    if (!policyRoot) {
      return;
    }
    const policyStartInput = policyRoot.querySelector('[data-policy-date-input][data-date-role="start"]');
    const policyEndInput = policyRoot.querySelector('[data-policy-date-input][data-date-role="end"]');
    applyPolicyFilters(
      policyRoot,
      policyRoot.dataset.selectedPolicyGroup || policyRoot.getAttribute('data-default-policy-group') || 'all',
      policyRoot.dataset.selectedPolicyRegion || policyRoot.getAttribute('data-default-policy-region') || 'all',
      policyRoot.dataset.selectedPolicyType || policyRoot.getAttribute('data-default-policy-type') || 'all',
      policyStartInput ? policyStartInput.value : '',
      policyEndInput ? policyEndInput.value : '',
    );
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') {
      return;
    }
    const overlay = document.querySelector('[data-guide-overlay]');
    if (overlay && !overlay.hidden) {
      closeGuideOverlay(overlay, true);
    }
  });

  const guideOverlay = document.querySelector('[data-guide-overlay]');
  if (guideOverlay && document.body.dataset.page === 'index.html') {
    let seenGuide = false;
    try {
      seenGuide = localStorage.getItem('youthTogetherGuideSeen-v1') === '1';
    } catch (error) {
      seenGuide = false;
    }
    if (!seenGuide) {
      guideOverlay.hidden = false;
      document.body.classList.add('is-guide-open');
    }
  }
})();
"""


NAV_ITEMS = [
    ("index.html", "홈"),
    ("news.html", "뉴스"),
    ("policies.html", "정책"),
    ("hub.html", "참여·회의"),
    ("tools.html", "자료도구"),
    ("contact.html", "제보·문의"),
]


NAV_ICONS = {
    "index.html": "홈",
    "news.html": "뉴",
    "policies.html": "정",
    "hub.html": "참",
    "tools.html": "자",
    "contact.html": "문",
}


def nav_label(active_page: str) -> str:
    for href, label in NAV_ITEMS:
        if href == active_page:
            return label
    return "홈"


def render_guide_link(active_page: str) -> str:
    active = " active" if active_page == "guide.html" else ""
    current = ' aria-current="page"' if active_page == "guide.html" else ""
    return f'<a class="guide-link{active}" href="guide.html" data-guide-open-link="true"{current}>이용방법</a>'


def render_nav(active_page: str) -> str:
    items = []
    for href, label in NAV_ITEMS:
        active = "active" if href == active_page else ""
        items.append(f'<a class="{active}" href="{href}">{html.escape(label)}</a>')
    return "".join(items)


def render_bottom_nav(active_page: str) -> str:
    items = []
    for href, label in NAV_ITEMS:
        active = "active" if href == active_page else ""
        items.append(
            f'<a class="{active}" href="{href}" data-icon="{html.escape(NAV_ICONS.get(href, label[:1]))}"><span>{html.escape(label)}</span></a>'
        )
    return "".join(items)


def render_guide_overlay(active_page: str) -> str:
    if active_page != "index.html":
        return ""
    return """
  <div class="guide-overlay" data-guide-overlay hidden>
    <div class="guide-dialog" role="dialog" aria-modal="true" aria-labelledby="guide-dialog-title">
      <span class="eyebrow">이용방법</span>
      <h2 id="guide-dialog-title">처음 오셨다면 이렇게 보시면 됩니다.</h2>
      <p>홈 첫 화면은 오늘 바로 볼 기사부터 보는 구조입니다. 기사 수와 정책, 참여·회의 건수도 첫 화면에서 함께 확인할 수 있습니다.</p>
      <div class="list">
        <div class="list-item"><strong>홈</strong><span>가장 먼저 볼 기사와 오늘 집계를 한 번에 봅니다.</span></div>
        <div class="list-item"><strong>정책</strong><span>정부 원문 중심의 공식 발표를 확인합니다.</span></div>
        <div class="list-item"><strong>참여·회의</strong><span>정부 회의와 지역 네트워크 움직임을 나눠서 봅니다.</span></div>
      </div>
      <div class="hero-actions">
        <button class="button primary" type="button" data-guide-dismiss="true">바로 보기</button>
        <a class="button" href="guide.html" data-guide-open-link="true">이용방법 자세히</a>
      </div>
    </div>
  </div>
"""


def render_status(status: dict) -> dict[str, str]:
    if not status:
        return {
            "state": "상태 정보 없음",
            "updated_at": "-",
            "finished_at": "-",
            "date_basis": "-",
            "update_frequency": "-",
        }

    date_basis = status.get("date_basis", {})
    update_policy = status.get("update_policy", {})
    times = update_policy.get("times", [])
    if times:
        update_frequency = f'매일 {", ".join(times)} ({update_policy.get("timezone", "Asia/Seoul")})'
    else:
        update_frequency = update_policy.get("frequency", "-")

    raw_state = (status.get("state") or "unknown").lower()
    state_map = {
        "completed": "정상",
        "running": "업데이트 중",
        "failed": "오류",
    }

    raw_date_basis = date_basis.get("article_date_basis", "-")
    if "published_date" in raw_date_basis:
        date_basis_label = "원문 날짜 우선"
    else:
        date_basis_label = raw_date_basis

    return {
        "state": html.escape(state_map.get(raw_state, status.get("state", "unknown"))),
        "updated_at": html.escape(format_display_datetime(status.get("updated_at"))),
        "finished_at": html.escape(format_display_datetime(status.get("finished_at"))),
        "date_basis": html.escape(date_basis_label),
        "update_frequency": html.escape(update_frequency),
    }


def render_article_actions(article: dict, include_link_button: bool = True) -> str:
    url = html.escape(article.get("url", ""))
    title = display_article_title(article, limit=140)
    title_attr = html.escape(title)
    parts: list[str] = ['<div class="article-actions">']
    if include_link_button:
        parts.append(
            f'<a class="mini-link article-link-action" href="{url}" target="_blank" rel="noreferrer" '
            f'aria-label="{title_attr} 링크 바로가기">링크 바로가기</a>'
        )
    parts.append(
        f'<button class="action-button" type="button" data-article-action="share" '
        f'data-article-url="{url}" data-share-title="{title_attr}" aria-label="{title_attr} 공유하기">공유하기</button>'
    )
    parts.append(
        f'<button class="action-button" type="button" data-article-action="copy" '
        f'data-article-url="{url}" data-share-title="{title_attr}" aria-label="{title_attr} 링크 복사">링크 복사</button>'
    )
    parts.append("</div>")
    parts.append('<div class="article-feedback" data-article-feedback aria-live="polite"></div>')
    return "".join(parts)


def render_article_list_item(
    article: dict,
    body: str,
    *,
    overline: str | None = None,
    title: str | None = None,
) -> str:
    url = article.get("url")
    display_title = title or display_article_title(article)
    if not url:
        return (
            f'<div class="list-item"><strong>{html.escape(display_title)}</strong>'
            f'<span>{html.escape(body)}</span></div>'
        )

    escaped_url = html.escape(url)
    escaped_title = html.escape(display_title)
    article_date = html.escape(article_date_value(article))
    overline_html = f'<em class="article-list-overline">{html.escape(overline)}</em>' if overline else ""
    return (
        f'<div class="list-item article-list-item" data-article-card="true" '
        f'data-article-url="{escaped_url}" data-article-title="{escaped_title}" data-article-date="{article_date}">'
        f'<a class="article-list-link" href="{escaped_url}" target="_blank" rel="noreferrer" '
        f'aria-label="{escaped_title} 링크 바로가기">'
        f"{overline_html}"
        f"<strong>{escaped_title}</strong>"
        f"<span>{html.escape(body)}</span>"
        f"</a>"
        f"{render_article_actions(article, include_link_button=False)}"
        f"</div>"
    )


def render_article_card(article: dict, extra_attrs: dict[str, str] | None = None) -> str:
    badges = "".join(f'<span class="badge">{html.escape(badge)}</span>' for badge in article.get("display_badges", [])[:2])
    badge_row = f'<div class="badge-row">{badges}</div>' if badges else ""
    summary_text = summarize_article_text(article, limit=112)
    escaped_url = html.escape(article.get("url", ""))
    escaped_title = html.escape(display_article_title(article))
    article_region = html.escape(news_region_label(article))
    article_group = hub_group_label(article)
    article_type = html.escape(hub_activity_label(article))
    article_region = html.escape(news_region_label(article))
    summary_html = (
        f'<p class="article-summary"><a class="article-summary-link" href="{escaped_url}" target="_blank" rel="noreferrer" '
        f'aria-label="{escaped_title} 링크 바로가기">{html.escape(summary_text)}</a></p>'
        if summary_text
        else ""
    )
    article_date = html.escape(article_date_value(article))
    attr_parts = [
        'class="article-card"',
        'data-article-card="true"',
        f'data-article-url="{escaped_url}"',
        f'data-article-title="{escaped_title}"',
        f'data-article-date="{article_date}"',
        f'data-article-region="{article_region}"',
    ]
    if extra_attrs:
        for key, value in extra_attrs.items():
            if value is None:
                continue
            attr_parts.append(f'{key}="{html.escape(str(value), quote=True)}"')
    attr_text = " ".join(attr_parts)
    return f"""
    <article {attr_text}>
      {render_article_meta(article)}
      <h3><a class="article-title-link" href="{escaped_url}" target="_blank" rel="noreferrer" aria-label="{escaped_title} 링크 바로가기">{escaped_title}</a></h3>
      {badge_row}
      {summary_html}
      {render_article_actions(article)}
    </article>
    """


def render_hub_record_card(article: dict) -> str:
    hub_topics = ", ".join(article.get("hub_topics", [])[:3]) or "참여 의제"
    governance_scope = article.get("governance_scope") or "참여 기록"
    activity_types = ", ".join(article.get("governance_activity_types", [])[:3]) or "활동 기록"
    summary_text = summarize_article_text(article, limit=112)
    escaped_url = html.escape(article.get("url", ""))
    escaped_title = html.escape(display_article_title(article))
    article_region = html.escape(news_region_label(article))
    article_group = hub_group_label(article)
    article_type = html.escape(hub_activity_label(article))
    summary_html = (
        f'<p class="article-summary"><a class="article-summary-link" href="{escaped_url}" target="_blank" rel="noreferrer" '
        f'aria-label="{escaped_title} 링크 바로가기">{html.escape(summary_text)}</a></p>'
        if summary_text
        else ""
    )
    article_date = html.escape(article_date_value(article))
    return f"""
    <article class="article-card" data-article-card="true" data-policy-card="true" data-policy-group="{article_group}" data-policy-type="{article_type}" data-article-url="{escaped_url}" data-article-title="{escaped_title}" data-article-date="{article_date}" data-article-region="{article_region}">
      {render_article_meta(article, category_label=governance_scope)}
      <h3><a class="article-title-link" href="{escaped_url}" target="_blank" rel="noreferrer" aria-label="{escaped_title} 링크 바로가기">{escaped_title}</a></h3>
      <div class="badge-row"><span class="badge">{html.escape(activity_types)}</span><span class="badge">{html.escape(hub_topics)}</span></div>
      {summary_html}
      {render_article_actions(article)}
    </article>
    """


def render_feature_card(title: str, description: str, href: str, meta: str) -> str:
    return f"""
    <article class="section-card">
      <div class="article-meta">{html.escape(meta)}</div>
      <h3>{html.escape(title)}</h3>
      <p>{html.escape(description)}</p>
      <a class="mini-link" href="{href}">바로 가기</a>
    </article>
    """


def render_compact_intro(kicker: str, description: str) -> str:
    return f"""
    <article class="page-intro-card">
      <div class="page-intro-top">
        <span class="page-intro-badge">{html.escape(kicker)}</span>
      </div>
      <p class="page-intro-copy">{html.escape(description)}</p>
    </article>
    """


def render_list_block(title: str, intro: str, items: list[tuple[str, str]]) -> str:
    list_items = []
    for heading, body in items:
        list_items.append(
            f'<div class="list-item"><strong>{html.escape(heading)}</strong><span>{html.escape(body)}</span></div>'
        )
    return f"""
    <section class="list-card">
      <h3>{html.escape(title)}</h3>
      <p>{html.escape(intro)}</p>
      <div class="list">{''.join(list_items)}</div>
    </section>
    """


def render_youth_metrics() -> str:
    metric_items = []
    for metric in YOUTH_METRICS:
        metric_items.append(
            f"""
            <article class="youth-metric-item">
              <span class="youth-metric-label">{html.escape(metric["label"])}</span>
              <strong class="youth-metric-value">{html.escape(metric["value"])}</strong>
              <div class="youth-metric-meta">
                <span>{html.escape(metric["basis"])}</span>
                <a class="youth-metric-source" href="{html.escape(metric["url"])}" target="_blank" rel="noreferrer">{html.escape(metric["source"])}</a>
              </div>
            </article>
            """
        )
    return f"""
    <section class="section" id="youth-metrics">
      <article class="youth-metrics-card">
        <div class="youth-metrics-head">
          <h2>청년 주요 지표</h2>
          <p>정책과 기사 흐름을 볼 때 함께 참고할 수 있도록, 최근 공식 통계와 공공 발표 기준 숫자를 함께 놓았습니다.</p>
        </div>
        <div class="youth-metrics-grid">{''.join(metric_items)}</div>
        <p class="youth-metrics-note">지표마다 연령 기준과 기준 시점이 다르므로, 카드 아래 표기를 함께 확인해 주세요.</p>
      </article>
    </section>
    """


def render_support_metrics() -> str:
    metric_items = []
    for metric in YOUTH_METRICS:
        metric_items.append(
            f"""
            <article class="home-support-metric-item">
              <span class="home-support-metric-label">{html.escape(metric["label"])}</span>
              <strong class="home-support-metric-value">{html.escape(metric["value"])}</strong>
              <div class="home-support-metric-meta">
                <span>{html.escape(metric["basis"])}</span>
                <a href="{html.escape(metric["url"])}" target="_blank" rel="noreferrer">{html.escape(metric["source"])}</a>
              </div>
            </article>
            """
        )
    return f"""
    <div class="home-support-metrics">
      <h3>청년 주요 지표</h3>
      <div class="home-support-metrics-grid">{''.join(metric_items)}</div>
      <p class="home-support-note">지표마다 연령 기준과 기준 시점이 다르므로, 카드 아래 표기를 함께 확인해 주세요.</p>
    </div>
    """


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def format_display_datetime(value: str | None) -> str:
    parsed = parse_iso_datetime(value)
    if not parsed:
        return "기준 시각 없음"
    return parsed.strftime("%Y-%m-%d %H:%M")


def format_header_datetime(value: str | None) -> str:
    parsed = parse_iso_datetime(value)
    if not parsed:
        return "갱신 대기"
    return parsed.strftime("%m.%d %H:%M")


def format_home_date_label(value: str | None) -> str:
    parsed = parse_iso_datetime(value)
    if not parsed:
        return "오늘"
    weekday = ["월", "화", "수", "목", "금", "토", "일"][parsed.weekday()]
    return parsed.strftime(f"%Y.%m.%d ({weekday})")


def truncate_text(value: str | None, limit: int = 140) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def normalize_inline_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def clean_article_title(value: str | None) -> str:
    title = normalize_inline_text(value)
    if not title:
        return "제목 없음"

    for marker in [
        " 부헤드라인 ",
        " 본문 ",
        " - 전체 | ",
        " | 카드/한컷",
        " - 카드/한컷",
        " | 멀티미디어",
        " - 멀티미디어",
    ]:
        if marker in title:
            title = title.split(marker, 1)[0].strip(" -|:")

    return normalize_inline_text(title) or "제목 없음"


def display_article_title(article: dict, limit: int = 96) -> str:
    return truncate_text(clean_article_title(article.get("title")), limit)


def article_date_value(article: dict) -> str:
    return ((article.get("published_date", "") or "")[:10]).strip()


def collect_article_dates(articles: list[dict]) -> list[str]:
    return sorted({date for article in articles if (date := article_date_value(article))}, reverse=True)


def news_region_label(article: dict) -> str:
    region = normalize_inline_text(article.get("region"))
    if not region or region == "전국":
        return "중앙"
    return region


def collect_news_regions(articles: list[dict]) -> list[str]:
    counts: dict[str, int] = {}
    for article in articles:
        region = news_region_label(article)
        counts[region] = counts.get(region, 0) + 1

    others = sorted(region for region in counts if region != "중앙")
    return ["중앙", *others]


def policy_type_label(article: dict) -> str:
    text = normalize_inline_text(f'{article.get("title", "")} {article.get("lead_text", "")}')
    if any(keyword in text for keyword in ("시행계획", "종합계획", "기본계획", "중장기계획", "마스터플랜")):
        return "시행계획"
    if "공약" in text:
        return "공약"
    if any(keyword in text for keyword in ("심의", "의결", "가결", "승인")):
        return "심의·의결"
    if any(keyword in text for keyword in ("모집", "선발", "공고", "접수")):
        return "모집"
    if any(keyword in text for keyword in ("지원사업", "지원 확대", "사업 추진", "사업 시행", "지원정책", "지원", "정주")):
        return "지원사업"
    if any(keyword in text for keyword in ("발표", "브리핑", "대책")):
        return "정책 발표"
    return "기타"


def hub_group_label(article: dict) -> str:
    scope = normalize_inline_text(article.get("governance_scope"))
    if scope == "정부":
        return "official"
    if scope == "지역":
        return "local"
    return "related"


def hub_activity_label(article: dict) -> str:
    activity_types = [normalize_inline_text(value) for value in article.get("governance_activity_types", [])]
    activity_types = [value for value in activity_types if value]
    return activity_types[0] if activity_types else "기타"


def collect_policy_types(articles: list[dict]) -> list[str]:
    preferred_order = ["시행계획", "공약", "지원사업", "심의·의결", "모집", "정책 발표", "기타"]
    seen = {policy_type_label(article) for article in articles}
    ordered = [label for label in preferred_order if label in seen]
    return ordered


def collect_hub_activity_types(articles: list[dict]) -> list[str]:
    preferred_order = ["회의", "위원회", "출범", "발표회", "협약", "간담회", "포럼", "워크숍", "모집", "기타"]
    seen = {hub_activity_label(article) for article in articles}
    ordered = [label for label in preferred_order if label in seen]
    return ordered


def render_policy_filter_panel(official_policies: list[dict], reference_policies: list[dict]) -> str:
    all_policies = [*official_policies, *reference_policies]
    group_buttons = [
        '<button class="filter-button active" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="all" aria-pressed="true">전체</button>',
        '<button class="filter-button" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="official" aria-pressed="false">정부 공식 발표</button>',
        '<button class="filter-button" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="local" aria-pressed="false">지자체 발표 소식</button>',
    ]

    region_buttons = [
        '<button class="filter-button active" type="button" data-policy-filter="true" '
        'data-filter-group="region" data-filter-value="all" aria-pressed="true">전체</button>'
    ]
    for region in collect_news_regions(all_policies):
        region_buttons.append(
            f'<button class="filter-button" type="button" data-policy-filter="true" '
            f'data-filter-group="region" data-filter-value="{html.escape(region)}" '
            f'aria-pressed="false">{html.escape(region)}</button>'
        )

    type_buttons = [
        '<button class="filter-button active" type="button" data-policy-filter="true" '
        'data-filter-group="type" data-filter-value="all" aria-pressed="true">전체</button>'
    ]
    for label in collect_policy_types(all_policies):
        type_buttons.append(
            f'<button class="filter-button" type="button" data-policy-filter="true" '
            f'data-filter-group="type" data-filter-value="{html.escape(label)}" '
            f'aria-pressed="false">{html.escape(label)}</button>'
        )

    dates = collect_article_dates(all_policies)
    date_min = html.escape(dates[-1]) if dates else ""
    date_max = html.escape(dates[0]) if dates else ""
    date_input_attrs = []
    if date_min:
        date_input_attrs.append(f'min="{date_min}"')
    if date_max:
        date_input_attrs.append(f'max="{date_max}"')
    if not dates:
        date_input_attrs.append('disabled="true"')
    date_input_attrs_text = " ".join(date_input_attrs)

    return f"""
    <section class="section">
      <article class="section-card filter-panel">
        <div class="filter-head">
          <h3>구분 · 지역 · 유형 · 기간</h3>
        </div>
        <div class="filter-stack">
          <div class="filter-group">
            <span class="filter-group-label">구분</span>
            <div class="filter-controls">{''.join(group_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label">지역</span>
            <div class="filter-controls">{''.join(region_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label">유형</span>
            <div class="filter-controls">{''.join(type_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label">기간</span>
            <div class="date-picker-row">
              <button class="filter-button active" type="button" data-policy-filter="true" data-filter-group="date" data-filter-value="all" aria-pressed="true">전체</button>
              <div class="date-range-fields">
                <label class="date-input-wrap" data-policy-date-launch="true">
                  <span class="date-picker-label">시작일</span>
                  <input class="date-input" type="date" data-policy-date-input="true" data-date-role="start" {date_input_attrs_text}>
                </label>
                <label class="date-input-wrap" data-policy-date-launch="true">
                  <span class="date-picker-label">종료일</span>
                  <input class="date-input" type="date" data-policy-date-input="true" data-date-role="end" {date_input_attrs_text}>
                </label>
              </div>
            </div>
          </div>
        </div>
        <div class="filter-status" data-policy-filter-status>전체 {len(all_policies)}건을 보고 있습니다.</div>
      </article>
    </section>
    """


def render_hub_filter_panel(government_records: list[dict], regional_records: list[dict], other_records: list[dict]) -> str:
    all_records = [*government_records, *regional_records, *other_records]
    group_buttons = [
        '<button class="filter-button active" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="all" aria-pressed="true">전체</button>',
        '<button class="filter-button" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="official" aria-pressed="false">정부 회의·위원회</button>',
        '<button class="filter-button" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="local" aria-pressed="false">지역 참여·네트워크</button>',
        '<button class="filter-button" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="related" aria-pressed="false">참고 기록</button>',
    ]

    region_buttons = [
        '<button class="filter-button active" type="button" data-policy-filter="true" '
        'data-filter-group="region" data-filter-value="all" aria-pressed="true">전체</button>'
    ]
    for region in collect_news_regions(all_records):
        region_buttons.append(
            f'<button class="filter-button" type="button" data-policy-filter="true" '
            f'data-filter-group="region" data-filter-value="{html.escape(region)}" '
            f'aria-pressed="false">{html.escape(region)}</button>'
        )

    type_buttons = [
        '<button class="filter-button active" type="button" data-policy-filter="true" '
        'data-filter-group="type" data-filter-value="all" aria-pressed="true">전체</button>'
    ]
    for label in collect_hub_activity_types(all_records):
        type_buttons.append(
            f'<button class="filter-button" type="button" data-policy-filter="true" '
            f'data-filter-group="type" data-filter-value="{html.escape(label)}" '
            f'aria-pressed="false">{html.escape(label)}</button>'
        )

    dates = collect_article_dates(all_records)
    date_min = html.escape(dates[-1]) if dates else ""
    date_max = html.escape(dates[0]) if dates else ""
    date_input_attrs = []
    if date_min:
        date_input_attrs.append(f'min="{date_min}"')
    if date_max:
        date_input_attrs.append(f'max="{date_max}"')
    if not dates:
        date_input_attrs.append('disabled="true"')
    date_input_attrs_text = " ".join(date_input_attrs)

    return f"""
    <section class="section">
      <article class="section-card filter-panel">
        <div class="filter-head">
          <h3>구분 · 지역 · 활동 · 기간</h3>
          <p>정부 회의·위원회, 지역 참여·네트워크, 참고 기록을 같은 기준으로 빠르게 살펴볼 수 있습니다.</p>
        </div>
        <div class="filter-stack">
          <div class="filter-group">
            <span class="filter-group-label">구분</span>
            <div class="filter-controls">{''.join(group_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label">지역</span>
            <div class="filter-controls">{''.join(region_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label">활동</span>
            <div class="filter-controls">{''.join(type_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label">기간</span>
            <div class="date-picker-row">
              <button class="filter-button active" type="button" data-policy-filter="true" data-filter-group="date" data-filter-value="all" aria-pressed="true">전체</button>
              <div class="date-range-fields">
                <label class="date-input-wrap" data-policy-date-launch="true">
                  <span class="date-picker-label">시작일</span>
                  <input class="date-input" type="date" data-policy-date-input="true" data-date-role="start" {date_input_attrs_text}>
                </label>
                <label class="date-input-wrap" data-policy-date-launch="true">
                  <span class="date-picker-label">종료일</span>
                  <input class="date-input" type="date" data-policy-date-input="true" data-date-role="end" {date_input_attrs_text}>
                </label>
              </div>
            </div>
          </div>
        </div>
        <div class="filter-status" data-policy-filter-status>전체 {len(all_records)}건을 보고 있습니다.</div>
      </article>
    </section>
    """


def is_local_policy_update(article: dict) -> bool:
    if article.get("is_official_source"):
        return False

    text = normalize_inline_text(f'{article.get("title", "")} {article.get("lead_text", "")}')
    region = news_region_label(article)
    has_local_actor = region != "중앙" or any(keyword in text for keyword in LOCAL_GOVERNMENT_ACTOR_KEYWORDS)
    has_policy_core = any(keyword in text for keyword in LOCAL_POLICY_CORE_KEYWORDS)
    has_policy_action = any(keyword in text for keyword in LOCAL_POLICY_ACTION_KEYWORDS)
    has_strong_signal = any(keyword in text for keyword in LOCAL_POLICY_STRONG_KEYWORDS)

    if not has_local_actor:
        return False
    if not has_policy_core:
        return False
    if not (has_policy_action or has_strong_signal):
        return False
    if any(keyword in text for keyword in LOCAL_POLICY_EXCLUDE_KEYWORDS) and not has_strong_signal:
        return False
    if article.get("is_hub_candidate") and not has_strong_signal:
        return False
    return True


def render_news_filter_panel(regions: list[str], dates: list[str], total_count: int) -> str:
    region_buttons = [
        '<button class="filter-button active" type="button" data-news-filter="true" '
        'data-filter-group="region" data-filter-value="all" aria-pressed="true">전체</button>'
    ]
    for region in regions:
        region_buttons.append(
            f'<button class="filter-button" type="button" data-news-filter="true" '
            f'data-filter-group="region" data-filter-value="{html.escape(region)}" '
            f'aria-pressed="false">{html.escape(region)}</button>'
        )

    date_min = html.escape(dates[-1]) if dates else ""
    date_max = html.escape(dates[0]) if dates else ""
    date_input_attrs = []
    if date_min:
        date_input_attrs.append(f'min="{date_min}"')
    if date_max:
        date_input_attrs.append(f'max="{date_max}"')
    if not dates:
        date_input_attrs.append('disabled="true"')
    date_input_attrs_text = " ".join(date_input_attrs)

    return f"""
    <section class="section">
      <article class="section-card filter-panel">
        <div class="filter-head">
          <h3>지역별 · 날짜별로 보기</h3>
          <p>지역은 바로 누르고, 날짜는 시작일과 종료일을 골라 필요한 구간만 빠르게 볼 수 있습니다.</p>
        </div>
        <div class="filter-stack">
          <div class="filter-group">
            <span class="filter-group-label">지역</span>
            <div class="filter-controls">{''.join(region_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label">기간</span>
            <div class="date-picker-row">
              <button class="filter-button active" type="button" data-news-filter="true" data-filter-group="date" data-filter-value="all" aria-pressed="true">전체</button>
              <div class="date-range-fields">
                <label class="date-input-wrap" data-news-date-launch="true">
                  <span class="date-picker-label">시작일</span>
                  <input class="date-input" type="date" data-news-date-input="true" data-date-role="start" {date_input_attrs_text}>
                </label>
                <label class="date-input-wrap" data-news-date-launch="true">
                  <span class="date-picker-label">종료일</span>
                  <input class="date-input" type="date" data-news-date-input="true" data-date-role="end" {date_input_attrs_text}>
                </label>
              </div>
            </div>
          </div>
        </div>
        <div class="filter-status" data-news-filter-status>전체 {total_count}건을 보고 있습니다.</div>
      </article>
    </section>
    """


def format_source_label(value: str | None) -> str:
    source = normalize_inline_text(value)
    if not source:
        return "출처 미상"
    aliases = {
        "v.daum.net": "다음 뉴스",
        "정책브리핑 RSS": "정책브리핑",
        "정책브리핑 청년정책 뉴스": "정책브리핑",
    }
    if source in aliases:
        return aliases[source]
    if source.startswith("www."):
        return source[4:]
    return source


def summarize_article_text(article: dict, limit: int = 118) -> str:
    text = normalize_inline_text(article.get("summary") or article.get("lead_text") or "")
    if not text:
        return ""

    title = normalize_inline_text(article.get("title"))
    raw_source = normalize_inline_text(article.get("source") or article.get("source_name"))
    source = format_source_label(raw_source)
    candidates = [title]
    if title and source:
        candidates.extend(
            [
                f"{title} {source}",
                f"{title} · {source}",
                f"{title} - {source}",
                f"{title} | {source}",
            ]
        )
    if title and raw_source and raw_source != source:
        candidates.extend(
            [
                f"{title} {raw_source}",
                f"{title} · {raw_source}",
                f"{title} - {raw_source}",
                f"{title} | {raw_source}",
            ]
        )

    for candidate in sorted({value for value in candidates if value}, key=len, reverse=True):
        if text.startswith(candidate):
            text = text[len(candidate) :].strip(" .,:;|-·[]()\"'")
            break

    suffixes = [source]
    if raw_source and raw_source != source:
        suffixes.append(raw_source)

    for suffix_source in suffixes:
        for suffix in [suffix_source, f"· {suffix_source}", f"- {suffix_source}", f"| {suffix_source}"]:
            if text.endswith(suffix):
                text = text[: -len(suffix)].rstrip(" .,:;|-·[]()\"'")
                break

    text = normalize_inline_text(text)
    if not text or text in {source, raw_source}:
        return ""
    if " " not in text and "." in text:
        return ""
    if title and (text == title or title in text and len(text) - len(title) <= 12):
        return ""

    return truncate_text(text, limit)


def render_article_meta(article: dict, category_label: str | None = None) -> str:
    categories = article.get("categories", [])
    category = category_label or (categories[0] if categories else "미분류")
    category_aliases = {
        "정책 오피셜": "공식 발표",
        "청년은 지금": "오늘 이슈",
        "지역 이슈": "지역 움직임",
        "논평·기고": "해설·의견",
        "허브 연관": "참고 기록",
    }
    category = category_aliases.get(category, category)
    region = news_region_label(article)
    source = format_source_label(article.get("source") or article.get("source_name"))
    published = (article.get("published_date", "") or "")[:10] or "날짜 미상"
    return (
        '<div class="article-meta">'
        '<div class="article-meta-tags">'
        f'<span class="meta-pill primary">{html.escape(category)}</span>'
        f'<span class="meta-pill subtle">{html.escape(region)}</span>'
        '</div>'
        '<div class="article-byline">'
        f'<span class="meta-item">{html.escape(source)}</span>'
        '<span class="meta-divider" aria-hidden="true">•</span>'
        f'<span class="meta-item">{html.escape(published)}</span>'
        '</div>'
        '</div>'
    )


def compact_article_meta(article: dict) -> str:
    bits = []
    source = format_source_label(article.get("source") or article.get("source_name"))
    published = article_date_value(article)
    if source:
        bits.append(source)
    if published:
        bits.append(published)
    region = article.get("region")
    if region and region != "전국":
        bits.append(region)
    return " · ".join(bits) or "기사 정보 없음"


def render_header_meta(active_page: str, status: dict) -> str:
    latest = status.get("finished_at") or status.get("updated_at")
    return (
        '<div class="header-side">'
        f'<strong>{html.escape(format_header_datetime(latest))}</strong>'
        '<span>최근 반영</span>'
        "</div>"
    )


def article_sort_key(article: dict) -> tuple[int, float]:
    parsed = parse_iso_datetime(article.get("published_date"))
    if not parsed:
        return (0, 0.0)
    return (1, parsed.timestamp())


def sort_articles_by_recency(articles: list[dict]) -> list[dict]:
    return sorted(articles, key=article_sort_key, reverse=True)


def resolve_freshness_hours(status: dict, default: int = 24) -> int:
    try:
        return int(status.get("date_basis", {}).get("freshness_target_hours") or default)
    except (TypeError, ValueError):
        return default


def filter_recent_articles(
    articles: list[dict],
    reference_time: str | None,
    max_age_hours: int,
) -> list[dict]:
    reference_dt = parse_iso_datetime(reference_time)
    if reference_dt is None:
        parsed_dates = [parse_iso_datetime(article.get("published_date")) for article in articles]
        parsed_dates = [value for value in parsed_dates if value is not None]
        reference_dt = max(parsed_dates) if parsed_dates else None
    if reference_dt is None:
        return []

    threshold = reference_dt - timedelta(hours=max_age_hours)
    filtered: list[dict] = []
    for article in articles:
        published_dt = parse_iso_datetime(article.get("published_date"))
        if published_dt is None:
            continue
        if published_dt >= threshold:
            filtered.append(article)
    return sort_articles_by_recency(filtered)


def latest_article_timestamp(articles: list[dict], fallback: str) -> str:
    sorted_articles = sort_articles_by_recency(articles)
    if sorted_articles and sorted_articles[0].get("published_date"):
        return sorted_articles[0]["published_date"]
    return fallback


def latest_reference_articles(articles: list[dict], limit: int = 5) -> list[dict]:
    sorted_articles = sort_articles_by_recency(articles)
    if not sorted_articles:
        return []
    latest_day = (sorted_articles[0].get("published_date") or "")[:10]
    if latest_day:
        same_day_articles = [
            article for article in sorted_articles if (article.get("published_date") or "")[:10] == latest_day
        ]
        if same_day_articles:
            return same_day_articles[:limit]
    return sorted_articles[:limit]


def describe_article_basis(articles: list[dict], empty_message: str) -> str:
    latest = latest_article_timestamp(articles, "")
    if not latest:
        return empty_message
    return format_display_datetime(latest)


def load_home_update_snapshot() -> dict:
    return read_json(HOME_UPDATE_SNAPSHOT, default={})


def save_home_update_snapshot(payload: dict) -> None:
    HOME_UPDATE_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    HOME_UPDATE_SNAPSHOT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def previous_update_reference(status: dict, page_updated_at: str | None) -> datetime | None:
    current_dt = parse_iso_datetime(page_updated_at)
    if current_dt is None:
        return None
    raw_times = status.get("update_policy", {}).get("times", [])
    schedule_minutes: list[int] = []
    for raw_value in raw_times:
        try:
            hour_text, minute_text = str(raw_value).split(":", 1)
            schedule_minutes.append(int(hour_text) * 60 + int(minute_text))
        except (TypeError, ValueError):
            continue
    if not schedule_minutes:
        return current_dt - timedelta(hours=6)

    current_minutes = current_dt.hour * 60 + current_dt.minute
    earlier_slots = [minutes for minutes in schedule_minutes if minutes < current_minutes]
    if earlier_slots:
        target_minutes = max(earlier_slots)
        target_day = current_dt.date()
    else:
        target_minutes = max(schedule_minutes)
        target_day = (current_dt - timedelta(days=1)).date()

    target_hour, target_minute = divmod(target_minutes, 60)
    return current_dt.replace(
        year=target_day.year,
        month=target_day.month,
        day=target_day.day,
        hour=target_hour,
        minute=target_minute,
        second=0,
        microsecond=0,
    )


def summarize_focus_counts(articles: list[dict]) -> tuple[str, int]:
    groups = article_groups(articles)
    focus_counts: list[tuple[str, int]] = []
    for category_key, label in [
        ("청년은 지금", "오늘 이슈"),
        ("지역 이슈", "지역 움직임"),
        ("논평·기고", "해설·의견"),
    ]:
        count = len(groups.get(category_key, []))
        if count:
            focus_counts.append((label, count))
    if not focus_counts:
        return ("오늘 흐름", 0)
    return sorted(focus_counts, key=lambda item: (-item[1], item[0]))[0]


def summarize_top_regions(articles: list[dict], limit: int = 2) -> list[tuple[str, int]]:
    region_counts: dict[str, int] = {}
    for article in articles:
        region = (article.get("region") or "").strip()
        if not region or region == "전국":
            continue
        region_counts[region] = region_counts.get(region, 0) + 1
    return sorted(region_counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def build_home_update_briefing(
    status: dict,
    page_updated_at: str,
    recent_news_articles: list[dict],
    official_policy_articles: list[dict],
    participation_count: int,
) -> dict[str, str]:
    snapshot = load_home_update_snapshot()
    stored_briefing = snapshot.get("briefing")
    if snapshot.get("page_updated_at") == page_updated_at and isinstance(stored_briefing, dict):
        return stored_briefing

    previous_urls = set(snapshot.get("recent_news_urls", [])) if snapshot.get("page_updated_at") else set()
    current_urls = [article.get("url") for article in recent_news_articles if article.get("url")]
    added_articles = [article for article in recent_news_articles if article.get("url") and article.get("url") not in previous_urls]
    if previous_urls:
        added_label = "추가 기사"
    else:
        reference_dt = previous_update_reference(status, page_updated_at)
        if reference_dt is not None:
            added_articles = [
                article
                for article in recent_news_articles
                if (published_dt := parse_iso_datetime(article.get("published_date"))) is not None and published_dt > reference_dt
            ]
        else:
            added_articles = []
        added_label = "직전 반영 뒤 기사"

    briefing_articles = added_articles or recent_news_articles
    top_focus_label, _ = summarize_focus_counts(briefing_articles)
    top_regions = summarize_top_regions(briefing_articles)
    top_region_label = top_regions[0][0] if top_regions else "전국"
    added_count = len(added_articles)
    if added_count > 0:
        copy = (
            f"이번 업데이트에 {added_label} {added_count}건이 들어왔고, "
            f"가장 많이 올라온 분야는 {top_focus_label}, 지역은 {top_region_label}입니다."
        )
    else:
        copy = (
            f"직전 반영 뒤 새로 잡힌 기사는 없고, "
            f"현재 화면에서는 {top_focus_label} 흐름과 {top_region_label} 지역 비중이 가장 큽니다."
        )
    meta = (
        f"뉴스 {len(recent_news_articles)}건 · 정책 {len(official_policy_articles)}건 · "
        f"참여·회의 {participation_count}건을 이번 화면에 반영했습니다."
    )
    briefing = {
        "label": "이번 업데이트 요약",
        "copy": copy,
        "meta": meta,
    }
    save_home_update_snapshot(
        {
            "page_updated_at": page_updated_at,
            "recent_news_urls": current_urls,
            "briefing": briefing,
        }
    )
    return briefing


def summarize_menu_items(articles: list[dict], fallback_items: list[tuple[str, str]], limit: int = 2) -> list[tuple[str, str]]:
    sorted_articles = sort_articles_by_recency(articles)
    items: list[tuple[str, str]] = []
    for article in sorted_articles[:limit]:
        meta_bits = [article.get("source", "")]
        if article.get("published_date"):
            meta_bits.append(article["published_date"][:10])
        if article.get("categories"):
            meta_bits.append(article["categories"][0])
        items.append((display_article_title(article, limit=84), " · ".join(bit for bit in meta_bits if bit)))
    return items or fallback_items


def filter_hub_articles(classified_articles: list[dict], scope: str | None = None) -> list[dict]:
    articles = [article for article in classified_articles if article.get("is_hub_candidate")]
    if scope is not None:
        articles = [article for article in articles if article.get("governance_scope") == scope]
    return sort_articles_by_recency(articles)


def render_empty_hub_state(title: str, body: str) -> str:
    return f'<article class="info-card"><h3>{html.escape(title)}</h3><p>{html.escape(body)}</p></article>'


def build_hub_menu_items(classified_articles: list[dict]) -> list[tuple[str, str]]:
    government_articles = filter_hub_articles(classified_articles, "정부")
    regional_articles = filter_hub_articles(classified_articles, "지역")

    items: list[tuple[str, str]] = []
    if government_articles:
        items.append(
            (
                f'정부 회의·위원회: {display_article_title(government_articles[0], limit=72)}',
                " · ".join(
                    bit
                    for bit in [
                        government_articles[0].get("source", ""),
                        government_articles[0].get("published_date", "")[:10],
                    ]
                    if bit
                ),
            )
        )
    else:
        items.append(("정부 회의·위원회", "현재 등록된 항목이 없습니다."))

    if regional_articles:
        items.append(
            (
                f'지역 참여·네트워크: {display_article_title(regional_articles[0], limit=72)}',
                " · ".join(
                    bit
                    for bit in [
                        regional_articles[0].get("source", ""),
                        regional_articles[0].get("published_date", "")[:10],
                    ]
                    if bit
                ),
            )
        )
    else:
        items.append(("지역 참여·네트워크", "현재 등록된 항목이 없습니다."))

    items.append(("제보·문의", "사이트 개선 제안과 협업 문의는 제보·문의에서 이어집니다."))
    return items[:3]


def build_menu_updates(articles: list[dict], classified_articles: list[dict], status: dict) -> list[dict]:
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    news_articles = [article for article in articles if not article.get("is_official_source")] or list(articles)
    policy_articles = [article for article in articles if article.get("is_official_source")]
    hub_articles = filter_hub_articles(classified_articles)

    return [
        {
            "eyebrow": "01 뉴스",
            "title": "청년 뉴스",
            "href": "news.html",
            "description": "청년 뉴스와 오늘 바로 볼 기사를 빠르게 확인할 수 있습니다.",
            "article_basis_label": "최신 기사 기준",
            "article_basis_time": latest_article_timestamp(news_articles, page_updated_at),
            "page_basis_label": "페이지 반영",
            "page_basis_time": page_updated_at,
            "items": summarize_menu_items(
                news_articles,
                [("오늘의 뉴스", "최신 기사와 요약을 함께 확인할 수 있습니다.")],
            ),
            "link_label": "뉴스 보기",
        },
        {
            "eyebrow": "02 정책",
            "title": "최근 정책",
            "href": "policies.html",
            "description": "정부 발표와 공식 정책 자료를 날짜순으로 확인할 수 있습니다.",
            "article_basis_label": "최신 정책 기준",
            "article_basis_time": latest_article_timestamp(policy_articles, page_updated_at),
            "page_basis_label": "페이지 반영",
            "page_basis_time": page_updated_at,
            "items": summarize_menu_items(
                policy_articles,
                [("최근 발표", "공식 발표가 이 영역에 표시됩니다.")],
            ),
            "link_label": "정책 바로가기",
        },
        {
            "eyebrow": "03 활동가 허브",
            "title": "청년활동가 허브",
            "href": "hub.html",
            "description": "정부와 지역의 청년 활동 소식을 볼 수 있습니다.",
            "article_basis_label": "허브 연관 기사 기준",
            "article_basis_time": latest_article_timestamp(hub_articles, page_updated_at),
            "page_basis_label": "페이지 반영",
            "page_basis_time": page_updated_at,
            "items": build_hub_menu_items(classified_articles),
            "link_label": "허브 보기",
        },
        {
            "eyebrow": "04 도구",
            "title": "정책제안서 작성 도구",
            "href": "tools.html",
            "description": "정책을 찾고 제안서를 준비할 때 필요한 메뉴입니다.",
            "article_basis_label": "도구 업데이트 기준",
            "article_basis_time": page_updated_at,
            "page_basis_label": "페이지 반영",
            "page_basis_time": page_updated_at,
            "items": [
                ("정책 찾기 사이트", "정책브리핑, 부처, 통계 사이트를 확인할 수 있습니다."),
                ("AI 도구 사용법", "질문 만들기와 내용 정리 방법을 안내합니다."),
            ],
            "link_label": "도구 보기",
        },
        {
            "eyebrow": "05 연락",
            "title": "운영자 연락하기",
            "href": "contact.html",
            "description": "문의, 제보, 협업, 검토 요청 유형을 확인할 수 있습니다.",
            "article_basis_label": "연락 구조 기준",
            "article_basis_time": page_updated_at,
            "page_basis_label": "페이지 반영",
            "page_basis_time": page_updated_at,
            "items": [
                ("운영 문의", "서비스 이용과 오류 관련 문의"),
                ("제보 / 협업", "유용한 소스와 활동 소식 제보"),
            ],
            "link_label": "연락 보기",
        },
    ]


def render_menu_update_card(menu: dict) -> str:
    item_html = "".join(
        f'<div class="list-item"><strong>{html.escape(title)}</strong><span>{html.escape(body)}</span></div>'
        for title, body in menu["items"]
    )
    return f"""
    <article class="menu-update-card">
      <div class="menu-update-top">
        <div class="menu-update-head">
          <span class="eyebrow">{html.escape(menu["eyebrow"])}</span>
          <h3>{html.escape(menu["title"])}</h3>
          <p class="menu-update-copy">{html.escape(menu["description"])}</p>
        </div>
      </div>
      <div class="menu-meta-grid">
        <div class="menu-meta">
          <strong>{html.escape(menu["article_basis_label"])}</strong>
          <span>{html.escape(format_display_datetime(menu["article_basis_time"]))}</span>
        </div>
        <div class="menu-meta">
          <strong>{html.escape(menu["page_basis_label"])}</strong>
          <span>{html.escape(format_display_datetime(menu["page_basis_time"]))}</span>
        </div>
      </div>
      <div class="list">{item_html}</div>
      <div class="menu-links">
        <a class="button primary" href="{html.escape(menu["href"])}">{html.escape(menu["link_label"])}</a>
      </div>
    </article>
    """


def article_groups(articles: list[dict]) -> dict[str, list[dict]]:
    groups = {
        "청년은 지금": [],
        "논평·기고": [],
        "지역 이슈": [],
    }
    for article in articles:
        categories = set(article.get("categories", []))
        if "논평·기고" in categories:
            groups["논평·기고"].append(article)
        elif "지역 이슈" in categories:
            groups["지역 이슈"].append(article)
        else:
            groups["청년은 지금"].append(article)
    for category in groups:
        groups[category] = sort_articles_by_recency(groups[category])
    return groups


def build_home_page(
    articles: list[dict],
    classified_articles: list[dict],
    status: dict,
    contact_settings: dict[str, str],
) -> str:
    status_meta = render_status(status)
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    all_articles = sort_articles_by_recency(classified_articles or articles)
    news_articles = [article for article in all_articles if not article.get("is_official_source")]
    recent_news_articles = filter_recent_articles(news_articles, page_updated_at, NEWS_WINDOW_HOURS)
    policy_articles = filter_recent_articles(
        [article for article in all_articles if article.get("is_official_source")],
        page_updated_at,
        24 * 90,
    )
    official_policy_articles = [article for article in policy_articles if article.get("source_kind") == "official"]
    government_hub_articles = filter_recent_articles(
        filter_hub_articles(classified_articles, "정부"),
        page_updated_at,
        24 * 90,
    )
    regional_hub_articles = filter_recent_articles(
        filter_hub_articles(classified_articles, "지역"),
        page_updated_at,
        24 * 90,
    )
    participation_count = len(government_hub_articles) + len(regional_hub_articles)
    home_date_label = format_home_date_label(page_updated_at)
    latest_news_basis = describe_article_basis(recent_news_articles, f"최근 {NEWS_WINDOW_DAYS}일 기사 없음")
    policy_basis = describe_article_basis(official_policy_articles or policy_articles, "최근 정책 없음")
    version_text = contact_settings.get("version_text", "").strip() or "버전 정보 준비 중"
    lead_message = (
        "혼자 버티는 하루가 너무 길게 느껴질 때에도, 오늘의 기사와 정책이 조금은 또렷한 길잡이가 되었으면 합니다. "
        "당신의 오늘이 작지 않다는 마음으로, 지금 필요한 흐름을 한자리에 모았습니다."
    )
    glance_stats_html = "".join(
        f'<article class="{card_class}"><span class="home-glance-label">{label}</span><strong class="home-glance-value">{value}</strong></article>'
        for card_class, label, value in [
            ("home-glance-item warm", "오늘의 기사", f"{len(recent_news_articles)}건"),
            ("home-glance-item neutral", "정책", f"{len(official_policy_articles)}건"),
            ("home-glance-item teal", "참여·회의", f"{participation_count}건"),
        ]
    )

    def render_urgent_news_item(index: int, article: dict) -> str:
        title = html.escape(display_article_title(article, limit=88))
        meta = html.escape(compact_article_meta(article))
        url = article.get("url")
        rank = f"{index:02d}"
        if not url:
            return (
                f'<article class="home-urgent-item"><div class="home-urgent-link">'
                f'<span class="home-urgent-rank">{rank}</span>'
                f'<div class="home-urgent-text"><strong>{title}</strong>'
                f'<span class="home-urgent-meta">{meta}</span></div></div></article>'
            )
        escaped_url = html.escape(url)
        return (
            f'<article class="home-urgent-item"><a class="home-urgent-link" href="{escaped_url}" '
            f'target="_blank" rel="noreferrer" aria-label="{title} 링크 바로가기">'
            f'<span class="home-urgent-rank">{rank}</span>'
            f'<div class="home-urgent-text"><strong>{title}</strong>'
            f'<span class="home-urgent-meta">{meta}</span></div></a></article>'
        )

    urgent_news_html = "".join(
        render_urgent_news_item(index, article) for index, article in enumerate(recent_news_articles[:5], start=1)
    ) or (
        '<article class="home-urgent-item"><div class="home-urgent-link"><span class="home-urgent-rank">00</span>'
        f'<div class="home-urgent-text"><strong>최근 {NEWS_WINDOW_DAYS}일 뉴스가 없습니다.</strong>'
        '<span class="home-urgent-meta">새 청년 뉴스가 수집되면 이 영역에 표시됩니다.</span></div></div></article>'
    )
    return f"""
    <section class="hero home-hero">
      <div class="home-briefing-grid">
        <article class="home-briefing-card lead lead-arch">
          <span class="home-briefing-date">{html.escape(home_date_label)}</span>
          <h1 class="home-briefing-title">청년은 오늘 -</h1>
          <p class="home-briefing-copy">{html.escape(lead_message)}</p>
        </article>
        <article class="home-briefing-card digest digest-organic">
          <div class="home-briefing-head">
            <h2>오늘 한눈에 보기</h2>
            <p>오늘의 기사와 정책, 참여·회의 흐름을 빠르게 가늠합니다.</p>
          </div>
          <div class="home-glance-grid">{glance_stats_html}</div>
          <div class="home-glance-links">
            <a class="mini-link" href="news.html">뉴스 보기</a>
            <a class="mini-link" href="policies.html">정책 보기</a>
            <a class="mini-link" href="hub.html">참여·회의 보기</a>
          </div>
          <div class="home-briefing-divider"></div>
          <div class="home-briefing-subhead">
            <h3>오늘 놓치면 안되는 뉴스 5가지</h3>
            <p>요약된 흐름을 기준으로 지금 가장 먼저 훑어볼 기사를 빠르게 묶었습니다.</p>
          </div>
          <div class="home-urgent-list">{urgent_news_html}</div>
        </article>
        <article class="home-briefing-card support support-pill">
          {render_support_metrics()}
        </article>
        <article class="home-briefing-card footer footer-warm">
          <div class="home-support-footer">
            <span class="home-support-version">{html.escape(version_text)}</span>
            <p class="home-support-copy">이 사이트는 무료로 운영됩니다. 청년들을 응원하기 위해 만들어졌습니다.</p>
            <p class="home-support-copy secondary">기사 한 줄과 정책 한 항목이 필요한 순간에 제때 닿기를 바라는 마음으로, 오늘의 흐름을 조용히 모아두고 있습니다.</p>
            <div class="home-support-meta">
              <span>페이지 반영 {format_display_datetime(page_updated_at)}</span>
              <span>정책 기준 {html.escape(policy_basis)}</span>
              <span>기사 기준 {html.escape(latest_news_basis)}</span>
              <span>{status_meta["update_frequency"]}</span>
            </div>
            <div class="home-support-links">
              <a href="guide.html">사이트 소개</a>
              <a href="contact.html">제보·문의</a>
            </div>
            <p class="home-support-credit">유쾌한 청년들, 박진감이 만들었습니다.</p>
          </div>
        </article>
      </div>
    </section>
    """


def build_guide_page(status: dict) -> str:
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    status_meta = render_status(status)
    menu_cards = "".join(
        [
            render_feature_card("홈", "오늘 바로 볼 기사와 오늘 집계를 먼저 보는 첫 화면입니다.", "index.html", "첫 화면"),
            render_feature_card("뉴스", f"최근 {NEWS_WINDOW_DAYS}일 청년 뉴스를 날짜별로 빠르게 훑어봅니다.", "news.html", "최근 기사"),
            render_feature_card("정책", "정부 공식 발표와 참고 기사를 구분해 원문 흐름을 확인합니다.", "policies.html", "공식 발표"),
            render_feature_card("참여·회의", "정부 회의와 지역 참여·네트워크 움직임을 한데 모아 봅니다.", "hub.html", "참여 흐름"),
            render_feature_card("자료도구", "자료 찾기, 초안 정리, 제보·문의로 이어지는 실무 동선을 정리했습니다.", "tools.html", "실무 도구"),
        ]
    )
    update_guide = render_list_block(
        "업데이트 읽는 법",
        "홈과 각 메뉴에서 보이는 기준 시각을 이렇게 읽으면 됩니다.",
        [
            ("기사 기준", "가장 최근 기사나 발표가 실제로 나온 시각입니다."),
            ("페이지 반영", "수집과 정리를 마치고 사이트에 다시 올린 시각입니다."),
            ("반영 주기", status_meta["update_frequency"] or "매일 정해진 시각에 반영됩니다."),
        ],
    )
    usage_guide = render_list_block(
        "빠르게 보는 순서",
        "처음 들어왔을 때 가장 덜 헤매는 흐름을 짧게 정리했습니다.",
        [
            ("1. 홈", "오늘 바로 볼 기사와 집계를 먼저 확인합니다."),
            ("2. 정책", "정부 공식 발표 원문과 정책브리핑을 바로 확인합니다."),
            ("3. 참여·회의", "위원회, 회의, 네트워크 소식이 이어지는지 살펴봅니다."),
            ("4. 자료도구·제보", "필요한 자료를 찾거나 운영팀에 제보·문의합니다."),
        ],
    )
    return f"""
    <section class="hero">
      <article class="hero-card">
        <span class="eyebrow">사이트 소개</span>
        <h1>청년세대와 관련된 이슈들을 한 데 모았습니다.</h1>
        <p class="hero-copy">최근 7일 기사와 정부 공식 발표, 참여·회의 기록을 한 화면 흐름으로 비교할 수 있게 정리했습니다. 홈은 오늘 바로 볼 기사부터 시작하고, 이 페이지에서는 메뉴와 보는 순서를 설명합니다.</p>
        <div class="hero-feature-meta">페이지 반영 {html.escape(format_display_datetime(page_updated_at))} · {html.escape(status_meta["update_frequency"])}</div>
        <div class="hero-actions">
          <a class="button primary" href="index.html">홈에서 기사 보기</a>
          <a class="button" href="news.html">뉴스부터 보기</a>
        </div>
      </article>
      <aside class="status-card">
        <h3>먼저 보면 좋은 메뉴</h3>
        <div class="list">
          <div class="list-item"><strong>홈</strong><span>첫 화면에서 오늘 바로 볼 기사와 업데이트 요약을 먼저 확인합니다.</span></div>
          <div class="list-item"><strong>정책</strong><span>정부 공식 발표와 참고 기사 구분이 가장 분명한 메뉴입니다.</span></div>
          <div class="list-item"><strong>참여·회의</strong><span>위원회, 회의, 지역 네트워크 움직임을 추적할 때 유용합니다.</span></div>
          <div class="list-item"><strong>제보·문의</strong><span>누락 기사, 협업 제안, 운영 문의를 바로 남길 수 있습니다.</span></div>
        </div>
      </aside>
    </section>
    <section class="section">
      <div class="section-head">
        <div>
          <h2>메뉴별 안내</h2>
          <p>원하는 목적에 맞춰 바로 이동할 수 있도록 메뉴 역할을 나눴습니다.</p>
        </div>
      </div>
      <div class="feature-grid">{menu_cards}</div>
    </section>
    <div class="home-dual-grid">
      <section class="section">{update_guide}</section>
      <section class="section">{usage_guide}</section>
    </div>
    """


def build_news_page(articles: list[dict], status: dict) -> str:
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    news_articles = [article for article in sort_articles_by_recency(articles) if not article.get("is_official_source")]
    recent_news_articles = filter_recent_articles(news_articles, page_updated_at, NEWS_WINDOW_HOURS)
    date_options = collect_article_dates(recent_news_articles)
    region_options = collect_news_regions(recent_news_articles)
    page_intro = render_compact_intro(
        "01 뉴스",
        "지역과 날짜 기준으로 최근 청년 뉴스를 빠르게 훑고, 필요한 기사만 골라볼 수 있습니다.",
    )
    news_filter_panel = render_news_filter_panel(region_options, date_options, len(recent_news_articles))
    cards_html = "".join(render_article_card(article) for article in recent_news_articles)
    return f"""
    <div data-news-filter-root="news" data-default-date-start="" data-default-date-end="" data-default-region="all">
      {page_intro}
      {news_filter_panel}
      <section class="section">
        <div class="article-grid">
          {cards_html or '<article class="info-card" data-news-empty-state="true"><h3>최근 뉴스가 없습니다</h3><p>새 청년 뉴스가 수집되면 이 영역에 표시됩니다.</p></article>'}
        </div>
        <article class="info-card" data-news-empty-state="true" hidden>
          <h3>조건에 맞는 기사가 없습니다</h3>
          <p>지역이나 날짜 조건을 바꾸면 다른 기사를 볼 수 있습니다.</p>
        </article>
      </section>
    </div>
    """


def build_policies_page(articles: list[dict], status: dict) -> str:
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    policies = filter_recent_articles(
        [article for article in articles if article.get("is_official_source")],
        page_updated_at,
        24 * 90,
    )
    official_policies = [article for article in policies if article.get("source_kind") == "official"]
    reference_policies = [article for article in policies if article.get("source_kind") != "official"]
    official_cards = "".join(render_article_card(article) for article in official_policies)
    reference_cards = "".join(render_article_card(article) for article in reference_policies[:8])
    return f"""
    <section class="hero">
      <article class="hero-card">
        <span class="eyebrow">02 정책</span>
        <h1>정부 공식 발표와 참고 기사를 구분해 보여드립니다.</h1>
        <p class="hero-copy">정책브리핑과 정부 발표는 위로, 지자체·언론 기사는 참고 영역으로 분리했습니다.</p>
      </article>
      <aside class="status-card">
        <h3>정책 보기 기준</h3>
        <div class="list">
          <div class="list-item"><strong>정부 공식 발표</strong><span>{len(official_policies)}건 · 정책브리핑과 정부 원문만 모았습니다.</span></div>
          <div class="list-item"><strong>참고 기사</strong><span>{len(reference_policies)}건 · 지자체 보도와 언론 기사는 별도 구역으로 분리했습니다.</span></div>
          <div class="list-item"><strong>페이지 반영</strong><span>{html.escape(format_display_datetime(page_updated_at))}</span></div>
        </div>
      </aside>
    </section>
    <section class="section">
      <div class="section-head">
        <div>
          <h2>정부 공식 발표</h2>
          <p>최근 90일 안에 나온 정부 원문과 공식 발표만 보여줍니다.</p>
        </div>
      </div>
      <div class="article-grid">{official_cards or '<article class="info-card"><h3>최근 공식 발표 없음</h3><p>최근 90일 안에 표시할 정부 원문이 아직 없습니다.</p></article>'}</div>
    </section>
    <section class="section">
      <div class="section-head">
        <div>
          <h2>참고로 볼 지자체·언론 기사</h2>
          <p>정책과 직접 연관된 기사이지만 정부 원문은 아닌 항목을 참고용으로 분리했습니다.</p>
        </div>
      </div>
      <div class="article-grid">{reference_cards or '<article class="info-card"><h3>참고 기사 없음</h3><p>현재 분리해 보여줄 참고 기사가 없습니다.</p></article>'}</div>
    </section>
    """


def build_policies_page_compact(articles: list[dict], status: dict) -> str:
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    recent_articles = filter_recent_articles(sort_articles_by_recency(articles), page_updated_at, 24 * 90)
    official_policies = [article for article in recent_articles if article.get("is_official_source")]
    reference_policies = [article for article in recent_articles if is_local_policy_update(article)]
    page_intro = render_compact_intro(
        "02 정책",
        "정부 공식 발표와 지자체 발표 소식을 구분해 보고, 지역·유형·기간 기준으로 필요한 정책만 빠르게 확인할 수 있습니다.",
    )
    official_cards = "".join(
        render_article_card(
            article,
            {
                "data-policy-card": "true",
                "data-policy-group": "official",
                "data-policy-type": policy_type_label(article),
            },
        )
        for article in official_policies
    )
    reference_cards = "".join(
        render_article_card(
            article,
            {
                "data-policy-card": "true",
                "data-policy-group": "local",
                "data-policy-type": policy_type_label(article),
            },
        )
        for article in reference_policies
    )
    policy_filter_panel = render_policy_filter_panel(official_policies, reference_policies)
    return f"""
    <div data-policy-filter-root="policies" data-default-policy-group="all" data-default-policy-region="all" data-default-policy-type="all" data-default-date-start="" data-default-date-end="">
      {page_intro}
      {policy_filter_panel}
      <section class="section" id="official-policies" data-policy-section="official">
        <div class="section-head">
          <div>
            <h2>정부 공식 발표</h2>
            <p>정책브리핑, 국무조정실, 고용노동부, 보건복지부, 국토교통부, 교육부, 금융위원회 등에서 직접 수집한 공식 발표입니다.</p>
          </div>
          <span class="mini-link" aria-disabled="true" data-policy-section-count>{len(official_policies)}건</span>
        </div>
        <div class="article-grid">{official_cards or '<article class="info-card"><h3>최근 공식 발표 없음</h3><p>최근 90일 안에 표시할 정부 원문이 아직 없습니다.</p></article>'}</div>
      </section>
      <section class="section" id="local-policy-updates" data-policy-section="local">
        <div class="section-head">
          <div>
            <h2>지자체 발표 소식</h2>
            <p>청년 정책과 공약, 시행계획 발표 성격이 분명한 지역 기사만 따로 모았습니다.</p>
          </div>
          <span class="mini-link" aria-disabled="true" data-policy-section-count>{len(reference_policies)}건</span>
        </div>
        <div class="article-grid">{reference_cards or '<article class="info-card"><h3>지자체 발표 소식 없음</h3><p>현재 기준으로 분리해 보여줄 지역 정책 발표 기사가 없습니다.</p></article>'}</div>
      </section>
      <article class="info-card" data-policy-empty-state="true" hidden>
        <h3>조건에 맞는 정책이 없습니다</h3>
        <p>구분이나 지역, 유형, 기간을 바꾸면 다른 정책을 볼 수 있습니다.</p>
      </article>
    </div>
    """


def build_hub_page(classified_articles: list[dict]) -> str:
    hub_records = filter_hub_articles(classified_articles)
    government_records = filter_hub_articles(classified_articles, "정부")[:6]
    regional_records = filter_hub_articles(classified_articles, "지역")[:6]
    other_records = [
        article
        for article in hub_records
        if article.get("governance_scope") not in {"정부", "지역"}
    ][:6]
    page_intro = render_compact_intro(
        "03 참여·회의",
        "청년 참여 회의와 지역 네트워크 움직임을 구분해 보고, 필요한 기록만 빠르게 걸러볼 수 있습니다.",
    )
    hub_filter_panel = render_hub_filter_panel(government_records, regional_records, other_records)
    government_cards = "".join(render_hub_record_card(article) for article in government_records)
    regional_cards = "".join(render_hub_record_card(article) for article in regional_records)
    other_cards = "".join(render_hub_record_card(article) for article in other_records)
    return f"""
    <div data-policy-filter-root="hub" data-default-policy-group="all" data-default-policy-region="all" data-default-policy-type="all" data-default-date-start="" data-default-date-end="">
      {page_intro}
      {hub_filter_panel}
      <section class="section" data-policy-section="official">
        <div class="section-head">
          <div>
            <h2>정부 회의·위원회</h2>
            <p>정부 기관이 연 회의, 위원회, 자문단, 협약 소식을 모았습니다.</p>
          </div>
          <span class="mini-link" aria-disabled="true" data-policy-section-count>{len(government_records)}건</span>
        </div>
        <div class="article-grid">{government_cards or render_empty_hub_state("등록된 정부 회의 기록이 없습니다", "새 항목이 수집되면 이 영역에 표시됩니다.")}</div>
      </section>
      <section class="section" data-policy-section="local">
        <div class="section-head">
          <div>
            <h2>지역 참여·네트워크</h2>
            <p>지방자치단체와 지역 네트워크 활동 소식을 따로 보여줍니다.</p>
          </div>
          <span class="mini-link" aria-disabled="true" data-policy-section-count>{len(regional_records)}건</span>
        </div>
        <div class="article-grid">{regional_cards or render_empty_hub_state("등록된 지역 참여 기록이 없습니다", "새 항목이 수집되면 이 영역에 표시됩니다.")}</div>
      </section>
      <section class="section" id="related" data-policy-section="related">
        <div class="section-head">
          <div>
            <h2>참고 기록</h2>
            <p>정부·지역 구역으로 바로 분류되지 않은 연관 기록입니다.</p>
          </div>
          <span class="mini-link" aria-disabled="true" data-policy-section-count>{len(other_records)}건</span>
        </div>
        <div class="article-grid">{other_cards or render_empty_hub_state("등록된 참고 기록이 없습니다", "연관 기록이 수집되면 이 영역에 표시됩니다.")}</div>
      </section>
      <article class="info-card" data-policy-empty-state="true" hidden>
        <h3>조건에 맞는 참여·회의 기록이 없습니다</h3>
        <p>구분이나 지역, 활동, 기간을 바꾸면 다른 기록을 확인할 수 있습니다.</p>
      </article>
    </div>
    """


def build_tools_page() -> str:
    page_intro = render_compact_intro(
        "04 자료도구",
        "정책 조사와 제안서 초안을 준비할 때 필요한 자료를 짧은 흐름으로 따라볼 수 있습니다.",
    )
    return f"""
    {page_intro}
    <section class="section">
      {render_list_block("빠른 시작", "처음이면 아래 세 단계부터 보면 가장 빠릅니다.", [("정부 원문 확인", "정책브리핑과 부처 자료로 기준점을 먼저 잡기"), ("AI로 질문 정리", "조사 범위와 논점을 짧게 정리하기"), ("검토 요청 준비", "문서 상태와 요청 포인트 적어두기")])}
    </section>
    <section class="section" id="search-sites">
      {render_list_block("공식 자료 찾기", "정책 근거를 찾을 때 먼저 보는 출처입니다.", [("정책브리핑 / 국무조정실", "공식 정책 발표와 회의체 자료 확인"), ("중앙부처 / 광역지자체", "부처별·지역별 청년정책 발표 확인"), ("KOSIS / 공공데이터", "통계와 데이터 출처 확인")])}
    </section>
    <section class="section" id="ai-guide">
      {render_list_block("AI로 정리하기", "AI는 조사와 정리를 돕는 용도로만 쓰는 편이 안전합니다.", [("검색 질문 만들기", "정책 찾기를 위한 질문 정리"), ("논점 정리", "기사와 근거를 항목별로 정리"), ("목차 초안", "제안서 구조를 먼저 잡아보기")])}
    </section>
    <section class="section" id="review">
      {render_list_block("검토 요청 가이드", "초안을 정리하고 검토받을 내용을 미리 적어두면 더 빠르게 이어집니다.", [("초안 점검", "현재 문서 상태와 부족한 자료 확인"), ("요청 포인트 정리", "어떤 부분을 봐주면 좋은지 정리"), ("협업 제안", "함께 검토하거나 보완할 사람 찾기")])}
    </section>
    """


def build_contact_page(contact_settings: dict[str, str]) -> str:
    contact_email = html.escape(contact_settings.get("email", ""))
    contact_updated_at = format_display_datetime(contact_settings.get("updated_at"))
    page_intro = render_compact_intro(
        "05 제보·문의",
        "빠진 기사 제보, 운영 문의, 검토 요청을 한곳에서 남기고 바로 이어서 확인할 수 있습니다.",
    )
    contact_overview = "".join(
        [
            f'<div class="list-item"><strong>단체</strong><span>{html.escape(contact_settings.get("organization_name", ""))}</span></div>',
            f'<div class="list-item"><strong>버전</strong><span>{html.escape(contact_settings.get("version_text", ""))}</span></div>',
            f'<div class="list-item"><strong>최근 수정</strong><span>{contact_updated_at}</span></div>',
            f'<div class="list-item"><strong>이메일</strong><span>{contact_email}</span></div>',
        ]
    )
    contact_notes = "".join(
        f'<div class="list-item"><strong>{label}</strong><span>{html.escape(value)}</span></div>'
        for label, value in [
            ("안내 1", contact_settings.get("extra_line_1", "")),
            ("안내 2", contact_settings.get("extra_line_2", "")),
        ]
        if value
    )
    notes_section = ""
    if contact_notes:
        notes_section = f"""
    <section class="section">
      <div class="section-head">
        <div>
          <h2>추가 안내</h2>
          <p>운영자가 설정한 안내 문구입니다.</p>
        </div>
      </div>
      <div class="list">{contact_notes}</div>
    </section>
    """
    return f"""
    {page_intro}
    <section class="section">
      <article class="list-card">
        <h3>기본 연락 정보</h3>
        <p>문의 전에 확인해두면 연결이 조금 더 빠릅니다.</p>
        <div class="list">{contact_overview}</div>
      </article>
    </section>
    <section class="section">
      {render_list_block("보내기 전에 함께 적어주면 좋은 내용", "문의 유형에 맞는 기본 정보를 함께 적어주면 답변과 검토가 더 빨라집니다.", [("문의·오류", "문제가 발생한 페이지, 상황, 기대한 동작"), ("제보·협업", "관련 링크, 왜 중요한지, 함께 하고 싶은 방식"), ("검토 요청", "문서 상태, 중점 검토 범위, 필요한 기한")])}
    </section>
    {notes_section}
    <section class="section">
      <div class="section-head">
        <div>
          <h2>바로가기</h2>
          <p>목적에 따라 아래 구역으로 바로 이동할 수 있습니다.</p>
        </div>
      </div>
      <div class="feature-grid">
        {render_feature_card("운영 문의", "사이트 운영 정책, 기능 문의, 사용성 피드백을 받습니다.", "#ops", "운영")}
        {render_feature_card("제보 · 협업", "유용한 소스, 지역 활동, 정책 제안 협업을 제보받습니다.", "#collab", "협업")}
        {render_feature_card("검토 요청", "정책제안서 초안 검토 요청 내용을 정리해 둘 수 있습니다.", "#review", "검토")}
      </div>
    </section>
    <section class="section" id="ops">
      {render_list_block("운영 문의", "서비스 이용 중 불편함이나 오류를 알려주세요.", [("오류 제보", "문제가 발생한 페이지와 상황"), ("사용성 제안", "화면 구성이나 정보 정렬 관련 제안"), ("운영 문의", "서비스 이용과 운영 기준 관련 문의")])}
    </section>
    <section class="section" id="collab">
      {render_list_block("제보 · 협업", "유용한 소스와 활동 소식, 협업 제안을 받습니다.", [("소스 제보", "청년 관련 기사와 자료 출처"), ("활동 소식", "지역 활동, 거버넌스, 행사 소식"), ("협업 제안", "함께 만들거나 검토할 수 있는 제안")])}
    </section>
    <section class="section" id="review">
      {render_list_block("검토 요청", "정책제안서나 실무 문서의 검토 요청 내용을 정리할 수 있습니다.", [("문서 상태", "초안인지 수정본인지 표시"), ("검토 범위", "무엇을 중점적으로 봐야 하는지 정리"), ("기한 안내", "언제까지 검토가 필요한지 표시")])}
    </section>
    """


def write_page(path: Path, page_title: str, active_page: str, content: str, status: dict) -> None:
    path.write_text(
        PAGE_TEMPLATE.format(
            page_title=html.escape(page_title),
            active_page=html.escape(active_page),
            styles=BASE_CSS,
            script=BASE_SCRIPT,
            guide_link=render_guide_link(active_page),
            header_meta=render_header_meta(active_page, status),
            nav=render_nav(active_page),
            bottom_nav=render_bottom_nav(active_page),
            guide_overlay=render_guide_overlay(active_page),
            content=content,
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "output" / "step5_summarized.json"))
    parser.add_argument("--output", default=str(ROOT / "web" / "index.html"))
    args = parser.parse_args()

    articles = read_json(Path(args.input), default=[])
    classified_articles = read_json(ROOT / "output" / "step3_classified.json", default=articles)
    status = read_json(ROOT / "output" / "pipeline_status.json", default={})
    web_root = Path(args.output).parent
    web_root.mkdir(parents=True, exist_ok=True)

    contact_settings = load_contact_settings()

    write_page(web_root / "index.html", "청년 투게더", "index.html", build_home_page(articles, classified_articles, status, contact_settings), status)
    write_page(web_root / "guide.html", "이용방법", "guide.html", build_guide_page(status), status)
    write_page(web_root / "news.html", "청년 뉴스", "news.html", build_news_page(classified_articles, status), status)
    write_page(
        web_root / "policies.html",
        "청년 정책",
        "policies.html",
        build_policies_page_compact(classified_articles, status),
        status,
    )
    write_page(web_root / "hub.html", "청년 참여·회의", "hub.html", build_hub_page(classified_articles), status)
    write_page(web_root / "tools.html", "자료·작성 도구", "tools.html", build_tools_page(), status)
    write_page(web_root / "contact.html", "제보·문의", "contact.html", build_contact_page(contact_settings), status)

    print(f"web_output={web_root / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
