# Source Collection Criteria

수집 소스·운영 상태 기준일: 2026-10-18. 세부 판단은 현행 설정과 실행 매니페스트를 우선한다.

## 현행 코드 기준

- 표준 설정은 `public-site/config/source_config.yaml`이다. 확장자는 YAML이지만 현재 내용은 JSON 구조의 `sources` 배열이다.
- 표준 실행은 `python public-site/scripts/rss_fetcher.py`이고, 결과는 `runtime/pipeline/step1_raw_articles.json`에 쌓인다.
- 현재 등록 소스는 88개, 활성 소스는 87개다. 활성 `kind`는 `official` 10개, `news` 42개, `local` 34개, `research` 1개다. 등록은 수집 성공을 뜻하지 않는다.
- 정책브리핑 RSS는 2026-07-01 공식 종료되어 비활성화했다. 종료 공지와 사유를 설정에 보존하고, 기존 공식 HTML 수집 경로는 유지한다.
- 현재 parser 분포는 `naver_news_search`, `rss`, `korea_withyou_policy_news`, `opm_press_release`, `mohw_press_release`, `molit_board_list`, `moe_press_release`, `fsc_press_release`다.
- 공식 소스는 정책브리핑, 국무조정실, 고용노동부, 보건복지부, 국토교통부, 교육부, 금융위원회 등 중앙정부 발표를 우선한다.
- 뉴스 소스는 네이버·구글의 `청년`, `청년정책`, `청년 정책` 기본 검색과 고용·주거·부채·지역·거버넌스 등 세부 검색 축을 병행한다. 구글 기본 검색은 RSS 응답 내 최대 100건이며 포털 전체 검색 결과와 같다는 보장이 없다.
- 네이버 다음 페이지는 화면의 XLoad ‘더 보기’ URL과 JSON `collection[].html`을 따른다. 고전적인 `start` 검색 URL은 현재 첫 결과를 반복할 수 있어 동일 페이지/기사 반복 시 중단한다. 다음 URL은 같은 검색어·허용된 네이버 호스트/경로만 따른다.
- 차단 여부는 화면 문구와 실제 CAPTCHA 리다이렉트를 확인한다. 정상 검색 페이지 공통 스크립트의 captcha/login 문자열만으로 차단 처리하지 않는다. 실제 CAPTCHA는 우회하지 않는다.
- 네이버 언론사 프로필의 이미지 링크와 ‘새 창 열림’ 안내는 발행사명에서 제외한다. 뒤 페이지 수집 실패는 앞 페이지 결과를 보존하되 매니페스트에서 `partial_result`로 표시한다.
- 일부 공식 소스는 `detail_enrichment`와 `detail_parser`를 사용해 목록 페이지 이후 상세 본문/일자를 보강한다.
- `include_youth_related`와 `include_keywords`는 수집 단계에서 청년 관련 가능성이 높은 항목을 좁히는 보조 기준이다.
- 최종 생존 여부는 수집 단계에서 확정하지 않는다. 이후 `dedup-filter`와 큐레이션 단계에서 청년성, 공개 적합성, 중복, 메뉴별 노출 기준을 다시 적용한다.

## 새 소스 추가 체크리스트

- `kind`를 먼저 정한다: 중앙정부/공식 발표면 `official`, 언론 검색이면 `news`.
- 기존 parser로 충분한지 확인한다. 새 HTML 구조라면 `collect.py`에 parser를 추가하고 source config의 `parser` 값과 맞춘다.
- 공식 소스는 가능하면 원문 URL과 게시일을 안정적으로 확보한다.
- 기본 검색 경로는 포털 대조용 넓은 후보를 확보하고, 주제별 검색은 범위·깊이를 보강한다. 최종 공개 적합성은 후속 분류에서 판단하며, 포털에 나타났다는 이유만으로 전부 공개하지 않는다.
- `limit`과 `detail_limit`은 수집량과 후속 enrichment 비용을 함께 고려한다.
- 추가 후 `source_healthcheck.py`, `rss_fetcher.py`, `article_funnel.json`으로 실제 수집량과 누락/과잉 여부를 확인한다.

## 개선 후보 / 논의 필요

- 지자체 동향 메뉴는 `지자체 발표 뉴스 모음`, `청년 관련 보도자료`, `기본·시행계획 지도`로 분리되었다.
- 17개 광역지자체를 대상으로 34개 `local` 경로가 등록되어 있다. 일부 범용 검색 경로는 오류 페이지로 이동하므로 실제 지역별 수집 성공은 매니페스트로 확인한다.
- 다음 수집 개편 1순위는 오류가 확인된 범용 검색 주소를 검증된 지자체 게시판 경로·파서로 교체하는 것이다.
  - 지역명이 들어간 언론사/포털 소스는 `local` kind로 승격하지 않는다.
  - 기본 source kind 후보: `local`.
  - 우선 대상: 각 시·도 보도자료, 청년포털, 고시·공고, 청년정책 기본계획/시행계획 게시판.
  - 공식 도메인 후보: `seoul.go.kr`, `busan.go.kr`, `daegu.go.kr`, `incheon.go.kr`, `gwangju.go.kr`, `daejeon.go.kr`, `ulsan.go.kr`, `sejong.go.kr`, `gg.go.kr`, `province.gangwon.kr`, `chungbuk.go.kr`, `chungnam.go.kr`, `jeonbuk.go.kr`, `jeonnam.go.kr`, `gb.go.kr`, `gyeongnam.go.kr`, `jeju.go.kr`.
- 네이버 검색 쿼리의 기간, 지역, 주제 의도를 별도 표로 관리할지 검토한다.
- `audit_portal_coverage.py`로 동일 응답 스냅샷과 기준 커밋을 재생해 검색 경로별 후보·분류·공개 후보를 대조한다. 다음의 실제 CAPTCHA, 포털별 정렬·기간·상한 차이, 수집 이후 게시된 기사, URL/제목 변경을 분리한다. 검색 표본의 일치 비율을 전체 수집률로 보고하지 않는다.
- 공식 소스별 `include_keywords`를 정책 메뉴 기준과 동기화할지 검토한다.
- 수집 단계에서 너무 많은 일반 기업/은행 홍보성 기사가 들어오는 경우, 쿼리와 후속 공개 적합성 기준 중 어디서 줄일지 분리해서 판단한다.
