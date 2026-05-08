from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import html
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

from _bootstrap import PUBLIC_CONFIG_ROOT, PUBLIC_WEB_ROOT, RUNTIME_PIPELINE_ROOT

from youth_info_platform.article_metadata import (
    article_identity_key,
    extract_youth_preview_text,
    normalize_media_url,
    preferred_article_url,
)
from youth_info_platform.contact_config import load_contact_settings
from youth_info_platform.curation import is_public_interest_article
from youth_info_platform.io_utils import read_json

PUBLIC_ARCHIVE_WINDOW_DAYS = 3650
PUBLIC_ARCHIVE_WINDOW_HOURS = PUBLIC_ARCHIVE_WINDOW_DAYS * 24
PUBLIC_ARCHIVE_LABEL = "수집된 누적"
NEWS_WINDOW_DAYS = PUBLIC_ARCHIVE_WINDOW_DAYS
NEWS_WINDOW_HOURS = PUBLIC_ARCHIVE_WINDOW_HOURS
HOME_TODAY_MAX_AGE_HOURS = 48
HOME_CATEGORY_WINDOW_HOURS = PUBLIC_ARCHIVE_WINDOW_HOURS
ELECTION_WINDOW_DAYS = PUBLIC_ARCHIVE_WINDOW_DAYS
ELECTION_WINDOW_HOURS = PUBLIC_ARCHIVE_WINDOW_HOURS
HOME_DAILY_LIMIT = 5
HOME_WEEKLY_LIMIT = 3
HOME_DAILY_STICKY_LIMIT = 2
HOME_DAILY_STICKY_HOURS = 24
HOME_WEEKLY_STICKY_HOURS = 72
HOME_UPDATE_SNAPSHOT = RUNTIME_PIPELINE_ROOT / "home_update_snapshot.json"
HOME_HOT_KEYWORD_LIMIT = 8
REMOTE_TEXT_CACHE: dict[str, str] = {}
ILLUSTRATION_ROOT = "assets/illustrations"
KOREA_ADM1_SVG = PUBLIC_WEB_ROOT / "assets" / "vendor" / "geoboundaries-kor-adm1.svg"
KOREA_ADM1_DISPLAY_MAX_X = 860.0
ASSET_VERSION = "20260501-sunlit-logo-1"
BRAND_MARK_SRC = f"assets/branding/youth-together-mark.svg?v={ASSET_VERSION}"
YOUTHSIDE_FOOTER_IMAGE_CANDIDATES = (
    "assets/branding/youthside_logo_youth-group_compass_u-s-accent_horizontal_4x.png",
)
PUBLIC_ANALYTICS_ENDPOINT = os.getenv("PUBLIC_SITE_ANALYTICS_ENDPOINT", "").strip()
PUBLIC_ANALYTICS_SCOPE = os.getenv("PUBLIC_SITE_ANALYTICS_SCOPE", "public").strip() or "public"


def normalize_admin_account(value: str | None) -> str:
    return " ".join(str(value or "").split()).casefold()


def split_admin_account_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [
        item.strip()
        for item in re.split(r"[,;\n]+", value)
        if item.strip()
    ]


def hash_admin_account(value: str) -> str:
    return hashlib.sha256(normalize_admin_account(value).encode("utf-8")).hexdigest()


def load_admin_account_hashes() -> list[str]:
    accounts: list[str] = []
    account_hashes: list[str] = []

    accounts.extend(split_admin_account_values(os.getenv("PUBLIC_SITE_ADMIN_ACCOUNTS")))
    account_hashes.extend(split_admin_account_values(os.getenv("PUBLIC_SITE_ADMIN_ACCOUNT_HASHES")))

    config = read_json(PUBLIC_CONFIG_ROOT / "admin_access.local.json", default={})
    if isinstance(config, dict):
        for key in ("allowed_accounts", "accounts"):
            values = config.get(key, [])
            if isinstance(values, str):
                accounts.extend(split_admin_account_values(values))
            elif isinstance(values, list):
                accounts.extend(str(value).strip() for value in values if str(value).strip())
        for key in ("allowed_account_hashes", "account_hashes"):
            values = config.get(key, [])
            if isinstance(values, str):
                account_hashes.extend(split_admin_account_values(values))
            elif isinstance(values, list):
                account_hashes.extend(str(value).strip() for value in values if str(value).strip())

    normalized_hashes = {
        value.lower()
        for value in account_hashes
        if re.fullmatch(r"[0-9a-fA-F]{64}", value.strip())
    }
    normalized_hashes.update(hash_admin_account(account) for account in accounts)
    return sorted(normalized_hashes)


PUBLIC_ADMIN_ACCOUNT_HASHES = load_admin_account_hashes()

CENTRAL_MINISTRY_AUTHORITIES = [
    "기획재정부",
    "교육부",
    "과학기술정보통신부",
    "외교부",
    "통일부",
    "법무부",
    "국방부",
    "행정안전부",
    "국가보훈부",
    "문화체육관광부",
    "농림축산식품부",
    "산업통상자원부",
    "보건복지부",
    "환경부",
    "고용노동부",
    "여성가족부",
    "국토교통부",
    "해양수산부",
    "중소벤처기업부",
]

CENTRAL_POLICY_EXTRA_AUTHORITIES = [
    "금융위원회",
]

MAJOR_CENTRAL_POLICY_AUTHORITIES = [
    *CENTRAL_MINISTRY_AUTHORITIES,
    *CENTRAL_POLICY_EXTRA_AUTHORITIES,
]

CENTRAL_AUTHORITY_OFFICIAL_URLS = {
    "기획재정부": "https://www.moef.go.kr/",
    "교육부": "https://www.moe.go.kr/",
    "과학기술정보통신부": "https://www.msit.go.kr/",
    "외교부": "https://www.mofa.go.kr/",
    "통일부": "https://www.unikorea.go.kr/",
    "법무부": "https://www.moj.go.kr/",
    "국방부": "https://www.mnd.go.kr/",
    "행정안전부": "https://www.mois.go.kr/",
    "국가보훈부": "https://www.mpva.go.kr/",
    "문화체육관광부": "https://www.mcst.go.kr/",
    "농림축산식품부": "https://www.mafra.go.kr/",
    "산업통상자원부": "https://www.motie.go.kr/",
    "보건복지부": "https://www.mohw.go.kr/",
    "환경부": "https://www.me.go.kr/",
    "고용노동부": "https://www.moel.go.kr/",
    "여성가족부": "https://www.mogef.go.kr/",
    "국토교통부": "https://www.molit.go.kr/",
    "해양수산부": "https://www.mof.go.kr/",
    "중소벤처기업부": "https://www.mss.go.kr/",
    "금융위원회": "https://www.fsc.go.kr/",
}


def build_central_authority_directory_entry(authority: str) -> dict:
    official_url = CENTRAL_AUTHORITY_OFFICIAL_URLS.get(authority, "https://www.korea.kr/")
    return {
        "policy_authority": authority,
        "title": f"{authority} 청년정책 공식 경로",
        "url": official_url,
        "published_date": "2026-01-01T00:00:00+09:00",
        "lead_text": (
            f"정부 동향에서 모든 중앙부처를 빠짐없이 탐색할 수 있도록 연결한 {authority} 공식 홈페이지입니다. "
            "청년 관련 보도자료, 공고, 기본계획은 원문에서 확인합니다."
        ),
        "policy_type": "기타",
    }


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

FEATURED_MAJOR_POLICY_WATCHLIST = [
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

FEATURED_MAJOR_POLICY_AUTHORITIES = {
    entry["policy_authority"]
    for entry in FEATURED_MAJOR_POLICY_WATCHLIST
}

CURATED_MAJOR_POLICY_WATCHLIST = [
    *FEATURED_MAJOR_POLICY_WATCHLIST,
    *[
        build_central_authority_directory_entry(authority)
        for authority in CENTRAL_MINISTRY_AUTHORITIES
        if authority not in FEATURED_MAJOR_POLICY_AUTHORITIES
    ],
]

HOME_LEAD_ILLUSTRATION = {
    "src": f"{ILLUSTRATION_ROOT}/home-moabom-collection.svg?v={ASSET_VERSION}",
    "alt": "청년들이 봄꽃 아래에서 오늘의 기사와 정책 정보를 살펴보는 홈 화면 일러스트",
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

HOME_RESEARCH_RESOURCES = [
    {
        "title": "2024년 청년의 삶 실태조사",
        "organization": "국무조정실",
        "basis": "2025-03-11 발표",
        "description": "노동, 주거, 건강, 관계 등 청년 삶 전반을 확인할 수 있는 대표 조사입니다.",
        "href": "https://www.opm.go.kr/opm/news/press1.do?articleNo=158583&attachNo=146521&mode=download",
        "tag": "정부 조사",
    },
    {
        "title": "청년통계지도",
        "organization": "통계청 SGIS",
        "basis": "지역 지표 서비스",
        "description": "청년 인구, 주거, 취업활동 지표를 지역별로 비교할 때 가장 먼저 열어볼 자료입니다.",
        "href": "https://sgis.kostat.go.kr/view/syrStats/main",
        "tag": "공식 통계",
    },
    {
        "title": "한국청소년정책연구원",
        "organization": "NYPI",
        "basis": "연구보고서·데이터",
        "description": "청년·청소년 정책 연구보고서와 데이터아카이브를 함께 확인할 수 있습니다.",
        "href": "https://www.nypi.re.kr/",
        "tag": "정책 연구",
    },
    {
        "title": "NKIS 국가정책연구포털",
        "organization": "국가정책연구포털",
        "basis": "국책연구 통합검색",
        "description": "국책연구기관의 정책·연구자료를 주제별로 확장 검색할 때 유용합니다.",
        "href": "https://www.nkis.re.kr/",
        "tag": "국책연구",
    },
]

HOME_REGIONAL_POLICY_MAX_AGE_HOURS = PUBLIC_ARCHIVE_WINDOW_HOURS
HOME_REGIONAL_POLICY_LIMIT = 5
HOME_APPLICATION_POLICY_MAX_AGE_HOURS = PUBLIC_ARCHIVE_WINDOW_HOURS
HOME_APPLICATION_POLICY_LIMIT = 5

HOME_APPLICATION_POLICY_ACTION_KEYWORDS = (
    "신청",
    "접수",
    "모집",
    "공고",
    "공모",
    "참가자",
    "참여자",
    "대상자",
    "교육생",
    "입주자",
    "수강생",
)

HOME_APPLICATION_POLICY_BENEFIT_KEYWORDS = (
    "지원",
    "지원사업",
    "지원금",
    "장려금",
    "수당",
    "월세",
    "주거비",
    "대출",
    "바우처",
    "교육",
    "훈련",
    "취업",
    "창업",
    "생활비",
    "상담",
    "멘토링",
)

HOME_APPLICATION_EVENT_KEYWORDS = (
    "청년내일저축계좌",
    "청년도약계좌",
    "청년도약 인재양성",
    "청년월세",
    "청년 월세",
    "청년취업사관학교",
    "부트캠프",
    "청년정책 경진대회",
)

HOME_APPLICATION_PERIOD_PATTERNS = (
    re.compile(
        r"((?:\d{4}[년./-]\s*)?\d{1,2}\s*(?:월|[./-])\s*\d{1,2}\s*(?:일)?\s*"
        r"(?:부터|~|∼|-|–|—)\s*"
        r"(?:\d{4}[년./-]\s*)?\d{1,2}\s*(?:월|[./-])\s*\d{1,2}\s*(?:일)?(?:까지)?)"
    ),
    re.compile(r"((?:\d{4}[년./-]\s*)?\d{1,2}\s*(?:월|[./-])\s*\d{1,2}\s*(?:일)?(?:까지|마감))"),
)

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

LOCAL_OFFICIAL_SOURCE_HINTS = (
    "시청",
    "도청",
    "군청",
    "구청",
    "특별시",
    "광역시",
    "특별자치시",
    "특별자치도",
    "청년포털",
    "청년정책과",
    "청년정책담당관",
    "도정",
    "시정",
    "군정",
    "구정",
)

LOCAL_ADMIN_UNIT_PATTERN = re.compile(
    r"(?:서울시|부산시|대구시|인천시|광주시|대전시|울산시|세종시|경기도|강원도|충청북도|충청남도|전북특별자치도|전라북도|전라남도|경상북도|경상남도|제주특별자치도|[가-힣]{2,}(?:시|군|구))(?:청|는|은|가|도|,|·|\s|$)"
)

LOCAL_PRESS_RELEASE_KEYWORDS = (
    "보도자료",
    "보도 자료",
    "보도",
    "시정뉴스",
    "도정뉴스",
    "군정뉴스",
    "구정뉴스",
    "브리핑",
)

HOME_CENTRAL_OFFICIAL_ANNOUNCEMENT_CHANNELS = {
    "press_release",
    "announcement",
    "notice",
    "official_notice",
    "public_notice",
    "board_notice",
}

HOME_CENTRAL_OFFICIAL_ANNOUNCEMENT_KEYWORDS = (
    "보도자료",
    "보도 자료",
    "보도·설명자료",
    "보도설명자료",
    "설명자료",
    "공고",
    "공지",
    "알림",
    "고시",
    "입법예고",
    "발표",
    "press-release",
    "press_release",
    "report",
)

HOME_GOVERNMENT_TREND_YOUTH_KEYWORDS = (
    "youth",
    "청년",
    "청년층",
    "청년세대",
    "청년정책",
    "청년위원",
    "청년보좌역",
    "대학생",
    "사회초년생",
    "취업",
    "구직",
    "일자리",
    "고용",
    "주거",
    "월세",
    "전세",
    "청년도약",
    "청년내일",
    "고립",
    "은둔",
    "금융",
    "대출",
)

HOME_LOCAL_OFFICIAL_ANNOUNCEMENT_CHANNELS = {
    "",
    "press_release",
    "announcement",
    "notice",
    "official_notice",
    "public_notice",
    "board_notice",
    "city_news",
    "province_news",
}

HOME_LOCAL_OFFICIAL_ANNOUNCEMENT_KEYWORDS = (
    *LOCAL_PRESS_RELEASE_KEYWORDS,
    "공고",
    "고시",
    "공지",
    "알림",
    "입법예고",
)

LOCAL_POLICY_PLAN_KEYWORDS = (
    "청년정책 기본계획",
    "청년 정책 기본계획",
    "청년정책 시행계획",
    "청년 정책 시행계획",
    "청년정책 종합계획",
    "청년 정책 종합계획",
    "청년정책 기본·시행계획",
    "기본계획",
    "시행계획",
    "종합계획",
)

LOCAL_YOUTH_PLAN_REGIONS = [
    {
        "id": "seoul",
        "name": "서울",
        "full_name": "서울특별시",
        "domain": "seoul.go.kr",
        "x": 47,
        "y": 18,
    },
    {"id": "busan", "name": "부산", "full_name": "부산광역시", "domain": "busan.go.kr", "x": 72, "y": 76},
    {"id": "daegu", "name": "대구", "full_name": "대구광역시", "domain": "daegu.go.kr", "x": 63, "y": 62},
    {"id": "incheon", "name": "인천", "full_name": "인천광역시", "domain": "incheon.go.kr", "x": 36, "y": 20},
    {"id": "gwangju", "name": "광주", "full_name": "광주광역시", "domain": "gwangju.go.kr", "x": 42, "y": 78},
    {"id": "daejeon", "name": "대전", "full_name": "대전광역시", "domain": "daejeon.go.kr", "x": 51, "y": 50},
    {"id": "ulsan", "name": "울산", "full_name": "울산광역시", "domain": "ulsan.go.kr", "x": 75, "y": 70},
    {"id": "sejong", "name": "세종", "full_name": "세종특별자치시", "domain": "sejong.go.kr", "x": 48, "y": 43},
    {"id": "gyeonggi", "name": "경기", "full_name": "경기도", "domain": "gg.go.kr", "x": 47, "y": 25},
    {
        "id": "gangwon",
        "name": "강원",
        "full_name": "강원특별자치도",
        "domain": "province.gangwon.kr",
        "x": 68,
        "y": 25,
    },
    {"id": "chungbuk", "name": "충북", "full_name": "충청북도", "domain": "chungbuk.go.kr", "x": 58, "y": 41},
    {"id": "chungnam", "name": "충남", "full_name": "충청남도", "domain": "chungnam.go.kr", "x": 38, "y": 47},
    {
        "id": "jeonbuk",
        "name": "전북",
        "full_name": "전북특별자치도",
        "domain": "jeonbuk.go.kr",
        "x": 45,
        "y": 62,
    },
    {"id": "jeonnam", "name": "전남", "full_name": "전라남도", "domain": "jeonnam.go.kr", "x": 41, "y": 84},
    {"id": "gyeongbuk", "name": "경북", "full_name": "경상북도", "domain": "gb.go.kr", "x": 68, "y": 53},
    {"id": "gyeongnam", "name": "경남", "full_name": "경상남도", "domain": "gyeongnam.go.kr", "x": 61, "y": 74},
    {"id": "jeju", "name": "제주", "full_name": "제주특별자치도", "domain": "jeju.go.kr", "x": 37, "y": 94},
]

LOCAL_YOUTH_PLAN_REGION_NAMES = [entry["name"] for entry in LOCAL_YOUTH_PLAN_REGIONS]
NEWS_FILTER_REGION_NAMES = ["중앙", *LOCAL_YOUTH_PLAN_REGION_NAMES]
LOCAL_REGION_NAME_ALIASES = {
    **{entry["full_name"]: entry["name"] for entry in LOCAL_YOUTH_PLAN_REGIONS},
    "강원도": "강원",
    "경상남도": "경남",
    "경상북도": "경북",
    "전라남도": "전남",
    "전라북도": "전북",
    "충청남도": "충남",
    "충청북도": "충북",
    "제주도": "제주",
}

KOREA_ADM1_REGION_NAMES = {
    "seoul": "Seoul",
    "busan": "Busan",
    "daegu": "Daegu",
    "incheon": "Incheon",
    "gwangju": "Gwangju",
    "daejeon": "Daejeon",
    "ulsan": "Ulsan",
    "sejong": "Sejong",
    "gyeonggi": "Gyeonggi",
    "gangwon": "Gangwon",
    "chungbuk": "North Chungcheong",
    "chungnam": "South Chungcheong",
    "jeonbuk": "North Jeolla",
    "jeonnam": "South Jeolla",
    "gyeongbuk": "North Gyeongsang",
    "gyeongnam": "South Gyeongsang",
    "jeju": "Jeju",
}

LOCAL_PLAN_STATUS_LABELS = {
    "confirmed": "원문 확인됨",
    "candidate": "후보 있음",
    "missing": "미확인",
}

# Marker coordinates are calculated from the ADM1 SVG path geometry.
# Gyeonggi wraps around Seoul, so its visual label is anchored in the southern
# part of the province instead of the path bounding-box center.
LOCAL_MAP_LABEL_COORDINATE_OVERRIDES = {
    "gyeonggi": (430.0, 320.0),
}

SMALL_MAP_REGION_HIT_RADII = {
    "seoul": 32.0,
    "incheon": 34.0,
    "busan": 32.0,
    "daegu": 36.0,
    "gwangju": 36.0,
    "daejeon": 32.0,
    "ulsan": 32.0,
    "sejong": 30.0,
}

SMALL_MAP_REGION_HIT_POINTS = {
    "seoul": (388.0, 225.0),
    "incheon": (320.0, 250.0),
    "daejeon": (448.0, 462.0),
    "sejong": (407.0, 412.0),
}

LOCAL_YOUTH_PLAN_STATIC_LINKS = {
    "seoul": {
        "basic_plan": {
            "title": "제3차 서울 청년정책 기본계획 관련 발표",
            "url": "https://news.seoul.go.kr/gov/?p=573264",
        },
        "implementation_plan": {
            "title": "2026년 지자체 청년정책 시행계획 수립 요약",
            "url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156758853&pWise=main&pWiseMain=L3",
        },
    },
    "busan": {
        "basic_plan": {
            "title": "제2차 부산광역시 청년정책 기본계획(2024~2028)",
            "url": "https://young.busan.go.kr/article/list.nm?menuCd=169",
        },
        "implementation_plan": {
            "title": "2026년 부산광역시 청년정책 시행계획",
            "url": "https://young.busan.go.kr/article/list.nm?menuCd=169",
        },
    },
    "daegu": {
        "basic_plan": {
            "title": "제3차 대구광역시 청년정책 기본계획 최종보고서",
            "url": "https://www.daegu.go.kr/public/index.do?menu_id=00935062",
        },
        "implementation_plan": {
            "title": "2026년 지자체 청년정책 시행계획 수립 요약",
            "url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156758853&pWise=main&pWiseMain=L3",
        },
    },
    "incheon": {
        "basic_plan": {
            "title": "인천광역시 제2차 청년정책 기본계획(2026~2030)",
            "url": "https://youth.incheon.go.kr/bbs/bbsMsgDetail.do?bcd=data&msg_seq=22&pgno=1",
        },
        "implementation_plan": {
            "title": "2026년 인천광역시 청년정책 시행계획",
            "url": "https://youth.incheon.go.kr/bbs/bbsMsgDetail.do?bcd=data&msg_seq=23",
        },
    },
    "gwangju": {
        "basic_plan": {
            "title": "광주 청년정책 기본계획 관련 정책자료",
            "url": "https://youth.gwangju.go.kr/www/57",
        },
        "implementation_plan": {
            "title": "2026년 지자체 청년정책 시행계획 수립 요약",
            "url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156758853&pWise=main&pWiseMain=L3",
        },
    },
    "daejeon": {
        "basic_plan": {
            "title": "대전광역시 청년정책 자료실",
            "url": "https://www.daejeonyouthportal.kr/board/BBSMSTR_000000000231/articleList.do?pageIndex=1",
        },
        "implementation_plan": {
            "title": "2026년 대전광역시 청년정책 시행계획",
            "url": "https://www.daejeonyouthportal.kr/board/BBSMSTR_000000000231/articleList.do?pageIndex=1",
        },
    },
    "ulsan": {
        "basic_plan": {
            "title": "울산 청년정책 기본계획 연구",
            "url": "https://www.ulsan.go.kr/photo/index.ulsan?areaCode=&cateCode=&cnt=&code=002004000000&dt1=&dt2=&dt3=&dt4=&ed=&menuCd=DOM_000000103002000000&mode=list&orderBy=2&page=38&resourceSid=456451&s=&sd=&searchStr=&searchType=",
        },
        "implementation_plan": {
            "title": "2026년 울산광역시 구·군 청년정책 시행계획",
            "url": "https://ulsan.go.kr/s/ulsanyouth/bbs/view.do?bbsId=BBS_0000000000000310&dataId=55832&mId=008006001000000000",
        },
    },
    "sejong": {
        "basic_plan": {
            "title": "세종특별자치시 청년정책 자료",
            "url": "https://news.sejong.go.kr/news/articleView.html?idxno=4060",
        },
        "implementation_plan": {
            "title": "2026년 지자체 청년정책 시행계획 수립 요약",
            "url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156758853&pWise=main&pWiseMain=L3",
        },
    },
    "gyeonggi": {
        "basic_plan": {
            "title": "제2차 경기도 청년정책 기본계획(2023~2027)",
            "url": "https://www.gg.go.kr/bbs/boardView.do?bIdx=206525783&bcIdx=&bsIdx=764&menuId=3108&page=1",
        },
        "implementation_plan": {
            "title": "2026년 경기도 청년정책 시행계획",
            "url": "https://youth.gg.go.kr/gg/intro/archives.do?article.offset=0&articleLimit=10&articleNo=9034&mode=view",
        },
    },
    "gangwon": {
        "basic_plan": {
            "title": "강원특별자치도 청년정책 자료",
            "url": "https://state.gwd.go.kr/portal/partinfo/welfare/youth",
        },
        "implementation_plan": {
            "title": "2025년 강원특별자치도 청년정책 시행계획",
            "url": "https://www.jeongseon.go.kr/youth/community/pds",
        },
    },
    "chungbuk": {
        "basic_plan": {
            "title": "충청북도 청년정책 자료실",
            "url": "https://www.chungbuk.go.kr/young/selectBbsNttList.do?bbsNo=175&key=1284&pageIndex=1&pageUnit=10&searchCnd=all&searchCtgry=&searchKrwd=",
        },
        "implementation_plan": {
            "title": "2026년 충청북도 청년정책 시행계획",
            "url": "https://www.chungbuk.go.kr/young/selectBbsNttView.do?bbsNo=175&key=1284&nttNo=418938",
        },
    },
    "chungnam": {
        "basic_plan": {
            "title": "충남 청년정책 개요",
            "url": "https://youth.chungnam.go.kr/web/main/contents/M010-01",
        },
        "implementation_plan": {
            "title": "2026년 충청남도 청년정책 시행계획",
            "url": "https://youth.chungnam.go.kr/web/main/contents/M010-01",
        },
    },
    "jeonbuk": {
        "basic_plan": {
            "title": "제2차 전라북도 청년정책 기본계획 수립 연구용역",
            "url": "https://www.jeonbuk.go.kr/board/view.jeonbuk?boardId=BBS_0000156&dataSid=328900&menuCd=DOM_000000111002000000&orderBy=TMP_FIELD1%3ADESC&paging=ok&startPage=18",
        },
        "implementation_plan": {
            "title": "2026년 전북특별자치도 청년정책 시행계획",
            "url": "https://www.jeonbuk.go.kr/board/list.jeonbuk?boardId=BBS_0000044&listCel=1&listRow=10&menuCd=DOM_000000104006003000&paging=ok&startPage=1",
        },
    },
    "jeonnam": {
        "basic_plan": {
            "title": "전라남도 청년정책",
            "url": "https://www.jeonnam.go.kr/contentsView.do?menuId=brand0401000000",
        },
        "implementation_plan": {
            "title": "전라남도 청년정책 시행계획 자료실",
            "url": "https://www.jeonnam.go.kr/B0308/boardView.do?displayHeader=&infoReturn=&menuId=brand0309000000&pageIndex=13&searchText=&searchType=&seq=184",
        },
    },
    "gyeongbuk": {
        "basic_plan": {
            "title": "경상북도 청년정책 기본계획 관련 발표",
            "url": "https://www.gb.go.kr/Main/page.do?BD_CODE=bbs_bodo&B_LEVEL=0&B_NUM=506966901&B_STEP=506966900&Start=440&V_NUM=13710&bdName=&cmd=2&dept_code=&dept_name=&key=4&mnu_uid=6792&p1=0&p2=0&tbbscode1=bbs_bodo&word=",
        },
        "implementation_plan": {
            "title": "2026년 경상북도 청년정책 시행계획 확정",
            "url": "https://www.gb.go.kr/Main/page.do?BD_CODE=bbs_bodo&B_LEVEL=0&B_NUM=506966901&B_STEP=506966900&Start=440&V_NUM=13710&bdName=&cmd=2&dept_code=&dept_name=&key=4&mnu_uid=6792&p1=0&p2=0&tbbscode1=bbs_bodo&word=",
        },
    },
    "gyeongnam": {
        "basic_plan": {
            "title": "경상남도 청년정책기본계획 수립 발표",
            "url": "https://youth.gyeongnam.go.kr/youth/board.es?act=view&bid=0006&list_no=722&mid=a10502000000&tag=",
        },
        "implementation_plan": {
            "title": "2026년 지자체 청년정책 시행계획 수립 요약",
            "url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156758853&pWise=main&pWiseMain=L3",
        },
    },
    "jeju": {
        "basic_plan": {
            "title": "제주 청년정책 기본계획 연계 자료",
            "url": "https://www.jeju.go.kr/youth/index.htm",
        },
        "implementation_plan": {
            "title": "2026년 제주특별자치도 인구정책 시행계획",
            "url": "https://www.jeju.go.kr/lifecycle/notice/guide.htm?act=download&no=1&seq=2011964",
        },
    },
}


BASE_CSS = """
  :root {
    --page-bg: #f3faf7;
    --app-bg: #fbfefd;
    --panel: #ffffff;
    --panel-soft: #d9f0ea;
    --text: #263238;
    --muted: #65727a;
    --line: rgba(38, 50, 56, 0.12);
    --accent: #006f63;
    --accent-soft: rgba(217, 240, 234, 0.9);
    --accent-strong: #004f47;
    --filter-accent: var(--accent-strong);
    --filter-accent-strong: var(--accent-strong);
    --filter-active-bg: var(--accent-strong);
    --filter-active-border: transparent;
    --filter-active-stroke: #004f47;
    --home-accent: #006f63;
    --home-accent-soft: rgba(0, 111, 99, 0.18);
    --home-teal: #a8d5ba;
    --home-teal-soft: rgba(168, 213, 186, 0.22);
    --shadow: 0 18px 42px rgba(31, 42, 51, 0.08);
    --shadow-soft: 0 8px 20px rgba(31, 42, 51, 0.05);
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  [hidden] { display: none !important; }
  body {
    margin: 0;
    color: var(--text);
    background: linear-gradient(180deg, #eef8f5 0%, var(--page-bg) 100%);
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
    font-size: 1.78rem;
    font-weight: 650;
    line-height: 1;
    letter-spacing: 0;
    white-space: nowrap;
  }
  .brand-sub {
    display: block;
    color: var(--muted);
    font-size: 0.78rem;
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
  .page-intro-title {
    margin: 0;
    color: var(--accent-strong);
    font-size: clamp(1.55rem, 1.28rem + 0.8vw, 2.1rem);
    line-height: 1.25;
    font-weight: 900;
    letter-spacing: 0;
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
  .article-grid {
    align-items: stretch;
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
    margin-top: 8px;
  }
  .action-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 9px 13px;
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
    color: var(--filter-accent-strong, var(--accent-strong));
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
    flex-wrap: nowrap;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 4px;
    scrollbar-width: none;
  }
  .filter-controls::-webkit-scrollbar {
    display: none;
  }
  .news-filter-panel .filter-stack {
    grid-template-columns: 1fr;
  }
  .news-filter-panel .filter-group.wide {
    grid-column: 1 / -1;
  }
  .news-filter-panel .filter-controls {
    flex-wrap: wrap;
    overflow: visible;
    padding-bottom: 0;
  }
  .news-filter-panel .filter-button {
    flex: 0 0 auto;
  }
  .filter-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 8px 12px;
    border: 1px solid rgba(31, 42, 51, 0.09);
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.92);
    color: var(--filter-accent-strong, var(--accent-strong));
    font-size: 0.8rem;
    font-weight: 700;
    white-space: nowrap;
    flex: 0 0 auto;
    cursor: pointer;
  }
  .filter-button.active {
    border-color: var(--filter-active-border, transparent);
    background: var(--filter-active-bg, var(--accent-strong));
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
    gap: 12px;
    position: relative;
    overflow: hidden;
    border-color: rgba(31, 42, 51, 0.12);
    padding: 17px 17px 17px 22px;
  }
  .article-card::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 5px;
    background: linear-gradient(180deg, rgba(57, 86, 119, 0.22), rgba(221, 147, 103, 0.2));
    opacity: 0.86;
  }
  .article-card > * {
    position: relative;
    z-index: 1;
  }
  .article-media {
    display: block;
    aspect-ratio: 16 / 9;
    overflow: hidden;
    border-radius: 8px;
    background: rgba(245, 241, 234, 0.96);
  }
  .article-thumbnail {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.2s ease;
  }
  .article-media:hover .article-thumbnail,
  .article-media:focus-visible .article-thumbnail {
    transform: scale(1.025);
  }
  .article-media.fallback {
    display: flex;
    align-items: center;
    justify-content: center;
    background:
      linear-gradient(135deg, rgba(246, 238, 225, 0.94), rgba(234, 244, 240, 0.94));
  }
  .article-media.fallback .article-thumbnail {
    object-fit: contain;
    padding: 18px;
    box-sizing: border-box;
    opacity: 0.92;
  }
  .article-media.fallback:hover .article-thumbnail,
  .article-media.fallback:focus-visible .article-thumbnail {
    transform: scale(1.015);
  }
  .article-meta {
    display: grid;
    gap: 7px;
  }
  .article-meta-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .meta-pill {
    display: inline-flex;
    align-items: center;
    padding: 7px 11px;
    border-radius: 999px;
    font-size: 0.8rem;
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
    font-size: 0.86rem;
    line-height: 1.5;
  }
  .article-byline .meta-divider {
    opacity: 0.45;
  }
  .article-byline .meta-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .publisher-icon {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    object-fit: contain;
    background: rgba(255, 255, 255, 0.86);
    box-shadow: 0 0 0 1px rgba(31, 42, 51, 0.08);
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
  .article-card h3 {
    font-size: clamp(1.16rem, 1.08rem + 0.42vw, 1.36rem);
    line-height: 1.32;
    letter-spacing: -0.045em;
  }
  .article-summary {
    margin: 0;
    color: rgba(31, 42, 51, 0.88);
    font-size: clamp(1.01rem, 0.98rem + 0.18vw, 1.09rem);
    line-height: 1.62;
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
  .footer-note a {
    color: var(--accent);
    font-weight: 800;
    text-decoration: underline;
    text-underline-offset: 3px;
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
    border-color: var(--home-accent-soft);
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
    border-color: var(--home-accent-soft);
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
    font-size: 3.22rem;
    font-weight: 650;
    line-height: 1.03;
    letter-spacing: 0;
    max-width: 11em;
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
    padding-right: clamp(188px, 39%, 272px);
    min-height: 312px;
  }
  .home-briefing-card > .home-illustration-slot {
    position: absolute;
    right: 16px;
    bottom: 2px;
    z-index: 0;
  }
  .home-illustration-slot {
    width: clamp(168px, 34%, 250px);
    max-width: 48%;
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
    font-size: 1.32rem;
    letter-spacing: 0;
  }
  .home-briefing-head p {
    margin: 0;
    color: var(--muted);
    font-size: 1rem;
    line-height: 1.62;
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
    border-color: var(--home-accent-soft);
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
    font-size: 0.88rem;
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
    border-color: var(--home-accent-soft);
    background: rgba(251, 235, 224, 0.94);
  }
  .home-keyword-strip {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .home-keyword-strip .home-keyword-list {
    gap: 8px;
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
  .home-briefing-tabs {
    display: grid;
    gap: 14px;
  }
  .home-briefing-tablist {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .home-briefing-tab {
    min-height: 46px;
    padding: 10px 12px;
    border: 1px solid rgba(57, 86, 119, 0.18);
    border-radius: 8px;
    background: rgba(241, 245, 250, 0.96);
    color: var(--accent-strong);
    font: inherit;
    font-size: 0.94rem;
    font-weight: 900;
    line-height: 1.25;
    cursor: pointer;
  }
  .home-briefing-tab[aria-selected="true"] {
    border-color: var(--accent-strong);
    background: var(--accent-strong);
    color: #ffffff;
  }
  .home-briefing-panel {
    display: grid;
    gap: 12px;
  }
  .home-briefing-panel[hidden] {
    display: none;
  }
  .home-briefing-panel-note {
    margin: 0;
    color: var(--muted);
    font-size: 0.94rem;
    line-height: 1.55;
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
    border-color: var(--home-accent-soft);
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
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0;
    min-width: 0;
  }
  .bottom-nav a span {
    white-space: nowrap;
  }
  .bottom-nav-icon {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 999px;
    background: var(--panel-soft);
    color: var(--accent-strong);
  }
  .bottom-nav-icon svg {
    width: 17px;
    height: 17px;
    stroke: currentColor;
    stroke-width: 2.2;
    stroke-linecap: round;
    stroke-linejoin: round;
    fill: none;
  }
  .bottom-nav a.active {
    color: var(--accent-strong);
  }
  .bottom-nav a.active .bottom-nav-icon {
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
      grid-template-columns: 82px minmax(0, 1fr);
      column-gap: 15px;
    }
    .brand-logo {
      width: 82px;
    }
    .brand-title {
      font-size: 2.26rem;
    }
    .brand-sub {
      font-size: 0.88rem;
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
    .article-card {
      padding: 22px 24px 22px 28px;
      gap: 13px;
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
      padding-right: clamp(218px, 34%, 296px);
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
      width: clamp(202px, 32%, 276px);
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
      align-items: stretch;
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
      font-size: 1.48rem;
    }
    .brand-sub {
      font-size: 0.7rem;
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
      width: min(184px, 52vw);
      max-width: 70%;
    }
    .home-briefing-title {
      font-size: 2.18rem;
      letter-spacing: 0;
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
      font-size: 1.24rem;
    }
    .brand-sub {
      font-size: 0.62rem;
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
    .bottom-nav-icon {
      width: 24px;
      height: 24px;
    }
    .bottom-nav-icon svg {
      width: 15px;
      height: 15px;
    }
  }

  /* GovNews-style dashboard skin: keeps the current pages and data contract. */
  :root {
    --page-bg: #f3faf7;
    --app-bg: #fbfefd;
    --panel: #ffffff;
    --panel-soft: #d9f0ea;
    --text: #263238;
    --muted: #65727a;
    --line: #e7ddc8;
    --accent: #006f63;
    --accent-soft: #d9f0ea;
    --accent-strong: #004f47;
    --surface-container-low: #f3faf7;
    --surface-container-high: #d9f0ea;
    --surface-container-highest: #ebddad;
    --error: #a84a34;
    --shadow: none;
    --shadow-soft: none;
  }
  body {
    background: var(--page-bg);
    font-family: "Public Sans", "Noto Sans KR", sans-serif;
    padding: 0;
  }
  .shell {
    max-width: none;
    width: 100%;
    min-height: 100vh;
    margin: 0;
    padding: 76px 18px 104px;
    border: 0;
    background: var(--surface-container-low);
    box-shadow: none;
  }
  .topbar {
    position: fixed;
    inset: 0 0 auto 0;
    height: 64px;
    margin: 0;
    padding: 0 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.14);
    background: #004f47;
    color: #ffffff;
    box-shadow: none;
    backdrop-filter: none;
  }
  .brand {
    grid-template-columns: 40px minmax(0, 1fr);
    column-gap: 12px;
    max-width: min(58vw, 360px);
    color: #ffffff;
  }
  .brand-logo {
    width: 40px;
    padding: 4px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.12);
  }
  .brand-title {
    color: #ffffff;
    font-size: 1.18rem;
    font-weight: 900;
  }
  .brand-sub {
    color: rgba(255, 255, 255, 0.72);
    font-size: 0.78rem;
  }
  .topbar-side {
    gap: 10px;
  }
  .guide-link {
    border-radius: 4px;
    border-color: rgba(255, 255, 255, 0.22);
    background: rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.92);
  }
  .guide-link:hover,
  .guide-link.active {
    background: rgba(255, 255, 255, 0.18);
    color: #ffffff;
  }
  .header-side strong {
    color: #ffffff;
    font-size: 0.86rem;
  }
  .header-side span {
    color: rgba(255, 255, 255, 0.68);
  }
  .hero-card,
  .status-card,
  .section-card,
  .article-card,
  .info-card,
  .list-card,
  .menu-update-card,
  .filter-panel,
  .news-intro-card,
  .page-intro-card {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel);
    box-shadow: none;
  }
  .page-intro-card {
    color: var(--text);
    background: var(--panel);
  }
  .page-intro-badge,
  .eyebrow {
    border-radius: 4px;
    background: var(--surface-container-highest);
    color: var(--accent-strong);
    font-size: 0.75rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }
  .page-intro-copy {
    color: var(--muted);
  }
  .page-intro-media img {
    filter: none;
  }
  .section {
    margin-top: 24px;
  }
  .section-head {
    padding-top: 18px;
    border-top: 1px solid var(--line);
  }
  .section-head p,
  .section-card p,
  .info-card p,
  .list-card p,
  .news-intro-copy {
    color: var(--muted);
  }
  .filter-panel {
    background: var(--panel);
  }
  .filter-button,
  .date-input-wrap,
  .filter-search-input,
  .action-button,
  .button,
  .badge,
  .meta-pill.subtle {
    border-radius: 4px;
    background: var(--surface-container-highest);
    border-color: transparent;
    box-shadow: none;
  }
  .filter-button.active,
  .button.primary,
  .meta-pill.primary {
    background: var(--accent-strong);
    color: #ffffff;
  }
  .article-grid {
    gap: 14px;
  }
  .article-card {
    grid-template-columns: minmax(0, 1fr) 96px;
    grid-template-areas:
      "meta meta"
      "title media"
      "badges media"
      "summary media"
      "actions actions"
      "feedback feedback";
    align-content: start;
    column-gap: 16px;
    row-gap: 10px;
    padding: 18px;
    border-color: var(--line);
    transition: box-shadow 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
  }
  .article-card:hover {
    border-color: #aeb4c2;
    box-shadow: 0 8px 18px rgba(26, 28, 31, 0.08);
    transform: translateY(-1px);
  }
  .article-card::before {
    display: none;
  }
  .article-meta {
    grid-area: meta;
  }
  .article-card h3 {
    grid-area: title;
    font-size: 1.04rem;
    line-height: 1.42;
    letter-spacing: 0;
  }
  .article-media {
    grid-area: media;
    width: 96px;
    height: 96px;
    aspect-ratio: 1;
    border-radius: 6px;
    background: var(--surface-variant, #e2e2e7);
  }
  .article-media.fallback {
    background: var(--surface-container-highest);
  }
  .article-media.fallback .article-thumbnail {
    padding: 18px;
  }
  .badge-row {
    grid-area: badges;
  }
  .article-summary {
    grid-area: summary;
    display: -webkit-box;
    overflow: hidden;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.58;
    white-space: normal;
  }
  .article-actions {
    grid-area: actions;
    padding-top: 12px;
    border-top: 1px solid var(--surface-container-highest);
  }
  .article-feedback {
    grid-area: feedback;
  }
  .meta-pill,
  .badge {
    padding: 5px 8px;
    font-size: 0.68rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }
  .article-byline {
    font-size: 0.78rem;
    color: var(--outline, #737780);
  }
  .mini-link {
    color: var(--accent);
  }
  .footer-note {
    color: var(--muted);
  }
  @media (min-width: 980px) {
    body {
      background: var(--surface-container-low);
    }
    .shell {
      max-width: none;
      padding: 88px 32px 48px 288px;
      background: var(--surface-container-low);
    }
    .shell > .hero,
    .shell > .section,
    .shell > .page-intro-card,
    .shell > .news-intro-card,
    .shell > .footer-note {
      max-width: 1280px;
      margin-left: auto;
      margin-right: auto;
    }
    .topbar {
      margin: 0;
      padding: 0 24px;
    }
    .brand {
      grid-template-columns: 40px minmax(0, 1fr);
      column-gap: 12px;
    }
    .brand-logo {
      width: 40px;
    }
    .brand-title {
      font-size: 1.22rem;
    }
    .brand-sub {
      font-size: 0.72rem;
    }
    .nav {
      position: fixed;
      left: 0;
      top: 64px;
      bottom: 0;
      z-index: 19;
      display: flex;
      width: 256px;
      padding: 78px 12px 24px;
      border-right: 1px solid #d1d5db;
      background: #ffffff;
      flex-direction: column;
      align-items: stretch;
      gap: 4px;
    }
    .nav::before {
      content: "Navigation\\A청년정책 모아봄";
      position: absolute;
      top: 20px;
      left: 24px;
      right: 24px;
      color: #004f47;
      font-size: 0.72rem;
      font-weight: 900;
      line-height: 1.55;
      white-space: pre;
      text-transform: uppercase;
    }
    .nav a {
      justify-content: flex-start;
      padding: 12px 14px;
      border-radius: 4px;
      border: 0;
      border-right: 4px solid transparent;
      color: #43474f;
      font-size: 0.9rem;
      font-weight: 700;
    }
    .nav a:hover {
      background: #f4f3f8;
      color: #004f47;
    }
    .nav a.active {
      border-right-color: #006f63;
      background: #f3faf7;
      color: #004f47;
    }
    .hero {
      grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
      gap: 16px;
    }
    .article-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }
    .filter-stack {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .news-filter-panel .filter-stack {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .news-filter-panel .filter-group.wide {
      grid-column: 1 / -1;
    }
  }
  @media (max-width: 720px) {
    .shell {
      padding-left: 14px;
      padding-right: 14px;
    }
    .topbar {
      height: auto;
      min-height: 64px;
      padding: 10px 14px;
    }
    .brand {
      grid-template-columns: 38px minmax(0, 1fr);
      max-width: none;
    }
    .brand-logo {
      width: 38px;
    }
    .brand-title {
      font-size: 1.08rem;
    }
    .brand-sub {
      font-size: 0.66rem;
    }
    .guide-link {
      padding: 7px 9px;
      font-size: 0.72rem;
    }
    .article-card {
      grid-template-columns: minmax(0, 1fr) 82px;
    }
    .article-media {
      width: 82px;
      height: 82px;
    }
    .article-card h3 {
      font-size: 0.98rem;
    }
    .article-summary {
      -webkit-line-clamp: 2;
      font-size: 0.86rem;
    }
  }

  /* Civic Dashboard skin: public portal chrome with top and side navigation. */
  :root {
    --page-bg: #f3faf7;
    --app-bg: #fbfefd;
    --panel: #ffffff;
    --panel-soft: #d9f0ea;
    --text: #263238;
    --muted: #65727a;
    --line: #e7ddc8;
    --accent: #006f63;
    --accent-soft: #d9f0ea;
    --accent-strong: #004f47;
    --surface: #fbfefd;
    --surface-container-low: #f3faf7;
    --surface-container-high: #d9f0ea;
    --surface-container-highest: #ebddad;
    --outline: #69757c;
    --outline-variant: #e7ddc8;
    --error: #a84a34;
    --shadow: none;
    --shadow-soft: none;
  }
  body {
    margin: 0;
    padding: 0;
    background: var(--surface-container-low);
    color: var(--text);
    font-family: "Public Sans", "Noto Sans KR", sans-serif;
    font-size: 16.5px;
    line-height: 1.62;
  }
  html {
    scroll-padding-top: 96px;
  }
  .topbar {
    position: fixed;
    inset: 0 0 auto 0;
    z-index: 60;
    display: flex;
    align-items: center;
    gap: 18px;
    height: 72px;
    min-height: 72px;
    margin: 0;
    padding: 0 18px;
    border-bottom: 1px solid var(--outline-variant);
    background: rgba(255, 255, 255, 0.98);
    color: var(--text);
    box-shadow: none;
    backdrop-filter: none;
  }
  .brand {
    display: grid;
    grid-template-columns: 40px minmax(0, 1fr);
    align-items: center;
    column-gap: 12px;
    flex: 0 1 320px;
    min-width: 0;
    max-width: min(58vw, 360px);
    color: var(--accent-strong);
  }
  .brand-logo {
    width: 44px;
    background: var(--surface-container-low);
    box-shadow: 0 0 0 1px var(--outline-variant);
  }
  .brand-title {
    color: var(--accent-strong);
    font-weight: 900;
    font-size: 1.28rem;
  }
  .brand-sub,
  .header-side span {
    color: var(--muted);
  }
  .header-side span {
    font-size: 0.82rem;
  }
  .brand-sub {
    font-size: 0.82rem;
    line-height: 1.35;
  }
  .top-nav {
    display: none;
    align-items: center;
    justify-content: flex-end;
    gap: 4px;
    margin-left: auto;
    min-width: 0;
    flex: 1 1 auto;
    height: 100%;
  }
  .top-nav-link {
    display: inline-flex;
    align-items: center;
    height: 100%;
    padding: 0 10px;
    border-bottom: 2px solid transparent;
    color: #4d565f;
    font-size: 0.96rem;
    font-weight: 800;
    white-space: nowrap;
  }
  .top-nav-link:hover {
    color: var(--accent-strong);
    background: var(--surface-container-low);
  }
  .top-nav-link.active {
    border-bottom-color: var(--accent);
    color: var(--accent-strong);
  }
  .app-layout {
    min-height: 100vh;
    padding-top: 72px;
    background: var(--surface-container-low);
  }
  .shell {
    max-width: none;
    width: 100%;
    min-height: calc(100vh - 72px);
    margin: 0;
    padding: 20px 14px 104px;
    border: 0;
    background: var(--surface-container-low);
    box-shadow: none;
  }
  .side-nav {
    display: none;
  }
  .topbar-side {
    gap: 10px;
    margin-left: 0;
  }
  .header-side strong {
    color: var(--accent-strong);
    font-size: 0.96rem;
  }
  .admin-entry {
    display: none;
    align-items: center;
    justify-content: center;
    min-height: 34px;
    padding: 0 12px;
    border: 1px solid var(--outline-variant);
    border-radius: 4px;
    background: var(--surface);
    color: var(--accent-strong);
    font: inherit;
    font-size: 0.88rem;
    font-weight: 800;
    cursor: pointer;
  }
  .admin-entry:hover {
    border-color: var(--accent);
    color: var(--accent-strong);
  }
  body.is-admin-authorized .admin-entry {
    border-color: var(--accent-strong);
    background: var(--accent-strong);
    color: #ffffff;
  }
  .admin-login-overlay {
    position: fixed;
    inset: 0;
    z-index: 95;
    display: grid;
    place-items: center;
    padding: 18px;
    background: rgba(26, 28, 31, 0.42);
  }
  .admin-login-dialog {
    width: min(100%, 440px);
    display: grid;
    gap: 16px;
    padding: 24px;
    border: 1px solid var(--outline-variant);
    border-radius: 8px;
    background: #ffffff;
    box-shadow: 0 18px 44px rgba(26, 28, 31, 0.18);
  }
  .admin-login-head {
    display: flex;
    align-items: start;
    justify-content: space-between;
    gap: 16px;
  }
  .admin-login-head h2 {
    margin: 0;
    color: var(--accent-strong);
    font-size: 1.2rem;
  }
  .admin-login-head p,
  .admin-login-warning,
  .admin-login-feedback {
    margin: 0;
    color: var(--muted);
    font-size: 0.86rem;
    line-height: 1.55;
  }
  .admin-login-close {
    border: 0;
    background: transparent;
    color: var(--outline);
    font: inherit;
    font-size: 1.2rem;
    cursor: pointer;
  }
  .admin-login-form {
    display: grid;
    gap: 12px;
  }
  .admin-login-form label {
    display: grid;
    gap: 7px;
    color: var(--accent-strong);
    font-size: 0.8rem;
    font-weight: 900;
  }
  .admin-login-input {
    width: 100%;
    min-height: 44px;
    padding: 10px 12px;
    border: 1px solid var(--outline-variant);
    border-radius: 4px;
    background: var(--surface);
    color: var(--text);
    font: inherit;
  }
  .admin-login-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .admin-login-feedback.error {
    color: var(--error);
  }
  .guide-link {
    border-radius: 4px;
    border-color: var(--outline-variant);
    background: var(--surface);
    color: var(--accent-strong);
    font-size: 0.88rem;
  }
  .guide-link:hover,
  .guide-link.active {
    border-color: var(--accent);
    background: var(--accent-strong);
    color: #ffffff;
  }
  .hero-card,
  .status-card,
  .section-card,
  .article-card,
  .info-card,
  .list-card,
  .menu-update-card,
  .filter-panel,
  .news-intro-card,
  .page-intro-card,
  .home-briefing-card,
  .home-section-card {
    border: 1px solid var(--outline-variant);
    border-radius: 8px;
    background: var(--panel);
    box-shadow: none;
  }
  .hero-card,
  .status-card,
  .section-card,
  .info-card,
  .list-card,
  .menu-update-card {
    padding: 20px;
  }
  .page-intro-card,
  .news-intro-card {
    padding: 20px 22px;
    color: var(--text);
    background: var(--panel);
  }
  .page-intro-badge,
  .eyebrow {
    border-radius: 4px;
    background: var(--surface-container-highest);
    color: var(--accent-strong);
    font-size: 0.86rem;
    letter-spacing: 0;
    text-transform: none;
  }
  .page-intro-title {
    color: var(--accent-strong);
  }
  .page-intro-copy,
  .hero-copy,
  .section-head p,
  .section-card p,
  .info-card p,
  .list-card p,
  .news-intro-copy,
  .filter-head p {
    color: var(--muted);
  }
  h1,
  h2,
  h3,
  .article-card h3 {
    letter-spacing: 0;
  }
  .section {
    margin-top: 28px;
  }
  .section-head {
    padding-top: 0;
    border-top: 0;
  }
  .filter-panel {
    gap: 16px;
    background: var(--panel);
  }
  .filter-stack {
    gap: 14px;
  }
  .filter-group-label {
    color: var(--filter-accent-strong, var(--accent-strong));
    font-size: 0.9rem;
    letter-spacing: 0;
    text-transform: none;
  }
  .filter-button,
  .date-input-wrap,
  .filter-search-input,
  .action-button,
  .button,
  .badge,
  .meta-pill.subtle,
  .list-item {
    border-radius: 4px;
    border-color: var(--outline-variant);
    background: var(--surface);
    box-shadow: none;
  }
  .filter-button {
    min-height: 44px;
    padding: 10px 16px;
    font-size: 0.98rem;
    line-height: 1.35;
  }
  .button,
  .action-button {
    min-height: 42px;
    font-size: 0.98rem;
    line-height: 1.35;
  }
  .filter-button.active,
  .button.primary,
  .meta-pill.primary {
    border-color: var(--accent-strong);
    background: var(--accent-strong);
    color: #ffffff;
  }
  .article-grid {
    grid-template-columns: 1fr;
    gap: 20px;
    align-items: stretch;
  }
  .article-card {
    display: flex;
    flex-direction: column;
    gap: 0;
    overflow: hidden;
    min-width: 0;
    padding: 0;
    border-color: var(--outline-variant);
    background: var(--panel);
    transition: box-shadow 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
  }
  .article-card:hover {
    border-color: #aeb4c2;
    box-shadow: 0 4px 12px rgba(26, 28, 31, 0.06);
    transform: translateY(-1px);
  }
  .article-card::before {
    display: none;
  }
  .article-card::after {
    content: "";
    position: absolute;
    right: 14px;
    bottom: 14px;
    z-index: 0;
    width: 58px;
    height: 58px;
    pointer-events: none;
    opacity: 0.12;
    background:
      radial-gradient(ellipse at 50% 16%, #d9f0ea 0 15%, transparent 16%),
      radial-gradient(ellipse at 84% 45%, #d9f0ea 0 15%, transparent 16%),
      radial-gradient(ellipse at 68% 86%, #d9f0ea 0 15%, transparent 16%),
      radial-gradient(ellipse at 30% 84%, #d9f0ea 0 15%, transparent 16%),
      radial-gradient(ellipse at 16% 43%, #d9f0ea 0 15%, transparent 16%),
      radial-gradient(circle at 50% 51%, #f2c66d 0 9%, transparent 10%);
    transform: rotate(-12deg);
  }
  .article-card.no-media::after {
    opacity: 0.18;
  }
  .article-card > * {
    position: relative;
    z-index: 1;
  }
  .article-card > :not(.article-media) {
    margin-left: 18px;
    margin-right: 18px;
  }
  .article-media {
    order: 0;
    display: block;
    width: 100%;
    height: 190px;
    aspect-ratio: auto;
    border-radius: 0;
    border-bottom: 1px solid var(--outline-variant);
    background: var(--surface-container-highest);
  }
  .article-media.fallback {
    background: var(--surface-container-highest);
  }
  .article-media.fallback .article-thumbnail {
    padding: 28px;
  }
  .article-meta {
    display: grid;
    gap: 8px;
    margin-top: 16px;
  }
  .article-meta-tags {
    gap: 6px;
  }
  .meta-pill,
  .badge {
    padding: 5px 8px;
    border-radius: 4px;
    font-size: 0.78rem;
    letter-spacing: 0;
    text-transform: none;
  }
  .meta-pill.primary {
    background: transparent;
    color: var(--accent-strong);
    padding-left: 0;
    padding-right: 0;
    font-weight: 900;
  }
  .article-byline {
    gap: 8px;
    color: var(--outline);
    font-size: 0.9rem;
  }
  .publisher-icon {
    width: 18px;
    height: 18px;
    border-radius: 4px;
  }
  .article-card h3 {
    margin-top: 10px;
    color: var(--accent-strong);
    font-size: 1.2rem;
    line-height: 1.42;
  }
  .badge-row {
    gap: 6px;
    margin-top: 10px;
  }
  .badge {
    color: var(--accent-strong);
    font-weight: 700;
  }
  .article-summary {
    display: -webkit-box;
    overflow: hidden;
    margin-top: 10px;
    color: var(--muted);
    font-size: 1rem;
    line-height: 1.6;
    white-space: normal;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
  }
  .article-actions {
    margin: auto 18px 18px;
    padding-top: 14px;
    border-top: 1px solid var(--surface-container-highest);
  }
  .article-feedback {
    margin: 0 18px 12px;
  }
  .article-card.no-media {
    gap: 0;
    padding: 20px;
    border-left: 4px solid var(--accent);
  }
  .article-card.no-media > :not(.article-media) {
    margin-left: 0;
    margin-right: 0;
  }
  .article-card.no-media .article-meta {
    margin-top: 0;
  }
  .article-card.no-media h3 {
    margin-top: 12px;
    font-size: 1.24rem;
  }
  .article-card.no-media .article-summary {
    -webkit-line-clamp: 4;
  }
  .article-card.no-media .article-actions {
    margin: auto 0 0;
  }
  .article-card.no-media .article-feedback {
    margin: 0;
  }
  .action-button,
  .mini-link {
    color: var(--accent-strong);
  }
  .home-briefing-grid {
    gap: 20px;
    margin-top: 0;
  }
  .civic-hero {
    display: block;
  }
  .home-briefing-card {
    gap: 16px;
    padding: 22px;
    overflow: hidden;
    background: var(--panel);
  }
  .home-briefing-card::before,
  .home-briefing-card::after {
    display: none;
  }
  .home-briefing-card.lead-arch,
  .home-briefing-card.digest-organic,
  .home-briefing-card.support-pill,
  .home-briefing-card.footer-warm {
    border-radius: 8px;
    background: var(--panel);
    box-shadow: none;
  }
  .home-briefing-card.lead-arch .home-briefing-date,
  .home-briefing-date {
    color: var(--accent-strong);
    font-size: 0.9rem;
    font-weight: 900;
    letter-spacing: 0;
    text-transform: none;
  }
  .home-briefing-card.lead-arch .home-briefing-title,
  .home-briefing-title {
    color: var(--accent-strong);
    max-width: 13em;
    font-size: clamp(2.05rem, 1.55rem + 2vw, 3.3rem);
    line-height: 1.08;
    letter-spacing: 0;
  }
  .home-briefing-card.lead-arch .home-briefing-copy,
  .home-briefing-copy {
    color: var(--muted);
    font-size: 1.08rem;
    line-height: 1.78;
  }
  .home-briefing-card.lead-arch.has-media {
    padding-right: 26px;
  }
  .home-briefing-card.lead {
    align-content: stretch;
  }
  .home-briefing-card.lead .home-briefing-content {
    align-self: stretch;
    display: flex;
    flex-direction: column;
  }
  .home-briefing-card.lead .hero-actions {
    margin-top: auto;
    padding-top: 14px;
  }
  .home-briefing-summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
    gap: 10px;
    margin-top: 4px;
    padding-top: 2px;
  }
  .home-briefing-summary span {
    display: grid;
    gap: 4px;
    min-width: 0;
    padding: 12px;
    border: 1px solid var(--outline-variant);
    border-radius: 4px;
    background: var(--surface);
  }
  .home-briefing-summary strong {
    color: var(--accent-strong);
    font-size: 1.22rem;
    font-weight: 900;
    line-height: 1.1;
  }
  .home-briefing-summary em {
    color: var(--muted);
    font-style: normal;
    font-size: 0.76rem;
    font-weight: 800;
    line-height: 1.25;
  }
  .home-briefing-card > .home-illustration-slot {
    position: relative;
    right: auto;
    bottom: auto;
    width: min(342px, 100%);
    margin: 8px 0 -10px auto;
    align-self: end;
    justify-self: end;
  }
  .home-illustration-img {
    filter: drop-shadow(0 20px 30px rgba(47, 41, 37, 0.14));
  }
  .home-glance-item,
  .home-keyword-panel,
  .home-urgent-link,
  .home-support-footer,
  .list-item {
    border-radius: 4px;
    border-color: var(--outline-variant);
    background: var(--surface);
    box-shadow: none;
  }
  .home-urgent-rank {
    border-radius: 999px;
    background: #d9f0ea;
    color: var(--accent-strong);
    font-size: 0.92rem;
  }
  .home-support-footer {
    padding: 20px;
  }
  .youth-metrics-card {
    display: grid;
    gap: 18px;
    padding: 22px;
    border: 1px solid var(--outline-variant);
    border-radius: 8px;
    background: var(--panel);
    box-shadow: none;
  }
  .youth-metrics-head {
    display: grid;
    gap: 8px;
    margin: 0;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--surface-container-highest);
  }
  .youth-metrics-head h2 {
    margin: 0;
    color: var(--accent-strong);
    font-size: 1.5rem;
    line-height: 1.35;
    letter-spacing: 0;
  }
  .youth-metrics-head p {
    margin: 0;
    color: var(--muted);
    font-size: 1rem;
    line-height: 1.62;
  }
  .youth-metrics-grid {
    display: grid;
    gap: 14px;
    grid-template-columns: 1fr;
  }
  .youth-metric-item {
    min-height: 150px;
    padding: 18px;
    border: 1px solid var(--outline-variant);
    border-radius: 8px;
    background: var(--surface);
    box-shadow: none;
  }
  .youth-metric-label {
    color: var(--muted);
    font-size: 0.92rem;
    font-weight: 900;
  }
  .youth-metric-value {
    color: var(--accent-strong);
    font-size: 1.95rem;
    font-weight: 900;
    letter-spacing: 0;
  }
  .youth-metric-meta {
    color: var(--muted);
  }
  .youth-metric-source {
    color: var(--accent-strong);
  }
  .youth-metrics-note {
    margin: 0;
    color: var(--outline);
  }
  .civic-flow-card {
    display: grid;
    gap: 12px;
  }
  .civic-flow-card h2 {
    margin: 0;
    color: var(--accent-strong);
    font-size: 1.2rem;
    line-height: 1.45;
  }
  .civic-flow-card .hero-actions {
    margin-top: 4px;
  }
  .home-maker-grid {
    display: grid;
    gap: 18px;
  }
  .home-maker-panel {
    grid-column: 1 / -1;
  }
  .home-maker-columns {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 18px;
  }
  .home-maker-column {
    display: grid;
    gap: 10px;
    align-content: start;
  }
  .home-maker-column h3 {
    margin: 0;
    color: var(--accent-strong);
    font-size: 1.08rem;
    line-height: 1.45;
  }
  .home-maker-column p {
    margin: 0;
  }
  .home-maker-panel .home-support-meta {
    margin-top: 4px;
  }
  .home-top-briefing .home-keyword-panel {
    display: none;
  }
  .home-top-briefing .home-glance-grid {
    grid-template-columns: 1fr;
  }
  .home-top-briefing .home-glance-item {
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    min-height: auto;
    padding: 10px 12px;
    text-align: left;
  }
  .home-top-briefing .home-glance-label {
    font-size: 0.86rem;
  }
  .home-top-briefing .home-glance-value {
    font-size: 1.24rem;
    letter-spacing: 0;
  }
  .home-top-briefing .home-briefing-tabs {
    gap: 10px;
  }
  .home-top-briefing .home-briefing-tab {
    min-height: 42px;
    padding-top: 8px;
    padding-bottom: 8px;
  }
  .home-top-briefing .home-briefing-panel-note {
    font-size: 0.88rem;
  }
  .home-top-briefing .home-urgent-list {
    max-height: none;
    overflow: visible;
  }
  .home-top-briefing .home-urgent-item {
    padding: 11px 0;
  }
  .home-top-briefing .home-urgent-link {
    gap: 12px;
  }
  .home-top-briefing .home-urgent-text strong {
    font-size: 0.94rem;
    line-height: 1.42;
  }
  .home-top-briefing .home-urgent-meta {
    font-size: 0.8rem;
  }
  .hero[id],
  .section[id],
  .home-briefing-card[id],
  .home-overview[id] {
    scroll-margin-top: 96px;
  }
  @media (min-width: 720px) {
    .article-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .youth-metrics-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  @media (min-width: 980px) {
    .shell {
      width: calc(100% - 256px);
      margin-left: 256px;
      padding: 32px;
      background: var(--surface-container-low);
    }
    .shell > .hero,
    .shell > .section,
    .shell > .page-intro-card,
    .shell > .news-intro-card,
    .shell > .footer-note,
    .shell > [data-news-filter-root],
    .shell > [data-policy-filter-root] {
      max-width: 1280px;
      margin-left: auto;
      margin-right: auto;
    }
    .topbar {
      padding: 0 32px;
      background: #ffffff;
      color: var(--text);
    }
    .brand {
      max-width: 360px;
    }
    .top-nav {
      display: flex;
    }
    .admin-entry {
      display: inline-flex;
    }
    .nav {
      display: none;
    }
    .side-nav {
      position: fixed;
      left: 0;
      top: 72px;
      bottom: 0;
      z-index: 45;
      display: flex;
      width: 256px;
      padding: 22px 12px 18px;
      border-right: 1px solid var(--outline-variant);
      background: #d9f0ea;
      flex-direction: column;
      gap: 18px;
      overflow-y: auto;
    }
    .side-nav-head {
      display: grid;
      gap: 4px;
      padding: 0 12px 14px;
      border-bottom: 1px solid rgba(115, 119, 128, 0.22);
    }
    .side-nav-head strong {
      color: var(--accent-strong);
      font-size: 1.08rem;
      font-weight: 900;
    }
    .side-nav-head span,
    .side-nav-kicker {
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.45;
    }
    .side-nav-links,
    .side-nav-admin {
      display: grid;
      gap: 4px;
    }
    .side-nav-link {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-height: 42px;
      padding: 10px 14px;
      border: 0;
      border-left: 4px solid transparent;
      background: transparent;
      color: #4d565f;
      font: inherit;
      font-size: 0.96rem;
      font-weight: 900;
      letter-spacing: 0;
      text-align: left;
      text-transform: none;
    }
    .side-nav-link:hover {
      background: #ffffff;
      color: var(--accent-strong);
    }
    .side-nav-link.active {
      border-left-color: var(--accent);
      background: #ffffff;
      color: var(--accent-strong);
    }
    .side-nav-admin {
      margin-top: auto;
      padding-top: 14px;
      border-top: 1px solid rgba(115, 119, 128, 0.22);
    }
    .side-nav-link.pending {
      color: #64748b;
      cursor: not-allowed;
      opacity: 0.78;
    }
    .side-nav-link.pending em {
      color: var(--outline);
      font-size: 0.78rem;
      font-style: normal;
      font-weight: 800;
    }
    .hero {
      grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
      gap: 24px;
    }
    .article-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 24px;
    }
    body[data-page="news.html"] .article-grid > .article-card.has-media:first-child,
    body[data-page="election.html"] .article-grid > .article-card.has-media:first-child {
      grid-column: span 2;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(280px, 0.92fr);
      grid-template-rows: auto auto auto 1fr auto auto;
      grid-template-areas:
        "media meta"
        "media title"
        "media badges"
        "media summary"
        "media actions"
        "media feedback";
      min-height: 360px;
      align-content: stretch;
    }
    body[data-page="news.html"] .article-grid > .article-card.has-media:first-child .article-media,
    body[data-page="election.html"] .article-grid > .article-card.has-media:first-child .article-media {
      grid-area: media;
      width: 100%;
      height: 100%;
      min-height: 360px;
      border-right: 1px solid var(--outline-variant);
      border-bottom: 0;
    }
    body[data-page="news.html"] .article-grid > .article-card.has-media:first-child .article-meta,
    body[data-page="election.html"] .article-grid > .article-card.has-media:first-child .article-meta {
      grid-area: meta;
      margin-top: 24px;
    }
    body[data-page="news.html"] .article-grid > .article-card.has-media:first-child h3,
    body[data-page="election.html"] .article-grid > .article-card.has-media:first-child h3 {
      grid-area: title;
      font-size: 1.42rem;
      line-height: 1.38;
    }
    body[data-page="news.html"] .article-grid > .article-card.has-media:first-child .badge-row,
    body[data-page="election.html"] .article-grid > .article-card.has-media:first-child .badge-row {
      grid-area: badges;
    }
    body[data-page="news.html"] .article-grid > .article-card.has-media:first-child .article-summary,
    body[data-page="election.html"] .article-grid > .article-card.has-media:first-child .article-summary {
      grid-area: summary;
      font-size: 1rem;
      -webkit-line-clamp: 4;
    }
    body[data-page="news.html"] .article-grid > .article-card.has-media:first-child .article-actions,
    body[data-page="election.html"] .article-grid > .article-card.has-media:first-child .article-actions {
      grid-area: actions;
    }
    body[data-page="news.html"] .article-grid > .article-card.has-media:first-child .article-feedback,
    body[data-page="election.html"] .article-grid > .article-card.has-media:first-child .article-feedback {
      grid-area: feedback;
    }
    body[data-page="index.html"] .home-briefing-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
      grid-template-areas: none;
      gap: 24px;
    }
    body[data-page="index.html"] .home-briefing-card.lead {
      grid-column: span 2;
      min-height: 380px;
      grid-template-columns: minmax(0, 1fr) minmax(300px, 0.52fr);
      align-items: end;
    }
    body[data-page="index.html"] .home-briefing-card.digest {
      grid-row: span 2;
    }
    body[data-page="index.html"] .home-briefing-card.support {
      grid-column: span 2;
    }
    body[data-page="index.html"] .home-briefing-card.footer {
      grid-column: 1 / -1;
    }
    body[data-page="index.html"] .civic-hero .home-briefing-grid {
      grid-template-columns: minmax(0, 1.15fr) minmax(360px, 0.85fr);
      grid-template-areas: "lead digest";
    }
    body[data-page="index.html"] .civic-hero .home-briefing-card.lead {
      grid-area: lead;
      grid-column: auto;
      grid-row: auto;
      align-items: end;
    }
    body[data-page="index.html"] .home-briefing-card.lead .home-illustration-slot {
      width: min(360px, 100%);
    }
    body[data-page="index.html"] .civic-hero .home-briefing-card.digest {
      grid-area: digest;
      grid-column: auto;
      grid-row: auto;
    }
    .youth-metrics-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .home-maker-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .filter-stack {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .news-filter-panel .filter-stack {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .news-filter-panel .filter-group.wide {
      grid-column: 1 / -1;
    }
  }
  @media (max-width: 720px) {
    .shell {
      padding-top: 18px;
      background: var(--surface-container-low);
    }
    .topbar {
      min-height: 68px;
      padding: 8px 14px;
      background: #ffffff;
      color: var(--text);
    }
    .topbar-side {
      gap: 8px;
    }
    .top-nav,
    .side-nav,
    .admin-entry {
      display: none;
    }
    .brand-logo {
      width: 38px;
    }
    .brand-title {
      font-size: 1.08rem;
    }
    .brand-sub,
    .header-side {
      display: none;
    }
    .article-media {
      height: 176px;
    }
    .article-card > :not(.article-media) {
      margin-left: 16px;
      margin-right: 16px;
    }
    .article-actions {
      margin: auto 16px 16px;
    }
    .article-card.no-media {
      padding: 18px;
    }
    .article-card.no-media > :not(.article-media) {
      margin-left: 0;
      margin-right: 0;
    }
    .article-card.no-media .article-actions {
      margin: auto 0 0;
    }
    .home-briefing-card {
      padding: 18px;
    }
    .home-briefing-title {
      font-size: clamp(1.9rem, 1.2rem + 8vw, 2.75rem);
    }
    .home-briefing-summary {
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }
    .home-briefing-summary span {
      padding: 10px 8px;
    }
    .home-briefing-summary strong {
      font-size: 1.04rem;
    }
    .home-briefing-summary em {
      font-size: 0.68rem;
    }
    .home-briefing-card > .home-illustration-slot {
      width: min(224px, 58vw);
      margin: 4px 0 -6px auto;
    }
  }
"""


DASHBOARD_TONE_CSS = """
  /* Youth policy dashboard tone: editorial data dashboard inspired by policy analytics tools. */
  :root {
    --page-bg: #f5f5f3;
    --app-bg: #f5f5f3;
    --panel: #ffffff;
    --panel-soft: #f3f1ed;
    --text: #181818;
    --muted: #6f6962;
    --line: #dedbd5;
    --accent: #006f63;
    --accent-soft: #e6f5f1;
    --accent-strong: #004f47;
    --surface: #ffffff;
    --surface-container-low: #f5f5f3;
    --surface-container-high: #efede9;
    --surface-container-highest: #e7e2da;
    --outline: #6f6962;
    --outline-variant: #dedbd5;
    --dashboard-dark: #183b36;
    --dashboard-dark-line: #0c2521;
    --dashboard-accent: #006f63;
    --filter-accent: #006f63;
    --filter-accent-strong: #004f47;
    --filter-active-bg: #006f63;
    --filter-active-border: #006f63;
    --filter-active-stroke: #004f47;
    --filter-active-soft: #d9f0ea;
    --success: #008a78;
    --danger: #c80000;
    --shadow: 0 16px 34px rgba(24, 24, 24, 0.08);
    --shadow-soft: 0 8px 20px rgba(24, 24, 24, 0.05);
  }
  body {
    background: var(--page-bg);
    color: var(--text);
    font-family: "Public Sans", "Noto Sans KR", sans-serif;
    font-size: 16px;
    line-height: 1.58;
  }
  .topbar {
    position: fixed;
    top: 0;
    right: 0;
    left: 260px;
    z-index: 60;
    height: 80px;
    min-height: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 22px;
    margin: 0;
    padding: 0 40px;
    border-bottom: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.96);
    color: var(--text);
    box-shadow: 0 1px 3px rgba(24, 24, 24, 0.04);
  }
  .top-nav {
    display: flex;
    align-items: stretch;
    justify-content: flex-start;
    gap: 18px;
    height: 100%;
    margin: 0;
    flex: 1 1 auto;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .top-nav::-webkit-scrollbar {
    display: none;
  }
  .top-nav-link {
    position: relative;
    display: inline-flex;
    align-items: center;
    height: 100%;
    padding: 0;
    border: 0;
    color: #736d66;
    background: transparent;
    font-size: 0.98rem;
    font-weight: 700;
    letter-spacing: 0;
    white-space: nowrap;
  }
  .top-nav-link:hover,
  .top-nav-link.active {
    color: var(--text);
    background: transparent;
  }
  .top-nav-link.active::after {
    content: "";
    position: absolute;
    right: 0;
    bottom: 0;
    left: 0;
    height: 2px;
    background: var(--accent);
  }
  .topbar-side {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 14px;
    width: min(720px, 100%);
    margin: 0 auto;
    min-width: 0;
  }
  .live-clock {
    color: var(--text);
    text-decoration: none;
  }
  .topbar-clock {
    display: none;
  }
  .global-search {
    display: flex;
    align-items: center;
    gap: 10px;
    width: clamp(180px, 18vw, 280px);
    height: 48px;
    padding: 0 18px;
    border: 1px solid transparent;
    border-radius: 999px;
    background: #f2f1ef;
    color: #756f68;
  }
  .global-search:focus-within {
    border-color: #cfc9c0;
    background: #ffffff;
  }
  .global-search-icon {
    display: inline-grid;
    place-items: center;
    width: 18px;
    height: 18px;
    color: #8c867e;
    font-size: 1.1rem;
    line-height: 1;
  }
  .global-search input {
    width: 100%;
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--text);
    font: inherit;
    font-size: 0.98rem;
  }
  .global-search input::placeholder {
    color: #686f7c;
  }
  .topbar-icon,
  .guide-link {
    display: inline-grid;
    place-items: center;
    flex: 0 0 auto;
    width: 36px;
    height: 36px;
    min-height: 36px;
    padding: 0;
    border: 0;
    border-radius: 999px;
    background: transparent;
    color: #373431;
    font: inherit;
    font-size: 1rem;
    font-weight: 900;
    cursor: pointer;
  }
  .guide-link {
    font-size: 0;
  }
  .guide-link::before {
    content: "?";
    font-size: 1rem;
  }
  .topbar-top-link {
    font-size: 1.05rem;
    line-height: 1;
  }
  .topbar-home-link {
    width: 32px;
    height: 32px;
    min-height: 32px;
  }
  .topbar-home-link svg {
    width: 18px;
    height: 18px;
    stroke: currentColor;
    stroke-width: 2.1;
    stroke-linecap: round;
    stroke-linejoin: round;
    fill: none;
  }
  .topbar-icon:hover,
  .guide-link:hover,
  .guide-link.active {
    background: #f0efed;
    color: var(--text);
  }
  .header-side {
    display: none;
  }
  .app-layout {
    min-height: 100vh;
    padding-top: 80px;
    background: var(--page-bg);
  }
  .shell {
    width: calc(100% - 260px);
    max-width: none;
    min-height: calc(100vh - 80px);
    margin: 0 0 0 260px;
    padding: 40px 40px 96px;
    border: 0;
    background: var(--page-bg);
    box-shadow: none;
  }
  .shell > .hero,
  .shell > .section,
  .shell > .page-intro-card,
  .shell > .news-intro-card,
  .shell > .footer-note,
  .shell > [data-news-filter-root],
  .shell > [data-policy-filter-root] {
    max-width: 1220px;
    margin-left: auto;
    margin-right: auto;
  }
  .side-nav {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 70;
    display: flex;
    width: 260px;
    padding: 28px 18px 96px;
    border-right: 1px solid var(--line);
    background: #fbfbfa;
    flex-direction: column;
    gap: 20px;
    overflow-y: auto;
  }
  .side-brand {
    display: grid;
    gap: 6px;
    padding: 0 12px 18px;
    color: var(--text);
  }
  .side-brand strong {
    font-size: 1.22rem;
    font-weight: 900;
    line-height: 1;
    letter-spacing: 0;
  }
  .side-brand span {
    color: #6d665f;
    font-size: 0.86rem;
    font-weight: 600;
  }
  .side-clock {
    display: grid;
    gap: 7px;
    margin: -10px 2px -4px;
    padding: 15px 16px;
    border: 1px solid rgba(65, 61, 56, 0.16);
    border-radius: 12px;
    background: #f5f3ef;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
  }
  .side-menu-section {
    display: grid;
    gap: 10px;
    padding: 2px 0 0;
  }
  .live-clock-kicker {
    color: #6d665f;
    font-size: 0.68rem;
    font-weight: 900;
    line-height: 1;
    letter-spacing: 0;
  }
  .live-clock-date {
    color: #4f4942;
    font-size: 0.86rem;
    font-weight: 800;
    line-height: 1;
    white-space: nowrap;
  }
  .live-clock-date-short {
    display: none;
  }
  .live-clock-time {
    color: #2f2c29;
    font-size: 1.58rem;
    font-weight: 900;
    line-height: 1;
    letter-spacing: 0;
    white-space: nowrap;
  }
  .side-nav-head {
    display: grid;
    gap: 6px;
    padding: 0 12px;
  }
  .side-nav-head strong {
    color: var(--text);
    font-size: 1.02rem;
    font-weight: 900;
    line-height: 1.25;
  }
  .side-nav-head span {
    color: #7a746d;
    font-size: 0.78rem;
    font-weight: 650;
    line-height: 1.55;
  }
  .side-nav-links {
    display: grid;
    gap: 6px;
  }
  .side-nav-link {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 14px;
    min-height: 60px;
    padding: 10px 18px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: #746d66;
    font: inherit;
    text-align: left;
    text-decoration: none;
  }
  .side-nav-link:hover,
  .side-nav-link.active {
    background: #f0efed;
    color: var(--text);
  }
  .side-nav-link.active {
    font-weight: 900;
  }
  .side-nav-link.primary-menu-link {
    min-height: 40px;
    padding: 6px 12px;
    border-radius: 10px;
  }
  .side-nav-link.primary-menu-link.active {
    background: #f0efed;
    color: #151515;
    box-shadow: inset 3px 0 0 var(--accent);
  }
  .side-nav-icon {
    position: relative;
    display: inline-grid;
    place-items: center;
    width: 30px;
    height: 30px;
    flex: 0 0 auto;
    color: currentColor;
  }
  .side-nav-icon svg {
    width: 24px;
    height: 24px;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
    fill: none;
  }
  .side-nav-link:hover .side-nav-icon,
  .side-nav-link.active .side-nav-icon {
    color: #0f0f0f;
  }
  .side-nav-text {
    display: grid;
    gap: 1px;
    min-width: 0;
  }
  .side-nav-text strong {
    font-size: 0.96rem;
    font-weight: 800;
    line-height: 1.2;
  }
  .side-nav-text small {
    color: #8a837a;
    font-size: 0.74rem;
    font-weight: 600;
  }
  .side-nav-section {
    display: grid;
    gap: 14px;
    padding: 20px 12px 4px;
    border-top: 1px solid #ebe8e2;
  }
  .side-nav-kicker {
    color: #8a837a;
    font-size: 0.74rem;
    font-weight: 900;
    letter-spacing: 0;
    text-transform: uppercase;
  }
  .side-marker-list {
    position: relative;
    display: grid;
    gap: 8px;
    padding-left: 0;
  }
  .side-marker-list::before {
    content: "";
    position: absolute;
    top: 18px;
    bottom: 18px;
    left: 8px;
    width: 1px;
    background: #dedbd5;
  }
  .side-marker-link {
    position: relative;
    display: grid;
    grid-template-columns: 18px minmax(0, 1fr);
    align-items: center;
    gap: 12px;
    min-height: 42px;
    padding: 5px 0;
    color: #746d66;
    font-size: 0.86rem;
    font-weight: 750;
  }
  .side-marker-dot {
    position: relative;
    z-index: 1;
    display: inline-block;
    width: 9px;
    height: 9px;
    margin-left: 4px;
    border: 1px solid #9b948b;
    border-radius: 999px;
    background: #fbfbfa;
  }
  .side-marker-label {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .side-marker-link:hover,
  .side-marker-link.active {
    color: var(--text);
  }
  .side-marker-link.active .side-marker-dot {
    width: 13px;
    height: 13px;
    margin-left: 2px;
    border-color: var(--accent);
    background: var(--accent);
    box-shadow: 0 0 0 4px var(--accent-soft);
  }
  .side-update-card {
    display: none;
    gap: 10px;
    margin-top: auto;
    padding: 20px;
    border: 1px solid #cbd8d4;
    border-radius: 8px;
    background: #f4f2ef;
    color: #5f5851;
  }
  .side-update-card strong {
    color: #2f2c29;
    font-size: 0.88rem;
  }
  .side-update-card span {
    color: #6d665f;
    font-size: 0.82rem;
    line-height: 1.7;
  }
  .side-nav-admin {
    display: grid;
    gap: 8px;
    padding-top: 18px;
    border-top: 1px solid #ebe8e2;
  }
  .side-utility-section {
    display: grid;
    gap: 8px;
    position: fixed;
    right: auto;
    bottom: 18px;
    left: 18px;
    z-index: 72;
    width: 224px;
    padding-top: 10px;
    border-top: 1px solid #ebe8e2;
    background: linear-gradient(180deg, rgba(251, 251, 250, 0.72), #fbfbfa 38%);
  }
  .side-admin-entry {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    min-height: 42px;
    padding: 10px 12px;
    border: 1px solid #ebe8e2;
    border-radius: 8px;
    background: #ffffff;
    color: #7a746d;
    font: inherit;
    font-size: 0.82rem;
    font-weight: 800;
    text-align: left;
    cursor: pointer;
  }
  .side-admin-entry em {
    color: #9a938a;
    font-size: 0.72rem;
    font-style: normal;
    font-weight: 800;
  }
  .side-admin-entry:hover,
  body.is-admin-authorized .side-admin-entry {
    border-color: #d7d0c5;
    background: #f6f4f0;
    color: var(--text);
  }
  .side-nav-link.pending {
    min-height: 42px;
    opacity: 0.68;
    cursor: not-allowed;
  }
  .side-nav-link.pending em {
    margin-left: auto;
    color: #9a938a;
    font-size: 0.72rem;
    font-style: normal;
    font-weight: 800;
  }
  .hero {
    gap: 24px;
    margin-bottom: 30px;
  }
  body[data-page="index.html"] .hero {
    display: block;
  }
  body[data-page="index.html"] .home-briefing-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 18px;
    min-height: auto;
    padding: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
    align-items: stretch;
  }
  body[data-page="index.html"] .home-briefing-card.lead {
    min-width: 0;
    min-height: 168px;
    padding: 28px 32px;
    border: 1px solid var(--dashboard-dark-line);
    border-radius: 8px;
    background: var(--dashboard-dark);
    box-shadow: none;
    display: grid;
    align-items: center;
    overflow: hidden;
  }
  body[data-page="index.html"] .home-briefing-card.lead .home-briefing-content {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas:
      "date actions"
      "title actions"
      "copy summary";
    gap: 10px 24px;
    max-width: none;
    align-items: center;
  }
  body[data-page="index.html"] .home-briefing-date,
  body[data-page="index.html"] .home-briefing-card.lead-arch .home-briefing-date {
    grid-area: date;
    display: inline-flex;
    width: fit-content;
    margin-bottom: 0;
    padding: 0 0 6px;
    border: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 0;
    background: transparent;
    color: rgba(255, 242, 222, 0.82);
    font-size: 0.82rem;
    font-weight: 800;
    letter-spacing: 0;
    text-transform: none;
  }
  body[data-page="index.html"] .home-briefing-title,
  body[data-page="index.html"] .home-briefing-card.lead-arch .home-briefing-title {
    grid-area: title;
    max-width: 100%;
    color: #ffffff;
    font-size: clamp(2.05rem, 3vw, 3.05rem);
    line-height: 1.08;
    letter-spacing: 0;
    text-shadow: 0 2px 0 #0c2521;
    word-break: keep-all;
    overflow-wrap: normal;
    text-wrap: auto;
  }
  body[data-page="index.html"] .home-briefing-copy,
  body[data-page="index.html"] .home-briefing-card.lead-arch .home-briefing-copy {
    grid-area: copy;
    max-width: 720px;
    color: rgba(255, 255, 255, 0.76);
    font-size: 1rem;
    line-height: 1.62;
    white-space: normal;
    word-break: keep-all;
    overflow-wrap: break-word;
  }
  body[data-page="index.html"] .home-briefing-summary {
    grid-area: summary;
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    min-width: 0;
    margin: 0;
  }
  body[data-page="index.html"] .home-briefing-summary span {
    min-width: 92px;
    padding: 8px 10px;
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 8px;
    background: rgba(255,255,255,0.08);
    color: #ffffff;
  }
  body[data-page="index.html"] .home-briefing-summary strong {
    color: #ffffff;
    font-size: 1.02rem;
    letter-spacing: 0;
  }
  body[data-page="index.html"] .home-briefing-summary em {
    color: rgba(255,255,255,0.68);
    font-size: 0.72rem;
  }
  body[data-page="index.html"] .home-briefing-card.lead .hero-actions {
    grid-area: actions;
    align-self: center;
    justify-self: end;
    margin: 0;
    padding: 0;
  }
  body[data-page="index.html"] .home-briefing-card > .home-illustration-slot {
    display: none;
  }
  .home-overview {
    display: grid;
    gap: 20px;
    padding: 28px 24px 24px;
    border: 1px solid #d2cec6;
    border-radius: 8px;
    background: #ffffff;
  }
  .home-overview-head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(320px, 0.9fr);
    gap: 18px;
    align-items: center;
  }
  .home-overview-kicker {
    display: inline-flex;
    width: fit-content;
    margin-bottom: 8px;
    padding: 6px 12px;
    border: 1px solid rgba(222, 119, 0, 0.35);
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent);
    font-size: 0.82rem;
    font-weight: 900;
  }
  .home-overview h2 {
    margin: 0;
    color: var(--text);
    font-size: clamp(1.7rem, 2.25vw, 2.42rem);
    line-height: 1.08;
  }
  .home-overview h3 {
    margin: 0;
    color: var(--text);
    font-size: 1.22rem;
    line-height: 1.25;
  }
  .home-overview p {
    margin: 8px 0 0;
    color: var(--muted);
  }
  .home-overview .home-glance-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .home-overview .home-glance-item {
    min-height: 86px;
    padding: 12px 10px;
  }
  .home-overview .home-glance-value {
    font-size: 1.28rem;
    letter-spacing: 0;
  }
  .home-overview-columns {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px;
    align-items: start;
  }
  .home-overview-column {
    display: grid;
    gap: 14px;
    min-width: 0;
    padding: 20px;
    border: 1px solid #dedbd5;
    border-radius: 8px;
    background: #fbfbfa;
  }
  .home-overview-column-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: start;
  }
  .home-overview-column-head span {
    display: block;
    margin-bottom: 4px;
    color: var(--accent);
    font-size: 0.82rem;
    font-weight: 900;
  }
  .home-overview-column .home-urgent-item {
    padding: 13px 0;
  }
  .home-overview-column .home-urgent-text strong {
    font-size: 0.98rem;
    line-height: 1.45;
  }
  .home-keyword-strip {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    min-width: 0;
    margin-top: -2px;
    padding: 0 2px 4px;
  }
  .home-keyword-strip .home-keyword-list {
    gap: 8px;
  }
  .home-keyword-strip .home-keyword-chip {
    min-height: 32px;
    padding: 6px 11px;
    border-radius: 999px;
    background: #edf8f5;
    box-shadow: none;
  }
  .home-application-panel {
    display: grid;
    gap: 18px;
    min-width: 0;
    padding: 24px;
    border: 1px solid #d2cec6;
    border-radius: 8px;
    background: #fbfefd;
  }
  .home-application-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }
  .home-application-head h2 {
    margin: 0;
    color: var(--text);
    font-size: clamp(1.45rem, 1.8vw, 2.02rem);
    line-height: 1.12;
    letter-spacing: 0;
  }
  .home-application-head-links {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 8px;
  }
  .home-application-head .mini-link {
    min-height: 38px;
    align-items: center;
    justify-content: center;
    gap: 7px;
    margin-top: 0;
    padding: 9px 14px;
    border: 1px solid rgba(0, 111, 99, 0.22);
    border-radius: 999px;
    background: #f5fbf8;
    color: #006f63;
    font-size: 0.82rem;
    font-weight: 900;
    line-height: 1;
    text-decoration: none;
  }
  .home-application-head .mini-link::after {
    content: "→";
    font-size: 0.9rem;
    line-height: 1;
  }
  .home-application-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
  }
  .home-application-card {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(150px, 0.34fr);
    gap: 18px;
    min-width: 0;
    padding: 18px;
    border: 1px solid #dedbd5;
    border-radius: 8px;
    background: #ffffff;
  }
  .home-application-card:first-child {
    grid-column: 1 / -1;
    padding: 20px;
    background: linear-gradient(135deg, #f3faf7 0%, #ffffff 48%, #f5fbf8 100%);
  }
  .home-application-main {
    display: grid;
    gap: 10px;
    min-width: 0;
  }
  .home-application-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .home-application-tags span {
    display: inline-flex;
    min-height: 26px;
    align-items: center;
    padding: 4px 9px;
    border: 1px solid #b8d9d2;
    border-radius: 999px;
    background: #edf8f5;
    color: #006f63;
    font-size: 0.74rem;
    font-weight: 900;
  }
  .home-application-card h4 {
    margin: 0;
    color: var(--text);
    font-size: 1.08rem;
    line-height: 1.42;
    word-break: keep-all;
    overflow-wrap: anywhere;
  }
  .home-application-card:first-child h4 {
    font-size: clamp(1.22rem, 1.8vw, 1.62rem);
    line-height: 1.34;
  }
  .home-application-card p {
    margin: 0;
    color: #5f5a54;
    font-size: 0.9rem;
    line-height: 1.6;
  }
  .home-application-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 12px;
    color: #786f66;
    font-size: 0.8rem;
    font-weight: 700;
  }
  .home-application-period {
    display: grid;
    align-content: space-between;
    gap: 12px;
    min-width: 0;
    padding-left: 18px;
    border-left: 1px solid #ebe8e2;
  }
  .home-application-period span {
    color: #7a746d;
    font-size: 0.78rem;
    font-weight: 900;
  }
  .home-application-period strong {
    color: #006f63;
    font-size: 1.06rem;
    line-height: 1.35;
    word-break: keep-all;
    overflow-wrap: anywhere;
  }
  .home-application-link {
    display: inline-flex;
    min-height: 42px;
    align-items: center;
    justify-content: center;
    padding: 0 14px;
    border: 1px solid #006f63;
    border-radius: 8px;
    background: #006f63;
    color: #ffffff;
    font-size: 0.86rem;
    font-weight: 900;
    text-align: center;
  }
  .home-application-empty {
    display: grid;
    gap: 6px;
    padding: 20px;
    border: 1px dashed #d2cec6;
    border-radius: 8px;
    background: #fbfbfa;
  }
  .home-application-empty strong {
    color: var(--text);
    font-size: 1rem;
  }
  .home-application-empty span {
    color: #6f6962;
    line-height: 1.55;
  }
  .hero-actions {
    gap: 12px;
  }
  .button {
    min-height: 50px;
    padding: 0 24px;
    border-radius: 8px;
    border-color: #beb9b1;
    background: #ffffff;
    color: var(--text);
    font-weight: 900;
    box-shadow: none;
  }
  .button.primary,
  .meta-pill.primary {
    border-color: var(--dashboard-accent);
    background: var(--dashboard-accent);
    color: #ffffff;
  }
  .filter-button.active {
    border-color: var(--filter-active-border);
    background: var(--filter-active-bg);
    color: #ffffff;
  }
  body[data-page="index.html"] .home-briefing-card.lead .button {
    border-color: rgba(255,255,255,0.24);
    background: transparent;
    color: #ffffff;
  }
  body[data-page="index.html"] .home-briefing-card.lead .button.primary {
    border-color: var(--dashboard-accent);
    background: var(--dashboard-accent);
  }
  .hero-card,
  .status-card,
  .section-card,
  .article-card,
  .info-card,
  .list-card,
  .menu-update-card,
  .filter-panel,
  .news-intro-card,
  .page-intro-card,
  .home-briefing-card,
  .home-section-card,
  .youth-metrics-card {
    border: 1px solid #d2cec6;
    border-radius: 8px;
    background: #ffffff;
    box-shadow: none;
  }
  .section {
    margin-top: 32px;
  }
  .section-head {
    align-items: end;
    margin-bottom: 18px;
    padding: 0;
    border: 0;
  }
  .section-head h2,
  .youth-metrics-head h2,
  .home-section-head h2,
  .page-intro-title {
    color: var(--text);
    font-size: 1.6rem;
    font-weight: 900;
    line-height: 1.25;
    letter-spacing: 0;
  }
  .section-head p,
  .youth-metrics-head p,
  .page-intro-copy,
  .hero-copy,
  .section-card p,
  .info-card p,
  .list-card p,
  .filter-head p {
    color: #5f5a54;
  }
  .page-intro-card,
  .news-intro-card {
    padding: 32px;
  }
  .page-intro-badge,
  .eyebrow {
    border-radius: 999px;
    background: #d9f0ea;
    color: #006f63;
    font-size: 0.78rem;
    letter-spacing: 0;
    text-transform: uppercase;
  }
  .youth-metrics-card {
    display: block;
    padding: 0;
    border: 0;
    background: transparent;
  }
  .youth-metrics-head {
    display: grid;
    gap: 6px;
    margin-bottom: 18px;
    padding: 0;
    border: 0;
  }
  .youth-metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 30px;
  }
  .youth-metric-item {
    min-height: 218px;
    padding: 30px;
    border: 1px solid #d2cec6;
    border-radius: 8px;
    background: #ffffff;
    box-shadow: none;
  }
  .youth-metric-label {
    color: #2c2926;
    font-size: 0.96rem;
    font-weight: 800;
  }
  .youth-metric-value {
    margin-top: 8px;
    color: var(--text);
    font-size: clamp(1.7rem, 2.3vw, 2.2rem);
    font-weight: 900;
    letter-spacing: 0;
  }
  .youth-metric-meta {
    margin-top: 20px;
    padding-top: 20px;
    border-top: 1px solid #ebe8e2;
    color: #3f3a35;
  }
  .youth-metric-source {
    color: #006f63;
    font-weight: 800;
  }
  .youth-metrics-note {
    color: #716b64;
  }
  .article-grid,
  .feature-grid {
    gap: 30px;
  }
  .local-menu-nav {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
  }
  .local-menu-card {
    display: grid;
    gap: 10px;
    min-height: 150px;
    padding: 22px;
    border: 1px solid #d2cec6;
    border-radius: 8px;
    background: #ffffff;
    color: inherit;
    text-decoration: none;
    transition: border-color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
  }
  .local-menu-card:hover {
    border-color: #bcb6ac;
    box-shadow: 0 12px 24px rgba(24, 24, 24, 0.06);
    transform: translateY(-1px);
  }
  .local-menu-card span {
    color: #006f63;
    font-size: 0.78rem;
    font-weight: 900;
  }
  .local-menu-card strong {
    color: var(--text);
    font-size: 1.18rem;
    line-height: 1.28;
  }
  .local-menu-card small {
    color: #5f5a54;
    font-size: 0.9rem;
    line-height: 1.55;
  }
  .local-plan-board {
    display: flex;
    justify-content: center;
  }
  .local-map-panel {
    width: min(100%, 760px);
    padding: 26px;
    border: 1px solid #d2cec6;
    border-radius: 8px;
    background:
      radial-gradient(circle at 60% 18%, rgba(0, 111, 99, 0.08), transparent 34%),
      linear-gradient(180deg, #fbfefd 0%, #f4f7f5 100%);
  }
  .local-map-canvas {
    position: relative;
    margin: 0 auto;
    overflow: visible;
    border-radius: 8px;
    background: #f1f5f2;
  }
  .local-map-canvas::before {
    content: none;
  }
  .local-map-canvas::after {
    content: none;
  }
  .local-map-region {
    color: #006f63;
    text-decoration: none;
  }
  .local-map-region:focus-visible {
    outline: 0;
  }
  .local-map-stage {
    position: relative;
    width: min(100%, 540px);
    margin: 0 auto;
    aspect-ratio: 860 / 1059.63;
  }
  .local-map-svg {
    display: block;
    width: 100%;
    height: 100%;
  }
  .local-map-path {
    fill: #f3faf7;
    stroke: rgba(0, 111, 99, 0.68);
    stroke-width: 2.2;
    stroke-linejoin: round;
    vector-effect: non-scaling-stroke;
    transition: fill 0.16s ease, stroke 0.16s ease, stroke-width 0.16s ease, filter 0.16s ease;
  }
  .local-map-path.status-confirmed {
    fill: #d9f0ea;
  }
  .local-map-path.status-candidate {
    fill: #bfe3dc;
  }
  .local-map-path.status-missing {
    fill: #f1f5f2;
  }
  .local-map-hit-target {
    fill: rgba(0, 0, 0, 0);
    stroke: transparent;
    pointer-events: all;
  }
  .local-map-region:hover .local-map-path,
  .local-map-region:focus-visible .local-map-path {
    fill: #006f63;
    stroke: #004c45;
    stroke-width: 2.8;
    filter: drop-shadow(0 8px 14px rgba(24, 24, 24, 0.16));
  }
  .local-map-region:hover,
  .local-map-region:focus-visible {
    color: #ffffff;
  }
  .local-map-source {
    margin: 12px 0 0;
    color: #6b655e;
    font-size: 0.78rem;
    line-height: 1.5;
    text-align: center;
  }
  .local-map-label-layer {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }
  .local-map-marker {
    position: absolute;
    z-index: 4;
    transform: translate(-50%, -50%);
    pointer-events: auto;
  }
  .local-map-label {
    display: inline-flex;
    min-width: 38px;
    min-height: 26px;
    align-items: center;
    justify-content: center;
    padding: 4px 8px;
    border: 1px solid rgba(0, 111, 99, 0.28);
    border-radius: 999px;
    background: rgba(255, 254, 251, 0.92);
    color: #004c45;
    font-size: 0.78rem;
    font-weight: 900;
    box-shadow: 0 8px 18px rgba(24, 24, 24, 0.08);
    cursor: default;
  }
  .local-map-popover {
    position: absolute;
    left: 50%;
    bottom: calc(100% + 9px);
    display: grid;
    min-width: 210px;
    gap: 9px;
    padding: 12px;
    border: 1px solid #d2cec6;
    border-radius: 8px;
    background: #ffffff;
    color: var(--text);
    box-shadow: 0 18px 36px rgba(24, 24, 24, 0.15);
    opacity: 0;
    pointer-events: none;
    transform: translate(-50%, 6px);
    transition: opacity 0.14s ease, transform 0.14s ease;
  }
  .local-map-popover::after {
    content: "";
    position: absolute;
    left: 50%;
    bottom: -7px;
    width: 12px;
    height: 12px;
    border-right: 1px solid #d2cec6;
    border-bottom: 1px solid #d2cec6;
    background: #ffffff;
    transform: translateX(-50%) rotate(45deg);
  }
  .local-map-popover strong {
    color: #2c2926;
    font-size: 0.9rem;
    line-height: 1.3;
  }
  .local-map-popover-count {
    color: #6b655e;
    font-size: 0.78rem;
    font-weight: 800;
  }
  .local-map-popover a {
    position: relative;
    z-index: 1;
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    min-height: 30px;
    padding: 6px 9px;
    border-radius: 6px;
    background: #e6f2ef;
    color: #006f63;
    font-size: 0.82rem;
    font-weight: 900;
  }
  .local-map-popover a::after {
    content: "↗";
    font-size: 0.74rem;
  }
  .local-map-popover-empty {
    color: #6b655e;
    font-size: 0.82rem;
    font-weight: 800;
  }
  .local-map-marker:hover,
  .local-map-marker:focus-within {
    z-index: 20;
  }
  .local-map-marker:hover .local-map-label,
  .local-map-marker:focus-within .local-map-label {
    background: #006f63;
    color: #ffffff;
  }
  .local-map-marker:hover .local-map-popover,
  .local-map-marker:focus-within .local-map-popover {
    opacity: 1;
    pointer-events: auto;
    transform: translate(-50%, 0);
  }
  .local-plan-status {
    background: #e6f2ef !important;
    color: #006f63 !important;
  }
  .local-plan-grid {
    display: grid;
    gap: 14px;
  }
  .local-plan-card {
    display: grid;
    gap: 12px;
    padding: 20px;
    border: 1px solid #d2cec6;
    border-radius: 8px;
    background: #ffffff;
  }
  .local-plan-card h3 {
    margin: 0;
    color: var(--text);
    font-size: 1.08rem;
    letter-spacing: 0;
  }
  .local-plan-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .local-plan-meta span {
    display: inline-flex;
    min-height: 26px;
    align-items: center;
    padding: 4px 9px;
    border-radius: 999px;
    background: #d9f0ea;
    color: #006f63;
    font-size: 0.74rem;
    font-weight: 900;
  }
  .local-plan-card p {
    margin: 0;
    color: #5f5a54;
    line-height: 1.62;
  }
  .local-plan-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .article-card,
  .section-card,
  .info-card,
  .list-card,
  .menu-update-card {
    border-radius: 8px;
  }
  .article-card:hover,
  .section-card:hover {
    border-color: #bcb6ac;
    box-shadow: 0 12px 24px rgba(24, 24, 24, 0.06);
    transform: translateY(-1px);
  }
  .article-card h3,
  .section-card h3,
  .info-card h3,
  .list-card h3 {
    color: var(--text);
    letter-spacing: 0;
  }
  .filter-panel {
    padding: 24px;
  }
  .filter-button,
  .date-input-wrap,
  .filter-search-input,
  .action-button,
  .badge,
  .meta-pill.subtle,
  .list-item,
  .home-glance-item,
  .home-keyword-panel,
  .home-urgent-link {
    border-radius: 8px;
    border-color: #dedbd5;
    background: #ffffff;
    box-shadow: none;
  }
  .mini-link,
  .action-button,
  .youth-metric-source {
    color: #006f63;
  }
  .footer-note {
    color: #77716a;
  }
  .site-footer {
    display: block;
    margin: 56px -40px -96px;
    padding: 0;
    border: 0;
    background: #183b36;
    color: #f7f6f2;
  }
  .site-footer a {
    color: inherit;
    text-decoration: none;
  }
  .site-footer-top {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(220px, 300px);
    align-items: stretch;
    border-bottom: 1px solid rgba(255, 255, 255, 0.18);
  }
  .site-footer-links {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0;
    min-height: 64px;
    padding: 0 36px;
  }
  .site-footer-links a {
    display: inline-flex;
    min-height: 44px;
    align-items: center;
    padding: 0 18px 0 0;
    margin-right: 28px;
    color: rgba(255, 255, 255, 0.92);
    font-size: 0.95rem;
    font-weight: 900;
    white-space: nowrap;
  }
  .site-footer-links a:hover {
    color: #9bd8cc;
  }
  .site-footer-related {
    position: relative;
    border-left: 1px solid rgba(255, 255, 255, 0.18);
  }
  .site-footer-related summary {
    display: flex;
    min-height: 64px;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    padding: 0 36px;
    color: rgba(255, 255, 255, 0.92);
    font-size: 0.95rem;
    font-weight: 900;
    cursor: pointer;
    list-style: none;
  }
  .site-footer-related summary::-webkit-details-marker {
    display: none;
  }
  .site-footer-related summary::after {
    content: "⌄";
    font-size: 1.35rem;
    line-height: 1;
  }
  .site-footer-related[open] summary::after {
    transform: rotate(180deg);
  }
  .site-footer-related-list {
    position: absolute;
    right: 18px;
    bottom: calc(100% + 10px);
    z-index: 4;
    display: grid;
    min-width: 240px;
    padding: 10px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 8px;
    background: #102d28;
    box-shadow: 0 18px 40px rgba(0, 0, 0, 0.24);
  }
  .site-footer-related-list a {
    display: flex;
    align-items: center;
    min-height: 38px;
    padding: 8px 10px;
    border-radius: 6px;
    color: rgba(255, 255, 255, 0.86);
    font-size: 0.86rem;
    font-weight: 800;
  }
  .site-footer-related-list a:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #9bd8cc;
  }
  .site-footer-body {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    align-items: start;
    gap: 36px;
    padding: 44px 40px 46px;
  }
  .site-footer-body.has-brand-image {
    grid-template-columns: minmax(360px, 0.46fr) minmax(360px, 1fr);
    align-items: center;
  }
  .site-footer-brand {
    display: grid;
    align-content: start;
    gap: 10px;
    min-width: 0;
  }
  .site-footer-brand strong {
    color: #ffffff;
    font-size: 1.42rem;
    font-weight: 900;
    line-height: 1.08;
    letter-spacing: 0;
  }
  .site-footer-brand span {
    color: #9bd8cc;
    font-size: 0.86rem;
    font-weight: 900;
    letter-spacing: 0.08em;
  }
  .site-footer-brand small {
    color: rgba(255, 255, 255, 0.64);
    font-size: 0.86rem;
    font-weight: 800;
  }
  .site-footer-brand-image {
    display: grid;
    align-items: center;
    min-width: 0;
  }
  .site-footer-brand-image-frame {
    display: grid;
    min-height: 0;
    align-items: center;
    width: fit-content;
    max-width: 100%;
    padding: 0;
    border-radius: 18px;
    overflow: hidden;
    background: #ffffff;
    box-shadow: 0 18px 34px rgba(0, 0, 0, 0.16);
  }
  .site-footer-brand-image img {
    display: block;
    width: min(100%, 500px);
    height: auto;
    justify-self: start;
    border-radius: inherit;
  }
  .site-footer-site-head {
    display: grid;
    gap: 6px;
    margin-bottom: 6px;
  }
  .site-footer-site-head strong {
    color: #ffffff;
    font-size: 1.36rem;
    font-weight: 900;
    line-height: 1.12;
    letter-spacing: 0;
  }
  .site-footer-site-head span {
    color: #9bd8cc;
    font-size: 0.82rem;
    font-weight: 900;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .site-footer-info {
    display: grid;
    gap: 12px;
    min-width: 0;
    color: rgba(255, 255, 255, 0.78);
    font-size: 0.93rem;
    line-height: 1.7;
  }
  .site-footer-info p {
    margin: 0;
  }
  .site-footer-info strong {
    color: #ffffff;
    font-weight: 900;
  }
  .site-footer-info-list {
    display: grid;
    gap: 8px;
  }
  .site-footer-info-list p {
    display: grid;
    grid-template-columns: 84px minmax(0, 1fr);
    gap: 10px;
    align-items: start;
  }
  .site-footer-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
    margin-top: 8px;
    color: rgba(255, 255, 255, 0.64);
    font-size: 0.84rem;
  }
  .site-footer-meta a {
    color: #9bd8cc;
    font-weight: 900;
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .bottom-nav {
    background: #ffffff;
  }
  @media (max-width: 1180px) {
    .topbar {
      left: 232px;
      padding: 0 24px;
      gap: 18px;
    }
    .side-nav {
      width: 232px;
      padding-bottom: 96px;
    }
    .side-utility-section {
      width: 196px;
    }
    .shell {
      width: calc(100% - 232px);
      margin-left: 232px;
      padding: 32px 24px 90px;
    }
    .site-footer {
      margin: 52px -24px -90px;
    }
    .site-footer-top {
      grid-template-columns: 1fr;
    }
    .site-footer-body {
      grid-template-columns: minmax(0, 1fr);
    }
    .site-footer-body.has-brand-image {
      grid-template-columns: minmax(300px, 0.42fr) minmax(0, 1fr);
    }
    .site-footer-related {
      border-top: 1px solid rgba(255, 255, 255, 0.18);
      border-left: 0;
    }
    .global-search {
      display: flex;
      width: clamp(220px, 36vw, 360px);
    }
    .top-nav {
      gap: 14px;
    }
    .top-nav-link {
      font-size: 0.92rem;
    }
    body[data-page="index.html"] .home-briefing-grid {
      grid-template-columns: 1fr;
      padding: 0;
    }
    body[data-page="index.html"] .home-briefing-card.lead .home-briefing-content {
      grid-template-columns: 1fr;
      grid-template-areas:
        "date"
        "title"
        "copy"
        "summary"
        "actions";
    }
    body[data-page="index.html"] .home-briefing-card.lead .hero-actions,
    body[data-page="index.html"] .home-briefing-summary {
      justify-self: start;
      justify-content: flex-start;
    }
    .home-overview-head,
    .home-overview-columns {
      grid-template-columns: 1fr;
    }
    .youth-metrics-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  @media (max-width: 900px) {
    .topbar {
      left: 0;
      height: 70px;
      min-height: 70px;
      padding: 0 16px;
      gap: 14px;
    }
    .topbar-side {
      width: 100%;
      margin: 0;
      justify-content: center;
      gap: 8px;
    }
    .topbar-home-link {
      width: 30px;
      height: 30px;
      min-height: 30px;
    }
    .topbar-home-link svg {
      width: 16px;
      height: 16px;
    }
    .topbar-clock {
      display: inline-grid;
      place-items: center;
      flex: 0 0 auto;
      width: 74px;
      min-height: 42px;
      padding: 6px 8px;
      border: 1px solid rgba(65, 61, 56, 0.14);
      border-radius: 999px;
      background: #f2f1ef;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.86);
    }
    .topbar-clock .live-clock-kicker,
    .topbar-clock .live-clock-date {
      display: none;
    }
    .topbar-clock .live-clock-date-short {
      display: block;
      color: #6d665f;
      font-size: 0.66rem;
      font-weight: 900;
      line-height: 1;
      white-space: nowrap;
    }
    .topbar-clock .live-clock-time {
      color: #373431;
      font-size: 0.9rem;
      font-weight: 900;
      line-height: 1.05;
    }
    .top-nav,
    .global-search,
    .side-nav {
      display: none;
    }
    .app-layout {
      padding-top: 70px;
    }
    .shell {
      width: 100%;
      max-width: 100%;
      margin-left: 0;
      padding: 22px 16px 96px;
      overflow-x: hidden;
    }
    .site-footer {
      margin: 42px -16px -96px;
    }
    .site-footer-links {
      align-items: flex-start;
      flex-direction: column;
      min-height: auto;
      padding: 16px 22px;
    }
    .site-footer-links a {
      min-height: 34px;
      margin-right: 0;
      padding-right: 0;
      font-size: 0.9rem;
    }
    .site-footer-related summary {
      min-height: 54px;
      padding: 0 22px;
      font-size: 0.9rem;
    }
    .site-footer-related-list {
      position: static;
      min-width: 0;
      margin: 0 16px 16px;
      box-shadow: none;
    }
    .site-footer-body {
      grid-template-columns: 1fr;
      gap: 22px;
      padding: 32px 22px 118px;
    }
    .site-footer-body.has-brand-image {
      grid-template-columns: 1fr;
    }
    .site-footer-brand-image img {
      width: min(100%, 360px);
    }
    .site-footer-brand-image-frame {
      border-radius: 14px;
    }
    .site-footer-brand strong {
      font-size: 1.24rem;
    }
    .site-footer-site-head strong {
      font-size: 1.22rem;
    }
    .site-footer-info-list p {
      grid-template-columns: 1fr;
      gap: 2px;
    }
    .site-footer-info {
      font-size: 0.88rem;
    }
    body[data-page="index.html"] .home-briefing-grid {
      width: 100%;
      max-width: 100%;
      min-height: auto;
      padding: 0;
      border-radius: 0;
    }
    body[data-page="index.html"] .home-briefing-card,
    body[data-page="index.html"] .home-briefing-content {
      width: 100%;
      max-width: 100%;
      min-width: 0;
    }
    body[data-page="index.html"] .home-briefing-title,
    body[data-page="index.html"] .home-briefing-card.lead-arch .home-briefing-title {
      max-width: 100%;
      font-size: clamp(2.1rem, 8.6vw, 2.75rem);
      line-height: 1.16;
      overflow-wrap: anywhere;
      text-wrap: balance;
    }
    body[data-page="index.html"] .home-briefing-copy,
    body[data-page="index.html"] .home-briefing-card.lead-arch .home-briefing-copy {
      width: 100%;
      font-size: 1rem;
      max-width: 100%;
      word-break: break-all;
      line-break: anywhere;
      overflow-wrap: anywhere;
    }
    body[data-page="index.html"] .home-briefing-card.lead {
      min-height: auto;
      padding: 24px 22px;
    }
    body[data-page="index.html"] .home-briefing-summary {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      width: 100%;
    }
    body[data-page="index.html"] .home-briefing-summary span {
      min-width: 0;
    }
    .home-overview {
      padding: 18px;
    }
    .home-overview .home-glance-grid {
      grid-template-columns: 1fr;
    }
    .home-overview-column {
      padding: 18px;
    }
    .home-overview-column-head {
      align-items: start;
      flex-direction: column;
    }
    .home-application-panel {
      padding: 18px;
    }
    .home-application-head {
      align-items: start;
      flex-direction: column;
    }
    .home-application-head-links {
      justify-content: flex-start;
    }
    .home-application-grid {
      grid-template-columns: 1fr;
    }
    .home-application-card,
    .home-application-card:first-child {
      grid-column: auto;
      grid-template-columns: 1fr;
      padding: 18px;
    }
    .home-application-period {
      padding: 14px 0 0;
      border-top: 1px solid #ebe8e2;
      border-left: 0;
    }
    .youth-metrics-grid,
    .article-grid,
    .feature-grid {
      grid-template-columns: 1fr;
      gap: 16px;
    }
    .youth-metric-item {
      min-height: 170px;
      padding: 22px;
    }
    .bottom-nav {
      display: grid;
    }
  }
  body[data-page="index.html"] .home-briefing-grid {
    grid-template-columns: 1fr !important;
    grid-template-areas: none !important;
    grid-auto-flow: row;
    gap: 18px;
    min-height: auto;
    padding: 0;
    border: 0;
    background: transparent;
  }
  body[data-page="index.html"] .home-briefing-card.lead {
    grid-area: auto !important;
    min-height: 172px;
    width: 100%;
    padding: 26px 34px 28px;
    grid-template-columns: 1fr !important;
    justify-items: center;
  }
  body[data-page="index.html"] .home-briefing-card.lead-arch.has-media {
    padding-right: 34px !important;
  }
  body[data-page="index.html"] .home-briefing-card.lead .home-illustration-slot {
    display: none !important;
  }
  body[data-page="index.html"] .home-overview {
    grid-area: auto !important;
    width: 100%;
  }
  body[data-page="index.html"] .home-briefing-card.lead .home-briefing-content {
    width: 100%;
    min-height: 100%;
    max-width: none;
    display: grid !important;
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      "date"
      "title"
      "copy";
    gap: 18px;
    place-items: center;
    align-content: center;
    justify-content: center;
    text-align: center;
  }
  body[data-page="index.html"] .home-briefing-date,
  body[data-page="index.html"] .home-briefing-card.lead-arch .home-briefing-date {
    align-self: center;
    justify-self: center;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 9px;
    min-height: auto;
    width: fit-content;
    max-width: 100%;
    padding: 0 0 7px;
    border: 0;
    border-bottom: 1px solid rgba(255, 238, 213, 0.22);
    border-radius: 0;
    background: transparent;
    box-shadow: none;
    color: rgba(255, 239, 214, 0.84);
    font-size: clamp(0.82rem, 0.72vw, 0.94rem);
    line-height: 1.2;
  }
  body[data-page="index.html"] .home-briefing-date-label {
    display: inline-flex;
    align-items: center;
    color: rgba(255, 208, 138, 0.86);
    font-size: 0.78rem;
    font-weight: 800;
    white-space: nowrap;
  }
  body[data-page="index.html"] .home-briefing-date-day {
    display: inline-flex;
    align-items: center;
    white-space: nowrap;
  }
  body[data-page="index.html"] .home-briefing-date-time {
    display: inline-flex;
    align-items: center;
    color: rgba(255, 239, 214, 0.9);
    font-size: inherit;
    font-weight: 800;
    white-space: nowrap;
  }
  body[data-page="index.html"] .home-briefing-title,
  body[data-page="index.html"] .home-briefing-card.lead-arch .home-briefing-title {
    align-self: center;
    justify-self: center;
    max-width: none;
    font-size: clamp(2.3rem, 3.4vw, 3.85rem);
    line-height: 0.96;
    white-space: nowrap;
    word-break: keep-all;
    overflow-wrap: break-word;
  }
  body[data-page="index.html"] .home-briefing-copy,
  body[data-page="index.html"] .home-briefing-card.lead-arch .home-briefing-copy {
    justify-self: center;
    align-self: center;
    max-width: 760px;
    color: rgba(238, 241, 236, 0.78);
    font-size: clamp(0.98rem, 1.03vw, 1.12rem);
    line-height: 1.6;
  }
  body[data-page="index.html"] .home-briefing-summary {
    display: none !important;
  }
  body[data-page="index.html"] .home-briefing-card.lead .hero-actions {
    display: none !important;
  }
  body[data-page="index.html"] .home-briefing-card.lead .button {
    min-height: 44px;
    padding: 0 18px;
  }
  @media (max-width: 1180px) {
    body[data-page="index.html"] .home-briefing-card.lead {
      min-height: auto;
    }
    body[data-page="index.html"] .home-briefing-card.lead .home-briefing-content {
      grid-template-columns: 1fr;
      grid-template-areas:
        "date"
        "title"
        "copy";
      gap: 14px;
      place-items: center;
      align-content: center;
      text-align: center;
    }
    body[data-page="index.html"] .home-briefing-summary,
    body[data-page="index.html"] .home-briefing-card.lead .hero-actions {
      justify-self: start;
      justify-content: flex-start;
    }
    body[data-page="index.html"] .home-briefing-title,
    body[data-page="index.html"] .home-briefing-card.lead-arch .home-briefing-title {
      font-size: clamp(2rem, 6.8vw, 2.85rem);
      white-space: normal;
    }
    body[data-page="index.html"] .home-briefing-copy,
    body[data-page="index.html"] .home-briefing-card.lead-arch .home-briefing-copy {
      justify-self: center;
      max-width: 780px;
    }
    .home-overview-head,
    .home-overview-columns {
      grid-template-columns: 1fr;
    }
  }
  @media (max-width: 900px) {
    body[data-page="index.html"] .home-briefing-card.lead {
      padding: 24px 22px 26px;
    }
    body[data-page="index.html"] .home-briefing-card.lead-arch.has-media {
      padding-right: 22px !important;
    }
    body[data-page="index.html"] .home-briefing-date,
    body[data-page="index.html"] .home-briefing-card.lead-arch .home-briefing-date {
      flex-wrap: wrap;
      justify-content: center;
      gap: 8px 12px;
      min-height: auto;
      padding: 0 0 7px;
      border-radius: 0;
      font-size: 0.8rem;
    }
    body[data-page="index.html"] .home-briefing-date-time {
      font-size: inherit;
    }
    body[data-page="index.html"] .home-briefing-copy,
    body[data-page="index.html"] .home-briefing-card.lead-arch .home-briefing-copy {
      font-size: 0.96rem;
      line-height: 1.62;
    }
    body[data-page="index.html"] .home-briefing-summary {
      width: 100%;
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .home-overview .home-glance-grid {
      grid-template-columns: 1fr;
    }
  }
  body:not([data-page="index.html"]) .page-intro-card,
  body:not([data-page="index.html"]) .news-intro-card,
  body:not([data-page="index.html"]) .hero-card {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 20px;
    align-items: center;
    min-height: auto;
    padding: 24px 28px;
    border-radius: 8px;
  }
  body:not([data-page="index.html"]) .page-intro-card.has-media {
    grid-template-columns: minmax(0, 1fr) 112px;
  }
  body:not([data-page="index.html"]) .page-intro-content {
    gap: 10px;
  }
  body:not([data-page="index.html"]) .page-intro-badge,
  body:not([data-page="index.html"]) .eyebrow {
    min-height: 32px;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 0.8rem;
  }
  body:not([data-page="index.html"]) .page-intro-title,
  body:not([data-page="index.html"]) .hero-card h1 {
    max-width: 980px;
    font-size: clamp(1.7rem, 2.2vw, 2.28rem);
    line-height: 1.16;
  }
  body:not([data-page="index.html"]) .page-intro-copy,
  body:not([data-page="index.html"]) .hero-copy {
    max-width: 980px;
    font-size: 1rem;
    line-height: 1.62;
  }
  body:not([data-page="index.html"]) .page-intro-media {
    width: 112px;
    margin: 0;
  }
  body:not([data-page="index.html"]) .hero {
    gap: 16px;
    margin-bottom: 22px;
  }
  body:not([data-page="index.html"]) .section {
    margin-top: 24px;
  }
  body:not([data-page="index.html"]) .section#filters {
    margin-top: 18px;
    scroll-margin-top: 96px;
  }
  body:not([data-page="index.html"]) .section#main-list {
    margin-top: 24px;
  }
  body:not([data-page="index.html"]) .filter-panel {
    padding: 22px 24px;
  }
  body:not([data-page="index.html"]) .filter-head {
    margin-bottom: 18px;
  }
  body:not([data-page="index.html"]) .filter-head h3 {
    font-size: 1.08rem;
  }
  body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    margin-bottom: 0;
    padding-bottom: 16px;
    border-bottom: 1px solid #ebe8e2;
  }
  body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-head .filter-status {
    display: inline-flex;
    min-height: 30px;
    align-items: center;
    padding: 0 11px;
    border: 1px solid #dedbd5;
    border-radius: 999px;
    background: #f4f7f5;
    color: #5f5a54;
    font-size: 0.8rem;
    font-weight: 800;
    white-space: nowrap;
  }
  body:not([data-page="index.html"]) .filter-head p {
    max-width: 760px;
    font-size: 0.9rem;
  }
  body:not([data-page="index.html"]) .filter-stack {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    gap: 20px 18px;
    align-items: start;
  }
  body:not([data-page="index.html"]) .filter-group {
    gap: 10px;
    min-width: 0;
  }
  body:not([data-page="index.html"]) .filter-group.wide,
  body:not([data-page="index.html"]) .filter-group-group,
  body:not([data-page="index.html"]) .filter-group-region,
  body:not([data-page="index.html"]) .filter-group-topic,
  body:not([data-page="index.html"]) .filter-group-scope,
  body:not([data-page="index.html"]) .filter-group-type {
    grid-column: 1 / -1;
  }
  body:not([data-page="index.html"]) .filter-group-search {
    grid-column: 1 / span 6;
  }
  body:not([data-page="index.html"]) .filter-group-date {
    grid-column: 7 / span 6;
  }
  body:not([data-page="index.html"]) .filter-button {
    min-height: 42px;
    padding: 0 14px;
    font-size: 0.82rem;
    line-height: 1.1;
  }
  body:not([data-page="index.html"]) .filter-search-input {
    min-height: 58px;
    padding: 0 18px;
  }
  body:not([data-page="index.html"]) .date-picker-row {
    grid-template-columns: minmax(112px, 140px) minmax(0, 1fr);
    gap: 14px;
    align-items: stretch;
  }
  body:not([data-page="index.html"]) .date-picker-row > .filter-button {
    width: 100%;
    min-height: 58px;
  }
  body:not([data-page="index.html"]) .date-range-fields {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
  }
  body:not([data-page="index.html"]) .date-input-wrap {
    min-width: 0;
    min-height: 58px;
    padding: 10px 16px;
  }
  body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-stack-map {
    grid-template-columns: minmax(244px, 332px) minmax(0, 1fr);
    gap: 0 24px;
    align-items: stretch;
  }
  body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-map-column,
  body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-control-column {
    display: grid;
    min-width: 0;
    align-content: start;
  }
  body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-map-column {
    padding-right: 22px;
    border-right: 1px solid #ebe8e2;
  }
  body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-control-column {
    gap: 22px;
  }
  body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-group-region-map,
  body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-group-topic,
  body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-group-type,
  body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-group-search,
  body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-group-date {
    grid-column: auto;
    grid-row: auto;
  }
  .filter-region-picker {
    display: grid;
    grid-template-columns: 1fr;
    gap: 12px;
  }
  .filter-region-quick {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .filter-region-map {
    width: min(100%, 316px);
    justify-self: center;
    align-self: start;
  }
  .filter-region-map-svg {
    display: block;
    width: 100%;
    height: auto;
  }
  .filter-region-map-region {
    color: #006f63;
    cursor: pointer;
  }
  .filter-region-map-region:focus-visible {
    outline: 0;
  }
  .filter-region-map-path {
    fill: #f1f5f2;
    stroke: rgba(0, 111, 99, 0.5);
    stroke-width: 1.55;
    stroke-linejoin: round;
    vector-effect: non-scaling-stroke;
    transition: fill 0.16s ease, stroke 0.16s ease, stroke-width 0.16s ease, filter 0.16s ease;
  }
  .filter-region-map-hit-target {
    fill: rgba(0, 0, 0, 0);
    stroke: transparent;
    pointer-events: all;
  }
  .filter-region-map-tooltip-layer {
    pointer-events: none;
  }
  .filter-region-map-tooltip {
    opacity: 0;
    pointer-events: none;
    transform-box: fill-box;
    transform-origin: center;
    transition: opacity 0.14s ease, transform 0.14s ease;
  }
  .filter-region-map-tooltip rect {
    fill: #ffffff;
    stroke: #d2cec6;
    stroke-width: 1.5;
    filter: drop-shadow(0 10px 18px rgba(24, 24, 24, 0.16));
  }
  .filter-region-map-tooltip text {
    fill: #2c2926;
    font-size: 28px;
    font-weight: 900;
    letter-spacing: 0;
  }
  .filter-region-map-tooltip .filter-region-map-count {
    fill: #006f63;
  }
  .filter-region-map-region:hover .filter-region-map-path,
  .filter-region-map-region:focus-visible .filter-region-map-path {
    fill: #d9f0ea;
    stroke: #006f63;
    stroke-width: 2.25;
  }
  .filter-region-map-tooltip.is-visible {
    opacity: 1;
  }
  .filter-region-map-region.active .filter-region-map-path {
    fill: var(--filter-active-bg);
    stroke: var(--filter-active-stroke);
    stroke-width: 2.45;
    filter: drop-shadow(0 8px 12px rgba(24, 24, 24, 0.16));
  }
  .filter-region-map-region.is-empty:not(.active) .filter-region-map-path {
    fill: #fbfaf5;
    stroke: rgba(107, 101, 94, 0.3);
    stroke-width: 1.05;
  }
  .filter-region-map-region.is-empty:not(.active):hover .filter-region-map-path,
  .filter-region-map-region.is-empty:not(.active):focus-visible .filter-region-map-path {
    fill: #f4f1ea;
    stroke: rgba(107, 101, 94, 0.54);
    stroke-width: 1.45;
  }
  .filter-region-map-tooltip.is-empty:not(.active) .filter-region-map-count {
    fill: #8a837a;
  }
  .filter-region-map-tooltip.active .filter-region-map-count {
    fill: var(--filter-active-bg);
  }
  body:not([data-page="index.html"]) .filter-controls {
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    overflow: visible;
    padding-bottom: 0;
  }
  body:not([data-page="index.html"]) .article-grid,
  body:not([data-page="index.html"]) .feature-grid {
    gap: 18px;
  }
  body:not([data-page="index.html"]) .article-card,
  body:not([data-page="index.html"]) .section-card,
  body:not([data-page="index.html"]) .info-card {
    min-width: 0;
  }
  @media (prefers-reduced-motion: no-preference) {
    .top-nav-link,
    .bottom-nav a,
    .side-marker-link,
    .button,
    .mini-link,
    .action-button,
    .filter-button,
    .article-card,
    .section-card,
    .info-card,
    .list-card,
    .page-intro-card,
    .home-overview-column,
    .home-application-card,
    .home-application-link,
    .home-urgent-link,
    .home-glance-item,
    .side-clock,
    .side-update-card,
    .article-media,
    .article-thumbnail {
      transition:
        background-color 180ms ease,
        border-color 180ms ease,
        box-shadow 180ms ease,
        color 180ms ease,
        opacity 180ms ease,
        transform 180ms ease;
      will-change: transform;
    }
    .top-nav-link:hover {
      transform: translateY(-1px);
    }
    .top-nav-link.active::after {
      transition: transform 180ms ease, opacity 180ms ease;
      transform-origin: center;
    }
    .bottom-nav a:hover {
      transform: translateY(-2px);
    }
    .side-marker-link:hover {
      transform: translateX(3px);
    }
    .side-clock:hover,
    .side-update-card:hover {
      transform: translateY(-1px);
      box-shadow: 0 12px 24px rgba(31, 42, 51, 0.08);
    }
    .button:hover,
    .mini-link:hover,
    .action-button:hover,
    .filter-button:hover {
      transform: translateY(-1px);
      box-shadow: 0 8px 18px rgba(31, 42, 51, 0.08);
    }
    .filter-button:hover:not(.active) {
      border-color: rgba(156, 110, 43, 0.32);
      background: #f3faf7;
    }
    .article-card:hover,
    .feature-grid > .section-card:hover,
    .home-maker-panel:hover,
    .info-card:hover,
    .list-card:hover,
    .page-intro-card:hover,
    .home-overview-column:hover,
    .home-application-card:hover,
    .home-glance-item:hover {
      transform: translateY(-2px);
      border-color: rgba(156, 110, 43, 0.24);
      box-shadow: 0 16px 36px rgba(31, 42, 51, 0.1);
    }
    .home-application-link:hover {
      transform: translateY(-1px);
      box-shadow: 0 10px 18px rgba(0, 111, 99, 0.16);
    }
    .home-urgent-item:hover .home-urgent-link {
      transform: translateX(3px);
      background: rgba(156, 110, 43, 0.06);
    }
    .article-media {
      overflow: hidden;
    }
    .article-card:hover .article-thumbnail,
    .article-media:hover .article-thumbnail {
      transform: scale(1.025);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
      transition-duration: 0.01ms !important;
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      scroll-behavior: auto !important;
    }
  }
  @media (max-width: 900px) {
    body:not([data-page="index.html"]) .page-intro-card,
    body:not([data-page="index.html"]) .news-intro-card,
    body:not([data-page="index.html"]) .hero-card {
      grid-template-columns: 1fr;
      padding: 20px;
    }
    body:not([data-page="index.html"]) .page-intro-card.has-media {
      grid-template-columns: 1fr;
    }
    body:not([data-page="index.html"]) .page-intro-media {
      width: 88px;
      justify-self: end;
    }
    body:not([data-page="index.html"]) .filter-stack {
      grid-template-columns: 1fr;
    }
    body:not([data-page="index.html"]) .section#filters {
      scroll-margin-top: 82px;
    }
    body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-head {
      align-items: flex-start;
      flex-direction: column;
    }
    body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-stack-map {
      grid-template-columns: 1fr;
      gap: 16px;
    }
    body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-map-column {
      padding-right: 0;
      padding-bottom: 16px;
      border-right: 0;
      border-bottom: 1px solid #ebe8e2;
    }
    body:not([data-page="index.html"]) .filter-group.wide,
    body:not([data-page="index.html"]) .filter-group-group,
    body:not([data-page="index.html"]) .filter-group-region,
    body:not([data-page="index.html"]) .filter-group-topic,
    body:not([data-page="index.html"]) .filter-group-scope,
    body:not([data-page="index.html"]) .filter-group-type,
    body:not([data-page="index.html"]) .filter-group-search,
    body:not([data-page="index.html"]) .filter-group-date {
      grid-column: 1 / -1;
    }
    body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-group-region-map,
    body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-group-topic,
    body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-group-type,
    body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-group-search,
    body:not([data-page="index.html"]) .filter-panel.has-region-map .filter-group-date {
      grid-column: 1 / -1;
      grid-row: auto;
    }
    body:not([data-page="index.html"]) .date-picker-row,
    body:not([data-page="index.html"]) .date-range-fields {
      grid-template-columns: 1fr;
    }
    .filter-region-map {
      width: min(100%, 320px);
    }
    .local-menu-nav {
      grid-template-columns: 1fr;
    }
    .local-map-panel {
      min-height: auto;
      padding: 16px;
    }
    .local-map-canvas {
      min-height: auto;
    }
    .local-map-stage {
      width: min(100%, 360px);
    }
    .local-map-label {
      min-width: 32px;
      min-height: 24px;
      padding: 3px 7px;
      font-size: 0.7rem;
    }
    .local-map-popover {
      min-width: 176px;
      padding: 10px;
    }
  }
  body[data-page="index.html"] .youth-metrics-grid {
    grid-template-columns: minmax(0, 1.35fr) repeat(3, minmax(0, 0.78fr));
    gap: 22px;
    align-items: stretch;
  }
  body[data-page="index.html"] .youth-metric-item {
    min-height: 194px;
    display: grid;
    align-content: space-between;
    gap: 14px;
    padding: 24px;
  }
  body[data-page="index.html"] .youth-metric-primary {
    min-height: 224px;
    padding: 28px 30px;
    background: #ffffff;
  }
  body[data-page="index.html"] .youth-metric-primary .youth-metric-value {
    font-size: clamp(2.35rem, 3.4vw, 3.35rem);
    line-height: 1.04;
  }
  body[data-page="index.html"] .youth-metric-compact .youth-metric-value {
    font-size: clamp(1.7rem, 2vw, 2.08rem);
  }
  .youth-metric-scale {
    width: 100%;
    height: 6px;
    border-radius: 999px;
    background: #ece9e4;
    overflow: hidden;
  }
  .youth-metric-scale span {
    display: block;
    width: 74%;
    height: 100%;
    border-radius: inherit;
    background: var(--text);
  }
  .home-data-board-grid {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(320px, 0.92fr);
    gap: 30px;
    align-items: start;
  }
  .home-research-only-grid {
    grid-template-columns: 1fr;
  }
  .home-region-block,
  .home-research-block {
    min-width: 0;
  }
  .home-region-table-wrap {
    overflow-x: auto;
    border-top: 1px solid #d2cec6;
  }
  .home-region-table {
    width: 100%;
    min-width: 680px;
    border-collapse: collapse;
    font-size: 0.94rem;
  }
  .home-region-table th,
  .home-region-table td {
    padding: 18px 14px;
    border-bottom: 1px solid #ebe8e2;
    text-align: left;
    vertical-align: top;
  }
  .home-region-table thead th {
    color: #756f68;
    font-size: 0.78rem;
    font-weight: 900;
    text-transform: uppercase;
  }
  .home-region-table tbody th {
    color: var(--text);
    font-size: 1rem;
    font-weight: 900;
    white-space: nowrap;
  }
  .home-region-table td strong,
  .home-region-table td span,
  .home-region-table td small {
    display: block;
  }
  .home-region-table td strong {
    color: var(--text);
    font-size: 1.02rem;
  }
  .home-region-table td span,
  .home-region-table td small {
    color: #6f6962;
    line-height: 1.45;
  }
  .home-region-table td small {
    max-width: 320px;
    margin-top: 4px;
    font-size: 0.82rem;
  }
  .home-region-focus,
  .home-report-tag {
    display: inline-flex;
    width: fit-content;
    min-height: 28px;
    align-items: center;
    padding: 4px 10px;
    border-radius: 999px;
    background: #e6f5f1;
    color: #006f63;
    font-size: 0.78rem;
    font-weight: 900;
  }
  .home-region-link {
    color: #006f63;
    font-weight: 900;
  }
  .home-region-empty {
    padding: 24px 0;
    border-top: 1px solid #d2cec6;
    border-bottom: 1px solid #ebe8e2;
  }
  .home-region-empty h3 {
    margin: 0;
    color: var(--text);
    font-size: 1.1rem;
  }
  .home-region-empty p {
    margin: 8px 0 0;
    color: var(--muted);
  }
  .home-research-block {
    display: grid;
    gap: 18px;
  }
  .home-research-head {
    display: grid;
    gap: 8px;
  }
  .home-research-head h2 {
    margin: 0;
    color: var(--text);
    font-size: 1.45rem;
    line-height: 1.22;
  }
  .home-research-head p {
    margin: 0;
    color: var(--muted);
  }
  .home-report-list {
    display: grid;
    gap: 12px;
  }
  .home-research-section .home-report-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .home-report-row {
    display: grid;
    gap: 7px;
    min-width: 0;
    padding: 18px;
    border: 1px solid #d2cec6;
    border-radius: 8px;
    background: #ffffff;
  }
  .home-report-row:hover {
    border-color: #bcb6ac;
    box-shadow: 0 10px 20px rgba(24, 24, 24, 0.05);
    transform: translateY(-1px);
  }
  .home-report-row strong {
    color: var(--text);
    font-size: 1rem;
    line-height: 1.38;
  }
  .home-report-meta,
  .home-report-row p {
    color: #6f6962;
    font-size: 0.84rem;
    line-height: 1.55;
  }
  .home-report-row p {
    margin: 0;
  }
  .home-research-block .button {
    width: 100%;
    justify-content: center;
  }
  @media (max-width: 1180px) {
    body[data-page="index.html"] .youth-metrics-grid,
    .home-data-board-grid {
      grid-template-columns: 1fr;
    }
    body[data-page="index.html"] .youth-metric-primary {
      min-height: 200px;
    }
  }
  @media (max-width: 900px) {
    body[data-page="index.html"] .youth-metrics-grid {
      grid-template-columns: 1fr;
      gap: 14px;
    }
    body[data-page="index.html"] .youth-metric-item {
      min-height: auto;
      padding: 20px;
    }
    .home-data-board-grid {
      gap: 22px;
    }
    .home-research-section .home-report-list {
      grid-template-columns: 1fr;
    }
    .home-region-table {
      min-width: 620px;
      font-size: 0.88rem;
    }
    .home-region-table th,
    .home-region-table td {
      padding: 14px 10px;
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
  <link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700;900&family=Noto+Sans+KR:wght@400;500;700;800&display=swap" rel="stylesheet">
  <link rel="icon" type="image/svg+xml" href="{brand_mark_src}">
  <style>{styles}</style>
</head>
<body data-page="{active_page}">
  <header class="topbar">
    <div class="topbar-side">
      {global_search}
      <a class="topbar-icon topbar-home-link" href="index.html" aria-label="홈">
        <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
          <path d="M4 11.5 12 5l8 6.5"></path>
          <path d="M6.5 10.5V20h11V10.5"></path>
          <path d="M10 20v-5h4v5"></path>
        </svg>
      </a>
      {live_clock_topbar}
      {guide_link}
      <a class="topbar-icon topbar-top-link" href="#page-top" aria-label="맨 위로">↑</a>
    </div>
  </header>
  <div class="app-layout">
    <aside class="side-nav" aria-label="현재 페이지 위치 마커">
      {side_nav}
    </aside>
    <div class="shell" id="page-top">
    {content}
    <footer class="site-footer" id="site-footer" aria-label="운영 안내">{footer_note}</footer>
    </div>
  </div>
  <nav class="bottom-nav" style="--bottom-nav-count: {bottom_nav_count};">{bottom_nav}</nav>
  {guide_overlay}
  {admin_login_overlay}
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

  function getRegionMapTooltip(region) {
    if (!region || !region.dataset || !region.dataset.regionMapId) {
      return null;
    }
    const svg = region.closest('.filter-region-map-svg');
    if (!svg) {
      return null;
    }
    return Array.from(svg.querySelectorAll('.filter-region-map-tooltip'))
      .find((tooltip) => tooltip.dataset.regionMapTooltip === region.dataset.regionMapId) || null;
  }

  function syncRegionMapTooltipState(region) {
    const tooltip = getRegionMapTooltip(region);
    if (!tooltip) {
      return;
    }
    tooltip.classList.toggle('active', region.classList.contains('active'));
    tooltip.classList.toggle('is-empty', region.classList.contains('is-empty'));
  }

  function setRegionMapTooltipVisibility(target, isVisible) {
    const region = target.closest && target.closest('.filter-region-map-region');
    if (!region) {
      return;
    }
    const tooltip = getRegionMapTooltip(region);
    if (!tooltip) {
      return;
    }
    if (isVisible) {
      const svg = region.closest('.filter-region-map-svg');
      svg.querySelectorAll('.filter-region-map-tooltip.is-visible').forEach((item) => {
        if (item !== tooltip) {
          item.classList.remove('is-visible');
        }
      });
    }
    tooltip.classList.toggle('is-visible', isVisible);
  }

  function updateRegionFilterButtonCount(button, count) {
    const label = button.getAttribute('data-region-label') || button.getAttribute('data-filter-value') || '';
    const safeCount = Number.isFinite(count) ? count : 0;
    if (label) {
      button.setAttribute('aria-label', `${label} ${safeCount}건 선택`);
    }
    const countNodes = [];
    const inlineCountNode = button.querySelector('[data-region-map-count]');
    if (inlineCountNode) {
      countNodes.push(inlineCountNode);
    }
    const tooltip = getRegionMapTooltip(button);
    const tooltipCountNode = tooltip && tooltip.querySelector('[data-region-map-count]');
    if (tooltipCountNode) {
      countNodes.push(tooltipCountNode);
    }
    countNodes.forEach((countNode) => {
      countNode.textContent = `${safeCount}건`;
    });
    button.dataset.regionVisibleCount = String(safeCount);
    button.classList.toggle('is-empty', safeCount === 0);
    syncRegionMapTooltipState(button);
  }

  function bringMapRegionToFront(target) {
    const region = target.closest && target.closest('.filter-region-map-region, .local-map-region');
    if (!region || !region.parentNode) {
      return;
    }
    if (!region.querySelector('.filter-region-map-hit-target, .local-map-hit-target')) {
      return;
    }
    const tooltipLayer = region.parentNode.querySelector('.filter-region-map-tooltip-layer');
    if (tooltipLayer) {
      region.parentNode.insertBefore(region, tooltipLayer);
    } else {
      region.parentNode.appendChild(region);
    }
  }

  function applyNewsFilters(root, selectedDateStart, selectedDateEnd, selectedRegion, selectedTopic, selectedQuery) {
    const normalizedDates = normalizeNewsDateRange(
      selectedDateStart ?? root.dataset.selectedDateStart ?? root.getAttribute('data-default-date-start') ?? '',
      selectedDateEnd ?? root.dataset.selectedDateEnd ?? root.getAttribute('data-default-date-end') ?? '',
    );
    const activeDateStart = normalizedDates.startDate;
    const activeDateEnd = normalizedDates.endDate;
    const hasDateRange = Boolean(activeDateStart || activeDateEnd);
    const activeRegion = selectedRegion || root.dataset.selectedRegion || root.getAttribute('data-default-region') || 'all';
    const activeTopic = selectedTopic || root.dataset.selectedTopic || root.getAttribute('data-default-topic') || 'all';
    const activeQuery = normalizeSearchQuery(
      selectedQuery ?? root.dataset.selectedSearchQuery ?? root.getAttribute('data-default-search-query') ?? ''
    );
    root.dataset.selectedDateStart = activeDateStart;
    root.dataset.selectedDateEnd = activeDateEnd;
    root.dataset.selectedRegion = activeRegion;
    root.dataset.selectedTopic = activeTopic;
    root.dataset.selectedSearchQuery = activeQuery;

    const articleCards = Array.from(root.querySelectorAll('[data-article-date]'));
    const regionCounts = new Map();
    let visibleCount = 0;

    articleCards.forEach((card) => {
      const articleDate = card.getAttribute('data-article-date') || '';
      const articleRegion = card.getAttribute('data-article-region') || '중앙';
      const articleTopics = (card.getAttribute('data-article-topics') || '').split('|').filter(Boolean);
      const isAfterStart = !activeDateStart || (articleDate && articleDate >= activeDateStart);
      const isBeforeEnd = !activeDateEnd || (articleDate && articleDate <= activeDateEnd);
      const dateMatch = !hasDateRange || (isAfterStart && isBeforeEnd);
      const regionMatch = activeRegion === 'all' || articleRegion === activeRegion;
      const topicMatch = activeTopic === 'all' || articleTopics.includes(activeTopic);
      const searchMatch = cardMatchesSearch(card, activeQuery);
      const isMatch = dateMatch && regionMatch && topicMatch && searchMatch;
      if (dateMatch && topicMatch && searchMatch) {
        regionCounts.set(articleRegion, (regionCounts.get(articleRegion) || 0) + 1);
      }
      card.hidden = !isMatch;
      if (isMatch) {
        visibleCount += 1;
      }
    });

    root.querySelectorAll('[data-news-filter]').forEach((button) => {
      const group = button.getAttribute('data-filter-group') || 'date';
      const value = button.getAttribute('data-filter-value') || 'all';
      const isActive = group === 'region'
        ? value === activeRegion
        : group === 'topic'
          ? value === activeTopic
          : (value === 'all' && !hasDateRange);
      if (group === 'region' && value !== 'all') {
        updateRegionFilterButtonCount(button, regionCounts.get(value) || 0);
      }
      button.classList.toggle('active', isActive);
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      syncRegionMapTooltipState(button);
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
      if (!hasDateRange && activeRegion === 'all' && activeTopic === 'all' && !searchLabel) {
        status.textContent = `전체 ${visibleCount}건을 보고 있습니다.`;
      } else {
        const parts = [];
        if (activeRegion !== 'all') {
          parts.push(activeRegion);
        }
        if (activeTopic !== 'all') {
          parts.push(`#${activeTopic}`);
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

  function getPolicyCountsByAttribute(articleCards, targetGroup, attributeName, activeType, activeDateStart, activeDateEnd, hasDateRange, activeQuery) {
    const counts = new Map();

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
        counts.set(attributeValue, (counts.get(attributeValue) || 0) + 1);
      }
    });

    return counts;
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
    const keepEmptyScopes = root.dataset.keepEmptyScopes === 'true';
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
    const localScopeCounts = getPolicyCountsByAttribute(
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
      if (activeScope !== 'all' && !keepEmptyScopes && !availableScopes.has(activeScope)) {
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
          button.hidden = !keepEmptyScopes && !availableScopes.has(value);
        }
        if (scopeKind === 'local' && value !== 'all') {
          updateRegionFilterButtonCount(button, localScopeCounts.get(value) || 0);
        }
        isActive = value === activeScope;
      }
      button.classList.toggle('active', isActive);
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      syncRegionMapTooltipState(button);
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

    const homeBriefingTab = event.target.closest('[data-home-briefing-tab]');
    if (homeBriefingTab) {
      event.preventDefault();
      const root = homeBriefingTab.closest('[data-home-briefing-tabs]');
      const target = homeBriefingTab.getAttribute('data-home-briefing-tab') || '';
      if (root && target) {
        root.querySelectorAll('[data-home-briefing-tab]').forEach((tab) => {
          const isActive = tab === homeBriefingTab;
          tab.classList.toggle('active', isActive);
          tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
          tab.tabIndex = isActive ? 0 : -1;
        });
        root.querySelectorAll('[data-home-briefing-panel]').forEach((panel) => {
          const isActive = panel.getAttribute('data-home-briefing-panel') === target;
          panel.hidden = !isActive;
          panel.classList.toggle('active', isActive);
        });
      }
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
      event.preventDefault();
      const root = filterButton.closest('[data-news-filter-root]');
      if (root) {
        const group = filterButton.getAttribute('data-filter-group') || 'date';
        const value = filterButton.getAttribute('data-filter-value') || 'all';
        applyNewsFilters(
          root,
          group === 'date' ? '' : (root.dataset.selectedDateStart || root.getAttribute('data-default-date-start') || ''),
          group === 'date' ? '' : (root.dataset.selectedDateEnd || root.getAttribute('data-default-date-end') || ''),
          group === 'region' ? value : (root.dataset.selectedRegion || root.getAttribute('data-default-region') || 'all'),
          group === 'topic' ? value : (root.dataset.selectedTopic || root.getAttribute('data-default-topic') || 'all'),
          root.dataset.selectedSearchQuery || root.getAttribute('data-default-search-query') || '',
        );
      }
      return;
    }

    const policyFilterButton = event.target.closest('[data-policy-filter]');
    if (policyFilterButton) {
      event.preventDefault();
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

  document.addEventListener('pointerover', (event) => {
    bringMapRegionToFront(event.target);
    setRegionMapTooltipVisibility(event.target, true);
  });

  document.addEventListener('pointerout', (event) => {
    const region = event.target.closest && event.target.closest('.filter-region-map-region');
    const relatedTarget = event.relatedTarget;
    const relatedRegion = relatedTarget && relatedTarget.closest
      ? relatedTarget.closest('.filter-region-map-region')
      : null;
    if (region && relatedRegion !== region) {
      setRegionMapTooltipVisibility(region, false);
    }
  });

  document.addEventListener('focusin', (event) => {
    bringMapRegionToFront(event.target);
    setRegionMapTooltipVisibility(event.target, true);
  });

  document.addEventListener('focusout', (event) => {
    setRegionMapTooltipVisibility(event.target, false);
  });

  const pageParams = new URLSearchParams(window.location.search);
  const queryFromUrl = normalizeSearchQuery(pageParams.get('q') || pageParams.get('keyword') || '');
  const topicFromUrl = normalizeSearchQuery(pageParams.get('topic') || '');

  document.querySelectorAll('[data-news-filter-root]').forEach((root) => {
    applyNewsFilters(
      root,
      root.getAttribute('data-default-date-start') || '',
      root.getAttribute('data-default-date-end') || '',
      root.getAttribute('data-default-region') || 'all',
      topicFromUrl || root.getAttribute('data-default-topic') || 'all',
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
        root.dataset.selectedTopic || root.getAttribute('data-default-topic') || 'all',
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
        root.dataset.selectedTopic || root.getAttribute('data-default-topic') || 'all',
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

  function setupLiveClock() {
    const clocks = Array.from(document.querySelectorAll('[data-live-clock]'));
    if (clocks.length === 0) {
      return;
    }
    const weekdayMap = {
      월요일: '월',
      화요일: '화',
      수요일: '수',
      목요일: '목',
      금요일: '금',
      토요일: '토',
      일요일: '일',
      Mon: '월',
      Tue: '화',
      Wed: '수',
      Thu: '목',
      Fri: '금',
      Sat: '토',
      Sun: '일',
    };

    function readPart(parts, type) {
      const part = parts.find((item) => item.type === type);
      return part ? part.value : '';
    }

    function clockParts(now) {
      try {
        const parts = new Intl.DateTimeFormat('ko-KR', {
          timeZone: 'Asia/Seoul',
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          weekday: 'short',
          hour: '2-digit',
          minute: '2-digit',
          hour12: false,
        }).formatToParts(now);
        const year = readPart(parts, 'year');
        const month = readPart(parts, 'month');
        const day = readPart(parts, 'day');
        const weekdayRaw = readPart(parts, 'weekday');
        const weekday = weekdayMap[weekdayRaw] || weekdayRaw.replace('요일', '');
        const hour = readPart(parts, 'hour').padStart(2, '0');
        const minute = readPart(parts, 'minute').padStart(2, '0');
        return { year, month, day, weekday, hour, minute };
      } catch (error) {
        const fallback = new Date(now.getTime() + (9 * 60 + now.getTimezoneOffset()) * 60000);
        const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
        return {
          year: String(fallback.getFullYear()),
          month: String(fallback.getMonth() + 1).padStart(2, '0'),
          day: String(fallback.getDate()).padStart(2, '0'),
          weekday: weekdays[fallback.getDay()],
          hour: String(fallback.getHours()).padStart(2, '0'),
          minute: String(fallback.getMinutes()).padStart(2, '0'),
        };
      }
    }

    function updateClock() {
      const parts = clockParts(new Date());
      const fullDate = `${parts.year}.${parts.month}.${parts.day} (${parts.weekday})`;
      const shortDate = `${parts.month}.${parts.day}`;
      const time = `${parts.hour}:${parts.minute}`;
      const iso = `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:00+09:00`;
      clocks.forEach((clock) => {
        clock.setAttribute('datetime', iso);
        clock.setAttribute('aria-label', `한국시간 ${fullDate} ${time}`);
        const fullDateNode = clock.querySelector('[data-live-clock-date]');
        const shortDateNode = clock.querySelector('[data-live-clock-date-short]');
        const timeNode = clock.querySelector('[data-live-clock-time]');
        if (fullDateNode) {
          fullDateNode.textContent = fullDate;
        }
        if (shortDateNode) {
          shortDateNode.textContent = shortDate;
        }
        if (timeNode) {
          timeNode.textContent = time;
        }
      });
    }

    updateClock();
    window.setInterval(updateClock, 30000);
  }

  function setupPageMarkers() {
    const markerLinks = Array.from(document.querySelectorAll('[data-marker-link]'));
    if (markerLinks.length === 0) {
      return;
    }

    const markerPairs = markerLinks.map((link) => {
      const href = link.getAttribute('href') || '';
      if (!href.startsWith('#')) {
        return null;
      }
      const targetId = decodeURIComponent(href.slice(1));
      const target = document.getElementById(targetId);
      return target ? { link, target } : null;
    }).filter(Boolean);

    if (markerPairs.length === 0) {
      return;
    }

    function activateMarker(activeLink) {
      markerLinks.forEach((link) => {
        const isActive = link === activeLink;
        link.classList.toggle('active', isActive);
        if (isActive) {
          link.setAttribute('aria-current', 'location');
        } else {
          link.removeAttribute('aria-current');
        }
      });
    }

    function activateFromHash() {
      const hash = window.location.hash || '#page-top';
      const current = markerPairs.find(({ link }) => link.getAttribute('href') === hash);
      if (current) {
        activateMarker(current.link);
      }
    }

    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        const visibleEntries = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => Math.abs(left.boundingClientRect.top) - Math.abs(right.boundingClientRect.top));
        if (visibleEntries.length === 0) {
          return;
        }
        const activePair = markerPairs.find(({ target }) => target === visibleEntries[0].target);
        if (activePair) {
          activateMarker(activePair.link);
        }
      }, {
        rootMargin: '-24% 0px -62% 0px',
        threshold: [0, 0.12, 0.35, 0.7],
      });
      markerPairs.forEach(({ target }) => observer.observe(target));
    }

    markerLinks.forEach((link) => {
      link.addEventListener('click', () => activateMarker(link));
    });
    window.addEventListener('hashchange', activateFromHash);
    activateFromHash();
  }

  setupLiveClock();
  setupPageMarkers();

  const guideOverlay = document.querySelector('[data-guide-overlay]');
  if (guideOverlay && document.body.dataset.page === 'index.html') {
    guideOverlay.hidden = true;
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


def build_admin_access_script() -> str:
    allowed_hashes = json.dumps(PUBLIC_ADMIN_ACCOUNT_HASHES, ensure_ascii=False)
    return f"""
(() => {{
  const allowedHashes = new Set({allowed_hashes});
  const storageKey = "youthMoabomAdminAccount-v1";
  const overlay = document.querySelector("[data-admin-login-overlay]");
  if (!overlay) {{
    return;
  }}
  const form = overlay.querySelector("[data-admin-login-form]");
  const input = overlay.querySelector("[data-admin-account-input]");
  const feedback = overlay.querySelector("[data-admin-login-feedback]");
  const logoutButtons = document.querySelectorAll("[data-admin-logout]");

  function normalizeAccount(value) {{
    return String(value || "").trim().replace(/\\s+/g, " ").toLocaleLowerCase();
  }}

  async function hashAccount(account) {{
    if (!window.crypto || !window.crypto.subtle || !window.TextEncoder) {{
      throw new Error("crypto_unavailable");
    }}
    const digest = await window.crypto.subtle.digest("SHA-256", new TextEncoder().encode(normalizeAccount(account)));
    return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
  }}

  function setFeedback(message, isError) {{
    if (!feedback) {{
      return;
    }}
    feedback.textContent = message || "";
    feedback.classList.toggle("error", Boolean(isError));
  }}

  function setAuthorized(account) {{
    const isAuthorized = Boolean(account);
    document.body.classList.toggle("is-admin-authorized", isAuthorized);
    document.querySelectorAll("[data-admin-only]").forEach((element) => {{
      element.hidden = !isAuthorized;
    }});
    document.querySelectorAll("[data-admin-entry-label]").forEach((label) => {{
      label.textContent = isAuthorized ? "관리 모드" : "관리 로그인";
    }});
    document.querySelectorAll("[data-admin-logout]").forEach((button) => {{
      button.hidden = !isAuthorized;
    }});
  }}

  function openDialog() {{
    overlay.hidden = false;
    setFeedback(allowedHashes.size ? "" : "허용 계정이 아직 설정되지 않았습니다.", !allowedHashes.size);
    window.setTimeout(() => {{
      if (input) {{
        input.focus();
      }}
    }}, 0);
  }}

  function closeDialog() {{
    overlay.hidden = true;
  }}

  async function verifyAccount(account) {{
    if (!allowedHashes.size || !account) {{
      return false;
    }}
    const accountHash = await hashAccount(account);
    return allowedHashes.has(accountHash);
  }}

  document.addEventListener("click", (event) => {{
    const openButton = event.target.closest("[data-admin-login-open]");
    if (openButton) {{
      event.preventDefault();
      openDialog();
      return;
    }}

    if (event.target.closest("[data-admin-login-close]") || event.target === overlay) {{
      event.preventDefault();
      closeDialog();
      return;
    }}

    if (event.target.closest("[data-admin-logout]")) {{
      event.preventDefault();
      try {{
        localStorage.removeItem(storageKey);
      }} catch (error) {{
        // ignore storage errors
      }}
      setAuthorized("");
      setFeedback("관리 표시 모드를 해제했습니다.", false);
      closeDialog();
    }}
  }});

  document.addEventListener("keydown", (event) => {{
    if (event.key === "Escape" && !overlay.hidden) {{
      closeDialog();
    }}
  }});

  if (form) {{
    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      const account = input ? normalizeAccount(input.value) : "";
      if (!allowedHashes.size) {{
        setFeedback("허용 계정이 설정되지 않았습니다. 배포 환경변수나 로컬 설정 파일을 확인해 주세요.", true);
        return;
      }}
      if (!account) {{
        setFeedback("계정을 입력해 주세요.", true);
        return;
      }}
      try {{
        const isAllowed = await verifyAccount(account);
        if (!isAllowed) {{
          try {{
            localStorage.removeItem(storageKey);
          }} catch (error) {{
            // ignore storage errors
          }}
          setAuthorized("");
          setFeedback("허용된 계정이 아닙니다.", true);
          return;
        }}
        try {{
          localStorage.setItem(storageKey, account);
        }} catch (error) {{
          // ignore storage errors
        }}
        setAuthorized(account);
        setFeedback("관리 예정 메뉴를 표시했습니다.", false);
        window.setTimeout(closeDialog, 450);
      }} catch (error) {{
        setFeedback("이 브라우저에서 임시 로그인 확인을 사용할 수 없습니다.", true);
      }}
    }});
  }}

  try {{
    const savedAccount = localStorage.getItem(storageKey);
    if (savedAccount) {{
      verifyAccount(savedAccount).then((isAllowed) => {{
        if (isAllowed) {{
          setAuthorized(savedAccount);
        }} else {{
          localStorage.removeItem(storageKey);
          setAuthorized("");
        }}
      }}).catch(() => setAuthorized(""));
    }} else {{
      setAuthorized("");
    }}
  }} catch (error) {{
    setAuthorized("");
  }}
}})();
"""


def build_page_script() -> str:
    return "\n".join((BASE_SCRIPT, build_admin_access_script(), build_analytics_script()))


NAV_ITEMS = [
    ("news.html", "뉴스 모음"),
    ("election.html", "선거·공약"),
    ("policies.html", "정부 동향"),
    ("plans.html", "지자체 동향"),
    ("hub.html", "참여기구"),
    ("tools.html", "연구·문헌"),
]


TOP_NAV_ITEMS = [("index.html", "홈"), *NAV_ITEMS]


PAGE_HEADINGS = {
    "index.html": "청년정책 모아봄",
    "news.html": "뉴스 모음",
    "election.html": "선거·공약",
    "policies.html": "정부 동향",
    "plans.html": "지자체 동향",
    "hub.html": "참여기구",
    "tools.html": "연구·문헌",
    "contact.html": "제보·문의",
    "guide.html": "아카이브",
}


CREATOR_CONTACT_URL = "https://litt.ly/spectac1e"
CREATOR_CONTACT_LABEL = "제작자 연락 채널"


SIDE_NAV_CONFIG = {
    "index.html": {
        "title": "오늘의 위치",
        "description": "첫 화면의 주요 구간",
        "items": [
            ("#page-top", "상단"),
            ("#today-briefing", "한눈에 보기"),
            ("#application-policies", "모집 중"),
            ("#youth-metrics", "핵심 지표"),
            ("#site-footer", "운영 안내"),
        ],
    },
    "news.html": {
        "title": "뉴스 모음 위치",
        "description": "필터와 기사 목록",
        "items": [("#page-top", "상단"), ("#filters", "필터"), ("#main-list", "주요 목록")],
    },
    "election.html": {
        "title": "선거·공약 위치",
        "description": "필터와 공약 흐름",
        "items": [("#page-top", "상단"), ("#filters", "필터"), ("#main-list", "주요 목록")],
    },
    "policies.html": {
        "title": "정부 동향 위치",
        "description": "중앙정부 공식 발표",
        "items": [("#page-top", "상단"), ("#filters", "필터"), ("#main-list", "정부 발표")],
    },
    "plans.html": {
        "title": "지자체 동향 위치",
        "description": "발표·보도자료·계획",
        "items": [
            ("#page-top", "상단"),
            ("#main-list", "발표 뉴스"),
            ("#local-press-releases", "보도자료"),
            ("#local-policy-map", "기본·시행계획"),
        ],
    },
    "hub.html": {
        "title": "참여기구 위치",
        "description": "자문·위원회·네트워크",
        "items": [("#page-top", "상단"), ("#filters", "필터"), ("#main-list", "공식 회의"), ("#public-governance", "참여 채널")],
    },
    "tools.html": {
        "title": "연구·문헌 위치",
        "description": "통계와 연구 자료",
        "items": [
            ("#page-top", "상단"),
            ("#main-list", "주요 목록"),
            ("#youth-stat-releases", "통계 발표"),
            ("#stats-research-links", "연구 링크"),
            ("#ai-guide", "AI 활용"),
            ("#review", "검토"),
        ],
    },
    "contact.html": {
        "title": "제보·문의 위치",
        "description": "연락과 요청 구간",
        "items": [("#page-top", "상단"), ("#main-list", "기본 정보"), ("#ops", "운영 문의"), ("#collab", "협업"), ("#review", "검토 요청")],
    },
    "guide.html": {
        "title": "이용 안내 위치",
        "description": "메뉴와 갱신 기준",
        "items": [("#page-top", "상단"), ("#main-list", "메뉴 안내")],
    },
}


ADMIN_NAV_PLACEHOLDERS = [
    "운영 대시보드",
    "기사 큐레이션",
    "수집 상태",
    "배포 상태",
    "문의 관리",
    "설정",
]


def nav_label(active_page: str) -> str:
    for href, label in NAV_ITEMS:
        if href == active_page:
            return label
    return "홈"


def page_heading(active_page: str) -> str:
    return "청년정책 모아봄"


def render_guide_link(active_page: str) -> str:
    active = " active" if active_page == "guide.html" else ""
    current = ' aria-current="page"' if active_page == "guide.html" else ""
    return f'<a class="guide-link{active}" href="guide.html" data-guide-open-link="true" aria-label="이용 안내"{current}>이용방법</a>'


def render_global_search() -> str:
    return (
        '<form class="global-search" action="news.html" method="get" role="search">'
        '<span class="global-search-icon" aria-hidden="true">⌕</span>'
        '<input type="search" name="q" autocomplete="off" placeholder="Search insights...">'
        '</form>'
    )


def render_live_clock(variant: str) -> str:
    class_name = "topbar-clock" if variant == "topbar" else "side-clock"
    return f"""
      <time class="live-clock {class_name}" data-live-clock aria-label="한국시간 현재 시각">
        <span class="live-clock-kicker">한국시간</span>
        <span class="live-clock-date" data-live-clock-date>오늘</span>
        <span class="live-clock-date-short" data-live-clock-date-short>오늘</span>
        <span class="live-clock-time" data-live-clock-time>--:--</span>
      </time>
    """


def render_top_nav(active_page: str) -> str:
    items = []
    for href, label in TOP_NAV_ITEMS:
        active = "active" if href == active_page else ""
        current = ' aria-current="page"' if active else ""
        items.append(f'<a class="top-nav-link {active}" href="{href}"{current}>{html.escape(label)}</a>')
    return "".join(items)


SIDE_PRIMARY_NAV_ICONS = {
    "index.html": "home",
    "news.html": "news",
    "election.html": "ballot",
    "policies.html": "government",
    "plans.html": "map",
    "hub.html": "meeting",
    "tools.html": "book",
}


def render_side_nav_icon(icon: str, class_name: str = "side-nav-icon") -> str:
    # Self-authored line icons. Kept inline so the static build has no external icon dependency.
    paths = {
        "home": """
          <path d="M4 11.5 12 5l8 6.5"></path>
          <path d="M6.5 10.5V20h11V10.5"></path>
          <path d="M10 20v-5h4v5"></path>
        """,
        "news": """
          <path d="M6 5.5h9.5L19 9v9.5H6z"></path>
          <path d="M15.5 5.5V9H19"></path>
          <path d="M9 12h6"></path>
          <path d="M9 15h6"></path>
          <path d="M9 18h4"></path>
        """,
        "ballot": """
          <path d="M6 10h12v10H6z"></path>
          <path d="M8.5 10 12 5l3.5 5"></path>
          <path d="m9.5 15 2 2 4-4"></path>
        """,
        "government": """
          <path d="M4 9.5 12 5l8 4.5"></path>
          <path d="M5.5 19h13"></path>
          <path d="M7 10.5V17"></path>
          <path d="M12 10.5V17"></path>
          <path d="M17 10.5V17"></path>
        """,
        "map": """
          <path d="M5 6.5 10 5l4 1.5 5-1.5v12.5L14 19l-4-1.5L5 19z"></path>
          <path d="M10 5v12.5"></path>
          <path d="M14 6.5V19"></path>
          <path d="M16.5 10.5h.01"></path>
        """,
        "meeting": """
          <path d="M8.5 10a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z"></path>
          <path d="M15.5 10a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z"></path>
          <path d="M4.5 19c.5-3 2-5 4-5s3.5 2 4 5"></path>
          <path d="M11.5 15c.8-.7 1.9-1 3-1 2 0 3.5 2 4 5"></path>
        """,
        "book": """
          <path d="M5.5 5.5h5A3.5 3.5 0 0 1 14 9v10a3.5 3.5 0 0 0-3.5-3.5h-5z"></path>
          <path d="M18.5 5.5h-4A3.5 3.5 0 0 0 11 9v10a3.5 3.5 0 0 1 3.5-3.5h4z"></path>
          <path d="M14 9h2.5"></path>
          <path d="M14 12h2.5"></path>
        """,
    }
    path_markup = paths.get(icon, paths["news"])
    return (
        f'<span class="{html.escape(class_name)}" aria-hidden="true">'
        '<svg viewBox="0 0 24 24" focusable="false">'
        f"{path_markup}"
        "</svg></span>"
    )


def render_side_primary_nav(active_page: str) -> str:
    links: list[str] = []
    for href, label in TOP_NAV_ITEMS:
        active = " active" if href == active_page else ""
        current = ' aria-current="page"' if active else ""
        icon = SIDE_PRIMARY_NAV_ICONS.get(href, "insights")
        links.append(
            f'<a class="side-nav-link primary-menu-link{active}" href="{href}" '
            f'data-side-icon="{html.escape(icon)}"{current}>'
            f'{render_side_nav_icon(icon)}'
            f'<span class="side-nav-text"><strong>{html.escape(label)}</strong></span></a>'
        )
    return "".join(links)


def render_admin_entry() -> str:
    return (
        '<button class="side-admin-entry" type="button" data-admin-login-open="true" '
        'title="임시 관리자 표시 모드 열기">'
        '<span data-admin-entry-label>관리 로그인</span><em>임시</em></button>'
    )


def render_side_nav(active_page: str) -> str:
    config = SIDE_NAV_CONFIG.get(active_page, SIDE_NAV_CONFIG["news.html"])
    marker_links: list[str] = []
    for index, (href, label) in enumerate(config["items"]):
        active = " active" if index == 0 else ""
        current = ' aria-current="location"' if index == 0 else ""
        marker_links.append(
            f'<a class="side-marker-link{active}" href="{html.escape(href)}" data-marker-link{current}>'
            '<span class="side-marker-dot" aria-hidden="true"></span>'
            f'<span class="side-marker-label">{html.escape(label)}</span></a>'
        )

    admin_items = "".join(
        f'<button class="side-nav-link pending" type="button" disabled aria-disabled="true">'
        f'<span>{html.escape(label)}</span><em>예정</em></button>'
        for label in ADMIN_NAV_PLACEHOLDERS
    )
    return f"""
      <a class="side-brand" href="index.html" aria-label="청년정책 모아봄 홈으로 이동">
        <strong>청년정책 모아봄</strong>
        <span>by YOUTHSIDE</span>
      </a>
      {render_live_clock("side")}
      <div class="side-menu-section">
        <span class="side-nav-kicker">주요 메뉴</span>
        <nav class="side-nav-links" aria-label="주요 메뉴">
          {render_side_primary_nav(active_page)}
        </nav>
      </div>
      <div class="side-nav-section">
        <span class="side-nav-kicker">스크롤 바로가기</span>
        <nav class="side-marker-list" aria-label="스크롤 바로가기">
          {''.join(marker_links)}
        </nav>
      </div>
      <a class="side-update-card" href="news.html">
        <strong>Weekly Update</strong>
        <span>새로 수집된 청년 정책·뉴스 흐름을 이번 주 단위로 확인하세요.</span>
      </a>
      <div class="side-nav-admin" data-admin-only="true" hidden>
        <span class="side-nav-kicker">관리 예정</span>
        {admin_items}
      </div>
      <div class="side-utility-section">
        {render_admin_entry()}
      </div>
    """


def render_admin_login_overlay() -> str:
    configured_note = (
        "허용된 계정을 입력하면 이 브라우저에서 관리 예정 메뉴가 표시됩니다."
        if PUBLIC_ADMIN_ACCOUNT_HASHES
        else "아직 허용 계정이 설정되지 않았습니다. 로컬 설정 또는 배포 환경변수에 계정을 추가해야 합니다."
    )
    return f"""
  <div class="admin-login-overlay" data-admin-login-overlay hidden>
    <section class="admin-login-dialog" role="dialog" aria-modal="true" aria-labelledby="admin-login-title">
      <div class="admin-login-head">
        <div>
          <h2 id="admin-login-title">관리자 임시 로그인</h2>
          <p>{html.escape(configured_note)}</p>
        </div>
        <button class="admin-login-close" type="button" data-admin-login-close="true" aria-label="닫기">×</button>
      </div>
      <p class="admin-login-warning">보안 안내: 공개 정적 사이트의 임시 로그인은 실제 권한 보호가 아닙니다. 민감한 관리 작업은 서버 인증이 붙은 운영 콘솔에서만 처리해야 합니다.</p>
      <form class="admin-login-form" data-admin-login-form="true">
        <label>
          계정
          <input class="admin-login-input" type="text" name="admin_account" autocomplete="username" placeholder="허용된 계정 입력" data-admin-account-input="true">
        </label>
        <div class="admin-login-actions">
          <button class="button primary" type="submit">확인</button>
          <button class="button" type="button" data-admin-logout="true" hidden>로그아웃</button>
        </div>
        <p class="admin-login-feedback" data-admin-login-feedback></p>
      </form>
    </section>
  </div>
    """


def render_bottom_nav(active_page: str) -> str:
    items = []
    for href, label in NAV_ITEMS:
        active = "active" if href == active_page else ""
        icon = SIDE_PRIMARY_NAV_ICONS.get(href, "news")
        items.append(
            f'<a class="{active}" href="{href}">{render_side_nav_icon(icon, "bottom-nav-icon")}<span>{html.escape(label)}</span></a>'
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
      <p>홈 첫 화면은 오늘 바로 볼 기사부터 보는 구조입니다. 뉴스 모음, 선거·공약, 정부 동향, 지자체 동향으로 나눠서 흐름을 볼 수 있습니다.</p>
      <div class="list">
        <div class="list-item"><strong>홈</strong><span>가장 먼저 볼 기사와 오늘 집계를 한 번에 봅니다.</span></div>
        <div class="list-item"><strong>뉴스 모음</strong><span>언론 기사 중 선거·공약성 기사를 제외한 청년 이슈를 봅니다.</span></div>
        <div class="list-item"><strong>정부 동향</strong><span>중앙정부 원문 중심의 공식 발표를 확인합니다.</span></div>
        <div class="list-item"><strong>지자체 동향</strong><span>지역 공공 주체가 발표한 청년 정책·공고 흐름을 봅니다.</span></div>
        <div class="list-item"><strong>선거·공약</strong><span>지방선거 시기에는 청년 공약과 선거 기사를 따로 모아 봅니다.</span></div>
        <div class="list-item"><strong>참여기구</strong><span>정부 회의와 지역 네트워크 움직임을 나눠서 봅니다.</span></div>
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


def render_publisher_icon(article: dict) -> str:
    icon_url = normalize_media_url(article.get("publisher_icon_url"), article_target_url(article))
    if not icon_url:
        return ""
    source = format_source_label(article.get("source") or article.get("source_name"))
    alt = f"{source} 아이콘" if source else "언론사 아이콘"
    return (
        f'<img class="publisher-icon" src="{html.escape(icon_url)}" alt="{html.escape(alt)}" '
        'loading="lazy" decoding="async" referrerpolicy="no-referrer" '
        'onerror="this.hidden=true">'
    )


def render_article_media(article: dict) -> str:
    image_url = normalize_media_url(article.get("image_url"), article_target_url(article))
    if not image_url:
        return ""

    url = html.escape(article_target_url(article))
    title = display_article_title(article)
    alt = normalize_inline_text(article.get("image_alt") or title)
    escaped_title = html.escape(title)
    onerror = (
        ' onerror="this.parentElement.hidden=true;'
        "var c=this.closest('.article-card');"
        "if(c){c.classList.remove('has-media');c.classList.add('no-media');}"
        '"'
    )
    return (
        f'<a class="article-media" href="{url}" target="_blank" rel="noreferrer" '
        f'aria-label="{escaped_title} 이미지와 기사 링크 바로가기">'
        f'<img class="article-thumbnail" src="{html.escape(image_url)}" alt="{html.escape(alt)}" '
        'loading="lazy" decoding="async" referrerpolicy="no-referrer" '
        f'{onerror}>'
        '</a>'
    )


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
    media_html = render_article_media(article)
    media_state_class = "has-media" if media_html else "no-media"
    topic_tags = article_topic_tags(article)
    badge_values = list(dict.fromkeys([*topic_tags, *article.get("display_badges", [])]))[:3]
    badges = "".join(f'<span class="badge">{html.escape(badge)}</span>' for badge in badge_values)
    badge_row = f'<div class="badge-row">{badges}</div>' if badges else ""
    summary_text = summarize_article_text(article, limit=112)
    escaped_url = html.escape(article_target_url(article))
    escaped_title = html.escape(display_article_title(article))
    article_region = html.escape(news_region_label(article))
    article_topics = html.escape("|".join(topic_tags), quote=True)
    article_search = html.escape(build_article_search_text(article, summary_text), quote=True)
    summary_html = (
        f'<p class="article-summary"><a class="article-summary-link" href="{escaped_url}" target="_blank" rel="noreferrer" '
        f'aria-label="{escaped_title} 링크 바로가기">{html.escape(summary_text)}</a></p>'
        if summary_text
        else ""
    )
    article_date = html.escape(article_date_value(article))
    attr_parts = [
        f'class="article-card {media_state_class}"',
        'data-article-card="true"',
        f'data-article-url="{escaped_url}"',
        f'data-article-title="{escaped_title}"',
        f'data-article-date="{article_date}"',
        f'data-article-region="{article_region}"',
        f'data-article-topics="{article_topics}"',
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
      {media_html}
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
    published = article_published_label(article) or "날짜 미상"
    publisher_icon = render_publisher_icon(article)
    return (
        '<div class="article-meta">'
        '<div class="article-meta-tags">'
        f'<span class="meta-pill primary">{html.escape(category_label)}</span>'
        f'<span class="meta-pill subtle">{html.escape(detail_label)}</span>'
        '</div>'
        '<div class="article-byline">'
        f'<span class="meta-item">{publisher_icon}{html.escape(source)}</span>'
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
    media_html = render_article_media(article)
    media_state_class = "has-media" if media_html else "no-media"
    return f"""
    <article class="article-card {media_state_class}" data-article-card="true" data-policy-card="true" data-policy-group="{article_group}" data-policy-scope="{article_scope}" data-policy-type="{article_type}" data-article-url="{escaped_url}" data-article-title="{escaped_title}" data-article-date="{article_date}" data-article-region="{article_region}" data-article-search="{article_search}">
      {media_html}
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


def render_compact_intro(
    kicker: str,
    description: str,
    media_key: str | None = None,
    *,
    title: str = "",
) -> str:
    media_config = PAGE_INTRO_ILLUSTRATIONS.get(media_key) if media_key else None
    media_html = render_card_illustration(
        media_config,
        slot_class="page-intro-media",
        img_class="page-intro-media-img",
    )
    media_class = " has-media" if media_html else ""
    title_html = f'<h1 class="page-intro-title">{html.escape(title)}</h1>' if title else ""
    return f"""
    <article class="page-intro-card{media_class}" data-media-host="page-intro">
      <div class="page-intro-content">
        <div class="page-intro-top">
          <span class="page-intro-badge">{html.escape(kicker)}</span>
        </div>
        {title_html}
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
    preferred_labels = ["청년 인구", "청년 실업률", "삶의 만족도", "고립·은둔 위기청년"]
    metric_by_label = {metric["label"]: metric for metric in YOUTH_METRICS}
    display_metrics = [metric_by_label[label] for label in preferred_labels if label in metric_by_label]
    if len(display_metrics) < 4:
        display_metrics.extend(metric for metric in YOUTH_METRICS if metric not in display_metrics)
    display_metrics = display_metrics[:4]

    metric_items = []
    for index, metric in enumerate(display_metrics):
        item_class = "youth-metric-item youth-metric-primary" if index == 0 else "youth-metric-item youth-metric-compact"
        primary_detail = (
            '<div class="youth-metric-scale" aria-hidden="true"><span></span></div>'
            if index == 0
            else ""
        )
        metric_items.append(
            f"""
            <article class="{item_class}">
              <span class="youth-metric-label">{html.escape(metric["label"])}</span>
              <strong class="youth-metric-value">{html.escape(metric["value"])}</strong>
              {primary_detail}
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
          <h2>핵심 지표 요약</h2>
          <p>오늘의 정책·뉴스 흐름을 볼 때 함께 확인할 공식 통계 기준값만 추려 놓았습니다.</p>
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


ARTICLE_EXPOSURE_DATE_FIELDS = (
    "publisher_published_at",
    "published_date",
    "portal_published_at",
)


def article_exposure_datetime(article: dict) -> datetime | None:
    for field in ARTICLE_EXPOSURE_DATE_FIELDS:
        value = article.get(field)
        parsed = parse_iso_datetime(str(value) if value else None)
        if parsed:
            return parsed
    return None


def article_exposure_timestamp(article: dict) -> float:
    parsed = article_exposure_datetime(article)
    return parsed.timestamp() if parsed else 0.0


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


def format_home_time_label(value: str | None) -> str:
    parsed = parse_iso_datetime(value)
    if not parsed:
        return "시각 대기"
    return parsed.strftime("%H:%M")


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
    parsed = article_exposure_datetime(article)
    return parsed.strftime("%Y-%m-%d") if parsed else ""


def article_topic_tags(article: dict, limit: int = 2) -> list[str]:
    tags = [normalize_inline_text(value) for value in article.get("topic_tags", [])]
    return [tag for tag in dict.fromkeys(tags) if tag][:limit]


def article_published_label(article: dict) -> str:
    for value in (
        article.get("publisher_published_at"),
        article.get("published_date"),
        article.get("portal_published_at"),
    ):
        parsed = parse_iso_datetime(value)
        if parsed:
            if any((parsed.hour, parsed.minute, parsed.second, parsed.microsecond)):
                return parsed.strftime("%Y-%m-%d %H:%M")
            return parsed.strftime("%Y-%m-%d")
        if value:
            return str(value)[:10]
    return ""


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
        normalize_inline_text(" ".join(article_topic_tags(article))),
        normalize_inline_text(" ".join(article.get("location_tags") or [])),
        news_region_label(article),
        *[normalize_inline_text(value) for value in article.get("display_badges", [])],
        *[normalize_inline_text(value) for value in extra_terms],
    ]
    return normalize_inline_text(" ".join(value for value in fields if value))


def collect_article_dates(articles: list[dict]) -> list[str]:
    return sorted({date for article in articles if (date := article_date_value(article))}, reverse=True)


def collect_news_topics(articles: list[dict]) -> list[str]:
    counts: dict[str, int] = {}
    for article in articles:
        for topic in article_topic_tags(article):
            counts[topic] = counts.get(topic, 0) + 1
    return sorted(counts, key=lambda topic: (-counts[topic], topic))


def news_region_label(article: dict) -> str:
    region = normalize_filter_region_label(article.get("region"))
    if not region or region == "전국":
        return "중앙"
    return region


def normalize_filter_region_label(value: str | None) -> str:
    region = normalize_inline_text(value)
    if not region:
        return ""
    if region in {"전국", "중앙"}:
        return region
    if region in LOCAL_REGION_NAME_ALIASES:
        return LOCAL_REGION_NAME_ALIASES[region]
    for entry in LOCAL_YOUTH_PLAN_REGIONS:
        if region == entry["name"] or region == f'{entry["name"]}시' or region == f'{entry["name"]}도':
            return entry["name"]
    return region


def collect_news_regions(articles: list[dict]) -> list[str]:
    counts: dict[str, int] = {}
    for article in articles:
        region = news_region_label(article)
        counts[region] = counts.get(region, 0) + 1

    extras = sorted(region for region in counts if region not in NEWS_FILTER_REGION_NAMES)
    return [*NEWS_FILTER_REGION_NAMES, *extras]


def collect_article_region_counts(articles: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for article in articles:
        region = news_region_label(article)
        if not region:
            continue
        counts[region] = counts.get(region, 0) + 1
    return counts


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
        *[(authority, authority) for authority in MAJOR_CENTRAL_POLICY_AUTHORITIES],
        ("국무조정실", "국무조정실"),
        ("국무총리비서실", "국무총리비서실"),
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
        region = normalize_filter_region_label(article.get("region"))
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
    <section class="section" id="filters">
      <article class="section-card filter-panel">
        <div class="filter-head">
          <h3>발표 필터</h3>
        </div>
        <div class="filter-stack">
          <div class="filter-group filter-group-group wide">
            <span class="filter-group-label">구분</span>
            <div class="filter-controls">{''.join(group_buttons)}</div>
          </div>
          <div class="filter-group filter-group-scope wide">
            <span class="filter-group-label" data-policy-scope-label="true">세부 구분</span>
            <div class="filter-controls">{''.join(scope_buttons)}</div>
          </div>
          <div class="filter-group filter-group-type wide">
            <span class="filter-group-label">유형</span>
            <div class="filter-controls">{''.join(type_buttons)}</div>
          </div>
          <div class="filter-group filter-group-search">
            <span class="filter-group-label">검색</span>
            <label class="filter-search-wrap">
              <input class="filter-search-input" type="search" data-policy-search-input="true" placeholder="기사 제목, 요약, 출처 검색">
            </label>
          </div>
          <div class="filter-group filter-group-date">
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


def render_announcement_filter_panel(
    articles: list[dict],
    *,
    group: str,
    scope_label: str,
    scope_values: list[str],
    search_placeholder: str,
    use_region_map: bool = False,
) -> str:
    scope_buttons = [
        '<button class="filter-button active" type="button" data-policy-filter="true" '
        'data-filter-group="scope" data-filter-value="all" data-policy-scope-button="true" data-scope-kind="all" '
        'aria-pressed="true">전체</button>'
    ]
    if not use_region_map:
        for value in scope_values:
            scope_buttons.append(
                f'<button class="filter-button" type="button" data-policy-filter="true" '
                f'data-filter-group="scope" data-filter-value="{html.escape(value)}" '
                f'data-policy-scope-button="true" data-scope-kind="{html.escape(group)}" aria-pressed="false">'
                f'{html.escape(value)}</button>'
            )
    region_map_html = (
        render_region_filter_map(filter_kind="policy", region_counts=collect_article_region_counts(articles))
        if use_region_map
        else ""
    )
    scope_controls_html = (
        f'<div class="filter-region-picker"><div class="filter-region-quick">{scope_buttons[0]}</div>'
        f'<div class="filter-region-map">{region_map_html}</div></div>'
        if use_region_map
        else f'<div class="filter-controls">{"".join(scope_buttons)}</div>'
    )

    type_buttons = [
        '<button class="filter-button active" type="button" data-policy-filter="true" '
        'data-filter-group="type" data-filter-value="all" aria-pressed="true">전체</button>'
    ]
    for label in collect_policy_types(articles):
        type_buttons.append(
            f'<button class="filter-button" type="button" data-policy-filter="true" '
            f'data-filter-group="type" data-filter-value="{html.escape(label)}" '
            f'aria-pressed="false">{html.escape(label)}</button>'
        )

    dates = collect_article_dates(articles)
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
    status_html = f'<div class="filter-status" data-policy-filter-status>전체 {len(articles)}건을 보고 있습니다.</div>'
    stack_class = "filter-stack filter-stack-map" if use_region_map else "filter-stack"
    map_column_open = '<div class="filter-map-column">' if use_region_map else ""
    map_column_close = '</div><div class="filter-control-column">' if use_region_map else ""
    control_column_close = "</div>" if use_region_map else ""
    status_in_head = status_html if use_region_map else ""
    status_after_stack = "" if use_region_map else status_html

    return f"""
    <section class="section" id="filters">
      <article class="section-card filter-panel{' has-region-map' if use_region_map else ''}">
        <div class="filter-head">
          <h3>자료 필터</h3>
          {status_in_head}
        </div>
        <div class="{stack_class}">
          {map_column_open}
          <div class="filter-group filter-group-scope filter-group-region-map wide">
            <span class="filter-group-label" data-policy-scope-label="true">{html.escape(scope_label)}</span>
            {scope_controls_html}
          </div>
          {map_column_close}
          <div class="filter-group filter-group-type wide">
            <span class="filter-group-label">유형</span>
            <div class="filter-controls">{''.join(type_buttons)}</div>
          </div>
          <div class="filter-group filter-group-search">
            <span class="filter-group-label">검색</span>
            <label class="filter-search-wrap">
              <input class="filter-search-input" type="search" data-policy-search-input="true" placeholder="{html.escape(search_placeholder)}">
            </label>
          </div>
          <div class="filter-group filter-group-date">
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
          {control_column_close}
        </div>
        {status_after_stack}
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
    <section class="section" id="filters">
      <article class="section-card filter-panel">
        <div class="filter-head">
          <h3>활동 필터</h3>
        </div>
        <div class="filter-stack">
          <div class="filter-group filter-group-group wide">
            <span class="filter-group-label">구분</span>
            <div class="filter-controls">{''.join(group_buttons)}</div>
          </div>
          <div class="filter-group filter-group-scope wide">
            <span class="filter-group-label" data-policy-scope-label="true">세부 구분</span>
            <div class="filter-controls">{''.join(scope_buttons)}</div>
          </div>
          <div class="filter-group filter-group-type wide">
            <span class="filter-group-label">활동</span>
            <div class="filter-controls">{''.join(type_buttons)}</div>
          </div>
          <div class="filter-group filter-group-search">
            <span class="filter-group-label">검색</span>
            <label class="filter-search-wrap">
              <input class="filter-search-input" type="search" data-policy-search-input="true" placeholder="기사 제목, 요약, 출처 검색">
            </label>
          </div>
          <div class="filter-group filter-group-date">
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


def with_display_badges(article: dict, *badges: str) -> dict:
    cleaned_badges = [str(badge).strip() for badge in badges if str(badge).strip()]
    if not cleaned_badges:
        return article
    existing_badges = [str(value).strip() for value in article.get("display_badges", []) if str(value).strip()]
    merged_badges = list(dict.fromkeys([*cleaned_badges, *existing_badges]))
    if merged_badges == existing_badges:
        return article
    tagged_article = dict(article)
    tagged_article["display_badges"] = merged_badges
    return tagged_article


def is_central_government_announcement(article: dict) -> bool:
    source_kind = normalize_inline_text(article.get("source_kind"))
    is_official_source = source_kind == "official" or bool(article.get("is_official_source"))
    if is_election_promise_article(article):
        return False
    if (article.get("campaign_political") or article.get("substantive_promise")) and not is_official_source:
        return False
    if home_campaign_political(article) and not is_official_source:
        return False
    if article.get("governance_scope") == "지자체" or article.get("is_regional_governance"):
        return False
    if not is_official_source:
        return False
    return source_kind == "official" or home_is_central_policy_source(article)


def central_government_announcement_text(article: dict) -> str:
    return normalize_inline_text(
        " ".join(
            str(value or "")
            for value in [
                article.get("title"),
                article.get("lead_text"),
                article.get("summary"),
                article.get("source"),
                article.get("source_name"),
                article.get("publisher_domain"),
                article.get("source_url"),
                article.get("publisher_url"),
                article.get("canonical_url"),
                article.get("url"),
            ]
        )
    )


def central_government_announcement_signal_text(article: dict) -> str:
    return normalize_inline_text(
        " ".join(
            str(value or "")
            for value in [
                article.get("title"),
                article.get("summary"),
                " ".join(article.get("issue_tags") or []),
                " ".join(article.get("topic_tags") or []),
            ]
        )
    )


def is_home_central_official_announcement(article: dict) -> bool:
    if not is_central_government_announcement(article):
        return False
    signal_text = central_government_announcement_signal_text(article).lower()
    if not any(keyword.lower() in signal_text for keyword in HOME_GOVERNMENT_TREND_YOUTH_KEYWORDS):
        return False
    text = central_government_announcement_text(article).lower()
    source_channel = normalize_inline_text(article.get("source_channel"))
    if source_channel in HOME_CENTRAL_OFFICIAL_ANNOUNCEMENT_CHANNELS:
        return True
    return any(keyword.lower() in text for keyword in HOME_CENTRAL_OFFICIAL_ANNOUNCEMENT_KEYWORDS)


def is_local_official_source(article: dict) -> bool:
    source_kind = normalize_inline_text(article.get("source_kind"))
    if source_kind in {"local", "regional_official", "municipal", "municipality"}:
        return True
    source_text = normalize_inline_text(
        " ".join(
            str(value)
            for value in [
                article.get("source"),
                article.get("source_name"),
                article.get("publisher_domain"),
                article.get("source_url"),
                article.get("publisher_url"),
            ]
            if value
        )
    )
    parsed_hosts = [
        urllib.parse.urlparse(str(article.get(key) or "")).netloc.lower()
        for key in ("source_url", "publisher_url", "canonical_url", "url")
    ]
    official_domains = [entry["domain"].lower() for entry in LOCAL_YOUTH_PLAN_REGIONS]
    if any(host and any(host == domain or host.endswith(f".{domain}") for domain in official_domains) for host in parsed_hosts):
        return True
    if any(keyword in source_text for keyword in LOCAL_OFFICIAL_SOURCE_HINTS):
        return True
    return False


def has_local_government_actor_signal(article: dict) -> bool:
    text = normalize_inline_text(
        " ".join(
            str(value or "")
            for value in [
                article.get("title"),
                article.get("lead_text"),
                article.get("summary"),
                article.get("source"),
                article.get("source_name"),
            ]
        )
    )
    return any(keyword in text for keyword in LOCAL_GOVERNMENT_ACTOR_KEYWORDS) or bool(
        LOCAL_ADMIN_UNIT_PATTERN.search(text)
    )


def is_local_government_announcement(article: dict) -> bool:
    if (
        is_election_promise_article(article)
        or home_campaign_political(article)
        or article.get("campaign_political")
        or article.get("substantive_promise")
    ):
        return False
    if article.get("is_official_source") and home_is_central_policy_source(article):
        return False
    if is_local_official_source(article):
        return True
    if not has_local_government_actor_signal(article):
        return False
    return is_local_policy_update(article)


def with_government_trend_badges(article: dict) -> dict:
    return with_display_badges(article, "정부 공식 발표")


def with_government_related_news_badges(article: dict) -> dict:
    return with_display_badges(article, "중앙정부 관련 뉴스")


def with_local_trend_badges(article: dict) -> dict:
    if is_local_official_source(article):
        return with_display_badges(article, "지자체 공식 발표")
    return with_display_badges(article, "지자체 발표 보도")


def with_local_news_badges(article: dict) -> dict:
    return with_display_badges(article, "지자체·청년 뉴스", local_region_label_for_article(article))


def local_government_article_text(article: dict) -> str:
    return normalize_inline_text(
        " ".join(
            str(value or "")
            for value in [
                article.get("title"),
                article.get("lead_text"),
                article.get("summary"),
                article.get("section"),
                article.get("source"),
                article.get("source_name"),
                article.get("publisher_domain"),
                " ".join(article.get("display_badges") or []),
            ]
        )
    )


def local_region_label_for_article(article: dict) -> str:
    explicit_region = normalize_filter_region_label(article.get("region_name") or article.get("region"))
    if explicit_region and explicit_region not in {"전국", "중앙"}:
        return explicit_region
    region = news_region_label(article)
    if region and region != "중앙":
        return region
    text = local_government_article_text(article)
    for entry in LOCAL_YOUTH_PLAN_REGIONS:
        if entry["full_name"] in text or entry["name"] in text or f'{entry["name"]}시' in text or f'{entry["name"]}도' in text:
            return entry["name"]
    return "지역 미상"


def is_local_official_announcement(article: dict) -> bool:
    if not is_local_government_announcement(article):
        return False
    return is_local_official_source(article)


def is_home_local_official_announcement(article: dict) -> bool:
    if (
        is_election_promise_article(article)
        or home_campaign_political(article)
        or article.get("campaign_political")
        or article.get("substantive_promise")
    ):
        return False
    if article.get("is_official_source") and home_is_central_policy_source(article):
        return False
    if not is_local_official_source(article):
        return False

    source_channel = normalize_inline_text(article.get("source_channel"))
    if source_channel == "policy_plan":
        return False
    if source_channel in HOME_LOCAL_OFFICIAL_ANNOUNCEMENT_CHANNELS:
        return True

    source_kind = normalize_inline_text(article.get("source_kind"))
    if source_kind in {"local", "regional_official", "municipal", "municipality"}:
        return True

    text = local_government_article_text(article)
    return any(keyword in text for keyword in HOME_LOCAL_OFFICIAL_ANNOUNCEMENT_KEYWORDS)


def is_local_youth_press_release(article: dict) -> bool:
    if normalize_inline_text(article.get("source_channel")) != "press_release":
        return False
    text = local_government_article_text(article)
    if "청년" not in text:
        return False
    return normalize_inline_text(article.get("source_kind")) == "local" or any(
        keyword in text for keyword in LOCAL_PRESS_RELEASE_KEYWORDS
    )


def is_local_youth_plan_document(article: dict) -> bool:
    if (
        is_election_promise_article(article)
        or home_campaign_political(article)
        or article.get("campaign_political")
        or article.get("substantive_promise")
    ):
        return False
    if article.get("is_official_source") and home_is_central_policy_source(article):
        return False
    if not is_local_official_source(article):
        return False
    text = local_government_article_text(article)
    if normalize_inline_text(article.get("source_channel")) == "policy_plan":
        return True
    return "청년" in text and any(keyword in text for keyword in LOCAL_POLICY_PLAN_KEYWORDS)


def is_local_youth_news_article(article: dict) -> bool:
    if normalize_inline_text(article.get("source_kind")) != "news":
        return False
    if (
        is_election_promise_article(article)
        or home_campaign_political(article)
        or article.get("campaign_political")
        or article.get("substantive_promise")
    ):
        return False
    text = normalize_inline_text(
        " ".join(
            str(value or "")
            for value in [article.get("title"), article.get("lead_text"), article.get("summary")]
        )
    )
    if "청년" not in text:
        return False
    return any(keyword in text for keyword in LOCAL_GOVERNMENT_ACTOR_KEYWORDS) or bool(
        LOCAL_ADMIN_UNIT_PATTERN.search(text)
    )


def with_local_press_release_badges(article: dict) -> dict:
    return with_display_badges(article, "청년 보도자료", local_region_label_for_article(article))


def with_local_plan_badges(article: dict) -> dict:
    return with_display_badges(article, "기본·시행계획", local_region_label_for_article(article))


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


def render_news_filter_panel(
    regions: list[str],
    topics: list[str],
    dates: list[str],
    total_count: int,
    *,
    use_region_map: bool = True,
    filter_title: str = "기사 필터",
    region_counts: dict[str, int] | None = None,
) -> str:
    region_buttons = [
        '<button class="filter-button active" type="button" data-news-filter="true" '
        'data-filter-group="region" data-filter-value="all" aria-pressed="true">전체</button>'
    ]
    region_button_values = ["중앙"] if use_region_map and "중앙" in regions else regions
    for region in region_button_values:
        if region == "all":
            continue
        region_buttons.append(
            f'<button class="filter-button" type="button" data-news-filter="true" '
            f'data-filter-group="region" data-filter-value="{html.escape(region)}" '
            f'aria-pressed="false">{html.escape(region)}</button>'
        )
    region_map_html = (
        render_region_filter_map(filter_kind="news", region_counts=region_counts or {})
        if use_region_map
        else ""
    )
    region_controls_html = (
        f'<div class="filter-region-picker"><div class="filter-region-quick">{"".join(region_buttons)}</div>'
        f'<div class="filter-region-map">{region_map_html}</div></div>'
        if use_region_map
        else f'<div class="filter-controls">{"".join(region_buttons)}</div>'
    )

    topic_buttons = [
        '<button class="filter-button active" type="button" data-news-filter="true" '
        'data-filter-group="topic" data-filter-value="all" aria-pressed="true">전체</button>'
    ]
    for topic in topics:
        topic_buttons.append(
            f'<button class="filter-button" type="button" data-news-filter="true" '
            f'data-filter-group="topic" data-filter-value="{html.escape(topic)}" '
            f'aria-pressed="false">#{html.escape(topic)}</button>'
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
    status_html = f'<div class="filter-status" data-news-filter-status>전체 {total_count}건을 보고 있습니다.</div>'
    stack_class = "filter-stack filter-stack-map" if use_region_map else "filter-stack"
    map_column_open = '<div class="filter-map-column">' if use_region_map else ""
    map_column_close = '</div><div class="filter-control-column">' if use_region_map else ""
    control_column_close = "</div>" if use_region_map else ""
    status_in_head = status_html if use_region_map else ""
    status_after_stack = "" if use_region_map else status_html

    return f"""
    <section class="section" id="filters">
      <article class="section-card filter-panel news-filter-panel{' has-region-map' if use_region_map else ''}">
        <div class="filter-head">
          <h3>{html.escape(filter_title)}</h3>
          {status_in_head}
        </div>
        <div class="{stack_class}">
          {map_column_open}
          <div class="filter-group filter-group-region filter-group-region-map wide">
            <span class="filter-group-label">지역</span>
            {region_controls_html}
          </div>
          {map_column_close}
          <div class="filter-group filter-group-topic wide">
            <span class="filter-group-label">주제</span>
            <div class="filter-controls">{''.join(topic_buttons)}</div>
          </div>
          <div class="filter-group filter-group-search">
            <span class="filter-group-label">검색</span>
            <label class="filter-search-wrap">
              <input class="filter-search-input" type="search" data-news-search-input="true" placeholder="기사 제목, 요약, 출처 검색">
            </label>
          </div>
          <div class="filter-group filter-group-date">
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
          {control_column_close}
        </div>
        {status_after_stack}
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
    text = normalize_inline_text(
        article.get("youth_excerpt")
        or extract_youth_preview_text(article, limit=limit * 2)
        or article.get("summary")
        or article.get("lead_text")
        or ""
    )
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
    topics = article_topic_tags(article)
    meta_labels = [*topics, region] if topics else [category, region]
    meta_pills = "".join(
        f'<span class="meta-pill {"primary" if index == 0 else "subtle"}">{html.escape(label)}</span>'
        for index, label in enumerate(dict.fromkeys(label for label in meta_labels if label))
    )
    source = format_source_label(article.get("source") or article.get("source_name"))
    published = article_published_label(article) or "날짜 미상"
    publisher_icon = render_publisher_icon(article)
    return (
        '<div class="article-meta">'
        '<div class="article-meta-tags">'
        f'{meta_pills}'
        '</div>'
        '<div class="article-byline">'
        f'<span class="meta-item">{publisher_icon}{html.escape(source)}</span>'
        '<span class="meta-divider" aria-hidden="true">•</span>'
        f'<span class="meta-item">{html.escape(published)}</span>'
        '</div>'
        '</div>'
    )


def compact_article_meta(article: dict) -> str:
    bits = []
    source = format_source_label(article.get("source") or article.get("source_name"))
    published = article_published_label(article)
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
    return (
        2 if is_highlighted else 1 if editorial_decision == "include" else 0,
        article_exposure_timestamp(article),
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
        parsed_dates = [article_exposure_datetime(article) for article in articles]
        parsed_dates = [value for value in parsed_dates if value is not None]
        reference_dt = max(parsed_dates) if parsed_dates else None
    if reference_dt is None:
        return []

    threshold = reference_dt - timedelta(hours=max_age_hours)
    filtered: list[dict] = []
    for article in articles:
        published_dt = article_exposure_datetime(article)
        if published_dt is None:
            continue
        if published_dt >= threshold:
            filtered.append(article)
    return sort_articles_by_recency(filtered)


def latest_article_timestamp(articles: list[dict], fallback: str) -> str:
    sorted_articles = sort_articles_by_recency(articles)
    if sorted_articles:
        published_dt = article_exposure_datetime(sorted_articles[0])
        if published_dt:
            return published_dt.isoformat()
    return fallback


def count_articles_on_reference_day(articles: list[dict], reference_time: str | None) -> int:
    reference_dt = parse_iso_datetime(reference_time)
    if reference_dt is None:
        parsed_dates = [article_exposure_datetime(article) for article in articles]
        parsed_dates = [value for value in parsed_dates if value is not None]
        reference_dt = max(parsed_dates) if parsed_dates else None
    if reference_dt is None:
        return 0

    seen_keys: set[str] = set()
    total = 0
    for article in articles:
        published_dt = article_exposure_datetime(article)
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
    latest_day = article_date_value(sorted_articles[0])
    if latest_day:
        same_day_articles = [
            article for article in sorted_articles if article_date_value(article) == latest_day
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
                if (published_dt := article_exposure_datetime(article)) is not None and published_dt > reference_dt
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
        f"뉴스 모음 {len(recent_news_articles)}건 · 정부 동향 {len(official_policy_articles)}건 · "
        f"참여기구 {participation_count}건을 이번 화면에 반영했습니다."
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
HOME_TOPIC_FILTER_LABELS = {"취업", "주거", "노동", "금융", "청년센터", "모집", "복지", "창업"}


def normalize_home_hot_keyword(value: object) -> str:
    keyword = normalize_inline_text(value)
    if not keyword:
        return ""
    return HOME_HOT_KEYWORD_ALIASES.get(keyword, keyword)


def home_hot_keyword_href(keyword: str) -> str:
    normalized = normalize_inline_text(keyword)
    if normalized in HOME_TOPIC_FILTER_LABELS:
        return f"news.html?topic={urllib.parse.quote(normalized)}"
    return f"news.html?q={urllib.parse.quote(normalized)}"


def home_topic_category_href(topic: str) -> str:
    return f"news.html?topic={urllib.parse.quote(normalize_inline_text(topic))}"


def articles_on_reference_day(articles: list[dict], reference_time: str | None) -> list[dict]:
    reference_dt = parse_iso_datetime(reference_time)
    if reference_dt is None:
        parsed_dates = [article_exposure_datetime(article) for article in articles]
        parsed_dates = [value for value in parsed_dates if value is not None]
        reference_dt = max(parsed_dates) if parsed_dates else None
    if reference_dt is None:
        return []

    day_articles: list[dict] = []
    seen_keys: set[str] = set()
    for article in articles:
        published_dt = article_exposure_datetime(article)
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
        article_keywords.extend(article_topic_tags(article))
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


def build_home_topic_categories(
    articles: list[dict],
    reference_time: str | None,
    *,
    limit: int = HOME_HOT_KEYWORD_LIMIT,
    max_age_hours: int = HOME_CATEGORY_WINDOW_HOURS,
) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for article in filter_recent_articles(articles, reference_time, max_age_hours):
        if not is_home_latest_news_candidate(article):
            continue
        for topic in dict.fromkeys(article_topic_tags(article)):
            counts[topic] = counts.get(topic, 0) + 1
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
    published_dt = article_exposure_datetime(article)
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
    if home_article_age_hours(article, reference_dt) > HOME_TODAY_MAX_AGE_HOURS:
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
    if home_article_age_hours(article, reference_dt) > HOME_TODAY_MAX_AGE_HOURS:
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
    age_hours = home_article_age_hours(article, reference_dt)
    if article.get("_home_primary_candidate") and age_hours <= HOME_TODAY_MAX_AGE_HOURS:
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


def is_home_latest_news_candidate(article: dict) -> bool:
    if article.get("is_official_source") or article.get("source_kind") == "official":
        return False
    if is_election_promise_article(article):
        return False
    if article.get("is_noise"):
        return False
    if article.get("article_type") == "opinion":
        return False
    if is_publicly_excluded(article):
        return False
    return True


def home_latest_news_sort_key(article: dict) -> tuple[int, float]:
    published_dt = article_exposure_datetime(article)
    if published_dt is None:
        return (0, 0.0)
    return (1, published_dt.timestamp())


def build_home_latest_news_candidate_articles(
    articles: list[dict],
    highlighted_article: dict | None,
) -> list[dict]:
    highlight_key = home_article_key(highlighted_article) if highlighted_article else ""
    candidates: list[dict] = []
    seen_keys: set[str] = set()
    for article in articles:
        article_key = home_article_key(article)
        if not article_key or article_key == highlight_key or article_key in seen_keys:
            continue
        if not is_home_latest_news_candidate(article):
            continue
        seen_keys.add(article_key)
        candidates.append(article)
    return sorted(candidates, key=home_latest_news_sort_key, reverse=True)


def build_home_latest_news_articles(
    articles: list[dict],
    highlighted_article: dict | None,
    *,
    limit: int = HOME_DAILY_LIMIT,
) -> list[dict]:
    return build_home_latest_news_candidate_articles(articles, highlighted_article)[:limit]


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
        if article_date := article_date_value(article):
            meta_bits.append(article_date)
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
    parsed_published = article_exposure_datetime(article)
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
                article_date_value(article),
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
                        article_date_value(government_articles[0]),
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
                        article_date_value(regional_articles[0]),
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
                        article_date_value(public_articles[0]),
                    ]
                    if bit
                ),
            )
        )
    else:
        items.append(("공공기관 참여·협의", "현재 등록된 항목이 없습니다."))

    return items[:3]


def home_regional_policy_region(article: dict) -> str:
    region = news_region_label(article)
    if not region or region in {"전국", "중앙"}:
        return ""
    return region


def home_regional_policy_focus(article: dict) -> str:
    policy_type = policy_type_label(article)
    if policy_type and policy_type != "기타":
        return policy_type
    tags = article_topic_tags(article, limit=1)
    if tags:
        return tags[0]
    if article.get("is_hub_candidate"):
        return "참여기구"
    return "지자체 동향"


def home_regional_policy_text(article: dict) -> str:
    return normalize_inline_text(
        " ".join(
            str(value or "")
            for value in [
                article.get("title"),
                article.get("summary"),
                article.get("lead_text"),
                article.get("source"),
                article.get("hub_owner_label"),
            ]
        )
    )


def home_has_regional_public_actor(article: dict) -> bool:
    text = home_regional_policy_text(article)
    actor_keywords = (
        *LOCAL_GOVERNMENT_ACTOR_KEYWORDS,
        "서울시",
        "부산시",
        "대구시",
        "인천시",
        "광주시",
        "대전시",
        "울산시",
        "세종시",
        "강원도",
        "충북도",
        "충남도",
        "전북도",
        "전남도",
        "경북도",
        "경남도",
        "제주도",
        "경제진흥원",
        "문화재단",
        "문화관광공사",
        "일자리재단",
        "청년센터",
    )
    return any(keyword in text for keyword in actor_keywords)


def home_has_youth_regional_signal(article: dict) -> bool:
    if article.get("has_direct_helpful_youth_signal") or article.get("has_youth_content_signal"):
        return True
    if article_topic_tags(article, limit=3) or article.get("issue_tags"):
        return True
    return "청년" in home_regional_policy_text(article)


def home_is_regional_roundup_article(article: dict) -> bool:
    title = clean_article_title(article.get("title"))
    return any(marker in title for marker in ("[패트롤]", "[은행가]", " 外", "외]"))


def home_is_central_policy_source(article: dict) -> bool:
    authority = policy_authority_label(article)
    source_text = home_regional_policy_text(article)
    central_keywords = (*MAJOR_CENTRAL_POLICY_AUTHORITIES, "국무조정실", "국무총리비서실", "정책브리핑")
    return any(keyword in authority or keyword in source_text for keyword in central_keywords)


def is_home_regional_policy_candidate(article: dict) -> bool:
    if not home_regional_policy_region(article):
        return False
    if is_election_promise_article(article) or home_campaign_political(article):
        return False
    if home_is_regional_roundup_article(article):
        return False
    if not home_has_youth_regional_signal(article):
        return False
    if article.get("governance_scope") == "지자체" or article.get("is_regional_governance"):
        return True
    if article.get("is_official_source") and home_is_central_policy_source(article):
        return False
    if not home_has_regional_public_actor(article):
        return False
    if article.get("is_official_source") or article.get("is_hub_candidate") or policy_type_label(article) != "기타":
        return True

    text = home_regional_policy_text(article)
    return any(keyword in text for keyword in LOCAL_POLICY_CORE_KEYWORDS)


def home_application_policy_text(article: dict) -> str:
    body = normalize_inline_text(article.get("body_text"))
    return normalize_inline_text(
        " ".join(
            str(value or "")
            for value in [
                article.get("title"),
                article.get("summary"),
                article.get("lead_text"),
                body[:2600],
                article.get("source"),
                article.get("source_name"),
                " ".join(article.get("topic_tags") or []),
                " ".join(article.get("issue_tags") or []),
            ]
        )
    )


def home_application_signal_text(article: dict) -> str:
    return normalize_inline_text(
        " ".join(
            str(value or "")
            for value in [
                article.get("title"),
                article.get("summary"),
                article.get("lead_text"),
                article.get("source"),
                article.get("source_name"),
                " ".join(article.get("topic_tags") or []),
                " ".join(article.get("issue_tags") or []),
            ]
        )
    )


def home_has_application_policy_signal(article: dict) -> bool:
    text = home_application_signal_text(article)
    has_action = any(keyword in text for keyword in HOME_APPLICATION_POLICY_ACTION_KEYWORDS)
    has_benefit = any(keyword in text for keyword in HOME_APPLICATION_POLICY_BENEFIT_KEYWORDS)
    policy_type = policy_type_label(article)

    if not has_action:
        return False
    if policy_type in {"모집", "지원사업"}:
        return True
    if has_benefit:
        return True
    return any(lane == "institution_program" for lane in article.get("ops_radar_lanes") or [])


def is_home_application_policy_candidate(article: dict) -> bool:
    if home_campaign_political(article) or article.get("campaign_political") or article.get("substantive_promise"):
        return False
    if home_is_regional_roundup_article(article):
        return False
    if not article_target_url(article):
        return False
    if not home_has_youth_regional_signal(article):
        return False
    if not home_has_application_policy_signal(article):
        return False
    if is_central_government_announcement(article):
        return True
    if is_local_government_announcement(article):
        return True
    if is_home_regional_policy_candidate(article):
        return True
    return False


def home_application_period_label(article: dict) -> str:
    text = home_application_policy_text(article)
    if "상시" in text and any(keyword in text for keyword in ("신청", "접수", "모집")):
        return "상시 접수"
    for pattern in HOME_APPLICATION_PERIOD_PATTERNS:
        match = pattern.search(text)
        if match:
            return normalize_inline_text(match.group(1))
    return "원문에서 확인"


def home_application_source_label(article: dict) -> str:
    if is_central_government_announcement(article):
        return "정부 발표"
    if is_local_official_source(article):
        return "지자체 공식"
    if is_local_government_announcement(article) or is_home_regional_policy_candidate(article):
        return "지자체 발표"
    return "정책 공고"


def home_application_event_key(article: dict) -> str:
    text = home_application_signal_text(article)
    for keyword in HOME_APPLICATION_EVENT_KEYWORDS:
        if keyword in text:
            return keyword

    title = clean_article_title(article.get("title"))
    title = re.sub(r"\s*[<|].*$", "", title)
    title = re.sub(r"[\[\](){}\"'‘’“”·….,:;!?]", " ", title)
    stopwords = {"보도자료", "안내", "공고", "모집", "접수", "신청", "신규", "대표홈페이지"}
    tokens = [token for token in normalize_inline_text(title).split() if token not in stopwords]
    return " ".join(tokens[:6]) or article_identity_key(article)


def home_application_display_title(article: dict, limit: int = 78) -> str:
    title = clean_article_title(article.get("title"))
    for marker in (" < ", " | "):
        if marker in title:
            title = title.split(marker, 1)[0].strip()
    return truncate_text(title, limit)


def home_application_summary(article: dict, limit: int = 118) -> str:
    source = normalize_inline_text(format_source_label(article.get("source") or article.get("source_name")))
    title = home_application_display_title(article, limit=140)
    for value in (
        article.get("youth_excerpt"),
        article.get("lead_text"),
        article.get("summary"),
        normalize_inline_text(article.get("body_text"))[:600],
    ):
        text = normalize_inline_text(value)
        for marker in ("본문으로 바로가기", "주메뉴 바로가기", "서브메뉴 바로가기", "푸터 바로가기", "메뉴 바로가기"):
            while text.startswith(marker):
                text = text[len(marker):].strip()
        if title and text.startswith(title):
            text = text[len(title):].strip(" -·:|")
        if not text:
            continue
        if text == source or text in {article.get("source"), article.get("source_name")}:
            continue
        if "홈페이지입니다" in text or len(text) < 12:
            continue
        return truncate_text(text, limit)
    return "신청 조건과 제출 방식은 원문에서 확인해 주세요."


def home_application_policy_score(article: dict) -> int:
    text = home_application_signal_text(article)
    score = 0
    if is_central_government_announcement(article):
        score += 22
    elif is_local_official_source(article):
        score += 18
    elif is_local_government_announcement(article):
        score += 14
    if policy_type_label(article) == "모집":
        score += 10
    elif policy_type_label(article) == "지원사업":
        score += 7
    if home_application_period_label(article) != "원문에서 확인":
        score += 8
    for keyword in ("신청", "접수", "모집", "공고"):
        if keyword in text:
            score += 3
    if any(lane == "institution_program" for lane in article.get("ops_radar_lanes") or []):
        score += 4
    return score


def build_home_application_policy_candidates(
    articles: list[dict],
    reference_time: str | None,
    *,
    limit: int = HOME_APPLICATION_POLICY_LIMIT,
) -> list[dict]:
    candidates = [
        article
        for article in articles
        if is_home_application_policy_candidate(article)
    ]
    recent_candidates = sorted(
        filter_recent_articles(candidates, reference_time, HOME_APPLICATION_POLICY_MAX_AGE_HOURS),
        key=lambda article: (home_application_policy_score(article), article_sort_key(article)[1]),
        reverse=True,
    )
    deduped: list[dict] = []
    seen_keys: set[str] = set()
    seen_event_keys: set[str] = set()
    for article in recent_candidates:
        key = article_identity_key(article)
        event_key = home_application_event_key(article)
        if key in seen_keys or event_key in seen_event_keys:
            continue
        seen_keys.add(key)
        seen_event_keys.add(event_key)
        deduped.append(article)

    return deduped[:limit]


def build_home_regional_policy_candidates(articles: list[dict], reference_time: str | None) -> list[dict]:
    candidates = [article for article in articles if is_home_regional_policy_candidate(article)]
    return filter_recent_articles(candidates, reference_time, HOME_REGIONAL_POLICY_MAX_AGE_HOURS)


def build_home_regional_policy_summaries(
    articles: list[dict],
    reference_time: str | None,
    *,
    limit: int = HOME_REGIONAL_POLICY_LIMIT,
) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    seen_keys: set[str] = set()
    for article in build_home_regional_policy_candidates(articles, reference_time):
        key = article_identity_key(article)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        region = home_regional_policy_region(article)
        if not region:
            continue
        grouped.setdefault(region, []).append(article)

    summaries: list[dict] = []
    for region, region_articles in grouped.items():
        sorted_region_articles = sort_articles_by_recency(region_articles)
        latest = sorted_region_articles[0]
        focus_counts: dict[str, int] = {}
        for article in sorted_region_articles:
            focus = home_regional_policy_focus(article)
            focus_counts[focus] = focus_counts.get(focus, 0) + 1
        focus_label = sorted(focus_counts, key=lambda label: (-focus_counts[label], label))[0]
        summaries.append(
            {
                "region": region,
                "count": len(sorted_region_articles),
                "focus": focus_label,
                "latest_date": article_date_value(latest) or "날짜 미상",
                "latest_title": display_article_title(latest, limit=52),
                "latest_url": article_target_url(latest),
                "sort_key": article_sort_key(latest),
            }
        )

    return sorted(summaries, key=lambda item: (item["count"], item["sort_key"]), reverse=True)[:limit]


def render_home_regional_policy_status(articles: list[dict], reference_time: str | None) -> str:
    summaries = build_home_regional_policy_summaries(articles, reference_time)
    if not summaries:
        return (
            '<article class="home-region-empty">'
            '<h3>지역별로 분리할 정책·동향 데이터가 아직 없습니다.</h3>'
            '<p>지자체 발표나 지역 기사 수집량이 늘어나면 이 영역이 자동으로 채워집니다.</p>'
            '</article>'
        )

    rows = []
    for summary in summaries:
        detail = "원문"
        if summary["latest_url"]:
            detail = (
                f'<a class="home-region-link" href="{html.escape(summary["latest_url"], quote=True)}" '
                f'target="_blank" rel="noreferrer">원문</a>'
            )
        rows.append(
            "<tr>"
            f'<th scope="row">{html.escape(summary["region"])}</th>'
            f'<td><strong>{summary["count"]}건</strong><span>{PUBLIC_ARCHIVE_LABEL}</span></td>'
            f'<td><span class="home-region-focus">{html.escape(summary["focus"])}</span></td>'
            f'<td><span>{html.escape(summary["latest_date"])}</span><small>{html.escape(summary["latest_title"])}</small></td>'
            f"<td>{detail}</td>"
            "</tr>"
        )

    return (
        '<div class="home-region-table-wrap">'
        '<table class="home-region-table">'
        '<thead><tr><th scope="col">지역</th><th scope="col">항목 수</th><th scope="col">주요 분야</th><th scope="col">최신 업데이트</th><th scope="col">상세</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
        '</div>'
    )


def render_home_application_policies(articles: list[dict], reference_time: str | None) -> str:
    candidates = build_home_application_policy_candidates(articles, reference_time)
    if not candidates:
        return (
            '<article class="home-application-panel" id="application-policies" aria-labelledby="application-policies-title">'
            '<div class="home-application-head">'
            '<h2 id="application-policies-title">지금 모집 중인 청년정책</h2>'
            '<a class="mini-link" href="plans.html#main-list">지자체 동향 보기</a>'
            '</div>'
            '<div class="home-application-empty">'
            '<strong>신청형 정책 후보가 아직 충분하지 않습니다.</strong>'
            '<span>새 공고가 수집되면 기간과 원문 링크가 이 영역에 먼저 표시됩니다.</span>'
            '</div>'
            '</article>'
        )

    cards = []
    for article in candidates:
        title = html.escape(home_application_display_title(article, limit=78))
        source_label = html.escape(home_application_source_label(article))
        policy_type = html.escape(home_regional_policy_focus(article))
        region = home_regional_policy_region(article) or news_region_label(article)
        region_label = html.escape(region if region and region != "중앙" else policy_authority_label(article))
        date_label = html.escape(article_date_value(article) or "날짜 미상")
        period_label = html.escape(home_application_period_label(article))
        url = html.escape(article_target_url(article), quote=True)
        summary = html.escape(home_application_summary(article, limit=118))
        cards.append(
            f"""
            <article class="home-application-card">
              <div class="home-application-main">
                <div class="home-application-tags">
                  <span>{source_label}</span>
                  <span>{policy_type}</span>
                  <span>{region_label}</span>
                </div>
                <h4>{title}</h4>
                <p>{summary}</p>
                <div class="home-application-meta">
                  <span>게시 {date_label}</span>
                  <span>{html.escape(format_source_label(article.get("source") or article.get("source_name")))}</span>
                </div>
              </div>
              <div class="home-application-period">
                <span>신청 기간</span>
                <strong>{period_label}</strong>
                <a class="home-application-link" href="{url}" target="_blank" rel="noreferrer">신청·공고 보기</a>
              </div>
            </article>
            """
        )

    return f"""
    <article class="home-application-panel" id="application-policies" aria-labelledby="application-policies-title">
      <div class="home-application-head">
        <h2 id="application-policies-title">지금 모집 중인 청년정책</h2>
        <div class="home-application-head-links">
          <a class="mini-link" href="policies.html#main-list">정부 동향</a>
          <a class="mini-link" href="plans.html#main-list">지자체 동향</a>
        </div>
      </div>
      <div class="home-application-grid">{''.join(cards)}</div>
    </article>
    """


def render_home_research_resources() -> str:
    items = []
    for resource in HOME_RESEARCH_RESOURCES:
        items.append(
            f"""
            <a class="home-report-row" href="{html.escape(resource["href"], quote=True)}" target="_blank" rel="noreferrer">
              <span class="home-report-tag">{html.escape(resource["tag"])}</span>
              <strong>{html.escape(resource["title"])}</strong>
              <span class="home-report-meta">{html.escape(resource["basis"])} · {html.escape(resource["organization"])}</span>
              <p>{html.escape(resource["description"])}</p>
            </a>
            """
        )
    return "".join(items)


def render_home_policy_research_board(articles: list[dict], reference_time: str | None) -> str:
    return f"""
    <section class="section home-data-board home-research-section" id="research-resources">
      <div class="section-head">
        <div>
          <h2>주요 연구·통계 자료</h2>
          <p>청년 정책을 이해할 때 함께 볼 만한 공식 조사, 통계, 연구 자료입니다.</p>
        </div>
        <a class="mini-link" href="tools.html#stats-research-links">모든 자료 보기</a>
      </div>
      <div class="home-data-board-grid home-research-only-grid">
        <aside class="home-research-block" aria-label="주요 연구·통계 자료">
          <div class="home-report-list">
            {render_home_research_resources()}
          </div>
        </aside>
      </div>
    </section>
    """


def build_menu_updates(articles: list[dict], classified_articles: list[dict], status: dict) -> list[dict]:
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    news_articles = [article for article in articles if not article.get("is_official_source")] or list(articles)
    policy_articles = [article for article in articles if article.get("is_official_source")]
    hub_articles = filter_hub_articles(classified_articles)

    return [
        {
            "eyebrow": "01 뉴스 모음",
            "title": "청년 뉴스 모음",
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
            "link_label": "뉴스 모음 보기",
        },
        {
            "eyebrow": "02 정부 동향",
            "title": "정부 공식 발표",
            "href": "policies.html",
            "description": "정부 발표와 공식 정책 자료를 날짜순으로 확인할 수 있습니다.",
            "article_basis_label": "최신 정부 발표 기준",
            "article_basis_time": latest_article_timestamp(policy_articles, page_updated_at),
            "page_basis_label": "페이지 반영",
            "page_basis_time": page_updated_at,
            "items": summarize_menu_items(
                policy_articles,
                [("최근 발표", "공식 발표가 이 영역에 표시됩니다.")],
            ),
            "link_label": "정부 동향 바로가기",
        },
        {
            "eyebrow": "03 참여기구",
            "title": "청년 참여기구",
            "href": "hub.html",
            "description": "정부와 지역의 청년 활동 소식을 볼 수 있습니다.",
            "article_basis_label": "허브 연관 기사 기준",
            "article_basis_time": latest_article_timestamp(hub_articles, page_updated_at),
            "page_basis_label": "페이지 반영",
            "page_basis_time": page_updated_at,
            "items": build_hub_menu_items(classified_articles),
            "link_label": "참여기구 보기",
        },
        {
            "eyebrow": "04 연구·문헌",
            "title": "연구·문헌 자료",
            "href": "tools.html",
            "description": "정책을 이해하고 인용할 때 필요한 연구·통계·법령 자료입니다.",
            "article_basis_label": "자료 업데이트 기준",
            "article_basis_time": page_updated_at,
            "page_basis_label": "페이지 반영",
            "page_basis_time": page_updated_at,
            "items": [
                ("공식 자료 바로가기", "정부와 기관이 제공하는 청년 정책·조사 자료를 한곳에서 봅니다."),
                ("연구·통계 링크", "보고서와 통계 자료를 빠르게 엽니다."),
            ],
            "link_label": "연구·문헌 보기",
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
    highlighted_article = next(
        (article for article in selected_articles if article.get("editorial_is_highlighted")),
        None,
    )
    latest_home_news_candidates = merge_home_candidate_articles(selected_news_articles, all_news_articles)
    latest_home_news_total = len(
        build_home_latest_news_candidate_articles(
            latest_home_news_candidates,
            highlighted_article,
        )
    )
    today_articles = build_home_latest_news_articles(
        latest_home_news_candidates,
        highlighted_article,
    )
    government_trend_articles = build_government_trend_articles(all_articles, page_updated_at)
    home_topic_categories = build_home_topic_categories(latest_home_news_candidates, page_updated_at)
    home_date_label = format_home_date_label(page_updated_at)
    home_time_label = format_home_time_label(page_updated_at)
    lead_message = "청년정책 흐름이 조금 더 선명해지도록, 꼭 봐야 할 뉴스와 중앙정부 공식 발표를 한곳에 모았습니다."
    home_category_links = "".join(
        f'<a class="home-keyword-chip" href="{html.escape(home_topic_category_href(topic))}">#{html.escape(topic)}</a>'
        for topic, _ in home_topic_categories
    )
    home_categories_html = (
        '<div class="home-keyword-strip" aria-label="최근 많이 잡힌 카테고리">'
        f'<div class="home-keyword-list">{home_category_links}</div>'
        '</div>'
        if home_category_links
        else ""
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
        '<div class="home-urgent-text"><strong>최근 올라온 청년 뉴스가 아직 없습니다.</strong>'
        '<span class="home-urgent-meta">새 청년 뉴스가 들어오면 이 영역이 먼저 채워집니다.</span></div></div></article>'
    )
    policy_briefing_html = "".join(
        render_home_news_item(index, article)
        for index, article in enumerate(government_trend_articles[:HOME_DAILY_LIMIT], start=1)
    ) or (
        '<article class="home-urgent-item"><div class="home-urgent-link"><span class="home-urgent-rank">00</span>'
        '<div class="home-urgent-text"><strong>확인할 정부 동향이 아직 없습니다.</strong>'
        '<span class="home-urgent-meta">중앙정부 공식 보도자료가 들어오면 이 영역이 먼저 채워집니다.</span></div></div></article>'
    )
    overview_stats_html = "".join(
        f'<article class="{card_class}"><span class="home-glance-label">{label}</span><strong class="home-glance-value">{value}</strong></article>'
        for card_class, label, value in [
            ("home-glance-item neutral", "가장 최근 뉴스", f"{latest_home_news_total}건"),
            ("home-glance-item teal", "정부 동향", f"{len(government_trend_articles)}건"),
        ]
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
    <section class="hero home-hero civic-hero" id="overview">
      <div class="home-briefing-grid">
        <article class="home-briefing-card lead lead-arch{home_lead_class}" data-media-host="home-lead">
          <div class="home-briefing-content">
            <span class="home-briefing-date" aria-label="마지막 업데이트 {html.escape(home_date_label)} {html.escape(home_time_label)}">
              <span class="home-briefing-date-label">마지막 업데이트</span>
              <span class="home-briefing-date-day">{html.escape(home_date_label)}</span>
              <span class="home-briefing-date-time">{html.escape(home_time_label)}</span>
            </span>
            <h1 class="home-briefing-title">청년정책 모아봄</h1>
            <p class="home-briefing-copy">{html.escape(lead_message)}</p>
          </div>
          {home_lead_media}
        </article>
        <section class="home-overview" id="today-briefing" aria-labelledby="today-briefing-title">
          <div class="home-overview-head">
            <div>
              <h2 id="today-briefing-title">오늘 한눈에 보기</h2>
            </div>
            <div class="home-glance-grid">{overview_stats_html}</div>
          </div>
          {home_categories_html}
          <div class="home-overview-columns">
            <article class="home-overview-column">
              <div class="home-overview-column-head">
                <div>
                  <span>가장 최근 뉴스</span>
                  <h3>지금 새로 들어온 기사</h3>
                </div>
              </div>
              <p class="home-briefing-panel-note">언론 기사 중 선거·공약성 기사를 제외한 최신 청년 이슈입니다.</p>
              <div class="home-urgent-list">{today_news_html}</div>
            </article>
            <article class="home-overview-column">
              <div class="home-overview-column-head">
                <div>
                  <span>정부 동향</span>
                  <h3>중앙정부 공식 발표</h3>
                </div>
              </div>
              <p class="home-briefing-panel-note">정부 동향 메뉴와 같은 기준으로 중앙정부 원문과 공식 발표만 봅니다.</p>
              <div class="home-urgent-list">{policy_briefing_html}</div>
            </article>
          </div>
        </section>
        {render_home_application_policies(all_articles, page_updated_at)}
      </div>
    </section>
    {render_youth_metrics()}
    """


def build_guide_page(status: dict) -> str:
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    status_meta = render_status(status)
    menu_cards = "".join(
        [
            render_feature_card("홈", "오늘 바로 볼 기사와 오늘 집계를 먼저 보는 첫 화면입니다.", "index.html", "첫 화면"),
            render_feature_card("뉴스 모음", "수집된 청년 뉴스를 날짜별로 오래 남겨 빠르게 훑어봅니다.", "news.html", "누적 기사"),
            render_feature_card("선거·공약", "수집된 선거 기사와 청년 공약 흐름을 일반 뉴스와 분리해 봅니다.", "election.html", "누적 흐름"),
            render_feature_card("정부 동향", "중앙정부와 부처가 공식으로 발표한 청년 정책 자료만 확인합니다.", "policies.html", "정부 발표"),
            render_feature_card("지자체 동향", "광역·기초지자체의 청년 정책 발표와 공고성 흐름을 지역별로 봅니다.", "plans.html", "지역 발표"),
            render_feature_card("참여기구", "위원회, 자문단, 청년정책 네트워크 같은 참여 구조를 모아 봅니다.", "hub.html", "참여 구조"),
            render_feature_card("연구·문헌", "연구보고서, 통계, 법령, 공식 자료를 바로 엽니다.", "tools.html", "연구 자료"),
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
            ("2. 정부 동향", "중앙정부 공식 발표와 정책브리핑을 바로 확인합니다."),
            ("3. 지자체 동향", "지역별 청년 정책 발표와 공고성 흐름을 따로 봅니다."),
            ("4. 참여기구", "위원회, 회의, 네트워크 소식이 이어지는지 살펴봅니다."),
            ("5. 연구·문헌", "연구보고서, 통계, 법령, 공식 자료를 확인합니다."),
        ],
    )
    return f"""
    <section class="hero">
      <article class="hero-card">
        <span class="eyebrow">사이트 소개</span>
        <h1>청년세대와 관련된 이슈들을 한 데 모았습니다.</h1>
        <p class="hero-copy">수집된 기사와 정부 공식 발표, 지자체 발표, 참여기구 기록을 오래 남기되 서로 섞이지 않게 나눠 볼 수 있도록 정리했습니다. 홈은 가장 최근에 볼 기사부터 시작하고, 이 페이지에서는 메뉴와 보는 순서를 설명합니다.</p>
        <div class="hero-feature-meta">페이지 반영 {html.escape(format_display_datetime(page_updated_at))} · {html.escape(status_meta["update_frequency"])}</div>
        <div class="hero-actions">
          <a class="button primary" href="index.html">홈에서 기사 보기</a>
          <a class="button" href="news.html">뉴스 모음 보기</a>
        </div>
      </article>
      <aside class="status-card">
        <h3>먼저 보면 좋은 메뉴</h3>
        <div class="list">
          <div class="list-item"><strong>홈</strong><span>첫 화면에서 오늘 바로 볼 기사와 업데이트 요약을 먼저 확인합니다.</span></div>
          <div class="list-item"><strong>정부 동향</strong><span>중앙정부 공식 발표와 정부 원문만 확인하는 메뉴입니다.</span></div>
          <div class="list-item"><strong>지자체 동향</strong><span>지역별 청년 정책 발표와 공고성 흐름을 따로 봅니다.</span></div>
          <div class="list-item"><strong>참여기구</strong><span>위원회, 회의, 지역 네트워크 움직임을 추적할 때 유용합니다.</span></div>
          <div class="list-item"><strong>제작자 연락</strong><span>누락 기사나 협업 제안은 하단의 제작자 연락 채널로 전달할 수 있습니다.</span></div>
        </div>
      </aside>
    </section>
    <section class="section" id="main-list">
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
    topic_options = collect_news_topics(recent_news_articles)
    page_intro = render_compact_intro(
        "뉴스 모음",
        "지역, 주제, 검색어, 날짜를 함께 써서 필요한 기사만 빠르게 찾습니다. 선거·공약 성격이 강한 기사는 별도 메뉴로 분리했습니다.",
        media_key="news",
        title="청년 뉴스 모음",
    )
    news_filter_panel = render_news_filter_panel(
        region_options,
        topic_options,
        date_options,
        len(recent_news_articles),
        region_counts=collect_article_region_counts(recent_news_articles),
    )
    cards_html = "".join(render_article_card(article) for article in recent_news_articles)
    return f"""
    <div data-news-filter-root="news" data-default-date-start="" data-default-date-end="" data-default-region="all" data-default-topic="all" data-default-search-query="">
      {page_intro}
      {news_filter_panel}
      <section class="section" id="main-list">
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
    topic_options = collect_news_topics(recent_election_articles)
    page_intro = render_compact_intro(
        "선거·공약",
        "청년 공약, 후보 동정, 선거성 기사를 일반 뉴스와 분리해서 봅니다. 공약 흐름과 정책 기사를 섞지 않기 위한 메뉴입니다.",
        title="선거·공약 뉴스",
    )
    election_filter_panel = render_news_filter_panel(
        region_options,
        topic_options,
        date_options,
        len(recent_election_articles),
        filter_title="선거·공약 필터",
        region_counts=collect_article_region_counts(recent_election_articles),
    )
    cards_html = "".join(render_article_card(article) for article in recent_election_articles)
    return f"""
    <div data-news-filter-root="election" data-default-date-start="" data-default-date-end="" data-default-region="all" data-default-topic="all" data-default-search-query="">
      {page_intro}
      {election_filter_panel}
      <section class="section" id="main-list">
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


def build_policy_plans_page(status: dict) -> str:
    page_updated_at = status.get("finished_at") or status.get("updated_at")
    page_intro = render_compact_intro(
        "정책계획",
        "청년정책 기본계획과 시행계획을 뉴스와 분리해 기준 문서로 모아두는 아카이브입니다.",
        media_key="policies",
        title="청년정책 기본·시행계획",
    )
    overview_cards = "".join(
        [
            render_feature_card(
                "기본계획",
                "국가와 지자체가 몇 년 단위로 세우는 청년정책의 큰 방향과 과제를 확인합니다.",
                "#main-list",
                "중장기 기준",
            ),
            render_feature_card(
                "시행계획",
                "연도별로 실제 추진 과제와 예산, 담당 부서를 확인할 수 있는 실행 문서입니다.",
                "#record-schema",
                "연도별 실행",
            ),
            render_feature_card(
                "원문 아카이브",
                "PDF, 게시판 원문, 확인일을 함께 남겨 기사와 정책 발표의 기준점으로 씁니다.",
                "#record-schema",
                "원문 중심",
            ),
        ]
    )
    target_groups = [
        ("국가", "중앙정부", "청년정책 기본계획, 연도별 시행계획, 청년정책조정위원회 기준 문서"),
        ("광역", "서울", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "부산", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "대구", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "인천", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "광주", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "대전", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "울산", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "세종", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "경기", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "강원", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "충북", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "충남", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "전북", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "전남", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "경북", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "경남", "기본계획·시행계획·청년정책 종합계획"),
        ("광역", "제주", "기본계획·시행계획·청년정책 종합계획"),
    ]
    target_cards = "".join(
        f"""
        <article class="section-card">
          <div class="article-meta">{html.escape(scope)}</div>
          <h3>{html.escape(name)}</h3>
          <p>{html.escape(description)}</p>
          <span class="mini-link" aria-disabled="true">원문 등록 예정</span>
        </article>
        """
        for scope, name, description in target_groups
    )
    return f"""
    {page_intro}
    <section class="section" id="overview">
      <div class="section-head">
        <div>
          <h2>정책계획을 따로 보는 이유</h2>
          <p>뉴스는 흐름을 보여주고, 기본계획과 시행계획은 정책의 기준 문서를 보여줍니다.</p>
        </div>
      </div>
      <div class="feature-grid">{overview_cards}</div>
    </section>
    <section class="section" id="main-list">
      <div class="section-head">
        <div>
          <h2>수집 대상</h2>
          <p>1차는 중앙정부와 17개 광역지자체를 기준으로 잡고, 이후 기초지자체를 확인된 곳부터 확장합니다.</p>
        </div>
        <span class="mini-link" aria-disabled="true">페이지 반영 {html.escape(format_display_datetime(page_updated_at))}</span>
      </div>
      <div class="feature-grid">{target_cards}</div>
    </section>
    <section class="section" id="record-schema">
      {render_list_block("문서별 기록 항목", "정책계획 문서는 아래 항목을 기준으로 정리할 예정입니다.", [("지역·기관", "중앙정부, 광역지자체, 이후 기초지자체까지 구분"), ("문서 유형", "기본계획, 시행계획, 종합계획, 연차별 계획"), ("적용 기간", "예: 2024~2028, 2026년 시행계획처럼 기간과 기준 연도 표시"), ("원문 링크", "PDF, 게시판, 보도자료 원문 링크와 최근 확인일"), ("핵심 키워드", "일자리, 주거, 교육, 복지, 참여, 금융 등 주요 분야 태그")])}
    </section>
    <section class="section">
      {render_list_block("등록 순서", "처음부터 모든 기초지자체까지 넣기보다, 기준 문서부터 안정적으로 쌓습니다.", [("1차", "중앙정부와 17개 광역지자체 기본계획·시행계획"), ("2차", "각 광역지자체의 청년포털·고시공고·보도자료 게시판 원문 연결"), ("3차", "기초지자체 계획은 확인된 지역부터 점진적으로 추가")])}
    </section>
    """


def build_policies_page(articles: list[dict], status: dict) -> str:
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    policies = filter_recent_articles(
        [article for article in articles if article.get("is_official_source")],
        page_updated_at,
        PUBLIC_ARCHIVE_WINDOW_HOURS,
    )
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
    <section class="section" id="main-list">
      <div class="section-head">
        <div>
          <h2>정부 공식 발표</h2>
          <p>수집된 기간 안의 정부 원문과 공식 발표를 최대한 길게 보여줍니다.</p>
        </div>
      </div>
      <div class="article-grid">{official_cards or '<article class="info-card"><h3>공식 발표 없음</h3><p>표시할 정부 원문이 아직 없습니다.</p></article>'}</div>
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


def build_government_official_release_articles(articles: list[dict], reference_time: str | None) -> list[dict]:
    recent_articles = filter_recent_articles(
        sort_articles_by_recency(articles),
        reference_time,
        PUBLIC_ARCHIVE_WINDOW_HOURS,
    )
    return [
        with_government_trend_badges(article)
        for article in recent_articles
        if is_home_central_official_announcement(article)
    ]


def build_government_policy_resource_articles() -> list[dict]:
    return [
        with_display_badges(article, "주요 정책 자료")
        for article in build_curated_major_policy_articles()
    ]


def build_government_trend_articles(articles: list[dict], reference_time: str | None) -> list[dict]:
    official_policies = build_government_official_release_articles(articles, reference_time)
    return [
        with_government_trend_badges(article)
        for article in add_major_policy_watchlist_articles(official_policies)
    ]


CENTRAL_GOVERNMENT_RELATED_NEWS_PROMINENT_KEYWORDS = (
    "정부",
    "중앙정부",
    "국무총리",
    "국무조정실",
    "정책브리핑",
    "부처",
    "장관",
    "차관",
    "국방장관",
    "금융위원장",
)


def central_government_related_news_prominent_text(article: dict) -> str:
    return normalize_inline_text(
        " ".join(
            str(value or "")
            for value in [
                article.get("title"),
                article.get("lead_text"),
                article.get("summary"),
                article.get("source"),
                article.get("source_name"),
                " ".join(article.get("issue_tags") or []),
                " ".join(article.get("topic_tags") or []),
            ]
        )
    )


def central_government_related_news_full_text(article: dict) -> str:
    body = normalize_inline_text(article.get("body_text"))[:1600]
    return normalize_inline_text(
        " ".join(
            value
            for value in [
                central_government_related_news_prominent_text(article),
                body,
            ]
            if value
        )
    )


def has_central_government_related_news_signal(article: dict) -> bool:
    prominent_text = central_government_related_news_prominent_text(article)
    if has_prominent_central_government_related_news_signal(article):
        return True

    full_text = central_government_related_news_full_text(article)
    return any(authority in full_text for authority in MAJOR_CENTRAL_POLICY_AUTHORITIES)


def has_prominent_central_government_related_news_signal(article: dict) -> bool:
    prominent_text = central_government_related_news_prominent_text(article)
    return any(keyword in prominent_text for keyword in CENTRAL_GOVERNMENT_RELATED_NEWS_PROMINENT_KEYWORDS) or any(
        authority in prominent_text for authority in MAJOR_CENTRAL_POLICY_AUTHORITIES
    )


def is_central_government_related_news_article(article: dict) -> bool:
    source_kind = normalize_inline_text(article.get("source_kind"))
    if source_kind == "official" or article.get("is_official_source"):
        return False
    if (
        is_election_promise_article(article)
        or home_campaign_political(article)
        or article.get("campaign_political")
        or article.get("substantive_promise")
    ):
        return False
    if article.get("is_noise") or article.get("article_type") == "opinion":
        return False
    if is_local_government_announcement(article) or home_is_regional_roundup_article(article):
        return False
    if has_local_government_actor_signal(article) and not has_prominent_central_government_related_news_signal(article):
        return False
    return has_central_government_related_news_signal(article)


def government_related_news_key(article: dict) -> str:
    title = clean_article_title(article.get("title"))
    title = re.sub(r"^\[[^\]]+\]\s*", "", title).strip()
    return normalize_inline_text(title).lower() or article_identity_key(article)


def deduplicate_government_related_news_articles(articles: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen_identity_keys: set[str] = set()
    seen_title_keys: set[str] = set()
    for article in sort_articles_by_recency(articles):
        identity_key = article_identity_key(article)
        title_key = government_related_news_key(article)
        if identity_key in seen_identity_keys or title_key in seen_title_keys:
            continue
        seen_identity_keys.add(identity_key)
        seen_title_keys.add(title_key)
        deduped.append(article)
    return deduped


def build_government_related_news_articles(articles: list[dict], reference_time: str | None) -> list[dict]:
    recent_articles = filter_recent_articles(
        sort_articles_by_recency(articles),
        reference_time,
        PUBLIC_ARCHIVE_WINDOW_HOURS,
    )
    related_news = [
        with_government_related_news_badges(article)
        for article in recent_articles
        if is_central_government_related_news_article(article)
    ]
    return deduplicate_government_related_news_articles(related_news)


def render_government_menu_nav() -> str:
    items = [
        ("#main-list", "01", "중앙정부 관련 뉴스", "언론 기사 중 중앙정부와 청년정책이 함께 핵심인 기사만 봅니다."),
        ("#government-official-releases", "02", "중앙정부 공식 보도자료", "정책브리핑, 국무조정실, 중앙부처 원문과 공식 발표를 봅니다."),
        ("#government-policy-resources", "03", "주요 정책·시행계획 자료", "청년정책 기본계획, 시행계획, 부처별 공식 경로를 연결합니다."),
    ]
    cards = "".join(
        f"""
        <a class="local-menu-card" href="{href}">
          <span>{html.escape(order)}</span>
          <strong>{html.escape(title)}</strong>
          <small>{html.escape(description)}</small>
        </a>
        """
        for href, order, title, description in items
    )
    return f"""
    <section class="section" id="government-menu">
      <div class="local-menu-nav">{cards}</div>
    </section>
    """


def render_government_related_news_grid(articles: list[dict]) -> str:
    cards = "".join(
        render_article_card(
            article,
            {
                "data-government-related-news-card": "true",
            },
        )
        for article in articles
    )
    if cards:
        return f'<div class="article-grid">{cards}</div>'
    return """
      <div class="article-grid">
        <article class="info-card">
          <h3>중앙정부 관련 뉴스 없음</h3>
          <p>중앙정부 정책과 직접 연결되는 언론 기사가 들어오면 이 영역에 표시됩니다.</p>
        </article>
      </div>
    """


def render_government_policy_resource_grid(articles: list[dict]) -> str:
    cards = "".join(
        render_article_card(
            article,
            {
                "data-government-policy-resource-card": "true",
                "data-policy-authority": policy_authority_label(article),
                "data-policy-type": policy_type_label(article),
            },
        )
        for article in articles
    )
    if cards:
        return f'<div class="article-grid">{cards}</div>'
    return """
      <div class="article-grid">
        <article class="info-card">
          <h3>주요 정책 자료 없음</h3>
          <p>중앙정부 기본계획과 부처별 공식 경로를 확인하면 이 영역에 표시됩니다.</p>
        </article>
      </div>
    """


def build_policies_page_compact(articles: list[dict], status: dict) -> str:
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    official_policies = build_government_official_release_articles(articles, page_updated_at)
    related_news_articles = build_government_related_news_articles(articles, page_updated_at)
    policy_resource_articles = build_government_policy_resource_articles()
    page_intro = render_compact_intro(
        "정부 동향",
        "중앙정부 관련 뉴스, 정부 공식 보도자료, 주요 정책·시행계획 자료를 지자체 동향처럼 구분해 봅니다.",
        media_key="policies",
        title="중앙정부 청년정책 보드",
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
    policy_filter_panel = render_announcement_filter_panel(
        official_policies,
        group="official",
        scope_label="부처·기관",
        scope_values=collect_policy_authorities(official_policies),
        search_placeholder="정부 발표 제목, 요약, 부처 검색",
    )
    return f"""
    {page_intro}
    {render_government_menu_nav()}
    <section class="section" id="main-list">
      <div class="section-head">
        <div>
          <h2>중앙정부 관련 뉴스</h2>
          <p>언론 기사 중 중앙정부 부처, 국무조정실, 정책브리핑, 장관·부처 발표와 직접 연결되는 청년정책 보도를 따로 모읍니다.</p>
        </div>
        <span class="mini-link" aria-disabled="true">{len(related_news_articles)}건</span>
      </div>
      {render_government_related_news_grid(related_news_articles)}
    </section>
    <div data-policy-filter-root="policies" data-policy-scope-mode="authority-region" data-default-policy-group="official" data-default-policy-region="all" data-default-policy-scope="all" data-default-policy-type="all" data-default-date-start="" data-default-date-end="" data-default-search-query="">
      {policy_filter_panel}
      <section class="section" id="government-official-releases" data-policy-section="official">
        <div class="section-head">
          <div>
            <h2>중앙정부 공식 보도자료</h2>
            <p>정책브리핑, 국무조정실, 19개 중앙부처 원문과 공식 자료를 표시합니다. 지자체 발표와 선거·공약성 기사는 다른 메뉴로 분리합니다.</p>
          </div>
          <span class="mini-link" aria-disabled="true" data-policy-section-count>{len(official_policies)}건</span>
        </div>
        <div class="article-grid">{official_cards or '<article class="info-card"><h3>정부 공식 발표 없음</h3><p>표시할 중앙정부 공식 발표가 아직 없습니다.</p></article>'}</div>
      </section>
      <article class="info-card" data-policy-empty-state="true" hidden>
        <h3>조건에 맞는 정부 발표가 없습니다</h3>
        <p>부처·기관, 유형, 기간을 바꾸면 다른 정부 발표를 볼 수 있습니다.</p>
      </article>
    </div>
    <section class="section" id="government-policy-resources">
      <div class="section-head">
        <div>
          <h2>주요 정책·시행계획 자료</h2>
          <p>청년정책 기본계획·시행계획, 주요 부처별 청년정책 공식 경로와 최근 확인된 핵심 자료를 연결합니다.</p>
        </div>
        <span class="mini-link" aria-disabled="true">{len(policy_resource_articles)}건</span>
      </div>
      {render_government_policy_resource_grid(policy_resource_articles)}
    </section>
    """


def local_official_search_url(region: dict, *terms: str) -> str:
    query = " ".join([f'site:{region["domain"]}', region["full_name"], *terms]).strip()
    return "https://www.google.com/search?" + urllib.parse.urlencode({"q": query})


def render_local_menu_nav() -> str:
    items = [
        ("#main-list", "01", "지자체 발표 뉴스 모음", "뉴스 중 지자체와 청년이 함께 핵심인 기사만 봅니다."),
        ("#local-press-releases", "02", "지자체 홈페이지 보도자료", "17개 광역지자체 홈페이지에서 청년 보도자료를 수집합니다."),
        ("#local-policy-map", "03", "기본·시행계획 지도", "지역별 청년정책 기본계획·시행계획 원문 링크를 연결합니다."),
    ]
    cards = "".join(
        f"""
        <a class="local-menu-card" href="{href}">
          <span>{html.escape(order)}</span>
          <strong>{html.escape(title)}</strong>
          <small>{html.escape(description)}</small>
        </a>
        """
        for href, order, title, description in items
    )
    return f"""
    <section class="section" id="local-menu">
      <div class="local-menu-nav">{cards}</div>
    </section>
    """


def render_local_article_grid(
    articles: list[dict],
    *,
    empty_title: str,
    empty_body: str,
    group: str = "local",
) -> str:
    cards = "".join(
        render_article_card(
            article,
            {
                "data-policy-card": "true",
                "data-policy-group": group,
                "data-policy-type": policy_type_label(article),
            },
        )
        for article in articles
    )
    if cards:
        return f'<div class="article-grid">{cards}</div>'
    return f"""
      <div class="article-grid">
        <article class="info-card">
          <h3>{html.escape(empty_title)}</h3>
          <p>{html.escape(empty_body)}</p>
        </article>
      </div>
    """


def build_local_plan_region_summaries(plan_documents: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for article in plan_documents:
        label = local_region_label_for_article(article)
        if label and label != "지역 미상":
            grouped.setdefault(label, []).append(article)

    summaries: list[dict] = []
    for region in LOCAL_YOUTH_PLAN_REGIONS:
        region_articles = sort_articles_by_recency(grouped.get(region["name"], []))
        latest = region_articles[0] if region_articles else None
        document_url = local_plan_document_url(latest) if latest else ""
        static_links = LOCAL_YOUTH_PLAN_STATIC_LINKS.get(region["id"], {})
        basic_plan = dict(static_links.get("basic_plan") or {})
        implementation_plan = dict(static_links.get("implementation_plan") or {})
        if latest and document_url:
            dynamic_link = {
                "title": display_article_title(latest, limit=72),
                "url": document_url,
            }
            text = local_government_article_text(latest)
            if "기본계획" in text:
                basic_plan = dynamic_link
            elif "시행계획" in text:
                implementation_plan = dynamic_link
            elif not implementation_plan:
                implementation_plan = dynamic_link
            elif not basic_plan:
                basic_plan = dynamic_link
        status = "confirmed" if basic_plan and implementation_plan else "candidate" if (basic_plan or implementation_plan or latest) else "missing"
        summaries.append(
            {
                **region,
                "count": len(region_articles),
                "latest": latest,
                "document_url": document_url,
                "basic_plan": basic_plan,
                "implementation_plan": implementation_plan,
                "status": status,
                "status_label": LOCAL_PLAN_STATUS_LABELS[status],
            }
        )
    return summaries


def local_plan_document_url(article: dict | None) -> str:
    if not article:
        return ""
    for key in ("original_document_url", "attachment_url", "download_url", "file_url"):
        value = normalize_inline_text(article.get(key))
        if value:
            return value
    return article_target_url(article)


def parse_svg_viewbox(value: str) -> tuple[float, float, float, float]:
    parts = [float(part) for part in re.findall(r"[-+]?\d+(?:\.\d+)?", value)]
    if len(parts) >= 4 and parts[2] and parts[3]:
        return parts[0], parts[1], parts[2], parts[3]
    return 0.0, 0.0, 1000.0, 1593.0


def korea_adm1_display_viewbox(
    viewbox: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    min_x, min_y, width, height = viewbox
    display_width = min(width, max(1.0, KOREA_ADM1_DISPLAY_MAX_X - min_x))
    return min_x, min_y, display_width, height


def format_svg_viewbox(viewbox: tuple[float, float, float, float]) -> str:
    min_x, min_y, width, height = viewbox
    return f"{min_x:.2f} {min_y:.2f} {width:.2f} {height:.2f}"


def svg_path_label_point(
    path_tag: str,
    *,
    region_id: str,
    viewbox: tuple[float, float, float, float],
) -> tuple[float, float]:
    override = LOCAL_MAP_LABEL_COORDINATE_OVERRIDES.get(region_id)
    if override:
        x, y = override
    else:
        d_match = re.search(r'\sd="([^"]+)"', path_tag)
        if not d_match:
            min_vx, min_vy, width, height = viewbox
            return min_vx + width / 2, min_vy + height / 2
        subpath_boxes: list[tuple[float, float, float, float, float]] = []
        for subpath in re.split(r"(?=M)", d_match.group(1)):
            coords = [float(value) for value in re.findall(r"[-+]?\d+(?:\.\d+)?", subpath)]
            points = list(zip(coords[0::2], coords[1::2]))
            if not points:
                continue
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            area = (max_x - min_x) * (max_y - min_y)
            subpath_boxes.append((area, min_x, min_y, max_x, max_y))
        if not subpath_boxes:
            min_vx, min_vy, width, height = viewbox
            return min_vx + width / 2, min_vy + height / 2
        _, min_x, min_y, max_x, max_y = max(subpath_boxes, key=lambda item: item[0])
        x = (min_x + max_x) / 2
        y = (min_y + max_y) / 2
    return x, y


def svg_path_label_percent(
    path_tag: str,
    *,
    region_id: str,
    viewbox: tuple[float, float, float, float],
) -> tuple[float, float]:
    min_vx, min_vy, width, height = viewbox
    x, y = svg_path_label_point(path_tag, region_id=region_id, viewbox=viewbox)
    return ((x - min_vx) / width * 100, (y - min_vy) / height * 100)


def korea_adm1_svg_parts() -> tuple[str, tuple[float, float, float, float], list[tuple[str, str]]]:
    try:
        svg_text = KOREA_ADM1_SVG.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        svg_text = ""
    viewbox_match = re.search(r'viewBox="([^"]+)"', svg_text)
    viewbox_value = viewbox_match.group(1) if viewbox_match else "0 0 1000 1593"
    viewbox_parts = parse_svg_viewbox(viewbox_value)
    path_pattern = re.compile(r"<path\b(?=[^>]*\bdata-name=\"([^\"]+)\")[^>]*/>", re.DOTALL)
    paths = [
        (html.unescape(match.group(1)), match.group(0))
        for match in path_pattern.finditer(svg_text)
    ]
    return viewbox_value, viewbox_parts, paths


def clean_region_svg_path_tag(path_tag: str, class_name: str) -> str:
    cleaned = re.sub(r'\s+id="[^"]*"', "", path_tag)
    cleaned = re.sub(r'\s+class="[^"]*"', "", cleaned)
    return cleaned.replace("<path", f'<path class="{class_name}"', 1)


def render_small_region_hit_target(region_id: str, x: float, y: float, class_name: str) -> str:
    radius = SMALL_MAP_REGION_HIT_RADII.get(region_id)
    if not radius:
        return ""
    return f'<circle class="{class_name}" cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" aria-hidden="true"></circle>'


def small_region_hit_point(region_id: str, x: float, y: float) -> tuple[float, float]:
    return SMALL_MAP_REGION_HIT_POINTS.get(region_id, (x, y))


def svg_tooltip_width(label: str) -> float:
    # Korean glyphs are wider in the SVG coordinate system than ASCII digits.
    weighted = sum(1.0 if ord(char) > 127 else 0.58 for char in label)
    return max(112.0, weighted * 28.0 + 34.0)


def render_region_map_tooltip(region: dict, count: int, x: float, y: float, viewbox: tuple[float, float, float, float]) -> str:
    min_vx, min_vy, _, _ = viewbox
    label = region["full_name"]
    label_width = svg_tooltip_width(f"{label} {count}건")
    tooltip_y = 56.0 if y - min_vy < 110.0 else -54.0
    rect_y = tooltip_y - 34.0
    text_y = tooltip_y - 10.0
    return (
        f'<g class="filter-region-map-tooltip" data-region-map-tooltip="{html.escape(region["id"])}" '
        f'transform="translate({x:.2f} {y:.2f})" aria-hidden="true">'
        f'<rect x="{-label_width / 2:.2f}" y="{rect_y:.2f}" width="{label_width:.2f}" height="38" rx="19"></rect>'
        f'<text x="0" y="{text_y:.2f}" text-anchor="middle">'
        f'{html.escape(label)} <tspan class="filter-region-map-count" data-region-map-count="true">{count}건</tspan>'
        '</text></g>'
    )


def render_region_filter_map(*, filter_kind: str, region_counts: dict[str, int] | None = None) -> str:
    region_counts = region_counts or {}
    _, source_viewbox_parts, map_paths = korea_adm1_svg_parts()
    display_viewbox_parts = korea_adm1_display_viewbox(source_viewbox_parts)
    display_viewbox_value = format_svg_viewbox(display_viewbox_parts)
    region_by_map_name = {
        KOREA_ADM1_REGION_NAMES[entry["id"]]: entry
        for entry in LOCAL_YOUTH_PLAN_REGIONS
        if entry["id"] in KOREA_ADM1_REGION_NAMES
    }
    region_paths: list[str] = []
    priority_region_paths: list[str] = []
    tooltip_paths: list[str] = []
    for map_name, original_path_tag in map_paths:
        region = region_by_map_name.get(map_name)
        if not region:
            continue
        path_tag = clean_region_svg_path_tag(original_path_tag, "filter-region-map-path")
        region_name = region["name"]
        region_count = int(region_counts.get(region_name, 0))
        label_x, label_y = svg_path_label_point(
            original_path_tag,
            region_id=region["id"],
            viewbox=source_viewbox_parts,
        )
        label_x, label_y = small_region_hit_point(region["id"], label_x, label_y)
        hit_target = render_small_region_hit_target(
            region["id"],
            label_x,
            label_y,
            "filter-region-map-hit-target",
        )
        tooltip = render_region_map_tooltip(region, region_count, label_x, label_y, display_viewbox_parts)
        tooltip_paths.append(tooltip)
        if filter_kind == "news":
            data_attrs = (
                'data-news-filter="true" data-filter-group="region" '
                f'data-filter-value="{html.escape(region_name)}"'
            )
        else:
            data_attrs = (
                'data-policy-filter="true" data-filter-group="scope" '
                f'data-filter-value="{html.escape(region_name)}" '
                'data-policy-scope-button="true" data-scope-kind="local"'
            )
        region_html = (
            f'<a class="filter-region-map-region" href="#filters" role="button" '
            f'aria-pressed="false" aria-label="{html.escape(region["full_name"])} {region_count}건 선택" '
            f'data-region-map-id="{html.escape(region["id"])}" '
            f'data-region-label="{html.escape(region["full_name"])}" data-region-count-initial="{region_count}" {data_attrs}>'
            f'{path_tag}{hit_target}</a>'
        )
        if region["id"] in SMALL_MAP_REGION_HIT_RADII:
            priority_region_paths.append(region_html)
        else:
            region_paths.append(region_html)
    region_paths.extend(priority_region_paths)
    if not region_paths:
        return ""
    return (
        f'<svg class="filter-region-map-svg" viewBox="{html.escape(display_viewbox_value)}" role="img" '
        'aria-label="광역지자체 지역 선택 지도" xmlns="http://www.w3.org/2000/svg">'
        f'{"".join(region_paths)}'
        f'<g class="filter-region-map-tooltip-layer" aria-hidden="true">{"".join(tooltip_paths)}</g></svg>'
    )


def render_korea_adm1_local_map(summaries: list[dict]) -> str:
    summary_by_map_name = {
        KOREA_ADM1_REGION_NAMES[summary["id"]]: summary
        for summary in summaries
        if summary["id"] in KOREA_ADM1_REGION_NAMES
    }
    _, source_viewbox_parts, map_paths = korea_adm1_svg_parts()
    display_viewbox_parts = korea_adm1_display_viewbox(source_viewbox_parts)
    viewbox = html.escape(format_svg_viewbox(display_viewbox_parts))
    region_paths: list[str] = []
    priority_region_paths: list[str] = []
    seen_region_ids: set[str] = set()
    for map_name, original_path_tag in map_paths:
        summary = summary_by_map_name.get(map_name)
        if not summary or summary["id"] in seen_region_ids:
            continue
        seen_region_ids.add(summary["id"])
        path_tag = clean_region_svg_path_tag(original_path_tag, f'local-map-path status-{summary["status"]}')
        label_x, label_y = svg_path_label_percent(
            path_tag,
            region_id=summary["id"],
            viewbox=display_viewbox_parts,
        )
        hit_x, hit_y = svg_path_label_point(
            path_tag,
            region_id=summary["id"],
            viewbox=source_viewbox_parts,
        )
        hit_x, hit_y = small_region_hit_point(summary["id"], hit_x, hit_y)
        summary["map_label_x"] = label_x
        summary["map_label_y"] = label_y
        hit_target = render_small_region_hit_target(
            summary["id"],
            hit_x,
            hit_y,
            "local-map-hit-target",
        )
        label = f'{summary["full_name"]} {summary["status_label"]}'
        primary_url = (
            (summary.get("implementation_plan") or {}).get("url")
            or (summary.get("basic_plan") or {}).get("url")
            or "#local-policy-map"
        )
        target_attr = ' target="_blank" rel="noreferrer"' if primary_url.startswith(("http://", "https://")) else ""
        region_html = (
            f'<a class="local-map-region" href="{html.escape(primary_url, quote=True)}"{target_attr} '
            f'data-local-map-region="{html.escape(summary["id"])}" aria-label="{html.escape(label)}">'
            f"{path_tag}{hit_target}</a>"
        )
        if summary["id"] in SMALL_MAP_REGION_HIT_RADII:
            priority_region_paths.append(region_html)
        else:
            region_paths.append(region_html)
    region_paths.extend(priority_region_paths)

    if not region_paths:
        fallback_links = "".join(
            f'<a class="local-map-fallback-link" href="{html.escape(((summary.get("implementation_plan") or {}).get("url") or (summary.get("basic_plan") or {}).get("url") or "#local-policy-map"), quote=True)}">'
            f'{html.escape(summary["name"])}</a>'
            for summary in summaries
        )
        return f'<div class="local-map-fallback">{fallback_links}</div>'

    return (
        f'<svg class="local-map-svg" viewBox="{viewbox}" role="img" '
        'aria-label="대한민국 광역지자체 청년정책 기본·시행계획 지도" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'{"".join(region_paths)}</svg>'
    )


def render_local_map_plan_link(label: str, link: dict) -> str:
    url = normalize_inline_text(link.get("url") if isinstance(link, dict) else "")
    title = normalize_inline_text(link.get("title") if isinstance(link, dict) else "") or label
    if not url:
        return f'<span class="local-map-popover-empty">{html.escape(label)} 미확인</span>'
    return (
        f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noreferrer" '
        f'title="{html.escape(title, quote=True)}">{html.escape(label)}</a>'
    )


def render_local_map_region_labels(summaries: list[dict]) -> str:
    markers = []
    for summary in summaries:
        x = float(summary.get("map_label_x", 50.0))
        y = float(summary.get("map_label_y", 50.0))
        markers.append(
            f"""
            <div class="local-map-marker" style="left: {x:.2f}%; top: {y:.2f}%;" tabindex="0">
              <span class="local-map-label">{html.escape(summary["name"])}</span>
              <div class="local-map-popover" role="tooltip">
                <strong>{html.escape(summary["full_name"])}</strong>
                <span class="local-map-popover-count">수집 후보 {int(summary.get("count") or 0)}건 · {html.escape(summary["status_label"])}</span>
                {render_local_map_plan_link("기본계획", summary.get("basic_plan") or {})}
                {render_local_map_plan_link("시행계획", summary.get("implementation_plan") or {})}
              </div>
            </div>
            """
        )
    return f'<div class="local-map-label-layer">{"".join(markers)}</div>'


def korea_adm1_map_aspect_style() -> str:
    _, source_viewbox_parts, _ = korea_adm1_svg_parts()
    _, _, width, height = korea_adm1_display_viewbox(source_viewbox_parts)
    if not width or not height:
        return ""
    return f' style="aspect-ratio: {width:.2f} / {height:.2f};"'


def render_local_policy_plan_map(plan_documents: list[dict]) -> str:
    summaries = build_local_plan_region_summaries(plan_documents)
    map_html = render_korea_adm1_local_map(summaries)
    markers_html = render_local_map_region_labels(summaries)
    map_aspect_style = korea_adm1_map_aspect_style()

    return f"""
    <section class="section" id="local-policy-map">
      <div class="section-head">
        <div>
          <h2>지자체별 청년정책 기본·시행계획</h2>
          <p>17개 광역지자체 공식 자료를 지역별로 연결합니다. 지역명 위에 올리면 기본계획과 시행계획 링크가 바로 열립니다.</p>
        </div>
        <span class="mini-link" aria-disabled="true">광역 17곳</span>
      </div>
      <div class="local-plan-board">
        <aside class="local-map-panel" aria-label="한반도 지역 선택 지도">
          <div class="local-map-canvas">
            <div class="local-map-stage"{map_aspect_style}>
              {map_html}
              {markers_html}
            </div>
            <p class="local-map-source">지도 원본: geoBoundaries KOR ADM1 / Natural Earth, <a href="https://www.geoboundaries.org/api/current/gbOpen/KOR/ADM1/" target="_blank" rel="noreferrer">Public Domain</a></p>
          </div>
        </aside>
      </div>
    </section>
    """


def build_local_government_trends_page(articles: list[dict], status: dict) -> str:
    page_updated_at = status.get("finished_at") or status.get("updated_at") or ""
    recent_articles = filter_recent_articles(
        sort_articles_by_recency(articles),
        page_updated_at,
        PUBLIC_ARCHIVE_WINDOW_HOURS,
    )
    local_news_articles = [
        with_local_news_badges(article)
        for article in recent_articles
        if is_local_youth_news_article(article)
    ]
    local_press_releases = [
        with_local_press_release_badges(article)
        for article in recent_articles
        if is_local_youth_press_release(article)
    ]
    local_plan_documents = [
        with_local_plan_badges(article)
        for article in recent_articles
        if is_local_youth_plan_document(article)
    ]
    page_intro = render_compact_intro(
        "지자체 동향",
        "뉴스 속 지자체·청년 이슈, 광역지자체 홈페이지 보도자료, 지역별 기본·시행계획 원문 경로를 분리해 봅니다.",
        media_key="policies",
        title="지역 청년정책 보드",
    )
    local_filter_panel = render_announcement_filter_panel(
        local_news_articles,
        group="local",
        scope_label="지역",
        scope_values=LOCAL_YOUTH_PLAN_REGION_NAMES,
        search_placeholder="지자체·청년 뉴스 제목, 요약, 지역 검색",
        use_region_map=True,
    )
    return f"""
    {page_intro}
    {render_local_menu_nav()}
    <div data-policy-filter-root="plans" data-policy-scope-mode="authority-region" data-keep-empty-sections="true" data-keep-empty-scopes="true" data-default-policy-group="local" data-default-policy-region="all" data-default-policy-scope="all" data-default-policy-type="all" data-default-date-start="" data-default-date-end="" data-default-search-query="">
      {local_filter_panel}
      <section class="section" id="main-list" data-policy-section="local">
        <div class="section-head">
          <div>
            <h2>지자체 발표 뉴스 모음</h2>
            <p>일반 뉴스 중 지자체와 청년이 함께 핵심 주제로 다뤄진 기사만 표시합니다.</p>
          </div>
          <span class="mini-link" aria-disabled="true" data-policy-section-count>{len(local_news_articles)}건</span>
        </div>
        {render_local_article_grid(local_news_articles, empty_title="최근 지자체·청년 뉴스 없음", empty_body="뉴스 중 지자체와 청년이 핵심 주제로 함께 잡힌 기사가 들어오면 이 영역에 표시됩니다.")}
      </section>
    </div>
    <section class="section" id="local-press-releases">
      <div class="section-head">
        <div>
          <h2>지자체 홈페이지 보도자료</h2>
          <p>17개 광역지자체 홈페이지에서 청년 단어가 들어간 보도자료와 시정·도정 뉴스를 자동 수집합니다.</p>
        </div>
        <span class="mini-link" aria-disabled="true">{len(local_press_releases)}건</span>
      </div>
      {render_local_article_grid(local_press_releases, empty_title="최근 지자체 청년 보도자료 없음", empty_body="광역지자체 홈페이지 검색 결과에서 청년 관련 보도자료가 확인되면 이 영역에 표시됩니다.")}
    </section>
    {render_local_policy_plan_map(local_plan_documents)}
    """


def build_hub_page(classified_articles: list[dict]) -> str:
    hub_records = filter_hub_articles(classified_articles)
    government_records = filter_hub_articles(classified_articles, "정부")
    regional_records = filter_hub_articles(classified_articles, "지자체")
    public_records = filter_hub_articles(classified_articles, "공공기관")
    page_intro = render_compact_intro(
        "참여기구",
        "뉴스와는 별도로, 중앙부처 자문·회의와 지역 청년정책 네트워크, 공공기관 참여·협의 기록만 구조화해 모았습니다.",
        media_key="hub",
        title="청년 참여기구 기록",
    )
    hub_filter_panel = render_hub_filter_panel(government_records, regional_records, public_records)
    government_cards = "".join(render_hub_record_card(article) for article in government_records)
    regional_cards = "".join(render_hub_record_card(article) for article in regional_records)
    public_cards = "".join(render_hub_record_card(article) for article in public_records)
    return f"""
    <div data-policy-filter-root="hub" data-policy-scope-mode="hub-detail" data-keep-empty-sections="true" data-default-policy-group="all" data-default-policy-region="all" data-default-policy-scope="all" data-default-policy-type="all" data-default-date-start="" data-default-date-end="" data-default-search-query="">
      {page_intro}
      {hub_filter_panel}
      <section class="section" id="main-list" data-policy-section="official">
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
        <h3>조건에 맞는 참여기구 기록이 없습니다</h3>
        <p>구분이나 세부, 활동, 기간을 바꾸면 다른 기록을 확인할 수 있습니다.</p>
      </article>
    </div>
    """


def build_tools_page(articles: list[dict], status: dict) -> str:
    page_intro = render_compact_intro(
        "연구·문헌",
        "청년 정책을 이해하고 인용할 때 필요한 연구보고서, 통계, 법령, 공식 자료를 모았습니다.",
        media_key="tools",
        title="연구·문헌 자료",
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
    <section class="section" id="main-list">
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
        "제보·문의",
        "빠진 기사 제보, 운영 문의, 검토 요청을 한곳에서 남기고 바로 이어서 확인할 수 있습니다.",
        media_key="contact",
        title="제보와 운영 문의",
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
    <section class="section" id="main-list">
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


def youthside_footer_image_src() -> str:
    for relative_src in YOUTHSIDE_FOOTER_IMAGE_CANDIDATES:
        if (PUBLIC_WEB_ROOT / relative_src).exists():
            return f"{relative_src}?v={ASSET_VERSION}"
    return ""


def render_youthside_footer_image() -> str:
    image_src = youthside_footer_image_src()
    if not image_src:
        return ""
    return f"""
        <div class="site-footer-brand-image" aria-label="유스사이드 브랜드 이미지">
          <div class="site-footer-brand-image-frame">
            <img src="{html.escape(image_src, quote=True)}" alt="유스사이드 로고" loading="lazy" decoding="async">
          </div>
        </div>
    """


def build_footer_note(contact_settings: dict[str, str]) -> str:
    copyright_text = (contact_settings.get("copyright_text") or "").strip()
    contact_email = (contact_settings.get("email") or "").strip()
    base_text = copyright_text or "© 2026 유스사이드 · 박진감"
    contact_link = (
        f'<a href="{html.escape(CREATOR_CONTACT_URL, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">{html.escape(CREATOR_CONTACT_LABEL)}</a>'
    )
    related_links = [
        ("정책브리핑 청년정책", "https://m.korea.kr/news/policyFocusList.do?pkgId=49500808"),
        ("청년기본법", "https://www.law.go.kr/LSW/LsiJoLinkP.do?docType=JO&joNo=001700000&languageType=KO&lsNm=%EC%B2%AD%EB%85%84%EA%B8%B0%EB%B3%B8%EB%B2%95&paras=1"),
        ("KOSIS 국가통계포털", "https://kosis.kr/index/index.do"),
        ("공공데이터포털", "https://www.data.go.kr/"),
    ]
    related_html = "".join(
        f'<a href="{html.escape(href, quote=True)}" target="_blank" rel="noreferrer">{html.escape(label)}</a>'
        for label, href in related_links
    )
    email_meta = (
        f'<span>이메일 {html.escape(contact_email)}</span>'
        if contact_email
        else ""
    )
    footer_brand_image = render_youthside_footer_image()
    footer_body_class = "site-footer-body has-brand-image" if footer_brand_image else "site-footer-body"
    footer_left = footer_brand_image
    footer_site_head = """
          <div class="site-footer-site-head">
            <strong>청년정책 모아봄</strong>
            <span>by YOUTHSIDE</span>
          </div>
    """
    return f"""
      <div class="site-footer-top">
        <nav class="site-footer-links" aria-label="운영 기준 바로가기">
          <a href="guide.html">이용 안내</a>
          <a href="guide.html#main-list">정보 기준</a>
          <a href="contact.html#ops">이메일 무단수집거부</a>
          <a href="contact.html">제보·문의</a>
        </nav>
        <details class="site-footer-related">
          <summary>관련 사이트</summary>
          <div class="site-footer-related-list">{related_html}</div>
        </details>
      </div>
      <div class="{footer_body_class}">
        {footer_left}
        <div class="site-footer-info">
          {footer_site_head}
          <div class="site-footer-info-list">
            <p><strong>운영 목적 :</strong><span>청년정책 활동가, 관련 업무 종사자, 그리고 모든 청년을 위한 정책 정보 안내 서비스입니다.</span></p>
            <p><strong>정보 기준 :</strong><span>공개 기사와 정부·지자체 발표를 수집·분류해 정책 흐름과 신청 정보를 한 화면에서 확인할 수 있도록 정리합니다.</span></p>
            <p><strong>확인 안내 :</strong><span>중요한 신청·의사결정은 반드시 원문 링크와 공식 발표를 함께 확인해 주세요.</span></p>
          </div>
          <div class="site-footer-meta">
            <span>{html.escape(base_text)}</span>
            {email_meta}
            <span>연락 {contact_link}</span>
          </div>
        </div>
      </div>
    """


def normalize_generated_html(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.splitlines()) + "\n"


def write_page(
    path: Path,
    page_title: str,
    active_page: str,
    content: str,
    status: dict,
    contact_settings: dict[str, str],
) -> None:
    path.write_text(
        normalize_generated_html(
            PAGE_TEMPLATE.format(
                page_title=html.escape(page_title),
                active_page=html.escape(active_page),
                styles=BASE_CSS + DASHBOARD_TONE_CSS,
                brand_mark_src=html.escape(BRAND_MARK_SRC),
                script=build_page_script(),
                page_heading=html.escape(page_heading(active_page)),
                top_nav=render_top_nav(active_page),
                live_clock_topbar=render_live_clock("topbar"),
                side_nav=render_side_nav(active_page),
                global_search=render_global_search(),
                guide_link=render_guide_link(active_page),
                header_meta=render_header_meta(active_page, status),
                admin_entry=render_admin_entry(),
                bottom_nav=render_bottom_nav(active_page),
                bottom_nav_count=len(NAV_ITEMS),
                guide_overlay=render_guide_overlay(active_page),
                admin_login_overlay=render_admin_login_overlay(),
                footer_note=build_footer_note(contact_settings),
                content=content,
            )
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
        "청년정책 모아봄",
        "index.html",
        build_home_page(articles, classified_articles, status, contact_settings),
        status,
        contact_settings,
    )
    write_page(web_root / "guide.html", "이용방법", "guide.html", build_guide_page(status), status, contact_settings)
    write_page(
        web_root / "news.html",
        "뉴스 모음",
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
        "정부 동향",
        "policies.html",
        build_policies_page_compact(classified_articles, status),
        status,
        contact_settings,
    )
    write_page(
        web_root / "plans.html",
        "지자체 동향",
        "plans.html",
        build_local_government_trends_page(classified_articles, status),
        status,
        contact_settings,
    )
    write_page(
        web_root / "hub.html",
        "참여기구",
        "hub.html",
        build_hub_page(classified_articles),
        status,
        contact_settings,
    )
    write_page(
        web_root / "tools.html",
        "연구·문헌",
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
