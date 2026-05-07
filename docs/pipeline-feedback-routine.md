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
- 홈 정부·지자체 동향 후보 부족
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
- 홈 정부·지자체 동향 후보가 충분한지
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

- 홈의 정부·지자체 동향 후보가 부족하다.

확인:

- `is_home_central_official_announcement`
- `is_home_local_official_announcement`
- `published_date`
- `canonical_url`/`publisher_url`이 상세 identity를 잃었는지
- 지자체 source가 날짜를 못 뽑고 있는지

조치:

- 공식 보도자료 상세 URL 보존
- 지자체 parser에서 날짜 추출 강화
- 홈 노출 조건은 완화보다 먼저 후보 품질을 확인

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
