# Source Collection Criteria

기준일: 2026-05-05 로컬 코드 기준.

## 현행 코드 기준

- 표준 설정은 `public-site/config/source_config.yaml`이다. 확장자는 YAML이지만 현재 내용은 JSON 구조의 `sources` 배열이다.
- 표준 실행은 `python public-site/scripts/rss_fetcher.py`이고, 결과는 `runtime/pipeline/step1_raw_articles.json`에 쌓인다.
- 현재 수집 소스는 31개이며, `kind` 기준으로 `official` 9개와 `news` 22개다.
- 현재 parser 분포는 `naver_news_search`, `rss`, `korea_withyou_policy_news`, `opm_press_release`, `mohw_press_release`, `molit_board_list`, `moe_press_release`, `fsc_press_release`다.
- 공식 소스는 정책브리핑, 국무조정실, 고용노동부, 보건복지부, 국토교통부, 교육부, 금융위원회 등 중앙정부 발표를 우선한다.
- 뉴스 소스는 주로 네이버 뉴스 검색 쿼리 기반이며, 청년정책, 고용, 주거, 부채, 지역, 거버넌스 등 운영 목적에 맞는 검색 축으로 나뉜다.
- 일부 공식 소스는 `detail_enrichment`와 `detail_parser`를 사용해 목록 페이지 이후 상세 본문/일자를 보강한다.
- `include_youth_related`와 `include_keywords`는 수집 단계에서 청년 관련 가능성이 높은 항목을 좁히는 보조 기준이다.
- 최종 생존 여부는 수집 단계에서 확정하지 않는다. 이후 `dedup-filter`와 큐레이션 단계에서 청년성, 공개 적합성, 중복, 메뉴별 노출 기준을 다시 적용한다.

## 새 소스 추가 체크리스트

- `kind`를 먼저 정한다: 중앙정부/공식 발표면 `official`, 언론 검색이면 `news`.
- 기존 parser로 충분한지 확인한다. 새 HTML 구조라면 `collect.py`에 parser를 추가하고 source config의 `parser` 값과 맞춘다.
- 공식 소스는 가능하면 원문 URL과 게시일을 안정적으로 확보한다.
- 뉴스 검색 소스는 너무 넓은 일반 키워드보다 청년 + 정책/이슈 맥락이 있는 쿼리로 제한한다.
- `limit`과 `detail_limit`은 수집량과 후속 enrichment 비용을 함께 고려한다.
- 추가 후 `source_healthcheck.py`, `rss_fetcher.py`, `article_funnel.json`으로 실제 수집량과 누락/과잉 여부를 확인한다.

## 개선 후보 / 논의 필요

- 지자체 동향 메뉴는 `지자체 발표 뉴스 모음`, `청년 관련 보도자료`, `기본·시행계획 지도`로 분리되었다.
- 현재 source config에는 17개 광역지자체 공식 보도자료/청년포털 직접 수집기가 아직 없다.
- 다음 수집 개편 1순위는 17개 광역지자체 공식 도메인을 `local` kind로 붙이는 것이다.
  - 지역명이 들어간 언론사/포털 소스는 `local` kind로 승격하지 않는다.
  - 기본 source kind 후보: `local`.
  - 우선 대상: 각 시·도 보도자료, 청년포털, 고시·공고, 청년정책 기본계획/시행계획 게시판.
  - 공식 도메인 후보: `seoul.go.kr`, `busan.go.kr`, `daegu.go.kr`, `incheon.go.kr`, `gwangju.go.kr`, `daejeon.go.kr`, `ulsan.go.kr`, `sejong.go.kr`, `gg.go.kr`, `province.gangwon.kr`, `chungbuk.go.kr`, `chungnam.go.kr`, `jeonbuk.go.kr`, `jeonnam.go.kr`, `gb.go.kr`, `gyeongnam.go.kr`, `jeju.go.kr`.
- 네이버 검색 쿼리의 기간, 지역, 주제 의도를 별도 표로 관리할지 검토한다.
- 공식 소스별 `include_keywords`를 정책 메뉴 기준과 동기화할지 검토한다.
- 수집 단계에서 너무 많은 일반 기업/은행 홍보성 기사가 들어오는 경우, 쿼리와 후속 공개 적합성 기준 중 어디서 줄일지 분리해서 판단한다.
