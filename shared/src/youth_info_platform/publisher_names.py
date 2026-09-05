"""Stable display names for publishers seen in collected public articles."""

from __future__ import annotations

from urllib.parse import urlparse


# Only map domains whose publication identity is established from the
# publisher's own masthead, feed metadata, or the archived source record.
PUBLISHER_DOMAIN_ALIASES = {
    "biz.chosun.com": "조선비즈",
    "biz.heraldcorp.com": "헤럴드경제",
    "bokjitoday.com": "복지투데이",
    "busan.com": "부산일보",
    "bvba.org": "투위복지뉴스",
    "cctoday.co.kr": "충청투데이",
    "chosun.com": "조선일보",
    "ddaily.co.kr": "디지털데일리",
    "donga.com": "동아일보",
    "domin.co.kr": "전북도민일보",
    "dt.co.kr": "디지털타임스",
    "economicsignal.co.kr": "경제시그널",
    "ebn.co.kr": "EBN",
    "edaily.co.kr": "이데일리",
    "ekn.kr": "에너지경제",
    "ekw.co.kr": "EKW 이코리아월드",
    "etnews.com": "전자신문",
    "fnnews.com": "파이낸셜뉴스",
    "fnnews1.com": "파이낸스뉴스",
    "g-enews.com": "글로벌이코노믹",
    "gjtnews.com": "광주타임즈",
    "gonggam.korea.kr": "K-공감",
    "greened.kr": "그린경제신문",
    "gukjenews.com": "국제뉴스",
    "gymnews.net": "경기청년신문",
    "hani.co.kr": "한겨레",
    "hankyung.com": "한국경제",
    "heraldcorp.com": "헤럴드경제",
    "hidomin.com": "경북도민일보",
    "ikld.kr": "국토일보",
    "joongang.co.kr": "중앙일보",
    "khan.co.kr": "경향신문",
    "koreaittimes.com": "코리아IT타임스",
    "koreancenter.or.kr": "연합뉴스 한민족센터",
    "kyongbuk.co.kr": "경북일보",
    "magazine.hankyung.com": "한경비즈니스",
    "mk.co.kr": "매일경제",
    "mtime.co.kr": "매일타임즈",
    "mssnews.com": "중소벤처기업신문",
    "mt.co.kr": "머니투데이",
    "news.bbsi.co.kr": "BBS 뉴스",
    "news.einfomax.co.kr": "연합인포맥스",
    "news.nate.com": "네이트 뉴스",
    "news.sbs.co.kr": "SBS 뉴스",
    "news1.kr": "뉴스1",
    "newscj.com": "천지일보",
    "newneek.co": "뉴닉",
    "newsis.com": "뉴시스",
    "newsnjeju.com": "뉴스제주",
    "newstomato.com": "뉴스토마토",
    "newsworks.co.kr": "뉴스웍스",
    "ppss.kr": "ㅍㅍㅅㅅ",
    "sedaily.com": "서울경제",
    "seoul.co.kr": "서울신문",
    "sisa-news.com": "시사뉴스",
    "sisakoreanews.kr": "시사코리아뉴스",
    "the-pr.co.kr": "THE PR",
    "thecm.net": "충청미디어",
    "thedailyeconomy.kr": "데일리경제",
    "thepowernews.co.kr": "더파워",
    "tk.newdaily.co.kr": "뉴데일리",
    "v.daum.net": "다음 뉴스",
    "viva100.com": "브릿지경제",
    "weekly.hankooki.com": "주간한국",
    "weeklykoreanz.com": "위클리코리아",
    "yeongnam.com": "영남일보",
    "jejumbc.com": "제주MBC",
    "yna.co.kr": "연합뉴스",
}


def publisher_display_name(value: str | None) -> str:
    """Return a human publisher label while preserving non-domain feed names."""

    raw = str(value or "").strip()
    if not raw:
        return ""
    candidate = raw
    if "://" in candidate:
        candidate = urlparse(candidate).netloc or candidate
    domain = candidate.lower().split("/")[0].removeprefix("www.")
    return PUBLISHER_DOMAIN_ALIASES.get(domain, raw)
