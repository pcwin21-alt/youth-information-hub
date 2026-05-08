# Pipeline Feedback Routine

기준일: 2026-05-07

목표는 운영자가 매번 눈으로 돌보지 않아도 파이프라인이 스스로 이상 신호를 발견하고, 가능한 범위에서는 스스로 복구하며, 복구가 어려운 문제는 원인과 다음 조치를 남기는 것이다.

## 루틴 개요

```text
정기 배치
  -> cron_runner.py
  -> publish_web
  -> pipeline_feedback.py
  -> critical이면 배치 실패 처리
  -> warning이면 리포트에 남기고 송출 유지
```

기본 정기 실행:

```powershell
python public-site\scripts\cron_runner.py --skip-outbound-notifications
```

정밀 점검 포함 실행:

```powershell
python public-site\scripts\cron_runner.py --skip-outbound-notifications --feedback-with-source-healthcheck
```

수동 자가복구 실행:

```powershell
python public-site\scripts\pipeline_feedback.py --self-heal --run-source-healthcheck
```

## 점검 산출물

- JSON: `runtime/pipeline/pipeline_feedback_report.json`
- Markdown: `runtime/pipeline/pipeline_feedback_report.md`
- 소스 헬스체크: `runtime/pipeline/source_healthcheck.json`
- 배치 상태: `runtime/pipeline/pipeline_status.json`
- 날짜 감사: `runtime/pipeline/article_date_audit.json`

## 매 배치 후 자동으로 보는 것

`pipeline_feedback.py`는 기본적으로 네트워크를 새로 긁지 않고 이미 생성된 산출물을 읽어 빠르게 판정한다.

Critical:

- 필수 산출물 누락
- 원본 수집량이 기준 이하
- 중복 제거 후 생존량이 기준 이하
- 분류/최종 송출량이 기준 이하
- 최근 배치 상태가 completed가 아님
- 날짜 감사 error 발생
- 공개 HTML 누락
- 뉴스 카드 부족
- 홈 정부 동향 후보 부족
- 브랜드 문구 누락
- 공식 소스 필터 통과 항목 0건

Warning:

- source healthcheck가 없거나 오래됨
- 지자체 소스 오류
- 지자체 공식 수집 지역 수 부족
- 공식 소스 중 total_items=0인 항목
- 날짜 감사 warning

Info:

- 송출 차단은 아니지만 운영자가 알아야 할 참고 신호

## 주기별 운영

### 매 배치

자동:

```powershell
python public-site\scripts\pipeline_feedback.py
```

판단:

- `verdict=pass`: 그대로 둔다.
- `verdict=warn`: 사이트 송출은 유지하되 리포트의 Next Actions를 backlog로 보낸다.
- `verdict=fail`: 배치 실패로 보고 원인 step을 재실행한다.

### 매일 1회

소스까지 정밀 점검:

```powershell
python public-site\scripts\pipeline_feedback.py --run-source-healthcheck
```

목적:

- 수집 source별 `total_items`, `filtered_items`, `date_error_count`를 갱신한다.
- 지자체 source의 0건/RuntimeError 추이를 본다.
- 공식 source가 조용히 깨지는 문제를 조기 발견한다.

### 주 1회

운영 리뷰:

```powershell
python public-site\scripts\source_healthcheck.py
python public-site\scripts\pipeline_feedback.py
python public-site\scripts\verify_site_artifacts.py --min-articles 1 --min-news-cards 0
```

리뷰 항목:

- 0건 source가 계속 0건인지
- RuntimeError source가 반복되는지
- 공식 source의 filtered_items가 특정 기관에만 몰리는지
- 지자체 수집 지역이 늘고 있는지
- 홈 정부 동향 후보가 충분한지
- 정부 동향의 정부 발표 뉴스 카드가 0건인지
- 정부 동향의 각 부처별 기본·시행계획 자료 카드가 빠졌는지
- 날짜 warning이 같은 parser에서 반복되는지

## 자가복구 정책

`--self-heal`은 보수적으로 동작한다.

자동으로 할 수 있는 것:

- `article_date_audit.json`이 없으면 `audit_article_dates.py` 실행
- `public-site/web/index.html`이 없으면 `web_updater.py` 실행
- `--run-source-healthcheck`가 같이 있으면 `source_healthcheck.py` 실행
- 핵심 산출물이 없거나 최근 배치 상태가 실패면 `cron_runner.py --skip-outbound-notifications --skip-feedback` 1회 실행

자동으로 하지 않는 것:

- source URL 임의 변경
- include/exclude keyword 임의 수정
- parser 로직 임의 완화
- 외부 알림 재송출
- git commit/push/deploy

이 제한은 중요하다. 자동 복구는 “다시 돌리면 회복되는 문제”만 처리하고, 기준 변경이 필요한 문제는 리포트로 남긴다.

## 실패별 대응

### low_raw_article_count

의미:

- 소스 수집 자체가 줄었다.

확인:

```powershell
python public-site\scripts\source_healthcheck.py
```

조치:

- `source_config.yaml`의 enabled source 수 확인
- parser registry 확인
- RSS/검색 URL이 차단되거나 HTML 구조가 바뀌었는지 확인

### low_filtered_article_count

의미:

- 수집은 됐지만 dedup/filter에서 너무 많이 빠졌다.

확인:

```powershell
python public-site\scripts\dedup_filter.py
```

조치:

- `drop_reason`
- `include_keywords`
- `exclude_keywords`
- 공식 source identity
- youth signal 기준

### low_summarized_article_count

의미:

- 공개 최종 선별이 과하게 줄었다.

확인:

```powershell
python public-site\scripts\run_curator.py
```

조치:

- bucket 최소치
- public relevance
- selection score
- editorial overrides

### low_home_government_trends

의미:

- 홈의 정부 동향 후보가 부족하다.

확인:

- `build_government_trend_articles`
- `is_central_government_announcement`
- `published_date`, `publisher_published_at`, `portal_published_at`
- `canonical_url`/`publisher_url`이 상세 identity를 잃었는지
- `policies.html`의 정부 발표 뉴스·정부 홈페이지 보도자료 후보와 홈 카운트가 맞는지

조치:

- 공식 보도자료 상세 URL 보존
- 홈 정부 영역은 `정부 동향` 페이지 후보 생성 기준을 공유한다.
- 지자체 공식 발표는 `지자체 동향` 또는 `신청 정책` 영역에서 다룬다.

### low_government_related_news_cards

의미:

- `정부 동향` 안의 `정부 발표 뉴스 모음` 구역에 표시되는 언론 기사 카드가 부족하다.
- 공식 보도자료 수집 문제와 별개로, 언론 기사 후보 분리 조건이 너무 좁거나 중앙정부 키워드가 누락됐을 수 있다.

확인:

- `build_government_related_news_articles`
- `is_central_government_related_news_article`
- 중앙정부 부처명, 국무조정실, 정책브리핑, 장관·부처 발표 키워드가 제목·요약·리드에서 잡히는지
- 지자체·선거·공약성 기사 제외 조건이 정부 발표 뉴스까지 과하게 막고 있지 않은지
- 제목·출처가 중앙정부 주체인데 리드의 지역 장소명 때문에 지자체 동향으로 밀려나지 않는지

조치:

- 정부 발표 뉴스는 공식 보도자료와 섞지 말고 정부 동향의 첫 구역(`#main-list`)에 둔다.
- 후보가 0건이면 `step3_classified.json`의 비공식 뉴스 중 중앙정부 키워드 후보를 먼저 샘플링한다.

### low_government_policy_resource_cards

의미:

- `정부 동향` 안의 `각 부처별 기본·시행계획 자료 모음` 구역에 표시되는 중앙부처 공식 경로 카드가 부족하다.
- 정부 동향 메뉴가 지자체 동향처럼 3갈래로 보이지 않거나, 중앙부처 watchlist 렌더링이 빠졌을 수 있다.

확인:

- `build_government_policy_resource_articles`
- `build_curated_major_policy_articles`
- `CENTRAL_MINISTRY_AUTHORITIES`
- `data-government-policy-resource-card="true"` 카드가 `policies.html`에 출력되는지

조치:

- 각 부처별 기본·시행계획 자료는 공식 보도자료와 섞지 말고 `government-policy-resources` 구역에 둔다.
- 카드가 0건이면 중앙부처 watchlist와 렌더링 속성 누락을 먼저 확인한다.

### news_cards_below_candidate_pool

의미:

- 공개 후보와 표시용 날짜가 충분한데 `news.html` 카드 수가 후보 풀의 기준 비율보다 낮다.
- 수집량 부족이 아니라 공개 HTML 노출 조건, 날짜 fallback, 메뉴 분리 조건에서 후보가 빠졌을 가능성이 높다.

확인:

- `pipeline_feedback_report.md`의 `news cards`, `public news candidates with display date`, `public news fallback-date candidates`
- `step3_classified.json`에서 `published_date`는 없지만 `portal_published_at`이나 `publisher_published_at`이 있는 기사 수
- `web_updater.py`의 표시용 날짜 순서: `publisher_published_at -> published_date -> portal_published_at`
- 뉴스/선거/정책 메뉴 분리 조건 때문에 `news.html`에서 제외된 후보가 있는지

조치:

- Google News처럼 원문 발행일이 비어 있는 기사는 `portal_published_at`을 공개 노출 날짜로 사용한다.
- `published_date` 자체를 포털 시각으로 덮어쓰지 않는다. 원문 발행일 의미는 유지하고, 공개 웹에서만 fallback을 적용한다.
- 카드 수가 40건처럼 낮아 보이면 `pipeline_status.json`의 collected/filtered 수와 후보 풀 지표를 먼저 비교한다.

### local_source_errors

의미:

- 지자체 공식 source가 깨졌거나 범용 검색 URL이 불안정하다.

조치:

- 범용 `/search?keyword=청년`보다 실제 보도자료/공고 게시판 URL을 우선한다.
- 지역별 parser fixture를 만든다.
- 17개 광역 지자체 중 최소 2개 이상부터 안정화하고 점진 확장한다.

## 기록 원칙

- 점검 결과는 JSON과 Markdown 둘 다 남긴다.
- critical은 배치를 실패시켜 조용한 오송출을 막는다.
- warning은 운영 backlog로 남긴다.
- “현재 동작”과 “개선 후보”를 문서에서 구분한다.
- 원인을 모르는 수동 완화는 금지한다. 먼저 funnel/source health/date audit으로 병목을 숫자로 확인한다.
