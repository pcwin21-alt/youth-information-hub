# Article Survival And Selection Criteria

기준일: 2026-05-05 로컬 코드 기준.

## 현행 코드 기준

### 1. 후보 기사 판정

- 기준 코드: `shared/src/youth_info_platform/curation.py`.
- 공식 소스(`source_kind == "official"`)는 후보 기사로 통과한다.
- 일반 뉴스는 다음 중 하나가 있어야 후보로 남는다.
  - `issue_tags`가 있음.
  - 청년 맥락이 의미 있게 잡힘.
  - 청년 키워드와 정책/운영 맥락이 함께 있음.
- 이 단계는 “최종 공개”가 아니라 중복 제거와 큐레이션으로 넘길 최소 후보 판정이다.

### 2. 중복 제거와 대표 기사

- 1차 식별은 `article_identity_key`를 쓴다. canonical/publisher/url/feed URL과 제목/출처/게시일 기반 identity가 중심이다.
- 같은 이야기 판정은 같은 도메인, 제목 유사도 0.92 이상, 게시 시각 차이 48시간 이내를 기준으로 한다.
- 대표 기사 선택은 공식 소스, publisher URL 보유, Google News wrapper 회피, 본문 enrichment 여부, source kind, issue tag 수, 최신성 순으로 유리하게 본다.
- 중복 그룹은 `dedup_group_id`, `related_article_count`, `related_sources`, `portal_urls`로 기록한다.

### 3. 분류와 공개 적합성

- 분류 단계에서 region, categories, issue_tags, topic_tags, article_type, governance_scope, hub_topics를 만든다.
- 일반 뉴스는 청년 콘텐츠 신호가 없거나 약하면 `missing_youth_content_signal` 또는 `weak_youth_signal`로 보류된다.
- 공개 부적합으로 빠지는 대표 기준은 다음과 같다.
  - noise 또는 opinion.
  - 청년 콘텐츠 신호 없음.
  - 정치 공격성 기사.
  - 약한 청년 신호.
  - 실질 정책 공약이 아닌 선거/후보/정당 기사.
  - 일반 기업 실적/홍보성 기사.
  - 청년 직접 도움 신호가 없는 정치 분석 기사.
- 공식 소스 또는 governance scope가 있는 기사는 공개 적합으로 우선 인정된다.
- 일반 뉴스는 직접 도움 신호 또는 운영상 관련 신호가 있어야 하며, `public_relevance_score >= 4`가 필요하다.

### 4. public_relevance_score

- 가산:
  - 직접 도움 청년 신호 +4.
  - 운영상 관련 신호 +4.
  - prominent text에 도움 맥락이 있고 의미 있는 청년 맥락이 있음 +2.
  - issue tag 최대 +2.
  - governance scope +2.
  - 공식 소스 +2.
  - clean article +1.
  - 실질 공약 +1.
- 감점:
  - 약한 청년 신호 -6.
  - 실질 공약 없는 선거성 기사 -6.
  - 정치 공격성 -8.
  - 일반 기업 실적/홍보성 기사 -10.
  - 청년 직접 도움 없는 정치 분석 기사 -8.

### 5. importance_score와 bucket

- `importance_score`는 categories, 공식성, governance, news source, 지역성, 본문 보유, issue tag, clean score, public relevance, 선거성, 최신성을 합산한다.
- 주요 가산:
  - 청년은 지금 +5, 정책 +4, 지역 +3, 의견 +2.
  - 공식 소스 +2, governance +2, news source +2.
  - 지역 명시 +1, 본문 보유 +1.
  - issue tag별 1~3점.
  - clean article +2, clean score 6 이상 +1.
  - public relevance score 전체 반영.
  - 1일 이내 +6, 3일 이내 +4, 7일 이내 +2, 30일 이내 +1.
- 주요 감점:
  - 선거성 -3.
  - 약한 청년 신호 -5.
  - 공개 부적합 -12.
  - 30일 이상 -3, 90일 이상 -4, 180일 이상 -6.
- bucket 최소 확보 기준:
  - `official_policy` 3건.
  - `youth_issue` 3건.
  - `opinion` 1건.
  - `regional_issue` 2건.
  - `governance` 1건.
- 최종 자동 선별 기본 limit은 10건이며, editorial highlight/include는 우선 보호한다.

## 개선 후보 / 논의 필요

- `public_relevance_score`, `importance_score`, bucket 최소치를 config로 분리할지 검토한다.
- 선거성 기사를 공개 부적합으로만 볼지, 선거·공약 메뉴로 라우팅할지 기준을 더 명확히 분리한다.
- “약한 청년 신호”와 “청년 직접 도움 신호”에 대한 golden article fixture를 만든다.
- 기업/은행/기관 홍보성 기사 중 실제 청년 지원사업과 단순 홍보를 가르는 별도 판정 기준을 강화한다.
- 지자체 동향의 첫 섹션은 이제 공식 도메인/공식 source kind가 확인되는 자료를 우선한다. 지역명만 포함한 언론사명은 공식 지자체 발표 근거로 쓰지 않는다. 현행 수집 데이터에서 언론 보도 기반 지역 발표는 홈 보조 흐름 또는 다른 fallback에는 쓰일 수 있지만, 지자체 동향의 `지자체 발표 뉴스 모음`에서는 제외하는 방향이다.
