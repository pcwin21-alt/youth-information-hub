from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import html
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

from _bootstrap import PUBLIC_WEB_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.article_metadata import article_identity_key, preferred_article_url
from youth_info_platform.contact_config import load_contact_settings
from youth_info_platform.curation import is_public_interest_article
from youth_info_platform.io_utils import read_json

NEWS_WINDOW_DAYS = 7
NEWS_WINDOW_HOURS = NEWS_WINDOW_DAYS * 24
ELECTION_WINDOW_DAYS = 21
ELECTION_WINDOW_HOURS = ELECTION_WINDOW_DAYS * 24
HOME_DAILY_LIMIT = 5
HOME_WEEKLY_LIMIT = 3
HOME_DAILY_STICKY_LIMIT = 2
HOME_DAILY_STICKY_HOURS = 24
HOME_WEEKLY_STICKY_HOURS = 72
HOME_UPDATE_SNAPSHOT = RUNTIME_PIPELINE_ROOT / "home_update_snapshot.json"
HOME_HOT_KEYWORD_LIMIT = 8
REMOTE_TEXT_CACHE: dict[str, str] = {}
ILLUSTRATION_ROOT = "assets/illustrations"
PUBLIC_ANALYTICS_ENDPOINT = os.getenv("PUBLIC_SITE_ANALYTICS_ENDPOINT", "").strip()
PUBLIC_ANALYTICS_SCOPE = os.getenv("PUBLIC_SITE_ANALYTICS_SCOPE", "public").strip() or "public"

MAJOR_CENTRAL_POLICY_AUTHORITIES = [
    "기획재정부",
    "교육부",
    "고용노동부",
    "행정안전부",
    "보건복지부",
    "국토교통부",
    "문화체육관광부",
    "중소벤처기업부",
    "금융위원회",
]

HUB_GROUP_CONFIG = {
    "official": {
        "scope": "정부",
        "title": "중앙부처 자문·회의",
        "description": "국무조정실과 중앙부처의 청년 관계장관회의, 자문단, 보좌역, 위원회 기록을 모았습니다.",
        "empty_title": "등록된 중앙부처 자문·회의 기록이 없습니다",
        "empty_body": "새 중앙부처 회의·자문 기록이 수집되면 이 영역에 표시됩니다.",
        "scope_label": "부처·기관",
        "button_label": "중앙부처 자문·회의",
    },
    "local": {
        "scope": "지자체",
        "title": "지역 청년정책 네트워크",
        "description": "지자체가 운영하는 청년정책네트워크, 청년협의체, 청년위원회, 참여단 기록을 묶었습니다.",
        "empty_title": "등록된 지역 청년정책 네트워크 기록이 없습니다",
        "empty_body": "새 지역 참여·네트워크 기록이 수집되면 이 영역에 표시됩니다.",
        "scope_label": "지역",
        "button_label": "지역 청년정책 네트워크",
    },
    "public": {
        "scope": "공공기관",
        "title": "공공기관 참여·협의",
        "description": "공공재단·진흥원·센터·공사·공단이 운영한 공식 청년 참여·자문 기록을 모았습니다.",
        "empty_title": "등록된 공공기관 참여·협의 기록이 없습니다",
        "empty_body": "새 공공기관 참여·협의 기록이 수집되면 이 영역에 표시됩니다.",
        "scope_label": "공공기관",
        "button_label": "공공기관 참여·협의",
    },
}

CURATED_MAJOR_POLICY_WATCHLIST = [
    {
        "policy_authority": "기획재정부",
        "title": "2026 경제성장전략, 대한민국 경제대도약 원년",
        "url": "https://www.moef.go.kr/nw/mosfnw/detailCardNewsView.do?menuNo=4040600&searchNttId1=MOSF_000000000076481",
        "published_date": "2026-01-13T00:00:00+09:00",
        "lead_text": "청년 4대 도약패키지로 주거·일자리·금융·교육·생활·복지 지원을 확대하는 2026 경제성장전략 카드뉴스입니다.",
        "policy_type": "시행계획",
    },
    {
        "policy_authority": "행정안전부",
        "title": "「2026년 청년마을 만들기 사업」 공모 안내",
        "url": "https://www.mois.go.kr/frt/bbs/type013/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000006&nttId=123187",
        "published_date": "2026-01-14T00:00:00+09:00",
        "lead_text": "전국 청년단체·기업을 대상으로 3년간 최대 6억 원을 지원하는 청년마을 만들기 사업 공고입니다.",
        "policy_type": "모집",
    },
    {
        "policy_authority": "보건복지부",
        "title": "가족돌봄·고립은둔 청년 의견 직접 듣다",
        "url": "https://www.mohw.go.kr/gallery.es?act=view&b_list=12&bid=0003&cg_code=C01&keyField=&list_no=379921&mid=a10605040000&nPage=1&orderby=&vlist_no_npage=1",
        "published_date": "2026-03-16T00:00:00+09:00",
        "lead_text": "청년미래센터 현장에서 가족돌봄·고립은둔 청년 의견을 듣고 자립·돌봄 지원 방향을 점검한 보건복지부 공식 현장 자료입니다.",
        "policy_type": "정책 발표",
    },
    {
        "policy_authority": "국토교통부",
        "title": "월세 부담 줄여줄게, 2026 청년월세 지원 랩",
        "url": "https://youtu.be/yYXSBPcfZvI?si=wsdo3zpR1D1VNR9a",
        "published_date": "2026-03-30T00:00:00+09:00",
        "lead_text": "국토교통부 포털 최신소식에 게시된 공식 설명 영상으로, 2026 청년월세 지원 내용을 한 번에 정리한 안내 자료입니다.",
        "policy_type": "지원사업",
    },
    {
        "policy_authority": "문화체육관광부",
        "title": "2026년 청년문화포럼·주간개최 위탁용역",
        "url": "https://www.mcst.go.kr/site/s_notice/notice/bidView.jsp?pSeq=19044",
        "published_date": "2026-04-07T00:00:00+09:00",
        "lead_text": "청년문화포럼과 청년문화주간 개최를 위한 문화체육관광부 공식 공고로, 청년 문화정책 의제를 다루는 최근 자료입니다.",
        "policy_type": "모집",
    },
    {
        "policy_authority": "중소벤처기업부",
        "title": "2026년 창업중심대학 참여기업 모집",
        "url": "https://www.mss.go.kr/site/smba/ex/bbs/View.do?bcIdx=1065967&cbIdx=86",
        "published_date": "2026-03-03T00:00:00+09:00",
        "lead_text": "청년정책과가 안내한 2026년 창업중심대학 참여기업 모집 공고로, 생애최초 청년 예비창업자와 초기 창업기업 지원을 담았습니다.",
        "policy_type": "모집",
    },
    {
        "policy_authority": "금융위원회",
        "title": "금융분야 청년정책 관련 청년의 의견을 수렴하였습니다",
        "url": "https://www.fsc.go.kr/no010101/86132?curPage=&srchBeginDt=&srchCtgry=&srchEndDt=&srchKey=&srchText=%EC%B2%AD%EB%85%84%EB%8F%84%EC%95%BD%EA%B3%84%EC%A2%8C",
        "published_date": "2026-01-26T00:00:00+09:00",
        "lead_text": "청년미래적금, 청년도약계좌 등 금융분야 청년정책에 대한 청년 의견을 수렴한 금융위원회 보도자료입니다.",
        "policy_type": "정책 발표",
    },
]

HOME_LEAD_ILLUSTRATION = {
    "src": f"{ILLUSTRATION_ROOT}/home-youth-group.svg",
    "alt": "떠오르는 해와 길, 정책 카드, 작은 새싹이 함께 있는 홈 화면 일러스트",
}

PAGE_INTRO_ILLUSTRATIONS = {
    "news": {
        "src": f"{ILLUSTRATION_ROOT}/intro-news.svg",
        "alt": "뉴스 문서와 돋보기 모티프 일러스트",
    },
    "policies": {
        "src": f"{ILLUSTRATION_ROOT}/intro-policies.svg",
        "alt": "정책 문서와 체크 표시 모티프 일러스트",
    },
    "hub": {
        "src": f"{ILLUSTRATION_ROOT}/intro-hub.svg",
        "alt": "대화와 연결을 나타내는 말풍선 모티프 일러스트",
    },
    "tools": {
        "src": f"{ILLUSTRATION_ROOT}/intro-tools.svg",
        "alt": "자료 정리를 나타내는 폴더와 메모 모티프 일러스트",
    },
    "contact": {
        "src": f"{ILLUSTRATION_ROOT}/intro-contact.svg",
        "alt": "문의와 전달을 나타내는 편지와 말풍선 모티프 일러스트",
    },
}

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
    --home-apricot-soft: rgba(221, 147, 103, 0.14);
    --home-teal: #7d8e98;
    --home-teal-soft: rgba(125, 142, 152, 0.12);
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
    display: grid;
    grid-template-columns: 76px minmax(0, 1fr);
    column-gap: 13px;
    row-gap: 2px;
    align-items: center;
    min-width: 0;
    flex: 1 1 auto;
    color: inherit;
    text-decoration: none;
  }
  .brand:hover .brand-logo,
  .brand:focus-visible .brand-logo {
    opacity: 0.92;
  }
  .brand:focus-visible {
    outline: 2px solid rgba(48, 75, 104, 0.45);
    outline-offset: 4px;
    border-radius: 8px;
  }
  .brand-logo {
    display: block;
    grid-row: 1 / span 2;
    width: 76px;
    max-width: none;
    height: auto;
    aspect-ratio: 1;
  }
  .brand-copy {
    display: grid;
    gap: 7px;
    align-self: center;
    min-width: 0;
  }
  .brand-title {
    display: block;
    color: var(--ink);
    font-size: 2.24rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: 0;
    white-space: nowrap;
  }
  .brand-sub {
    display: block;
    color: var(--muted);
    font-size: 0.92rem;
    font-weight: 500;
    line-height: 1.25;
    word-break: keep-all;
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
  .page-intro-card.has-media {
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: end;
    gap: 16px;
  }
  .page-intro-content {
    display: grid;
    gap: 10px;
    min-width: 0;
  }
  .page-intro-media {
    width: 104px;
    align-self: end;
    justify-self: end;
    margin: 0 -2px -2px 0;
    pointer-events: none;
  }
  .page-intro-media img {
    display: block;
    width: 100%;
    height: auto;
    filter: drop-shadow(0 12px 18px rgba(8, 18, 31, 0.18));
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
  .tools-resource-grid,
  .tools-survey-grid {
    grid-template-columns: 1fr;
  }
  .resource-card {
    position: relative;
    overflow: hidden;
    display: grid;
    gap: 12px;
    align-content: start;
    min-height: 100%;
    border-radius: 30px;
    border: 1px solid rgba(31, 42, 51, 0.08);
    background: linear-gradient(180deg, var(--resource-wash, rgba(255, 255, 255, 0.98)) 0%, rgba(255, 255, 255, 0.98) 100%);
    box-shadow: var(--shadow-soft);
  }
  .resource-card::after {
    content: "";
    position: absolute;
    right: -22px;
    bottom: -28px;
    width: 116px;
    height: 116px;
    border-radius: 36px;
    background: var(--resource-glow, rgba(57, 86, 119, 0.08));
    opacity: 0.9;
    pointer-events: none;
  }
  .resource-card > * {
    position: relative;
    z-index: 1;
  }
  .resource-card .article-meta {
    display: inline-flex;
    width: max-content;
    padding: 6px 11px;
    border-radius: 999px;
    border: 1px solid rgba(31, 42, 51, 0.08);
    background: rgba(255, 255, 255, 0.76);
  }
  .resource-card h3 {
    margin: 0;
    font-size: 1.08rem;
    line-height: 1.38;
    letter-spacing: -0.03em;
  }
  .resource-card p {
    margin: 0;
  }
  .resource-status-list {
    display: grid;
    gap: 8px;
    margin-top: auto;
    padding-top: 14px;
    border-top: 1px solid rgba(31, 42, 51, 0.08);
  }
  .resource-status-item {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }
  .resource-status-item strong {
    color: var(--muted);
    font-size: 0.76rem;
    font-weight: 700;
    line-height: 1.45;
  }
  .resource-status-item span {
    color: var(--accent-strong);
    font-size: 0.79rem;
    font-weight: 700;
    line-height: 1.45;
    text-align: right;
  }
  .resource-link {
    align-items: center;
    gap: 6px;
    width: max-content;
    margin-top: 4px;
    padding: 10px 14px;
    border-radius: 999px;
    border: 1px solid rgba(31, 42, 51, 0.08);
    background: rgba(255, 255, 255, 0.78);
  }
  .resource-link::after {
    content: "↗";
    font-size: 0.82rem;
  }
  .resource-card--navy {
    --resource-wash: rgba(57, 86, 119, 0.12);
    --resource-glow: rgba(57, 86, 119, 0.16);
  }
  .resource-card--warm {
    --resource-wash: rgba(221, 147, 103, 0.12);
    --resource-glow: rgba(221, 147, 103, 0.16);
  }
  .resource-card--teal {
    --resource-wash: rgba(125, 142, 152, 0.12);
    --resource-glow: rgba(125, 142, 152, 0.16);
  }
  .resource-card--sand {
    --resource-wash: rgba(227, 218, 204, 0.62);
    --resource-glow: rgba(214, 198, 178, 0.32);
  }
  .resource-card--survey {
    border-radius: 32px;
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
  .filter-search-wrap {
    display: grid;
    gap: 6px;
  }
  .filter-search-input {
    width: 100%;
    padding: 12px 14px;
    border: 1px solid rgba(31, 42, 51, 0.08);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.96);
    color: var(--text);
    font: inherit;
    font-size: 0.92rem;
    font-weight: 600;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.78);
  }
  .filter-search-input::placeholder {
    color: rgba(102, 113, 123, 0.82);
    font-weight: 500;
  }
  .filter-search-input:focus {
    outline: 2px solid rgba(57, 86, 119, 0.14);
    outline-offset: 1px;
    border-color: rgba(57, 86, 119, 0.24);
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
    line-height: 1.55;
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
      radial-gradient(circle at top left, rgba(57, 86, 119, 0.14), transparent 30%),
      radial-gradient(circle at top right, rgba(221, 147, 103, 0.16), transparent 28%),
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
    background: radial-gradient(circle, rgba(57, 86, 119, 0.16) 0%, rgba(57, 86, 119, 0) 74%);
  }
  .home-briefing-card.digest-organic {
    border-color: var(--home-apricot-soft);
    border-radius: 34px 30px 88px 34px;
    background:
      radial-gradient(circle at top right, rgba(221, 147, 103, 0.18), transparent 30%),
      radial-gradient(circle at bottom left, rgba(57, 86, 119, 0.08), transparent 28%),
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
    border-color: rgba(31, 42, 51, 0.08);
    border-radius: 30px;
    background:
      linear-gradient(180deg, rgba(252, 249, 244, 0.99) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-briefing-card.support-pill::after {
    display: none;
  }
  .home-briefing-card.footer-warm {
    padding: 0;
    gap: 0;
    border-color: var(--home-apricot-soft);
    border-radius: 36px 36px 84px 44px;
    background:
      radial-gradient(circle at top right, rgba(221, 147, 103, 0.18), transparent 28%),
      radial-gradient(circle at bottom left, rgba(57, 86, 119, 0.06), transparent 30%),
      linear-gradient(180deg, rgba(249, 240, 233, 0.99) 0%, rgba(255, 255, 255, 0.99) 100%);
    color: var(--text);
  }
  .home-briefing-card.footer-warm::after {
    right: -62px;
    bottom: -88px;
    width: 124px;
    height: 124px;
    border-radius: 999px;
    background: rgba(221, 147, 103, 0.1);
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
    letter-spacing: -0.055em;
    max-width: 12em;
    white-space: normal;
  }
  .home-briefing-title-line {
    display: block;
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
    white-space: pre-line;
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
  .home-briefing-content {
    display: grid;
    gap: 18px;
    min-width: 0;
  }
  .home-briefing-card.lead-arch.has-media {
    padding-right: clamp(164px, 36%, 236px);
    min-height: 312px;
  }
  .home-briefing-card > .home-illustration-slot {
    position: absolute;
    right: 16px;
    bottom: 2px;
    z-index: 0;
  }
  .home-illustration-slot {
    width: clamp(142px, 30%, 214px);
    max-width: 42%;
    pointer-events: none;
  }
  .home-illustration-slot img {
    display: block;
    width: 100%;
    height: auto;
    filter: drop-shadow(0 16px 22px rgba(8, 18, 31, 0.22));
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
    grid-template-columns: minmax(140px, 190px) minmax(0, 1fr);
    gap: 14px;
    align-items: stretch;
  }
  .home-glance-item {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 8px;
    min-height: 132px;
    padding: 16px 12px;
    border-radius: 8px;
    border: 1px solid rgba(23, 33, 49, 0.08);
    background:
      linear-gradient(180deg, rgba(250, 248, 243, 0.96) 0%, rgba(255, 255, 255, 0.99) 100%);
    text-align: center;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.88);
  }
  .home-glance-item.full {
    width: 100%;
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
    border-color: rgba(57, 86, 119, 0.12);
    background:
      radial-gradient(circle at top, rgba(57, 86, 119, 0.1), transparent 44%),
      linear-gradient(180deg, rgba(244, 246, 249, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
  }
  .home-glance-label {
    color: var(--muted);
    font-size: 0.75rem;
    font-weight: 800;
    line-height: 1.3;
  }
  .home-glance-value {
    font-size: 1.88rem;
    font-weight: 800;
    letter-spacing: -0.05em;
    line-height: 1;
    color: var(--accent-strong);
  }
  .home-keyword-panel {
    display: grid;
    gap: 10px;
    min-height: 132px;
    padding: 16px;
    border: 1px solid rgba(23, 33, 49, 0.08);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.72);
  }
  .home-keyword-heading {
    display: grid;
    gap: 3px;
  }
  .home-keyword-heading strong {
    color: var(--accent-strong);
    font-size: 0.86rem;
    line-height: 1.35;
  }
  .home-keyword-heading span {
    color: var(--muted);
    font-size: 0.76rem;
    line-height: 1.45;
  }
  .home-keyword-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-content: start;
  }
  .home-keyword-chip {
    display: inline-flex;
    align-items: center;
    min-height: 34px;
    padding: 7px 10px;
    border: 1px solid rgba(57, 86, 119, 0.14);
    border-radius: 8px;
    background: rgba(241, 245, 250, 0.96);
    color: var(--accent-strong);
    font-size: 0.78rem;
    font-weight: 800;
    line-height: 1.2;
    text-decoration: none;
  }
  .home-keyword-chip:nth-child(odd) {
    border-color: var(--home-apricot-soft);
    background: rgba(251, 235, 224, 0.94);
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
  .home-urgent-item:last-child {
    border-bottom: 0;
    padding-bottom: 0;
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
  .home-support-footer {
    display: grid;
    gap: 14px;
    padding: 24px 28px 30px 26px;
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
    align-items: flex-start;
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
    border-radius: 16px;
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
      linear-gradient(180deg, rgba(243, 246, 249, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
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
      linear-gradient(180deg, rgba(243, 246, 249, 0.98) 0%, rgba(255, 255, 255, 0.99) 100%);
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
    grid-template-columns: repeat(var(--bottom-nav-count, 6), minmax(0, 1fr));
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
    .brand {
      grid-template-columns: 86px minmax(0, 1fr);
      column-gap: 16px;
    }
    .brand-logo {
      width: 86px;
    }
    .brand-title {
      font-size: 2.76rem;
    }
    .brand-sub {
      font-size: 1rem;
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
    .home-briefing-card.lead-arch.has-media {
      padding-right: clamp(188px, 30%, 252px);
    }
    .home-briefing-card.digest-organic {
      border-radius: 40px 34px 104px 40px;
    }
    .home-briefing-card.support-pill {
      border-radius: 32px;
    }
    .home-briefing-card.footer-warm {
      border-radius: 38px 38px 96px 48px;
    }
    .home-support-footer {
      padding: 28px 34px 34px 30px;
    }
    .home-briefing-card > .home-illustration-slot {
      right: 24px;
      bottom: 4px;
    }
    .home-illustration-slot {
      width: clamp(170px, 30%, 236px);
    }
    .page-intro-card.has-media {
      grid-template-columns: minmax(0, 1fr) 124px;
      gap: 20px;
    }
    .page-intro-media {
      width: 124px;
      margin-right: -8px;
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
    .tools-resource-grid,
    .tools-survey-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
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
    .brand {
      grid-template-columns: 70px minmax(0, 1fr);
      column-gap: 11px;
    }
    .brand-logo {
      width: 70px;
    }
    .brand-title {
      font-size: 1.92rem;
    }
    .brand-sub {
      font-size: 0.82rem;
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
    .home-briefing-card.lead-arch.has-media {
      padding-right: 20px;
      min-height: 0;
    }
    .home-briefing-card.digest-organic {
      border-radius: 28px 24px 64px 28px;
    }
    .home-briefing-card.support-pill {
      border-radius: 26px;
    }
    .home-briefing-card.footer-warm {
      border-radius: 28px 28px 56px 34px;
    }
    .home-support-footer {
      padding: 22px 22px 26px 22px;
    }
    .home-briefing-card > .home-illustration-slot {
      position: relative;
      right: auto;
      bottom: auto;
      margin: 4px 0 -6px auto;
    }
    .home-illustration-slot {
      width: min(148px, 42vw);
      max-width: 58%;
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
    .home-glance-grid {
      grid-template-columns: minmax(0, 1fr);
    }
    .home-keyword-panel {
      min-height: 0;
      padding: 14px;
    }
    .page-intro-card.has-media {
      grid-template-columns: minmax(0, 1fr) 86px;
      gap: 12px;
    }
    .page-intro-media {
      width: 86px;
      margin-right: -6px;
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
    .brand {
      grid-template-columns: 60px minmax(0, 1fr);
      column-gap: 10px;
    }
    .brand-logo {
      width: 60px;
    }
    .brand-title {
      font-size: 1.6rem;
    }
    .brand-sub {
      font-size: 0.72rem;
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
  <link rel="icon" type="image/svg+xml" href="assets/branding/youth-together-mark.svg">
  <style>{styles}</style>
</head>
<body data-page="{active_page}">
  <div class="shell">
    <header class="topbar">
<a class="brand" href="index.html" aria-label="청년 모아봄 홈으로 이동">
        <img class="brand-logo" src="assets/branding/youth-together-mark.svg" alt="">
        <div class="brand-copy">
          <span class="brand-title">청년 모아봄</span>
          <span class="brand-sub">오늘의 청년 정책과 이슈를 모아봅니다</span>
        </div>
      </a>
      <div class="topbar-side">
        {guide_link}
        {header_meta}
        <nav class="nav">{nav}</nav>
      </div>
    </header>
    {content}
    <footer class="footer-note">{footer_note}</footer>
  </div>
  <nav class="bottom-nav" style="--bottom-nav-count: {bottom_nav_count};">{bottom_nav}</nav>
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

  function normalizeSearchQuery(value) {
    return (value || '').trim().replace(/\s+/g, ' ');
  }

  function cardMatchesSearch(card, query) {
    const normalizedQuery = normalizeSearchQuery(query);
    if (!normalizedQuery) {
      return true;
    }
    const searchText = (card.getAttribute('data-article-search') || '').toLowerCase();
    return normalizedQuery.toLowerCase().split(' ').every((term) => searchText.includes(term));
  }

  function formatSearchLabel(query) {
    const normalizedQuery = normalizeSearchQuery(query);
    return normalizedQuery ? `검색 "${normalizedQuery}"` : '';
  }

  function applyNewsFilters(root, selectedDateStart, selectedDateEnd, selectedRegion, selectedQuery) {
    const normalizedDates = normalizeNewsDateRange(
      selectedDateStart ?? root.dataset.selectedDateStart ?? root.getAttribute('data-default-date-start') ?? '',
      selectedDateEnd ?? root.dataset.selectedDateEnd ?? root.getAttribute('data-default-date-end') ?? '',
    );
    const activeDateStart = normalizedDates.startDate;
    const activeDateEnd = normalizedDates.endDate;
    const hasDateRange = Boolean(activeDateStart || activeDateEnd);
    const activeRegion = selectedRegion || root.dataset.selectedRegion || root.getAttribute('data-default-region') || 'all';
    const activeQuery = normalizeSearchQuery(
      selectedQuery ?? root.dataset.selectedSearchQuery ?? root.getAttribute('data-default-search-query') ?? ''
    );
    root.dataset.selectedDateStart = activeDateStart;
    root.dataset.selectedDateEnd = activeDateEnd;
    root.dataset.selectedRegion = activeRegion;
    root.dataset.selectedSearchQuery = activeQuery;

    const articleCards = Array.from(root.querySelectorAll('[data-article-date]'));
    let visibleCount = 0;

    articleCards.forEach((card) => {
      const articleDate = card.getAttribute('data-article-date') || '';
      const articleRegion = card.getAttribute('data-article-region') || '중앙';
      const isAfterStart = !activeDateStart || (articleDate && articleDate >= activeDateStart);
      const isBeforeEnd = !activeDateEnd || (articleDate && articleDate <= activeDateEnd);
      const dateMatch = !hasDateRange || (isAfterStart && isBeforeEnd);
      const regionMatch = activeRegion === 'all' || articleRegion === activeRegion;
      const searchMatch = cardMatchesSearch(card, activeQuery);
      const isMatch = dateMatch && regionMatch && searchMatch;
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

    root.querySelectorAll('[data-news-search-input]').forEach((searchInput) => {
      if (searchInput.value !== activeQuery) {
        searchInput.value = activeQuery;
      }
    });

    const status = root.querySelector('[data-news-filter-status]');
    if (status) {
      const dateLabel = formatNewsDateRange(activeDateStart, activeDateEnd);
      const searchLabel = formatSearchLabel(activeQuery);
      if (!hasDateRange && activeRegion === 'all' && !searchLabel) {
        status.textContent = `전체 ${visibleCount}건을 보고 있습니다.`;
      } else {
        const parts = [];
        if (activeRegion !== 'all') {
          parts.push(activeRegion);
        }
        if (searchLabel) {
          parts.push(searchLabel);
        }
        if (hasDateRange) {
          parts.push(dateLabel);
        }
        status.textContent = `${parts.join(' · ')} 기사 ${visibleCount}건을 보고 있습니다.`;
      }
    }

    const emptyState = root.querySelector('[data-news-empty-state]');
    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }
  }

  function getPolicyAvailabilityByAttribute(articleCards, targetGroup, attributeName, activeType, activeDateStart, activeDateEnd, hasDateRange, activeQuery) {
    const availableValues = new Set();

    articleCards.forEach((card) => {
      const articleGroup = card.getAttribute('data-policy-group') || 'official';
      if (articleGroup !== targetGroup) {
        return;
      }
      const attributeValue = card.getAttribute(attributeName) || '';
      const articleType = card.getAttribute('data-policy-type') || '기타';
      const articleDate = card.getAttribute('data-article-date') || '';
      const typeMatch = activeType === 'all' || articleType === activeType;
      const isAfterStart = !activeDateStart || (articleDate && articleDate >= activeDateStart);
      const isBeforeEnd = !activeDateEnd || (articleDate && articleDate <= activeDateEnd);
      const dateMatch = !hasDateRange || (isAfterStart && isBeforeEnd);
      const searchMatch = cardMatchesSearch(card, activeQuery);

      if (attributeValue && typeMatch && dateMatch && searchMatch) {
        availableValues.add(attributeValue);
      }
    });

    return availableValues;
  }

  function formatPolicyGroup(value, scopeMode) {
    if (scopeMode === 'hub-detail') {
      if (value === 'official') {
        return '중앙부처 자문·회의';
      }
      if (value === 'local') {
        return '지역 청년정책 네트워크';
      }
      if (value === 'public') {
        return '공공기관 참여·협의';
      }
      return '전체';
    }
    if (value === 'official') {
      return '중앙정부';
    }
    if (value === 'local') {
      return '지자체';
    }
    return '전체';
  }

  function formatPolicyScopeLabel(group, scopeMode) {
    if (scopeMode === 'hub-detail') {
      if (group === 'official') {
        return '부처·기관';
      }
      if (group === 'local') {
        return '지역';
      }
      if (group === 'public') {
        return '공공기관';
      }
      return '세부 구분';
    }
    if (group === 'official') {
      return '중앙부처·기관';
    }
    if (group === 'local') {
      return '지역';
    }
    return '세부 구분';
  }

  function applyPolicyFilters(root, selectedGroup, selectedRegion, selectedType, selectedDateStart, selectedDateEnd, selectedQuery) {
    const normalizedDates = normalizeNewsDateRange(
      selectedDateStart ?? root.dataset.selectedDateStart ?? root.getAttribute('data-default-date-start') ?? '',
      selectedDateEnd ?? root.dataset.selectedDateEnd ?? root.getAttribute('data-default-date-end') ?? '',
    );
    const scopeMode = root.dataset.policyScopeMode || '';
    const activeGroup = selectedGroup || root.dataset.selectedPolicyGroup || root.getAttribute('data-default-policy-group') || 'all';
    let activeRegion = selectedRegion || root.dataset.selectedPolicyRegion || root.getAttribute('data-default-policy-region') || 'all';
    let activeScope = root.dataset.selectedPolicyScope || root.getAttribute('data-default-policy-scope') || 'all';
    const activeType = selectedType || root.dataset.selectedPolicyType || root.getAttribute('data-default-policy-type') || 'all';
    const activeQuery = normalizeSearchQuery(
      selectedQuery ?? root.dataset.selectedSearchQuery ?? root.getAttribute('data-default-search-query') ?? ''
    );
    const activeDateStart = normalizedDates.startDate;
    const activeDateEnd = normalizedDates.endDate;
    const hasDateRange = Boolean(activeDateStart || activeDateEnd);
    const usesPolicyScope = scopeMode === 'authority-region' || scopeMode === 'hub-detail';
    const usesHubDetailScope = scopeMode === 'hub-detail';
    const keepEmptySections = root.dataset.keepEmptySections === 'true';
    root.dataset.selectedPolicyGroup = activeGroup;
    root.dataset.selectedPolicyRegion = activeRegion;
    root.dataset.selectedPolicyScope = activeScope;
    root.dataset.selectedPolicyType = activeType;
    root.dataset.selectedSearchQuery = activeQuery;
    root.dataset.selectedDateStart = activeDateStart;
    root.dataset.selectedDateEnd = activeDateEnd;

    if (usesHubDetailScope) {
      activeRegion = 'all';
      root.dataset.selectedPolicyRegion = 'all';
    }

    const articleCards = Array.from(root.querySelectorAll('[data-policy-card="true"]'));
    const regionTargetGroup = usesPolicyScope ? (activeGroup === 'all' ? 'local' : activeGroup) : activeGroup;
    const availableRegions = getPolicyAvailabilityByAttribute(
      articleCards,
      regionTargetGroup,
      'data-article-region',
      activeType,
      activeDateStart,
      activeDateEnd,
      hasDateRange,
      activeQuery,
    );
    const availableAuthorities = getPolicyAvailabilityByAttribute(
      articleCards,
      'official',
      usesHubDetailScope ? 'data-policy-scope' : 'data-policy-authority',
      activeType,
      activeDateStart,
      activeDateEnd,
      hasDateRange,
      activeQuery,
    );
    const availableLocalScopes = getPolicyAvailabilityByAttribute(
      articleCards,
      'local',
      usesHubDetailScope ? 'data-policy-scope' : 'data-article-region',
      activeType,
      activeDateStart,
      activeDateEnd,
      hasDateRange,
      activeQuery,
    );
    const availablePublicScopes = getPolicyAvailabilityByAttribute(
      articleCards,
      'public',
      'data-policy-scope',
      activeType,
      activeDateStart,
      activeDateEnd,
      hasDateRange,
      activeQuery,
    );
    if (activeRegion !== 'all' && !availableRegions.has(activeRegion)) {
      activeRegion = 'all';
    }
    root.dataset.selectedPolicyRegion = activeRegion;

    let visibleScopeKind = 'all';
    let availableScopes = new Set();
    if (usesPolicyScope) {
      if (activeGroup === 'official') {
        visibleScopeKind = 'official';
        availableScopes = availableAuthorities;
      } else if (activeGroup === 'local') {
        visibleScopeKind = 'local';
        availableScopes = usesHubDetailScope ? availableLocalScopes : availableRegions;
      } else if (usesHubDetailScope && activeGroup === 'public') {
        visibleScopeKind = 'public';
        availableScopes = availablePublicScopes;
      } else {
        activeScope = 'all';
      }
      if (activeScope !== 'all' && !availableScopes.has(activeScope)) {
        activeScope = 'all';
      }
      root.dataset.selectedPolicyScope = activeScope;
    }

    const visibleByGroup = { official: 0, local: 0, public: 0, related: 0 };
    let visibleCount = 0;

    articleCards.forEach((card) => {
      const articleGroup = card.getAttribute('data-policy-group') || 'official';
      const articleRegion = card.getAttribute('data-article-region') || '중앙';
      const articleAuthority = card.getAttribute('data-policy-authority') || '';
      const articleScope = usesHubDetailScope
        ? (card.getAttribute('data-policy-scope') || '')
        : (articleGroup === 'official' ? articleAuthority : articleRegion);
      const articleType = card.getAttribute('data-policy-type') || '기타';
      const articleDate = card.getAttribute('data-article-date') || '';
      const groupMatch = activeGroup === 'all' || articleGroup === activeGroup;
      const regionMatch = activeRegion === 'all' || articleRegion === activeRegion;
      const scopeMatch = !usesPolicyScope || activeGroup === 'all' || activeScope === 'all' || articleScope === activeScope;
      const typeMatch = activeType === 'all' || articleType === activeType;
      const isAfterStart = !activeDateStart || (articleDate && articleDate >= activeDateStart);
      const isBeforeEnd = !activeDateEnd || (articleDate && articleDate <= activeDateEnd);
      const dateMatch = !hasDateRange || (isAfterStart && isBeforeEnd);
      const searchMatch = cardMatchesSearch(card, activeQuery);
      const isMatch = groupMatch && regionMatch && scopeMatch && typeMatch && dateMatch && searchMatch;
      card.hidden = !isMatch;
      if (isMatch) {
        visibleCount += 1;
        visibleByGroup[articleGroup] = (visibleByGroup[articleGroup] || 0) + 1;
      }
    });

    root.querySelectorAll('[data-policy-filter]').forEach((button) => {
      const group = button.getAttribute('data-filter-group') || 'group';
      const value = button.getAttribute('data-filter-value') || 'all';
      const isScopeButton = button.hasAttribute('data-policy-scope-button');
      let isActive =
        group === 'group' ? value === activeGroup :
        group === 'region' ? value === activeRegion :
        group === 'type' ? value === activeType :
        value === 'all' && !hasDateRange;
      if (group === 'region' && value !== 'all') {
        button.hidden = !availableRegions.has(value);
      }
      if (usesPolicyScope && isScopeButton) {
        const scopeKind = button.getAttribute('data-scope-kind') || 'all';
        if (scopeKind === 'all') {
          button.hidden = false;
        } else if (scopeKind !== visibleScopeKind) {
          button.hidden = true;
        } else {
          button.hidden = !availableScopes.has(value);
        }
        isActive = value === activeScope;
      }
      button.classList.toggle('active', isActive);
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    const scopeLabel = root.querySelector('[data-policy-scope-label]');
    if (scopeLabel && usesPolicyScope) {
      scopeLabel.textContent = formatPolicyScopeLabel(activeGroup, scopeMode);
    }

    root.querySelectorAll('[data-policy-date-input]').forEach((dateInput) => {
      const role = dateInput.getAttribute('data-date-role') || 'start';
      const nextValue = role === 'end' ? activeDateEnd : activeDateStart;
      if (dateInput.value !== nextValue) {
        dateInput.value = nextValue;
      }
    });

    root.querySelectorAll('[data-policy-search-input]').forEach((searchInput) => {
      if (searchInput.value !== activeQuery) {
        searchInput.value = activeQuery;
      }
    });

    root.querySelectorAll('[data-policy-section]').forEach((section) => {
      const sectionGroup = section.getAttribute('data-policy-section') || 'official';
      const visibleInSection = visibleByGroup[sectionGroup] || 0;
      const shouldKeepEmpty = keepEmptySections && (activeGroup === 'all' || sectionGroup === activeGroup);
      section.hidden = visibleInSection === 0 && !shouldKeepEmpty;
      const count = section.querySelector('[data-policy-section-count]');
      if (count) {
        count.textContent = `${visibleInSection}건`;
      }
    });

    const status = root.querySelector('[data-policy-filter-status]');
    if (status) {
      const parts = [];
      if (activeGroup !== 'all') {
        parts.push(formatPolicyGroup(activeGroup, scopeMode));
      }
      if (usesPolicyScope && activeGroup !== 'all' && activeScope !== 'all') {
        parts.push(activeScope);
      } else if (activeRegion !== 'all') {
        parts.push(activeRegion);
      }
      if (activeType !== 'all') {
        parts.push(activeType);
      }
      if (activeQuery) {
        parts.push(formatSearchLabel(activeQuery));
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
          root.dataset.selectedSearchQuery || root.getAttribute('data-default-search-query') || '',
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
        if (filterGroup === 'scope') {
          root.dataset.selectedPolicyScope = filterValue;
        }
        applyPolicyFilters(
          root,
          filterGroup === 'group' ? filterValue : (root.dataset.selectedPolicyGroup || root.getAttribute('data-default-policy-group') || 'all'),
          filterGroup === 'region' ? filterValue : (root.dataset.selectedPolicyRegion || root.getAttribute('data-default-policy-region') || 'all'),
          filterGroup === 'type' ? filterValue : (root.dataset.selectedPolicyType || root.getAttribute('data-default-policy-type') || 'all'),
          filterGroup === 'date' ? '' : (root.dataset.selectedDateStart || root.getAttribute('data-default-date-start') || ''),
          filterGroup === 'date' ? '' : (root.dataset.selectedDateEnd || root.getAttribute('data-default-date-end') || ''),
          root.dataset.selectedSearchQuery || root.getAttribute('data-default-search-query') || '',
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

  const pageParams = new URLSearchParams(window.location.search);
  const queryFromUrl = normalizeSearchQuery(pageParams.get('q') || pageParams.get('keyword') || '');

  document.querySelectorAll('[data-news-filter-root]').forEach((root) => {
    applyNewsFilters(
      root,
      root.getAttribute('data-default-date-start') || '',
      root.getAttribute('data-default-date-end') || '',
      root.getAttribute('data-default-region') || 'all',
      queryFromUrl || root.getAttribute('data-default-search-query') || '',
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
      root.getAttribute('data-default-search-query') || '',
    );
  });

  document.addEventListener('input', (event) => {
    const searchInput = event.target.closest('[data-news-search-input]');
    if (searchInput) {
      const root = searchInput.closest('[data-news-filter-root]');
      if (!root) {
        return;
      }
      applyNewsFilters(
        root,
        root.dataset.selectedDateStart || root.getAttribute('data-default-date-start') || '',
        root.dataset.selectedDateEnd || root.getAttribute('data-default-date-end') || '',
        root.dataset.selectedRegion || root.getAttribute('data-default-region') || 'all',
        searchInput.value,
      );
      return;
    }

    const policySearchInput = event.target.closest('[data-policy-search-input]');
    if (!policySearchInput) {
      return;
    }
    const policyRoot = policySearchInput.closest('[data-policy-filter-root]');
    if (!policyRoot) {
      return;
    }
    applyPolicyFilters(
      policyRoot,
      policyRoot.dataset.selectedPolicyGroup || policyRoot.getAttribute('data-default-policy-group') || 'all',
      policyRoot.dataset.selectedPolicyRegion || policyRoot.getAttribute('data-default-policy-region') || 'all',
      policyRoot.dataset.selectedPolicyType || policyRoot.getAttribute('data-default-policy-type') || 'all',
      policyRoot.dataset.selectedDateStart || policyRoot.getAttribute('data-default-date-start') || '',
      policyRoot.dataset.selectedDateEnd || policyRoot.getAttribute('data-default-date-end') || '',
      policySearchInput.value,
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
        root.dataset.selectedSearchQuery || root.getAttribute('data-default-search-query') || '',
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
      policyRoot.dataset.selectedSearchQuery || policyRoot.getAttribute('data-default-search-query') || '',
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


def build_analytics_script() -> str:
    endpoint = PUBLIC_ANALYTICS_ENDPOINT or "/analytics/collect/"
    return f"""
(() => {{
  const endpoint = {json.dumps(endpoint, ensure_ascii=False)};
  const scope = {json.dumps(PUBLIC_ANALYTICS_SCOPE, ensure_ascii=False)};
  function getStoredId(storage, key) {{
    try {{
      let value = storage.getItem(key);
      if (!value) {{
        value = (window.crypto && window.crypto.randomUUID) ? window.crypto.randomUUID() : `${{Date.now()}}-${{Math.random().toString(16).slice(2)}}`;
        storage.setItem(key, value);
      }}
      return value;
    }} catch (error) {{
      return `${{Date.now()}}-${{Math.random().toString(16).slice(2)}}`;
    }}
  }}
  const visitorId = getStoredId(window.localStorage, "ytVisitorId");
  const sessionId = getStoredId(window.sessionStorage, "ytSessionId");
  const payload = JSON.stringify({{
    site_scope: scope,
    visitor_id: visitorId,
    session_id: sessionId,
    page_path: window.location.pathname,
    page_url: window.location.href,
    page_title: document.title,
    referrer: document.referrer || "",
    source_origin: window.location.origin || ""
  }});
  try {{
    if (navigator.sendBeacon) {{
      navigator.sendBeacon(endpoint, payload);
    }} else {{
      fetch(endpoint, {{
        method: "POST",
        mode: "no-cors",
        keepalive: true,
        headers: {{ "Content-Type": "text/plain;charset=UTF-8" }},
        body: payload
      }});
    }}
  }} catch (error) {{
    console.debug("analytics_beacon_failed", error);
  }}
}})();
"""


def build_page_script() -> str:
    return "\n".join((BASE_SCRIPT, build_analytics_script()))


NAV_ITEMS = [
    ("index.html", "홈"),
    ("news.html", "뉴스"),
    ("election.html", "선거·공약"),
    ("policies.html", "정책"),
    ("hub.html", "참여·회의"),
    ("tools.html", "자료도구"),
    ("contact.html", "제보·문의"),
]


NAV_ICONS = {
    "index.html": "홈",
    "news.html": "뉴",
    "election.html": "선",
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
      <p>홈 첫 화면은 오늘 바로 볼 기사부터 보는 구조입니다. 오늘 날짜로 올라온 기사 전체 수를 먼저 보고, 뉴스와 선거·공약, 정책 흐름으로 이어서 볼 수 있습니다.</p>
      <div class="list">
        <div class="list-item"><strong>홈</strong><span>가장 먼저 볼 기사와 오늘 집계를 한 번에 봅니다.</span></div>
        <div class="list-item"><strong>정책</strong><span>정부 원문 중심의 공식 발표를 확인합니다.</span></div>
        <div class="list-item"><strong>선거·공약</strong><span>지방선거 시기에는 청년 공약과 선거 기사를 따로 모아 봅니다.</span></div>
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
    url = html.escape(article_target_url(article))
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
    url = article_target_url(article)
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
    escaped_url = html.escape(article_target_url(article))
    escaped_title = html.escape(display_article_title(article))
    article_region = html.escape(news_region_label(article))
    article_search = html.escape(build_article_search_text(article, summary_text), quote=True)
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
        f'data-article-search="{article_search}"',
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


def render_hub_article_meta(article: dict, category_label: str) -> str:
    detail_label = hub_scope_detail_label(article)
    source = format_source_label(article.get("source") or article.get("source_name"))
    published = (article.get("published_date", "") or "")[:10] or "날짜 미상"
    return (
        '<div class="article-meta">'
        '<div class="article-meta-tags">'
        f'<span class="meta-pill primary">{html.escape(category_label)}</span>'
        f'<span class="meta-pill subtle">{html.escape(detail_label)}</span>'
        '</div>'
        '<div class="article-byline">'
        f'<span class="meta-item">{html.escape(source)}</span>'
        '<span class="meta-divider" aria-hidden="true">•</span>'
        f'<span class="meta-item">{html.escape(published)}</span>'
        '</div>'
        '</div>'
    )


def render_hub_record_card(article: dict) -> str:
    hub_topics = ", ".join(article.get("hub_topics", [])[:3]) or "참여 의제"
    governance_scope = article.get("governance_scope") or "참여 기록"
    activity_types = ", ".join(article.get("governance_activity_types", [])[:3]) or "활동 기록"
    summary_text = summarize_article_text(article, limit=112)
    escaped_url = html.escape(article_target_url(article))
    escaped_title = html.escape(display_article_title(article))
    article_region = html.escape(news_region_label(article))
    article_group = hub_group_label(article)
    article_scope = html.escape(hub_scope_detail_label(article))
    article_type = html.escape(hub_activity_label(article))
    summary_html = (
        f'<p class="article-summary"><a class="article-summary-link" href="{escaped_url}" target="_blank" rel="noreferrer" '
        f'aria-label="{escaped_title} 링크 바로가기">{html.escape(summary_text)}</a></p>'
        if summary_text
        else ""
    )
    article_date = html.escape(article_date_value(article))
    article_search = html.escape(
        build_article_search_text(article, summary_text, governance_scope, activity_types, hub_topics, article_scope),
        quote=True,
    )
    return f"""
    <article class="article-card" data-article-card="true" data-policy-card="true" data-policy-group="{article_group}" data-policy-scope="{article_scope}" data-policy-type="{article_type}" data-article-url="{escaped_url}" data-article-title="{escaped_title}" data-article-date="{article_date}" data-article-region="{article_region}" data-article-search="{article_search}">
      {render_hub_article_meta(article, governance_scope)}
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


def render_external_feature_card(title: str, description: str, href: str, meta: str) -> str:
    return f"""
    <article class="section-card">
      <div class="article-meta">{html.escape(meta)}</div>
      <h3>{html.escape(title)}</h3>
      <p>{html.escape(description)}</p>
      <a class="mini-link" href="{html.escape(href)}" target="_blank" rel="noreferrer">사이트 열기</a>
    </article>
    """


def fetch_remote_text(url: str) -> str:
    cached = REMOTE_TEXT_CACHE.get(url)
    if cached is not None:
        return cached

    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()
    except Exception:
        REMOTE_TEXT_CACHE[url] = ""
        return ""

    text = payload.decode("utf-8", "ignore")
    REMOTE_TEXT_CACHE[url] = text
    return text


def extract_remote_value(url: str, patterns: list[str], fallback: str = "") -> tuple[str, bool]:
    text = fetch_remote_text(url)
    if not text:
        return fallback, False

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        captured = match.group(1) if match.groups() else match.group(0)
        value = normalize_inline_text(html.unescape(captured))
        if value:
            return value, True

    return fallback, True


def find_related_resource_articles(articles: list[dict], keywords: list[str]) -> list[dict]:
    normalized_keywords = [normalize_inline_text(keyword) for keyword in keywords if normalize_inline_text(keyword)]
    if not normalized_keywords:
        return []

    matched: list[dict] = []
    for article in sort_articles_by_recency(articles):
        haystack = normalize_inline_text(
            " ".join(
                str(article.get(field, ""))
                for field in ("title", "lead_text", "summary", "classification_reason", "source", "source_name")
            )
        )
        if any(keyword in haystack for keyword in normalized_keywords):
            matched.append(article)
    return matched


def build_resource_status_rows(resource: dict, articles: list[dict]) -> list[tuple[str, str]]:
    basis_value, is_reachable = extract_remote_value(
        resource.get("href", ""),
        resource.get("basis_patterns", []),
        resource.get("basis_fallback", ""),
    )
    is_available = bool(basis_value) or is_reachable
    rows = [
        (resource.get("basis_label", "공식 기준"), basis_value or "기준 정보 확인 중"),
        ("자료 상태", "자료 확인됨" if is_available else "자동 확인 필요"),
    ]

    related_articles = find_related_resource_articles(articles, resource.get("keywords", []))
    if related_articles:
        latest = related_articles[0]
        latest_date = article_date_value(latest) or "날짜 미상"
        rows.append(("최근 기사 추적", f"{latest_date} · {len(related_articles)}건"))
    else:
        rows.append(("최근 기사 추적", "최근 수집 기사 없음"))

    return rows


def render_resource_card(
    title: str,
    description: str,
    href: str,
    meta: str,
    *,
    tone: str = "sand",
    status_rows: list[tuple[str, str]] | None = None,
) -> str:
    status_html = ""
    if status_rows:
        rendered_rows = "".join(
            f'<div class="resource-status-item"><strong>{html.escape(label)}</strong><span>{html.escape(value)}</span></div>'
            for label, value in status_rows
        )
        status_html = f'<div class="resource-status-list">{rendered_rows}</div>'

    return f"""
    <article class="section-card resource-card resource-card--{html.escape(tone)}">
      <div class="article-meta">{html.escape(meta)}</div>
      <h3>{html.escape(title)}</h3>
      <p>{html.escape(description)}</p>
      {status_html}
      <a class="mini-link resource-link" href="{html.escape(href)}" target="_blank" rel="noreferrer">사이트 열기</a>
    </article>
    """


def render_card_illustration(
    config: dict[str, str] | None,
    *,
    slot_class: str,
    img_class: str,
    loading: str = "lazy",
) -> str:
    if not config:
        return ""

    onerror = (
        "const host=this.closest('[data-media-host]');"
        "if(host){host.classList.remove('has-media');}"
        "this.parentElement.remove();"
    )
    return (
        f'<div class="{slot_class}">'
        f'<img class="{img_class}" src="{html.escape(config["src"])}" alt="{html.escape(config["alt"])}" '
        f'decoding="async" loading="{loading}" onerror="{onerror}"></div>'
    )


def render_compact_intro(kicker: str, description: str, media_key: str | None = None) -> str:
    media_config = PAGE_INTRO_ILLUSTRATIONS.get(media_key) if media_key else None
    media_html = render_card_illustration(
        media_config,
        slot_class="page-intro-media",
        img_class="page-intro-media-img",
    )
    media_class = " has-media" if media_html else ""
    return f"""
    <article class="page-intro-card{media_class}" data-media-host="page-intro">
      <div class="page-intro-content">
        <div class="page-intro-top">
          <span class="page-intro-badge">{html.escape(kicker)}</span>
        </div>
        <p class="page-intro-copy">{html.escape(description)}</p>
      </div>
      {media_html}
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


def article_target_url(article: dict) -> str:
    return preferred_article_url(article) or article.get("url") or ""


def build_article_search_text(article: dict, *extra_terms: str) -> str:
    fields = [
        clean_article_title(article.get("title")),
        normalize_inline_text(article.get("summary")),
        normalize_inline_text(article.get("lead_text")),
        normalize_inline_text(article.get("section")),
        normalize_inline_text(article.get("source")),
        normalize_inline_text(article.get("source_name")),
        normalize_inline_text(" ".join(article.get("authors") or [])),
        normalize_inline_text(" ".join(article.get("issue_tags") or [])),
        normalize_inline_text(" ".join(article.get("location_tags") or [])),
        news_region_label(article),
        *[normalize_inline_text(value) for value in article.get("display_badges", [])],
        *[normalize_inline_text(value) for value in extra_terms],
    ]
    return normalize_inline_text(" ".join(value for value in fields if value))


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
    override = normalize_inline_text(article.get("policy_type_override"))
    if override:
        return override

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


def policy_authority_label(article: dict) -> str:
    explicit_authority = normalize_inline_text(article.get("policy_authority"))
    if explicit_authority:
        return explicit_authority

    source_text = normalize_inline_text(
        " ".join(
            value
            for value in [
                article.get("policy_authority"),
                article.get("source"),
                article.get("source_name"),
                article.get("publisher_domain"),
            ]
            if value
        )
    )

    preferred_matches = [
        ("기획재정부", "기획재정부"),
        ("교육부", "교육부"),
        ("고용노동부", "고용노동부"),
        ("행정안전부", "행정안전부"),
        ("보건복지부", "보건복지부"),
        ("국토교통부", "국토교통부"),
        ("문화체육관광부", "문화체육관광부"),
        ("중소벤처기업부", "중소벤처기업부"),
        ("금융위원회", "금융위원회"),
        ("국무조정실", "국무조정실"),
        ("정책브리핑", "정책브리핑"),
    ]
    for keyword, label in preferred_matches:
        if keyword in source_text:
            return label

    return format_source_label(article.get("source") or article.get("source_name"))


def hub_group_label(article: dict) -> str:
    scope = normalize_inline_text(article.get("governance_scope"))
    if scope == "정부":
        return "official"
    if scope == "지자체":
        return "local"
    if scope == "공공기관":
        return "public"
    return "public"


def hub_scope_detail_label(article: dict) -> str:
    group = hub_group_label(article)
    owner_label = normalize_inline_text(article.get("hub_owner_label"))
    if group == "local":
        return owner_label or news_region_label(article)
    if group in {"official", "public"}:
        return owner_label or format_source_label(article.get("source") or article.get("source_name"))
    return owner_label or news_region_label(article)


def hub_activity_label(article: dict) -> str:
    activity_types = [normalize_inline_text(value) for value in article.get("governance_activity_types", [])]
    activity_types = [value for value in activity_types if value]
    return activity_types[0] if activity_types else "기타"


def collect_policy_types(articles: list[dict]) -> list[str]:
    preferred_order = ["시행계획", "공약", "지원사업", "심의·의결", "모집", "정책 발표", "기타"]
    seen = {policy_type_label(article) for article in articles}
    ordered = [label for label in preferred_order if label in seen]
    return ordered


def collect_policy_authorities(articles: list[dict]) -> list[str]:
    preferred_order = MAJOR_CENTRAL_POLICY_AUTHORITIES
    seen = {policy_authority_label(article) for article in articles if policy_authority_label(article)}
    ordered = [label for label in preferred_order if label in seen]
    return ordered


def build_curated_major_policy_articles() -> list[dict]:
    curated_articles: list[dict] = []
    for entry in CURATED_MAJOR_POLICY_WATCHLIST:
        authority = entry["policy_authority"]
        article = {
            "title": entry["title"],
            "url": entry["url"],
            "publisher_url": entry["url"],
            "canonical_url": entry["url"],
            "feed_url": entry["url"],
            "source": authority,
            "source_name": authority,
            "source_kind": "official",
            "source_url": entry["url"],
            "published_date": entry["published_date"],
            "publisher_published_at": entry["published_date"],
            "lead_text": entry["lead_text"],
            "summary": entry["lead_text"],
            "policy_authority": authority,
            "is_official_source": True,
            "region": "전국",
            "display_badges": ["공식 자료", authority],
            "issue_tags": [],
            "location_tags": [],
            "policy_type_override": entry["policy_type"],
            "pipeline_flags": {
                "collected": True,
                "deduped": True,
                "classified": True,
                "selected": False,
                "published": True,
            },
        }
        curated_articles.append(article)
    return curated_articles


def add_major_policy_watchlist_articles(articles: list[dict]) -> list[dict]:
    if not articles:
        return build_curated_major_policy_articles()

    existing_authorities = {
        policy_authority_label(article)
        for article in articles
        if policy_authority_label(article) in MAJOR_CENTRAL_POLICY_AUTHORITIES
    }
    existing_keys = {
        normalize_inline_text(article.get("publisher_url") or article.get("canonical_url") or article.get("url"))
        or normalize_inline_text(f'{article.get("title", "")}|{policy_authority_label(article)}')
        for article in articles
    }

    supplemented = list(articles)
    for curated in build_curated_major_policy_articles():
        authority = curated["policy_authority"]
        identity_key = normalize_inline_text(curated.get("publisher_url") or curated.get("url"))
        if authority in existing_authorities:
            continue
        if identity_key in existing_keys:
            continue
        supplemented.append(curated)

    return sort_articles_by_recency(supplemented)


def collect_local_policy_regions(articles: list[dict]) -> list[str]:
    counts: dict[str, int] = {}
    for article in articles:
        region = normalize_inline_text(article.get("region"))
        if not region or region == "전국":
            continue
        counts[region] = counts.get(region, 0) + 1
    return sorted(counts, key=lambda region: (-counts[region], region))


def collect_hub_activity_types(articles: list[dict]) -> list[str]:
    preferred_order = ["회의", "위원회", "자문", "출범", "모집", "협약", "간담회", "포럼", "워크숍", "발표회", "기타"]
    seen = {hub_activity_label(article) for article in articles}
    ordered = [label for label in preferred_order if label in seen]
    return ordered


def collect_hub_scope_labels(articles: list[dict]) -> list[str]:
    counts: dict[str, int] = {}
    for article in articles:
        label = hub_scope_detail_label(article)
        if not label or label == "중앙":
            continue
        counts[label] = counts.get(label, 0) + 1
    return sorted(counts, key=lambda label: (-counts[label], label))


def render_policy_filter_panel(official_policies: list[dict], reference_policies: list[dict]) -> str:
    all_policies = [*official_policies, *reference_policies]
    group_buttons = [
        '<button class="filter-button active" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="all" aria-pressed="true">전체</button>',
        '<button class="filter-button" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="official" aria-pressed="false">중앙정부</button>',
        '<button class="filter-button" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="local" aria-pressed="false">지자체</button>',
    ]

    scope_buttons = [
        '<button class="filter-button active" type="button" data-policy-filter="true" '
        'data-filter-group="scope" data-filter-value="all" data-policy-scope-button="true" data-scope-kind="all" '
        'aria-pressed="true">전체</button>'
    ]
    for authority in collect_policy_authorities(official_policies):
        scope_buttons.append(
            f'<button class="filter-button" type="button" data-policy-filter="true" '
            f'data-filter-group="scope" data-filter-value="{html.escape(authority)}" '
            f'data-policy-scope-button="true" data-scope-kind="official" aria-pressed="false" hidden>'
            f'{html.escape(authority)}</button>'
        )
    for region in collect_local_policy_regions(reference_policies):
        scope_buttons.append(
            f'<button class="filter-button" type="button" data-policy-filter="true" '
            f'data-filter-group="scope" data-filter-value="{html.escape(region)}" '
            f'data-policy-scope-button="true" data-scope-kind="local" aria-pressed="false" hidden>'
            f'{html.escape(region)}</button>'
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
          <h3>구분 · 세부 · 유형 · 검색 · 기간</h3>
        </div>
        <div class="filter-stack">
          <div class="filter-group">
            <span class="filter-group-label">구분</span>
            <div class="filter-controls">{''.join(group_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label" data-policy-scope-label="true">세부 구분</span>
            <div class="filter-controls">{''.join(scope_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label">유형</span>
            <div class="filter-controls">{''.join(type_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label">검색</span>
            <label class="filter-search-wrap">
              <input class="filter-search-input" type="search" data-policy-search-input="true" placeholder="기사 제목, 요약, 출처 검색">
            </label>
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


def render_hub_filter_panel(
    government_records: list[dict],
    regional_records: list[dict],
    public_records: list[dict],
) -> str:
    all_records = [*government_records, *regional_records, *public_records]
    group_buttons = [
        '<button class="filter-button active" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="all" aria-pressed="true">전체</button>',
        '<button class="filter-button" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="official" aria-pressed="false">중앙부처 자문·회의</button>',
        '<button class="filter-button" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="local" aria-pressed="false">지역 청년정책 네트워크</button>',
        '<button class="filter-button" type="button" data-policy-filter="true" '
        'data-filter-group="group" data-filter-value="public" aria-pressed="false">공공기관 참여·협의</button>',
    ]

    scope_buttons = [
        '<button class="filter-button active" type="button" data-policy-filter="true" '
        'data-filter-group="scope" data-filter-value="all" data-policy-scope-button="true" data-scope-kind="all" '
        'aria-pressed="true">전체</button>'
    ]

    for label in collect_hub_scope_labels(government_records):
        scope_buttons.append(
            f'<button class="filter-button" type="button" data-policy-filter="true" '
            f'data-filter-group="scope" data-filter-value="{html.escape(label)}" '
            f'data-policy-scope-button="true" data-scope-kind="official" aria-pressed="false" hidden>'
            f'{html.escape(label)}</button>'
        )
    for label in collect_hub_scope_labels(regional_records):
        scope_buttons.append(
            f'<button class="filter-button" type="button" data-policy-filter="true" '
            f'data-filter-group="scope" data-filter-value="{html.escape(label)}" '
            f'data-policy-scope-button="true" data-scope-kind="local" aria-pressed="false" hidden>'
            f'{html.escape(label)}</button>'
        )
    for label in collect_hub_scope_labels(public_records):
        scope_buttons.append(
            f'<button class="filter-button" type="button" data-policy-filter="true" '
            f'data-filter-group="scope" data-filter-value="{html.escape(label)}" '
            f'data-policy-scope-button="true" data-scope-kind="public" aria-pressed="false" hidden>'
            f'{html.escape(label)}</button>'
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
          <h3>구분 · 세부 · 활동 · 검색 · 기간</h3>
          <p>뉴스와 별도로, 중앙부처 자문·회의와 지역 청년정책 네트워크, 공공기관 참여 기록만 구조화해 봅니다.</p>
        </div>
        <div class="filter-stack">
          <div class="filter-group">
            <span class="filter-group-label">구분</span>
            <div class="filter-controls">{''.join(group_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label" data-policy-scope-label="true">세부 구분</span>
            <div class="filter-controls">{''.join(scope_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label">활동</span>
            <div class="filter-controls">{''.join(type_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label">검색</span>
            <label class="filter-search-wrap">
              <input class="filter-search-input" type="search" data-policy-search-input="true" placeholder="기사 제목, 요약, 출처 검색">
            </label>
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


def is_election_promise_article(article: dict) -> bool:
    if article.get("is_official_source"):
        return False
    return home_campaign_political(article)


def with_election_badges(article: dict) -> dict:
    badges: list[str] = []
    if home_substantive_promise(article):
        badges.append("정책 공약")
    elif home_campaign_political(article):
        badges.append("선거 기사")

    existing_badges = [str(value).strip() for value in article.get("display_badges", []) if str(value).strip()]
    merged_badges = list(dict.fromkeys([*badges, *existing_badges]))
    if merged_badges == existing_badges:
        return article

    tagged_article = dict(article)
    tagged_article["display_badges"] = merged_badges
    return tagged_article


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
          <h3>지역 · 검색 · 날짜별로 보기</h3>
          <p>지역은 바로 누르고, 검색어와 날짜를 함께 써서 필요한 기사만 빠르게 찾을 수 있습니다.</p>
        </div>
        <div class="filter-stack">
          <div class="filter-group">
            <span class="filter-group-label">지역</span>
            <div class="filter-controls">{''.join(region_buttons)}</div>
          </div>
          <div class="filter-group">
            <span class="filter-group-label">검색</span>
            <label class="filter-search-wrap">
              <input class="filter-search-input" type="search" data-news-search-input="true" placeholder="기사 제목, 요약, 출처 검색">
            </label>
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
    editorial_decision = str(article.get("editorial_decision") or "").strip().lower()
    is_highlighted = bool(article.get("editorial_is_highlighted"))
    parsed = parse_iso_datetime(article.get("published_date"))
    timestamp = parsed.timestamp() if parsed else 0.0
    return (
        2 if is_highlighted else 1 if editorial_decision == "include" else 0,
        timestamp,
    )


def sort_articles_by_recency(articles: list[dict]) -> list[dict]:
    return sorted(articles, key=article_sort_key, reverse=True)


def is_publicly_excluded(article: dict) -> bool:
    return str(article.get("editorial_decision") or "").strip().lower() == "exclude"


def filter_public_articles(articles: list[dict]) -> list[dict]:
    filtered: list[dict] = []
    for article in articles:
        if is_publicly_excluded(article):
            continue
        editorial_decision = str(article.get("editorial_decision") or "").strip().lower()
        if article.get("editorial_is_highlighted") or editorial_decision == "include":
            filtered.append(article)
            continue
        if is_public_interest_article(article):
            filtered.append(article)
    return filtered


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


def count_articles_on_reference_day(articles: list[dict], reference_time: str | None) -> int:
    reference_dt = parse_iso_datetime(reference_time)
    if reference_dt is None:
        parsed_dates = [parse_iso_datetime(article.get("published_date")) for article in articles]
        parsed_dates = [value for value in parsed_dates if value is not None]
        reference_dt = max(parsed_dates) if parsed_dates else None
    if reference_dt is None:
        return 0

    seen_keys: set[str] = set()
    total = 0
    for article in articles:
        published_dt = parse_iso_datetime(article.get("published_date"))
        if published_dt is None:
            continue
        if reference_dt.tzinfo is not None and published_dt.tzinfo is not None:
            published_day = published_dt.astimezone(reference_dt.tzinfo).date()
        else:
            published_day = published_dt.date()
        if published_day != reference_dt.date():
            continue
        identity = article_identity_key(article)
        if identity in seen_keys:
            continue
        seen_keys.add(identity)
        total += 1
    return total


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
    current_urls = [article_target_url(article) for article in recent_news_articles if article_target_url(article)]
    added_articles = [
        article
        for article in recent_news_articles
        if article_target_url(article) and article_target_url(article) not in previous_urls
    ]
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
    updated_snapshot = dict(snapshot)
    updated_snapshot.update(
        {
            "page_updated_at": page_updated_at,
            "recent_news_urls": current_urls,
            "briefing": briefing,
        }
    )
    save_home_update_snapshot(
        updated_snapshot
    )
    return briefing


def home_article_key(article: dict) -> str:
    return article_target_url(article) or clean_article_title(article.get("title"))


def _home_text(article: dict) -> str:
    return normalize_inline_text(
        " ".join(
            value
            for value in [
                clean_article_title(article.get("title")),
                normalize_inline_text(article.get("summary")),
                normalize_inline_text(article.get("lead_text")),
                normalize_inline_text(article.get("section")),
            ]
            if value
        )
    )


HOME_TITLE_SIGNAL_KEYWORDS: tuple[str, ...] = (
    "청년",
    "청년층",
    "청년세대",
    "사회초년생",
    "취준생",
    "대학생",
    "청년센터",
    "청년공간",
    "청년허브",
    "청년정책",
    "주거",
    "월세",
    "전세",
    "주택",
    "고용",
    "취업",
    "일자리",
    "노동",
    "노동권",
    "복지",
    "고립",
    "은둔",
    "부채",
    "대출",
    "지원사업",
    "모집",
    "예산",
    "조례",
    "시행계획",
    "종합계획",
    "기본계획",
    "위탁",
)

HOME_BUSINESS_RESULT_KEYWORDS: tuple[str, ...] = (
    "순이익",
    "영업이익",
    "매출",
    "실적",
    "자사주",
    "주주환원",
    "배당",
    "증권",
    "주가",
    "시가총액",
    "소각",
)

HOME_POLITICAL_ANALYSIS_KEYWORDS: tuple[str, ...] = (
    "여론조사",
    "보수 성향",
    "진보 성향",
    "지지율",
    "표심",
    "민심",
    "정치 성향",
)

HOME_EXPLICIT_YOUTH_LEAD_KEYWORDS: tuple[str, ...] = (
    "청년센터",
    "청년공간",
    "청년허브",
    "청년정책",
    "청년 일자리",
    "청년일자리",
    "청년 주거",
    "청년주거",
    "청년 대출",
    "청년부채",
    "청년 금융",
    "청년금융",
    "청년 지원사업",
    "청년지원사업",
    "청년 모집",
    "청년모집",
    "청년 예산",
    "청년조례",
    "청년 조례",
    "청년 노동",
    "청년복지",
    "청년 복지",
    "청년 고립",
    "청년 은둔",
    "취업 후 상환",
    "대학생",
    "취준생",
    "사회초년생",
)


def _home_title_text(article: dict) -> str:
    return normalize_inline_text(
        " ".join(
            value
            for value in [
                clean_article_title(article.get("title")),
                normalize_inline_text(article.get("section")),
            ]
            if value
        )
    )


def home_has_direct_title_signal(article: dict) -> bool:
    title_text = _home_title_text(article)
    return any(keyword in title_text for keyword in HOME_TITLE_SIGNAL_KEYWORDS)


def home_is_generic_business_result_article(article: dict) -> bool:
    title_text = _home_title_text(article)
    if not title_text:
        return False
    if home_has_direct_title_signal(article):
        return False
    return any(keyword in title_text for keyword in HOME_BUSINESS_RESULT_KEYWORDS)


def home_is_political_analysis_article(article: dict) -> bool:
    title_text = _home_title_text(article)
    if not title_text:
        return False
    if home_has_direct_title_signal(article):
        return False
    return any(keyword in title_text for keyword in HOME_POLITICAL_ANALYSIS_KEYWORDS)


def home_has_explicit_youth_lead_signal(article: dict) -> bool:
    lead_text = normalize_inline_text(
        " ".join(
            value
            for value in [
                normalize_inline_text(article.get("summary")),
                normalize_inline_text(article.get("lead_text")),
            ]
            if value
        )
    )
    if not lead_text:
        return False
    return any(keyword in lead_text for keyword in HOME_EXPLICIT_YOUTH_LEAD_KEYWORDS)


HOME_HOT_KEYWORD_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("청년센터", ("청년센터", "청년공간", "청년허브")),
    ("지원사업", ("지원사업", "지원 사업", "지원금", "바우처", "수당")),
    ("모집", ("모집", "공모", "신청", "접수", "선발")),
    ("취업", ("취업", "채용", "일자리", "고용", "대학일자리")),
    ("주거", ("주거", "주택", "월세", "전세", "임대")),
    ("금융", ("금융", "부채", "대출", "자산", "적금", "저축")),
    ("노동", ("노동", "노동권", "임금", "근로")),
    ("고립·은둔", ("고립", "은둔", "외로움")),
    ("복지", ("복지", "돌봄", "마음건강", "상담")),
    ("창업", ("창업", "스타트업", "벤처")),
    ("예산", ("예산", "추경", "재정")),
    ("조례", ("조례", "의회", "시행계획", "종합계획", "기본계획")),
)

HOME_HOT_KEYWORD_ALIASES = {
    "청년센터 운영": "청년센터",
    "고용": "취업",
    "부채": "금융",
    "고립·은둔": "고립·은둔",
}


def normalize_home_hot_keyword(value: object) -> str:
    keyword = normalize_inline_text(value)
    if not keyword:
        return ""
    return HOME_HOT_KEYWORD_ALIASES.get(keyword, keyword)


def articles_on_reference_day(articles: list[dict], reference_time: str | None) -> list[dict]:
    reference_dt = parse_iso_datetime(reference_time)
    if reference_dt is None:
        parsed_dates = [parse_iso_datetime(article.get("published_date")) for article in articles]
        parsed_dates = [value for value in parsed_dates if value is not None]
        reference_dt = max(parsed_dates) if parsed_dates else None
    if reference_dt is None:
        return []

    day_articles: list[dict] = []
    seen_keys: set[str] = set()
    for article in articles:
        published_dt = parse_iso_datetime(article.get("published_date"))
        if published_dt is None:
            continue
        if reference_dt.tzinfo is not None and published_dt.tzinfo is not None:
            published_day = published_dt.astimezone(reference_dt.tzinfo).date()
        else:
            published_day = published_dt.date()
        if published_day != reference_dt.date():
            continue
        identity = article_identity_key(article)
        if identity in seen_keys:
            continue
        seen_keys.add(identity)
        day_articles.append(article)
    return day_articles


def build_home_hot_keywords(articles: list[dict], reference_time: str | None, limit: int = HOME_HOT_KEYWORD_LIMIT) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for article in articles_on_reference_day(articles, reference_time):
        text = _home_text(article)
        article_keywords: list[str] = []
        for tag in article.get("issue_tags") or []:
            keyword = normalize_home_hot_keyword(tag)
            if keyword:
                article_keywords.append(keyword)
        for label, patterns in HOME_HOT_KEYWORD_PATTERNS:
            if any(pattern in text for pattern in patterns):
                article_keywords.append(label)
        for keyword in dict.fromkeys(article_keywords):
            counts[keyword] = counts.get(keyword, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def merge_home_candidate_articles(primary_articles: list[dict], fallback_articles: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen_keys: set[str] = set()
    for article, is_primary in [
        *((article, True) for article in primary_articles),
        *((article, False) for article in fallback_articles),
    ]:
        article_key = home_article_key(article)
        if not article_key or article_key in seen_keys:
            continue
        seen_keys.add(article_key)
        tagged_article = dict(article)
        tagged_article["_home_primary_candidate"] = is_primary
        merged.append(tagged_article)
    return merged


def home_campaign_political(article: dict) -> bool:
    text = _home_text(article)
    return any(
        keyword in text
        for keyword in (
            "선거",
            "후보",
            "예비후보",
            "유세",
            "공천",
            "지지율",
            "단일화",
            "출마",
            "경선",
            "정당",
            "국민의힘",
            "더불어민주당",
            "민주당",
            "개혁신당",
            "조국혁신당",
            "진보당",
            "공약",
        )
    )


def home_article_age_hours(article: dict, reference_dt: datetime | None) -> float:
    if reference_dt is None:
        return 10_000.0
    published_dt = parse_iso_datetime(article.get("published_date"))
    if published_dt is None:
        return 10_000.0
    delta = reference_dt - published_dt
    return max(delta.total_seconds() / 3600, 0.0)


def home_has_policy_or_operational_signal(article: dict) -> bool:
    if article.get("has_policy_operational_context"):
        return True
    text = _home_text(article)
    return any(
        keyword in text
        for keyword in (
            "청년센터",
            "청년공간",
            "청년허브",
            "운영",
            "위탁",
            "개소",
            "신설",
            "폐지",
            "예산",
            "조례",
            "시행계획",
            "종합계획",
            "기본계획",
            "지원사업",
            "모집",
            "발표",
            "시행",
            "설치",
            "확대",
        )
    )


def home_has_structural_issue_signal(article: dict) -> bool:
    if article.get("issue_tags"):
        return True
    text = _home_text(article)
    return any(
        keyword in text
        for keyword in (
            "고용",
            "취업",
            "실업",
            "주거",
            "주택",
            "월세",
            "전세",
            "부채",
            "금융",
            "노동",
            "노동권",
            "은둔",
            "고립",
            "복지",
            "청년센터",
            "청년공간",
            "청년허브",
        )
    )


def home_substantive_promise(article: dict) -> bool:
    return home_campaign_political(article) and home_has_policy_or_operational_signal(article)


def home_weak_youth_signal(article: dict) -> bool:
    if article.get("weak_youth_signal"):
        return True
    text = _home_text(article)
    if not any(keyword in text for keyword in ("청년", "청년층", "청년세대", "사회초년생", "대학생", "취준생")):
        return False
    if home_has_policy_or_operational_signal(article) or home_has_structural_issue_signal(article):
        return False
    if any(
        keyword in text
        for keyword in (
            "청년보좌역",
            "청년자문단",
            "청년참여단",
            "청년네트워크",
            "청년협의체",
            "청년위원회",
            "청년거버넌스",
        )
    ):
        return False
    return True


def is_home_today_candidate(article: dict, reference_dt: datetime | None) -> bool:
    if article.get("is_official_source"):
        return False
    if article.get("article_type") == "opinion" or article.get("is_noise"):
        return False
    if home_is_generic_business_result_article(article):
        return False
    if home_is_political_analysis_article(article):
        return False
    if home_campaign_political(article):
        return False
    if home_weak_youth_signal(article):
        return False
    if home_article_age_hours(article, reference_dt) > NEWS_WINDOW_HOURS:
        return False
    if not home_has_direct_title_signal(article) and not home_has_explicit_youth_lead_signal(article):
        return False
    return (
        home_has_policy_or_operational_signal(article)
        or home_has_structural_issue_signal(article)
        or int(article.get("clean_score") or 0) >= 4
        or bool(article.get("governance_scope"))
    )


def is_home_today_fill_candidate(article: dict, reference_dt: datetime | None) -> bool:
    if is_home_today_candidate(article, reference_dt):
        return True
    if article.get("is_official_source"):
        return False
    if article.get("article_type") == "opinion" or article.get("is_noise"):
        return False
    if home_is_generic_business_result_article(article):
        return False
    if home_is_political_analysis_article(article):
        return False
    if home_campaign_political(article):
        return False
    if home_article_age_hours(article, reference_dt) > NEWS_WINDOW_HOURS:
        return False
    if home_weak_youth_signal(article) and not article.get("issue_tags") and int(article.get("clean_score") or 0) < 4:
        return False
    if not home_has_direct_title_signal(article) and not home_has_explicit_youth_lead_signal(article):
        return False
    return (
        bool(article.get("issue_tags"))
        or home_has_policy_or_operational_signal(article)
        or home_has_structural_issue_signal(article)
        or int(article.get("clean_score") or 0) >= 3
        or bool(article.get("governance_scope"))
    )


def is_home_weekly_candidate(article: dict, reference_dt: datetime | None) -> bool:
    if article.get("is_official_source"):
        return False
    if article.get("article_type") == "opinion" or article.get("is_noise"):
        return False
    if home_is_generic_business_result_article(article):
        return False
    if home_is_political_analysis_article(article):
        return False
    if home_campaign_political(article) and not home_substantive_promise(article):
        return False
    if home_article_age_hours(article, reference_dt) > NEWS_WINDOW_HOURS:
        return False
    if home_weak_youth_signal(article) and int(article.get("clean_score") or 0) < 4:
        return False
    if not home_has_direct_title_signal(article) and not home_has_explicit_youth_lead_signal(article):
        return False
    return (
        home_substantive_promise(article)
        or home_has_policy_or_operational_signal(article)
        or home_has_structural_issue_signal(article)
        or int(article.get("clean_score") or 0) >= 4
        or bool(article.get("governance_scope"))
    )


def score_home_today_article(article: dict, reference_dt: datetime | None) -> int:
    score = int(article.get("importance_score") or 0)
    if article.get("_home_primary_candidate"):
        score += 24
    if home_has_policy_or_operational_signal(article):
        score += 6
    if home_has_structural_issue_signal(article):
        score += 4
    if int(article.get("clean_score") or 0) >= 4:
        score += 3
    if article.get("governance_scope"):
        score += 2
    if home_substantive_promise(article):
        score -= 3
    age_hours = home_article_age_hours(article, reference_dt)
    if age_hours <= 24:
        score += 8
    elif age_hours <= 48:
        score += 5
    elif age_hours <= 72:
        score += 2
    elif age_hours <= 120:
        score -= 1
    else:
        score -= 3
    return score


def score_home_weekly_article(article: dict, reference_dt: datetime | None) -> int:
    score = int(article.get("importance_score") or 0)
    if home_has_policy_or_operational_signal(article):
        score += 7
    if home_has_structural_issue_signal(article):
        score += 4
    if int(article.get("clean_score") or 0) >= 4:
        score += 4
    if int(article.get("clean_score") or 0) >= 6:
        score += 2
    if article.get("governance_scope"):
        score += 3
    if home_substantive_promise(article):
        score += 3
    age_hours = home_article_age_hours(article, reference_dt)
    if age_hours <= 72:
        score += 4
    elif age_hours <= NEWS_WINDOW_HOURS:
        score += 2
    return score


def _snapshot_entries(snapshot: dict, key: str) -> list[dict[str, str]]:
    raw_entries = snapshot.get(key)
    if isinstance(raw_entries, list):
        entries = [
            {
                "url": str(entry.get("url") or "").strip(),
                "started_at": str(entry.get("started_at") or "").strip(),
            }
            for entry in raw_entries
            if isinstance(entry, dict) and str(entry.get("url") or "").strip()
        ]
        if entries:
            return entries

    urls = snapshot.get(f"{key[:-8]}_urls", []) if key.endswith("_entries") else []
    started_at = str(snapshot.get(f"{key[:-8]}_started_at") or "").strip() if key.endswith("_entries") else ""
    if not isinstance(urls, list):
        return []
    return [{"url": str(url).strip(), "started_at": started_at} for url in urls if str(url).strip()]


def select_home_articles_with_hysteresis(
    *,
    candidates: list[dict],
    previous_entries: list[dict[str, str]],
    reference_dt: datetime | None,
    limit: int,
    sticky_limit: int,
    sticky_hours: int,
    excluded_keys: set[str] | None = None,
) -> tuple[list[dict], list[dict[str, str]]]:
    excluded_keys = excluded_keys or set()
    candidate_map = {home_article_key(article): article for article in candidates}
    rank_map = {home_article_key(article): index for index, article in enumerate(candidates)}
    sticky_rank_limit = max(limit + sticky_limit, limit)
    retained: list[dict] = []
    retained_entry_map: dict[str, str] = {}

    for entry in previous_entries:
        article_key = entry.get("url", "").strip()
        article = candidate_map.get(article_key)
        if not article or article_key in excluded_keys:
            continue
        if not article.get("_home_primary_candidate"):
            continue
        rank_index = rank_map.get(article_key, sticky_rank_limit + 1)
        if rank_index >= sticky_rank_limit:
            continue
        started_at = entry.get("started_at", "").strip()
        started_dt = parse_iso_datetime(started_at) or reference_dt
        if started_dt is None:
            continue
        age_hours = max((reference_dt - started_dt).total_seconds() / 3600, 0.0) if reference_dt else 0.0
        if age_hours > sticky_hours:
            continue
        retained.append(article)
        retained_entry_map[article_key] = started_at or (
            reference_dt.isoformat() if reference_dt is not None else ""
        )
        if len(retained) >= sticky_limit:
            break

    selected: list[dict] = list(retained)
    selected_keys = {home_article_key(article) for article in selected}
    entry_rows: list[dict[str, str]] = [
        {"url": article_key, "started_at": retained_entry_map[article_key]}
        for article_key in retained_entry_map
    ]

    for article in candidates:
        article_key = home_article_key(article)
        if article_key in excluded_keys or article_key in selected_keys:
            continue
        selected.append(article)
        selected_keys.add(article_key)
        entry_rows.append(
            {
                "url": article_key,
                "started_at": reference_dt.isoformat() if reference_dt is not None else "",
            }
        )
        if len(selected) >= limit:
            break

    return selected[:limit], entry_rows[:limit]


def build_home_curated_lists(
    selected_news_articles: list[dict],
    highlighted_article: dict | None,
    page_updated_at: str,
) -> tuple[list[dict], list[dict], dict]:
    reference_dt = parse_iso_datetime(page_updated_at)
    snapshot = load_home_update_snapshot()
    previous_today_entries = _snapshot_entries(snapshot, "today_entries")
    previous_weekly_entries = _snapshot_entries(snapshot, "weekly_entries")

    highlight_key = home_article_key(highlighted_article) if highlighted_article else ""
    base_articles = [article for article in selected_news_articles if home_article_key(article) != highlight_key]

    today_primary_articles = [
        article for article in base_articles if is_home_today_candidate(article, reference_dt)
    ]
    today_fill_articles = [
        article
        for article in base_articles
        if not is_home_today_candidate(article, reference_dt) and is_home_today_fill_candidate(article, reference_dt)
    ]
    today_ranked = sorted(
        today_primary_articles,
        key=lambda article: (
            score_home_today_article(article, reference_dt),
            article_sort_key(article)[1],
        ),
        reverse=True,
    )
    today_fill_ranked = sorted(
        today_fill_articles,
        key=lambda article: (
            score_home_today_article(article, reference_dt) - 5,
            article_sort_key(article)[1],
        ),
        reverse=True,
    )
    today_ranked = [*today_ranked, *today_fill_ranked]
    today_articles, today_entries = select_home_articles_with_hysteresis(
        candidates=today_ranked,
        previous_entries=previous_today_entries,
        reference_dt=reference_dt,
        limit=HOME_DAILY_LIMIT,
        sticky_limit=HOME_DAILY_STICKY_LIMIT,
        sticky_hours=HOME_DAILY_STICKY_HOURS,
    )
    today_keys = {home_article_key(article) for article in today_articles}

    weekly_ranked = sorted(
        [
            article
            for article in base_articles
            if home_article_key(article) not in today_keys and is_home_weekly_candidate(article, reference_dt)
        ],
        key=lambda article: (
            score_home_weekly_article(article, reference_dt),
            article_sort_key(article)[1],
        ),
        reverse=True,
    )
    weekly_articles, weekly_entries = select_home_articles_with_hysteresis(
        candidates=weekly_ranked,
        previous_entries=previous_weekly_entries,
        reference_dt=reference_dt,
        limit=HOME_WEEKLY_LIMIT,
        sticky_limit=HOME_WEEKLY_LIMIT,
        sticky_hours=HOME_WEEKLY_STICKY_HOURS,
    )

    updated_snapshot = dict(snapshot)
    updated_snapshot.update(
        {
            "today_entries": today_entries,
            "today_urls": [entry["url"] for entry in today_entries],
            "today_started_at": today_entries[0]["started_at"] if today_entries else "",
            "weekly_entries": weekly_entries,
            "weekly_urls": [entry["url"] for entry in weekly_entries],
            "weekly_started_at": weekly_entries[0]["started_at"] if weekly_entries else "",
        }
    )
    save_home_update_snapshot(updated_snapshot)
    return today_articles, weekly_articles, updated_snapshot


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


def hub_representative_sort_key(article: dict) -> tuple[int, int, int, int, int, str]:
    source_kind = normalize_inline_text(article.get("source_kind"))
    source_text = normalize_inline_text(" ".join([str(article.get("source") or ""), str(article.get("source_name") or "")]))
    is_official = 0 if source_kind == "official" or "보도자료" in source_text or "브리핑" in source_text else 1
    source_rank = {"official": 0, "local": 1, "news": 2}.get(source_kind, 3)
    has_publisher_url = 0 if article.get("publisher_url") else 1
    owner_label = normalize_inline_text(article.get("hub_owner_label"))
    owner_match = 0 if owner_label and owner_label in source_text else 1
    parsed_published = parse_iso_datetime(article.get("published_date"))
    timestamp = -int(parsed_published.timestamp()) if parsed_published else 0
    return (
        is_official,
        source_rank,
        has_publisher_url,
        owner_match,
        timestamp,
        display_article_title(article, limit=120),
    )


def normalize_hub_owner_for_cluster(article: dict) -> str:
    owner = normalize_inline_text(article.get("hub_owner_label")) or news_region_label(article)
    if normalize_inline_text(article.get("governance_scope")) != "지자체":
        return owner
    if owner.endswith("시") and len(owner) > 2:
        return owner[:-1]
    if owner.endswith("도") and len(owner) > 2:
        return owner[:-1]
    if owner.endswith("군") and len(owner) > 2:
        return owner[:-1]
    if owner.endswith("구") and len(owner) > 2:
        return owner[:-1]
    return owner


def hub_event_coarse_key(article: dict) -> str:
    scope = article.get("governance_scope")
    region_key = "" if scope == "지자체" else normalize_inline_text(article.get("region"))
    return normalize_inline_text(
        " | ".join(
            value
            for value in [
                scope,
                normalize_hub_owner_for_cluster(article),
                region_key,
                (article.get("hub_topics") or [""])[0],
                (article.get("governance_activity_types") or [""])[0],
                (article.get("published_date", "") or "")[:10],
            ]
            if value
        )
    )


def deduplicate_hub_articles(classified_articles: list[dict]) -> list[dict]:
    raw_articles = [article for article in classified_articles if article.get("is_hub_candidate")]
    grouped: dict[str, list[dict]] = {}

    for article in sort_articles_by_recency(raw_articles):
        coarse_key = hub_event_coarse_key(article) or display_article_title(article, limit=120)
        grouped.setdefault(coarse_key, []).append(article)

    deduped: list[dict] = []
    for cluster in grouped.values():
        representative = dict(sorted(cluster, key=hub_representative_sort_key)[0])
        representative["hub_related_count"] = len(cluster)
        representative["hub_related_sources"] = list(
            dict.fromkeys(
                format_source_label(item.get("source") or item.get("source_name"))
                for item in cluster
                if item.get("source") or item.get("source_name")
            )
        )
        deduped.append(representative)
    return sort_articles_by_recency(deduped)


def filter_hub_articles(classified_articles: list[dict], scope: str | None = None) -> list[dict]:
    articles = deduplicate_hub_articles(classified_articles)
    if scope is not None:
        articles = [article for article in articles if article.get("governance_scope") == scope]
    return articles


def render_empty_hub_state(title: str, body: str) -> str:
    return f'<article class="info-card"><h3>{html.escape(title)}</h3><p>{html.escape(body)}</p></article>'


def build_hub_menu_items(classified_articles: list[dict]) -> list[tuple[str, str]]:
    government_articles = filter_hub_articles(classified_articles, "정부")
    regional_articles = filter_hub_articles(classified_articles, "지자체")
    public_articles = filter_hub_articles(classified_articles, "공공기관")

    items: list[tuple[str, str]] = []
    if government_articles:
        items.append(
            (
                f'중앙부처 자문·회의: {display_article_title(government_articles[0], limit=72)}',
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
        items.append(("중앙부처 자문·회의", "현재 등록된 항목이 없습니다."))

    if regional_articles:
        items.append(
            (
                f'지역 청년정책 네트워크: {display_article_title(regional_articles[0], limit=72)}',
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
        items.append(("지역 청년정책 네트워크", "현재 등록된 항목이 없습니다."))

    if public_articles:
        items.append(
            (
                f'공공기관 참여·협의: {display_article_title(public_articles[0], limit=72)}',
                " · ".join(
                    bit
                    for bit in [
                        public_articles[0].get("source", ""),
                        public_articles[0].get("published_date", "")[:10],
                    ]
                    if bit
                ),
            )
        )
    else:
        items.append(("공공기관 참여·협의", "현재 등록된 항목이 없습니다."))

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
                ("공식 자료 바로가기", "정부와 기관이 제공하는 청년 정책·조사 자료를 한곳에서 봅니다."),
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
    selected_articles = sort_articles_by_recency(articles or classified_articles)
    all_articles = sort_articles_by_recency(classified_articles or selected_articles)
    selected_news_articles = [
        article
        for article in selected_articles
        if not article.get("is_official_source") and not is_election_promise_article(article)
    ]
    recent_news_articles = filter_recent_articles(selected_news_articles, page_updated_at, NEWS_WINDOW_HOURS)
    all_news_articles = [
        article
        for article in all_articles
        if not article.get("is_official_source") and not is_election_promise_article(article)
    ]
    recent_home_news_candidates = merge_home_candidate_articles(
        recent_news_articles,
        filter_recent_articles(all_news_articles, page_updated_at, NEWS_WINDOW_HOURS),
    )
    highlighted_article = next(
        (article for article in selected_articles if article.get("editorial_is_highlighted")),
        None,
    )
    today_articles, _, _ = build_home_curated_lists(
        recent_home_news_candidates,
        highlighted_article,
        page_updated_at,
    )
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
    today_total_count = count_articles_on_reference_day(all_articles, page_updated_at)
    hot_keywords = build_home_hot_keywords(recent_home_news_candidates, page_updated_at)
    home_date_label = format_home_date_label(page_updated_at)
    latest_news_basis = describe_article_basis(recent_news_articles, f"최근 {NEWS_WINDOW_DAYS}일 기사 없음")
    policy_basis = describe_article_basis(official_policy_articles or policy_articles, "최근 정책 없음")
    lead_message = (
        "혼자 챙기기엔 너무 많은 하루에도,\n"
        "청년에게 닿는 정책과 이슈는 놓치지 않도록.\n\n"
        "오늘 필요한 기사와 흐름을\n"
        "한곳에 차분히 모아두었습니다.\n\n"
        "작은 정보 하나가 오늘의 길잡이가 되기를 바랍니다."
    )
    glance_stats_html = "".join(
        f'<article class="{card_class}"><span class="home-glance-label">{label}</span><strong class="home-glance-value">{value}</strong></article>'
        for card_class, label, value in [
            ("home-glance-item warm full", "오늘 올라온 기사", f"{today_total_count}건"),
        ]
    )
    hot_keyword_links = "".join(
        f'<a class="home-keyword-chip" href="news.html?q={urllib.parse.quote(keyword)}">#{html.escape(keyword)}</a>'
        for keyword, _ in hot_keywords
    )
    hot_keyword_body = hot_keyword_links or '<span class="home-urgent-meta">오늘 키워드가 더 모이면 표시됩니다.</span>'
    hot_keywords_html = (
        '<article class="home-keyword-panel">'
        '<div class="home-keyword-heading"><strong>오늘 많이 잡힌 키워드</strong>'
        '<span>누르면 뉴스 탭에서 바로 걸러봅니다.</span></div>'
        f'<div class="home-keyword-list">{hot_keyword_body}</div>'
        '</article>'
    )

    def render_home_news_item(index: int, article: dict) -> str:
        title = html.escape(display_article_title(article, limit=88))
        meta = html.escape(compact_article_meta(article))
        url = article_target_url(article)
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

    today_news_html = "".join(
        render_home_news_item(index, article) for index, article in enumerate(today_articles[:HOME_DAILY_LIMIT], start=1)
    ) or (
        '<article class="home-urgent-item"><div class="home-urgent-link"><span class="home-urgent-rank">00</span>'
        '<div class="home-urgent-text"><strong>오늘 크게 볼 기사가 아직 없습니다.</strong>'
        '<span class="home-urgent-meta">새 청년 뉴스가 들어오면 이 영역이 먼저 채워집니다.</span></div></div></article>'
    )
    def render_home_highlight_card(article: dict | None) -> str:
        if not article:
            return ""

        title = html.escape(display_article_title(article, limit=88))
        summary = html.escape(
            article.get("summary")
            or article.get("lead_text")
            or "운영자가 대표로 지정한 기사입니다."
        )
        meta = html.escape(compact_article_meta(article))
        badges = list(dict.fromkeys([badge for badge in article.get("display_badges", []) if badge]))
        badges = ["하이라이트", *[badge for badge in badges if badge != "하이라이트"]][:3]
        badge_html = "".join(f'<span class="tag">{html.escape(badge)}</span>' for badge in badges)
        url = article_target_url(article)
        if url:
            body_html = (
                f'<a class="list-item" href="{html.escape(url)}" target="_blank" rel="noreferrer">'
                f'<strong>{title}</strong><span>{summary}</span></a>'
            )
        else:
            body_html = f'<div class="list-item"><strong>{title}</strong><span>{summary}</span></div>'
        return (
            '<article class="home-briefing-card home-highlight-card">'
            '<div class="home-section-head">'
            '<div class="home-section-title">'
            '<h2>대표 하이라이트</h2>'
            '<p class="home-section-copy">운영자가 놓치지 말아야 할 기사로 직접 지정한 항목입니다.</p>'
            '</div>'
            f'<div class="tag-list">{badge_html}</div>'
            '</div>'
            f'{body_html}'
            f'<div class="home-meta-line"><span>{meta}</span></div>'
            '</article>'
        )

    highlight_card_html = render_home_highlight_card(highlighted_article)
    home_lead_media = render_card_illustration(
        HOME_LEAD_ILLUSTRATION,
        slot_class="home-illustration-slot",
        img_class="home-illustration-img",
        loading="eager",
    )
    home_lead_class = " has-media" if home_lead_media else ""
    return f"""
    <section class="hero home-hero">
      <div class="home-briefing-grid">
        <article class="home-briefing-card lead lead-arch{home_lead_class}" data-media-host="home-lead">
          <div class="home-briefing-content">
            <span class="home-briefing-date">{html.escape(home_date_label)}</span>
            <h1 class="home-briefing-title"><span class="home-briefing-title-line">청년의 오늘을</span><span class="home-briefing-title-line">모아봅니다.</span></h1>
            <p class="home-briefing-copy">{html.escape(lead_message)}</p>
          </div>
          {home_lead_media}
        </article>
        <article class="home-briefing-card digest digest-organic">
          <div class="home-briefing-head">
            <h2>오늘 한눈에 보기</h2>
            <p>오늘 날짜로 올라온 기사 전체 수와 많이 잡힌 키워드를 함께 봅니다.</p>
          </div>
          <div class="home-glance-grid">{glance_stats_html}{hot_keywords_html}</div>
          <div class="home-briefing-divider"></div>
          <div class="home-briefing-subhead">
            <h3>오늘 놓치면 안되는 뉴스 5가지</h3>
            <p>오늘성, 즉시성, 정책·현장 맥락을 더 좁게 보고 지금 먼저 볼 기사를 묶었습니다.</p>
          </div>
          <div class="home-urgent-list">{today_news_html}</div>
        </article>
        {highlight_card_html}
        <article class="home-briefing-card support support-pill">
          {render_support_metrics()}
        </article>
        <article class="home-briefing-card footer footer-warm">
          <div class="home-support-footer">
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
            render_feature_card("선거·공약", f"최근 {ELECTION_WINDOW_DAYS}일 선거 기사와 청년 공약 흐름을 일반 뉴스와 분리해 봅니다.", "election.html", "선거 흐름"),
            render_feature_card("정책", "정부 공식 발표와 행정성 높은 참고 기사를 구분해 원문 흐름을 확인합니다.", "policies.html", "공식 발표"),
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
    news_articles = [
        article
        for article in sort_articles_by_recency(articles)
        if not article.get("is_official_source") and not is_election_promise_article(article)
    ]
    recent_news_articles = filter_recent_articles(news_articles, page_updated_at, NEWS_WINDOW_HOURS)
    date_options = collect_article_dates(recent_news_articles)
    region_options = collect_news_regions(recent_news_articles)
    page_intro = render_compact_intro(
        "01 뉴스",
        "지역과 날짜 기준으로 최근 청년 뉴스를 빠르게 훑고, 선거·공약 성격이 강한 기사는 별도 탭으로 분리했습니다.",
        media_key="news",
    )
    news_filter_panel = render_news_filter_panel(region_options, date_options, len(recent_news_articles))
    cards_html = "".join(render_article_card(article) for article in recent_news_articles)
    return f"""
    <div data-news-filter-root="news" data-default-date-start="" data-default-date-end="" data-default-region="all" data-default-search-query="">
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


def build_election_page(articles: list[dict], status: dict) -> str:
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    election_articles = [
        with_election_badges(article)
        for article in sort_articles_by_recency(articles)
        if is_election_promise_article(article)
    ]
    recent_election_articles = filter_recent_articles(election_articles, page_updated_at, ELECTION_WINDOW_HOURS)
    date_options = collect_article_dates(recent_election_articles)
    region_options = collect_news_regions(recent_election_articles)
    page_intro = render_compact_intro(
        "02 선거·공약",
        "지방선거 시기에는 청년 공약과 선거성 기사를 이 탭으로 분리해, 일반 뉴스와 정책 흐름을 더 또렷하게 보이게 했습니다.",
    )
    election_filter_panel = render_news_filter_panel(region_options, date_options, len(recent_election_articles))
    cards_html = "".join(render_article_card(article) for article in recent_election_articles)
    return f"""
    <div data-news-filter-root="election" data-default-date-start="" data-default-date-end="" data-default-region="all" data-default-search-query="">
      {page_intro}
      <section class="section">
        <article class="info-card">
          <h3>이 탭은 이렇게 봅니다</h3>
          <p>후보 동정, 유세, 공천, 청년 공약 기사까지 선거 국면의 흐름을 따로 모았습니다. 일반 뉴스와 정책 탭에서는 이런 기사 비중을 낮추고 여기에서 더 모아 보게 했습니다.</p>
        </article>
      </section>
      {election_filter_panel}
      <section class="section">
        <div class="article-grid">
          {cards_html or '<article class="info-card" data-news-empty-state="true"><h3>최근 선거·공약 기사가 없습니다</h3><p>청년 관련 선거 기사와 공약 기사가 수집되면 이 영역에 표시됩니다.</p></article>'}
        </div>
        <article class="info-card" data-news-empty-state="true" hidden>
          <h3>조건에 맞는 기사가 없습니다</h3>
          <p>지역이나 날짜 조건을 바꾸면 다른 선거·공약 기사를 볼 수 있습니다.</p>
        </article>
      </section>
    </div>
    """


def build_policies_page(articles: list[dict], status: dict) -> str:
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    policies = filter_recent_articles([article for article in articles if article.get("is_official_source")], page_updated_at, 24 * 90)
    official_policies = [article for article in policies if article.get("source_kind") == "official"]
    reference_policies = [
        article
        for article in policies
        if article.get("source_kind") != "official" and not is_election_promise_article(article)
    ]
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
    official_policies = add_major_policy_watchlist_articles(official_policies)
    reference_policies = [
        article
        for article in recent_articles
        if is_local_policy_update(article) and not is_election_promise_article(article)
    ]
    page_intro = render_compact_intro(
        "03 정책",
        "중앙정부 정책 자료와 지자체 발표 소식을 나눠 보고, 선거성 기사는 별도 탭으로 분리해 정책 흐름을 더 선명하게 봅니다.",
        media_key="policies",
    )
    official_cards = "".join(
        render_article_card(
            article,
            {
                "data-policy-card": "true",
                "data-policy-group": "official",
                "data-policy-authority": policy_authority_label(article),
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
    <div data-policy-filter-root="policies" data-policy-scope-mode="authority-region" data-default-policy-group="all" data-default-policy-region="all" data-default-policy-scope="all" data-default-policy-type="all" data-default-date-start="" data-default-date-end="" data-default-search-query="">
      {page_intro}
      {policy_filter_panel}
      <section class="section" id="official-policies" data-policy-section="official">
        <div class="section-head">
          <div>
            <h2>중앙정부 정책 자료</h2>
            <p>기획재정부·교육부·고용노동부·행정안전부·보건복지부·국토교통부·문화체육관광부·중소벤처기업부·금융위원회 기준으로 최근 자료를 모았습니다.</p>
          </div>
          <span class="mini-link" aria-disabled="true" data-policy-section-count>{len(official_policies)}건</span>
        </div>
        <div class="article-grid">{official_cards or '<article class="info-card"><h3>최근 중앙정부 정책 자료 없음</h3><p>최근 90일 안에 표시할 중앙정부 정책 자료가 아직 없습니다.</p></article>'}</div>
      </section>
      <section class="section" id="local-policy-updates" data-policy-section="local">
        <div class="section-head">
          <div>
            <h2>지자체 발표 소식</h2>
            <p>청년 정책과 시행계획, 행정 발표 성격이 분명한 지역 기사만 따로 모았습니다. 선거·공약성 기사는 별도 탭에서 봅니다.</p>
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
    government_records = filter_hub_articles(classified_articles, "정부")
    regional_records = filter_hub_articles(classified_articles, "지자체")
    public_records = filter_hub_articles(classified_articles, "공공기관")
    page_intro = render_compact_intro(
        "04 참여·회의",
        "뉴스와는 별도로, 중앙부처 자문·회의와 지역 청년정책 네트워크, 공공기관 참여·협의 기록만 구조화해 모았습니다.",
        media_key="hub",
    )
    hub_filter_panel = render_hub_filter_panel(government_records, regional_records, public_records)
    government_cards = "".join(render_hub_record_card(article) for article in government_records)
    regional_cards = "".join(render_hub_record_card(article) for article in regional_records)
    public_cards = "".join(render_hub_record_card(article) for article in public_records)
    return f"""
    <div data-policy-filter-root="hub" data-policy-scope-mode="hub-detail" data-keep-empty-sections="true" data-default-policy-group="all" data-default-policy-region="all" data-default-policy-scope="all" data-default-policy-type="all" data-default-date-start="" data-default-date-end="" data-default-search-query="">
      {page_intro}
      {hub_filter_panel}
      <section class="section" data-policy-section="official">
        <div class="section-head">
          <div>
            <h2>{HUB_GROUP_CONFIG["official"]["title"]}</h2>
            <p>{HUB_GROUP_CONFIG["official"]["description"]}</p>
          </div>
          <span class="mini-link" aria-disabled="true" data-policy-section-count>{len(government_records)}건</span>
        </div>
        <div class="article-grid">{government_cards or render_empty_hub_state(HUB_GROUP_CONFIG["official"]["empty_title"], HUB_GROUP_CONFIG["official"]["empty_body"])}</div>
      </section>
      <section class="section" data-policy-section="local">
        <div class="section-head">
          <div>
            <h2>{HUB_GROUP_CONFIG["local"]["title"]}</h2>
            <p>{HUB_GROUP_CONFIG["local"]["description"]}</p>
          </div>
          <span class="mini-link" aria-disabled="true" data-policy-section-count>{len(regional_records)}건</span>
        </div>
        <div class="article-grid">{regional_cards or render_empty_hub_state(HUB_GROUP_CONFIG["local"]["empty_title"], HUB_GROUP_CONFIG["local"]["empty_body"])}</div>
      </section>
      <section class="section" id="public-governance" data-policy-section="public">
        <div class="section-head">
          <div>
            <h2>{HUB_GROUP_CONFIG["public"]["title"]}</h2>
            <p>{HUB_GROUP_CONFIG["public"]["description"]}</p>
          </div>
          <span class="mini-link" aria-disabled="true" data-policy-section-count>{len(public_records)}건</span>
        </div>
        <div class="article-grid">{public_cards or render_empty_hub_state(HUB_GROUP_CONFIG["public"]["empty_title"], HUB_GROUP_CONFIG["public"]["empty_body"])}</div>
      </section>
      <article class="info-card" data-policy-empty-state="true" hidden>
        <h3>조건에 맞는 참여·회의 기록이 없습니다</h3>
        <p>구분이나 세부, 활동, 기간을 바꾸면 다른 기록을 확인할 수 있습니다.</p>
      </article>
    </div>
    """


def build_tools_page(articles: list[dict], status: dict) -> str:
    page_intro = render_compact_intro(
        "04 자료도구",
        "정책 조사와 제안서 초안을 준비할 때 필요한 자료를 짧은 흐름으로 따라볼 수 있습니다.",
        media_key="tools",
    )
    page_updated_at = status.get("updated_at") or status.get("finished_at")
    tools_check_badge = f'<span class="mini-link" aria-disabled="true">자동 확인 {html.escape(format_display_datetime(page_updated_at))}</span>'

    youth_stat_resources = [
        {
            "title": "2024년 청년의 삶 실태조사",
            "description": "국무조정실이 청년기본법에 따라 2년마다 발표하는 대표 실태조사로, 노동·주거·건강·관계까지 폭넓게 담고 있습니다.",
            "href": "https://www.opm.go.kr/opm/news/press1.do?articleNo=158583&attachNo=146521&mode=download",
            "meta": "정부 조사",
            "tone": "navy",
            "basis_label": "공식 발표",
            "basis_patterns": [
                r"게시일[^0-9]{0,80}(20\d{2}-\d{2}-\d{2})",
                r"(20\d{2}-\d{2}-\d{2})",
            ],
            "basis_fallback": "2025-03-11",
            "keywords": ["청년의 삶 실태조사", "청년 삶 실태조사", "청년 삶 실태"],
        },
        {
            "title": "청년통계지도",
            "description": "통계청 SGIS에서 청년 인구, 부모동거, 주택소유, 취업활동 같은 지표를 지역별로 바로 볼 수 있습니다.",
            "href": "https://sgis.kostat.go.kr/view/syrStats/main",
            "meta": "통계청 서비스",
            "tone": "teal",
            "basis_label": "서비스 기준",
            "basis_patterns": [
                r"(20\d{2}년\s*\d{1,2}월 기준)",
            ],
            "basis_fallback": "2025년 8월 기준",
            "keywords": ["청년통계지도", "청년통계등록부", "청년통계"],
        },
        {
            "title": "2025년 5월 청년층 부가조사 결과",
            "description": "통계청 경제활동인구조사 기반 자료로 고용률, 첫 일자리 소요기간, 직장 체험, 취업시험 준비를 확인할 수 있습니다.",
            "href": "https://www.kostat.go.kr/boardDownload.es?bid=210&list_no=437676&seq=9",
            "meta": "고용 통계",
            "tone": "warm",
            "basis_label": "공식 발표",
            "basis_patterns": [
                r"(20\d{2}-\d{2}-\d{2})",
            ],
            "basis_fallback": "2025-07-23",
            "keywords": ["청년층 부가조사", "경제활동인구조사 청년층", "청년층 고용"],
        },
        {
            "title": "사회조사로 살펴본 청년의 의식변화",
            "description": "통계청 사회조사로 청년의 결혼, 출산, 노동, 가치관 변화를 묶어 보여주는 기획 보도자료입니다.",
            "href": "https://kostat.go.kr/board.es?act=view&bid=219&list_no=426708&mid=a10301060300&ref_bid=&tag=",
            "meta": "인식 조사",
            "tone": "sand",
            "basis_label": "공식 발표",
            "basis_patterns": [
                r"게시일[^0-9]{0,80}(20\d{2}-\d{2}-\d{2})",
                r"(20\d{2}-\d{2}-\d{2})",
            ],
            "basis_fallback": "2023-08-28",
            "keywords": ["사회조사로 살펴본 청년의 의식변화", "청년의 의식변화", "사회조사 청년"],
        },
    ]
    youth_stats_cards = "".join(
        render_resource_card(
            resource["title"],
            resource["description"],
            resource["href"],
            resource["meta"],
            tone=resource["tone"],
            status_rows=build_resource_status_rows(resource, articles),
        )
        for resource in youth_stat_resources
    )

    reference_resources = [
        {
            "title": "정책브리핑 청년정책 특집",
            "description": "정부가 모아둔 청년정책 기사, 해설, 제도 소개를 한 화면에서 훑을 수 있는 공식 특집 페이지입니다.",
            "href": "https://m.korea.kr/news/policyFocusList.do?pkgId=49500808",
            "meta": "공식 특집",
            "tone": "warm",
            "note": ("추천 활용", "정부 정책 흐름 확인"),
        },
        {
            "title": "청년기본법",
            "description": "청년의 범위, 국가와 지자체의 책무, 실태조사와 기본계획 근거를 법령 원문으로 바로 확인할 수 있습니다.",
            "href": "https://www.law.go.kr/LSW/LsiJoLinkP.do?docType=JO&joNo=001700000&languageType=KO&lsNm=%EC%B2%AD%EB%85%84%EA%B8%B0%EB%B3%B8%EB%B2%95&paras=1",
            "meta": "법령 원문",
            "tone": "navy",
            "note": ("추천 활용", "법적 근거 문구 확인"),
        },
        {
            "title": "KOSIS 국가통계포털",
            "description": "인구, 고용, 주거, 복지 같은 국가승인통계를 표와 시계열로 바로 확인할 수 있습니다.",
            "href": "https://kosis.kr/index/index.do",
            "meta": "공식 통계",
            "tone": "sand",
            "note": ("추천 활용", "수치 인용·시계열 비교"),
        },
        {
            "title": "공공데이터포털",
            "description": "CSV, XLS, API 형태의 원자료를 내려받아 지역별·대상별 근거를 직접 가공할 때 유용합니다.",
            "href": "https://www.data.go.kr/",
            "meta": "공공 데이터",
            "tone": "teal",
            "note": ("추천 활용", "원자료 내려받기"),
        },
        {
            "title": "지표누리",
            "description": "e-나라지표, 국민 삶의 질 지표, 저출생 통계지표처럼 정책 설명이 붙은 핵심 지표를 한 번에 볼 수 있습니다.",
            "href": "https://www.index.go.kr/",
            "meta": "공식 지표",
            "tone": "warm",
            "note": ("추천 활용", "설명 붙은 핵심 지표"),
        },
        {
            "title": "한국청소년정책연구원",
            "description": "청년·청소년 정책 연구보고서와 데이터아카이브를 확인할 때 가장 먼저 보기 좋은 전문 연구기관입니다.",
            "href": "https://www.nypi.re.kr/",
            "meta": "청년 연구",
            "tone": "sand",
            "note": ("추천 활용", "청년 연구보고서 확인"),
        },
        {
            "title": "NKIS 국가정책연구포털",
            "description": "국책연구기관 연구보고서와 정책·연구자료를 통합검색으로 찾을 수 있습니다.",
            "href": "https://www.nkis.re.kr/",
            "meta": "국책연구",
            "tone": "navy",
            "note": ("추천 활용", "국책연구 통합검색"),
        },
        {
            "title": "국회입법조사처",
            "description": "이슈와논점, NARS 현안분석처럼 쟁점을 빠르게 훑을 수 있는 입법·정책 자료를 볼 수 있습니다.",
            "href": "https://www.nars.go.kr/",
            "meta": "입법자료",
            "tone": "teal",
            "note": ("추천 활용", "쟁점 정리·입법 검토"),
        },
        {
            "title": "KDI 경제교육·정보센터",
            "description": "국내연구자료와 경제정책정보를 기관별로 모아 볼 수 있어 배경 설명과 선행연구를 함께 잡기 좋습니다.",
            "href": "https://eiec.kdi.re.kr/",
            "meta": "정책자료",
            "tone": "warm",
            "note": ("추천 활용", "배경 설명·선행연구"),
        },
    ]
    reference_cards = "".join(
        render_resource_card(
            resource["title"],
            resource["description"],
            resource["href"],
            resource["meta"],
            tone=resource["tone"],
            status_rows=[resource["note"]],
        )
        for resource in reference_resources
    )
    return f"""
    {page_intro}
    <section class="section">
      {render_list_block("빠른 시작", "처음이면 아래 세 단계부터 보면 가장 빠릅니다.", [("정부 원문 확인", "정책브리핑과 부처 자료로 기준점을 먼저 잡기"), ("AI로 질문 정리", "조사 범위와 논점을 짧게 정리하기"), ("검토 요청 준비", "문서 상태와 요청 포인트 적어두기")])}
    </section>
    <section class="section" id="youth-stat-releases">
      <div class="section-head">
        <div>
          <h2>청년 조사·통계 발표 모음</h2>
          <p>청년을 직접 대상으로 조사하거나, 청년만 따로 떼어 발표한 공식 통계를 건별로 모았습니다.</p>
        </div>
        {tools_check_badge}
      </div>
      <div class="article-grid tools-survey-grid">{youth_stats_cards}</div>
    </section>
    <section class="section" id="stats-research-links">
      <div class="section-head">
        <div>
          <h2>정부·기관 제공 공식 자료 바로가기</h2>
          <p>정책브리핑과 법령, 통계, 연구자료까지 제안서 근거를 보강할 때 자주 쓰는 공식 사이트를 우선순위대로 묶었습니다.</p>
        </div>
      </div>
      <div class="feature-grid tools-resource-grid">{reference_cards}</div>
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
        media_key="contact",
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


def build_footer_note(contact_settings: dict[str, str]) -> str:
    copyright_text = (contact_settings.get("copyright_text") or "").strip()
    organization_name = (contact_settings.get("organization_name") or "").strip()
    if copyright_text:
        return html.escape(copyright_text)
    if organization_name:
        return html.escape(f"운영: {organization_name}")
    return "운영: 유스사이드(Youthside)"


def write_page(
    path: Path,
    page_title: str,
    active_page: str,
    content: str,
    status: dict,
    contact_settings: dict[str, str],
) -> None:
    path.write_text(
        PAGE_TEMPLATE.format(
            page_title=html.escape(page_title),
            active_page=html.escape(active_page),
            styles=BASE_CSS,
            script=build_page_script(),
            guide_link=render_guide_link(active_page),
            header_meta=render_header_meta(active_page, status),
            nav=render_nav(active_page),
            bottom_nav=render_bottom_nav(active_page),
            bottom_nav_count=len(NAV_ITEMS),
            guide_overlay=render_guide_overlay(active_page),
            footer_note=build_footer_note(contact_settings),
            content=content,
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(RUNTIME_PIPELINE_ROOT / "step5_summarized.json"))
    parser.add_argument("--status-input", default=str(RUNTIME_PIPELINE_ROOT / "pipeline_status.json"))
    parser.add_argument("--output", default=str(PUBLIC_WEB_ROOT / "index.html"))
    args = parser.parse_args()

    articles = filter_public_articles(read_json(Path(args.input), default=[]))
    classified_articles = filter_public_articles(
        read_json(RUNTIME_PIPELINE_ROOT / "step3_classified.json", default=articles)
    )
    status = read_json(Path(args.status_input), default={})
    web_root = Path(args.output).parent
    web_root.mkdir(parents=True, exist_ok=True)

    contact_settings = load_contact_settings()

    write_page(
        web_root / "index.html",
        "청년 모아봄",
        "index.html",
        build_home_page(articles, classified_articles, status, contact_settings),
        status,
        contact_settings,
    )
    write_page(web_root / "guide.html", "이용방법", "guide.html", build_guide_page(status), status, contact_settings)
    write_page(
        web_root / "news.html",
        "청년 뉴스",
        "news.html",
        build_news_page(classified_articles, status),
        status,
        contact_settings,
    )
    write_page(
        web_root / "election.html",
        "청년 선거·공약",
        "election.html",
        build_election_page(classified_articles, status),
        status,
        contact_settings,
    )
    write_page(
        web_root / "policies.html",
        "청년 정책",
        "policies.html",
        build_policies_page_compact(classified_articles, status),
        status,
        contact_settings,
    )
    write_page(
        web_root / "hub.html",
        "청년 참여·회의",
        "hub.html",
        build_hub_page(classified_articles),
        status,
        contact_settings,
    )
    write_page(
        web_root / "tools.html",
        "자료·작성 도구",
        "tools.html",
        build_tools_page(classified_articles, status),
        status,
        contact_settings,
    )
    write_page(
        web_root / "contact.html",
        "제보·문의",
        "contact.html",
        build_contact_page(contact_settings),
        status,
        contact_settings,
    )

    print(f"web_output={web_root / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
