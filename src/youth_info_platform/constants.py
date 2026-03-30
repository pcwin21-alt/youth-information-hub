from __future__ import annotations

CATEGORY_POLICY = "정책 오피셜"
CATEGORY_NOW = "청년은 지금"
CATEGORY_OPINION = "논평·기고"
CATEGORY_REGION = "지역 이슈"

CATEGORIES = [
    CATEGORY_POLICY,
    CATEGORY_NOW,
    CATEGORY_OPINION,
    CATEGORY_REGION,
]

REGIONS = [
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "경기",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
]

OFFICIAL_KEYWORDS = [
    "정책브리핑",
    "보도자료",
    "브리핑",
    "시행",
    "발표",
    "계획",
    "대책",
]

NOW_KEYWORDS = [
    "현실",
    "현황",
    "실태",
    "통계",
    "조사",
    "백서",
    "고용",
    "부채",
    "주거",
    "빈곤",
]

OPINION_KEYWORDS = [
    "논평",
    "칼럼",
    "기고",
    "사설",
    "오피니언",
]

NOISE_KEYWORDS = [
    "아이돌",
    "연예",
    "홍보",
    "예능",
    "스포츠",
    "프로야구",
]

YOUTH_KEYWORDS = [
    "청년",
    "청년층",
    "청년세대",
    "사회초년생",
    "대학생",
    "취준생",
]

HUB_KEYWORDS = [
    "청년보좌역",
    "2030자문단",
    "2030청년자문단",
    "청년자문단",
    "청년정책조정위원회",
    "청년정책 관계장관회의",
    "청년정책 실무조정회의",
    "청년참여단",
    "청년네트워크",
    "청년협의체",
    "청년위원회",
]

GOVERNMENT_GOVERNANCE_KEYWORDS = [
    "청년보좌역",
    "2030자문단",
    "2030청년자문단",
    "청년자문단",
    "청년정책조정위원회",
    "청년정책 관계장관회의",
    "청년정책 실무조정회의",
    "청년위원회",
    "청년정책책임관",
]

REGIONAL_GOVERNANCE_KEYWORDS = [
    "청년협의체",
    "청년위원회",
    "청년네트워크",
    "청년정책네트워크",
    "청년참여단",
    "청년참여위원회",
    "청년정책협의체",
    "청년정책협의회",
    "청년협의회",
    "청년거버넌스",
]

HUB_ROUTING_KEYWORDS = list(
    dict.fromkeys(HUB_KEYWORDS + ["청년정책책임관"] + REGIONAL_GOVERNANCE_KEYWORDS)
)

YOUTH_RELATED_KEYWORDS = list(dict.fromkeys(YOUTH_KEYWORDS + HUB_ROUTING_KEYWORDS))

LOCAL_GOVERNMENT_CONTEXT_KEYWORDS = [
    "지방자치단체",
    "지자체",
    "도청",
    "시청",
    "군청",
    "구청",
    "도의회",
    "시의회",
    "군의회",
    "구의회",
    "시장",
    "도지사",
    "군수",
    "구청장",
]

CENTRAL_GOVERNMENT_CONTEXT_KEYWORDS = [
    "국무총리",
    "국무조정실",
    "정책브리핑",
    "정부서울청사",
    "장관",
    "차관",
    "부처",
    "정부위원회",
]

GOVERNANCE_ACTIVITY_KEYWORDS = {
    "회의": ["회의", "회의체", "관계장관회의", "실무조정회의", "협의회"],
    "간담회": ["간담회", "간담"],
    "위원회": ["위원회", "자문단", "참여단"],
    "협약": ["협약", "업무협약", "MOU"],
    "발표회": ["발표회", "브리핑", "발표"],
    "포럼": ["포럼", "토론회", "공청회"],
    "워크숍": ["워크숍", "워크샵"],
    "모집": ["모집", "모집공고", "선발"],
    "출범": ["출범", "발족"],
}
