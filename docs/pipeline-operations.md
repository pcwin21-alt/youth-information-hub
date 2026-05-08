# Pipeline Operations

기준일: 2026-05-07

이 문서는 청년정책 모아봄 공개 사이트가 관리하는 파이프라인과 각 단계의 실행 방식, 산출물 계약, 운영 노하우를 정리한다. 표준 런타임 경로는 `runtime/pipeline/`, 공개 HTML 경로는 `public-site/web/`, 공유 DB 경로는 `runtime/db/articles.db`다.

## 전체 흐름

```text
source_config.yaml
  -> rss_fetcher.py
  -> dedup_filter.py
  -> run_curator.py
  -> audit_article_dates.py
  -> db_writer.py
  -> web_updater.py
  -> pipeline_feedback.py
  -> optional notifications
```

전체 실행 명령:

```powershell
python public-site\scripts\cron_runner.py --skip-outbound-notifications
```

정기 스케줄은 Windows Scheduler 기준 `09:00`, `15:00`, `21:00` 1일 3회다. 기준 정의는 `shared/src/youth_info_platform/status_utils.py`의 `UPDATE_POLICY`에 기록되어 있다.

## 1. 뉴스·공식 발표 수집

Entry point:

```powershell
python public-site\scripts\rss_fetcher.py
```

입력:

- `public-site/config/source_config.yaml`

출력:

- `runtime/pipeline/step1_raw_articles.json`

주요 코드:

- `shared/src/youth_info_platform/collect.py`
- parser registry: `PARSER_REGISTRY`

운영 기준:

- `kind=official`: 정책브리핑, 중앙부처 RSS/보도자료, 위원회·정부기관 발표.
- `kind=news`: 네이버/구글 뉴스 검색 기반 언론 기사.
- `kind=local`: 지자체 공식 보도자료, 공고, 청년정책 기본·시행계획.
- 수집 단계는 “많이 모으되 소스별 1차 keyword/domain 필터를 적용”한다.
- 최종 공개 여부는 이 단계에서 확정하지 않는다. 공개 판단은 dedup/filter와 curator가 맡는다.

현재 노하우:

- Google News RSS는 portal published date를 원문 날짜로 신뢰하지 않는다.
- Naver 검색 결과는 publisher URL, publisher name, allowed/blocked domain을 같이 본다.
- 공식 HTML 게시판은 canonical URL이 게시판 루트로 떨어지는 경우가 있다. 이 경우 원래 상세 URL의 `articleNo`, `newsId`, `nttNo` 같은 식별자를 보존해야 중복으로 접히지 않는다.
- 지자체 수집은 범용 검색 URL보다 지자체별 보도자료/공고 board parser가 안정적이다. 범용 검색은 0건 또는 RuntimeError가 나도 전체 배치를 중단하지 않는 보조 소스로 본다.

## 2. 유튜브 수집

Entry point:

```powershell
python public-site\scripts\youtube_fetcher.py
```

출력:

- `runtime/pipeline/step1_raw_youtube.json`

현재 MVP에서는 기사 송출의 핵심 경로가 아니며, 공개 사이트 보조 콘텐츠 후보로만 다룬다.

## 3. 중복 제거와 1차 생존 필터

Entry point:

```powershell
python public-site\scripts\dedup_filter.py
```

입력:

- `runtime/pipeline/step1_raw_articles.json`

출력:

- `runtime/pipeline/step2_filtered.json`

주요 코드:

- `shared/src/youth_info_platform/curation.py`
- `shared/src/youth_info_platform/article_metadata.py`

운영 기준:

- 같은 URL, publisher URL, canonical URL, feed URL을 우선 식별자로 본다.
- URL 식별자가 불안정하면 제목/출처/게시일 기반 보조 identity를 사용한다.
- 공식 소스와 청년 직접 신호가 있는 기사는 생존 우선순위가 높다.
- noise, 순수 선거전, 홍보성 기업 기사, 청년 신호가 약한 일반 정치 분석은 공개 후보에서 멀어진다.

주의:

- 후처리 메타데이터가 기존 수집 제목보다 일반적인 페이지 제목이면 원제목을 보존한다.
- 공식/지자체 게시판의 canonical이 상세 identity를 잃으면 기존 상세 URL을 유지한다.

## 4. 큐레이션·분류·요약

Entry point:

```powershell
python public-site\scripts\run_curator.py
```

입력:

- `runtime/pipeline/step2_filtered.json`

출력:

- `runtime/pipeline/step3_classified.json`
- `runtime/pipeline/step4_selected.json`
- `runtime/pipeline/step5_summarized.json`
- `runtime/pipeline/article_funnel.json`
- `runtime/pipeline/ops_radar.json`

운영 기준:

- `step3_classified`: 공개 가능성, topic, region, policy type, governance signal을 붙인 전체 후보.
- `step4_selected`: 홈/주요 카드에 올릴 좁은 선별본.
- `step5_summarized`: 공개 DB와 상단 요약에 쓰는 최종 기사.
- `article_funnel.json`: 왜 남았고 왜 빠졌는지 추적하는 운영 감사 파일.
- `ops_radar.json`: 운영자가 놓치기 쉬운 후보를 따로 잡아내는 보조 레이더.

노하우:

- 홈의 일부 섹션은 `step5`만 보지 않고 `step3_classified`의 공개 후보까지 본다. 그래서 “최종 selected가 적다”와 “홈 후보가 적다”는 다른 문제다.
- 반대로 `step3`에 후보가 있어도 `published_date`가 없으면 최근성 필터에서 빠질 수 있다.

## 5. 날짜 감사

Entry point:

```powershell
python public-site\scripts\audit_article_dates.py
```

출력:

- `runtime/pipeline/article_date_audit.json`

운영 기준:

- error는 송출 차단 조건이다.
- warning은 즉시 차단하지 않지만 반복 source는 parser 개선 후보로 올린다.
- Google News wrapper 날짜와 원문 날짜를 구분한다.

## 6. DB 발행

Entry point:

```powershell
python public-site\scripts\db_writer.py
```

입력:

- `runtime/pipeline/step5_summarized.json`
- `runtime/pipeline/step2_filtered.json`

출력:

- `runtime/db/articles.db`

운영 기준:

- 공개용 최종 기사와 archive를 함께 갱신한다.
- DB는 기관용 포털과 공유될 수 있으므로 schema 변경은 공개 사이트와 기관 사이트를 함께 고려한다.

## 7. 공개 HTML 발행

Entry point:

```powershell
python public-site\scripts\web_updater.py
```

입력:

- `step5_summarized.json`
- `step3_classified.json`
- settings/contact 설정

출력:

- `public-site/web/*.html`

주요 노출 기준:

- 홈 최신 뉴스: 공식 소스 제외, 선거·공약 제외, noise/opinion 제외.
- 홈 정부 동향: `정부 동향` 페이지의 중앙정부 공식 발표·주요 정책 자료 후보를 사용한다. 지자체 발표는 홈의 정부 영역에 섞지 않는다.
- 정책/정부 동향 페이지: `중앙정부 관련 뉴스`, `중앙정부 공식 보도자료`, `주요 정책·시행계획 자료` 세 구역으로 분리한다.
- 지자체 동향 페이지: 지자체 공식 보도자료, 공고, 기본·시행계획 우선.
- 뉴스 페이지: 언론 기사 중심, 공식 발표는 별도 메뉴로 보낸다.

노하우:

- 홈 리스트가 적을 때는 `HOME_DAILY_LIMIT`부터 보지 않는다. 먼저 후보 풀 수를 본다.
- 홈 정부 동향 후보 풀은 `build_government_trend_articles`를 통해 중앙정부 공식 발표와 주요 정책 자료를 함께 보강한다. 날짜는 표시용 fallback 기준과 URL identity를 함께 확인한다.
- 중앙정부 관련 뉴스 후보 풀은 `build_government_related_news_articles`를 통해 `정부 동향` 첫 구역으로 렌더한다. 공식 보도자료와 섞지 않는다.
- 주요 정책·시행계획 자료는 `build_government_policy_resource_articles`의 중앙부처 watchlist로 렌더한다.
- `public-site/web/`는 Pages prebuilt 배포의 원본이다. `public-site/dist/`는 패키징 산출물이다.

## 8. 피드백 점검

Entry point:

```powershell
python public-site\scripts\pipeline_feedback.py
```

출력:

- `runtime/pipeline/pipeline_feedback_report.json`
- `runtime/pipeline/pipeline_feedback_report.md`

역할:

- 수집량, 필터 생존량, 최종 송출량, 날짜 오류, source health, 공개 HTML, 홈 정부 동향 후보 수, 정부 동향 내부 구역 카드 수를 한 번에 점검한다.
- `critical`은 배치를 실패시킬 수 있는 문제다.
- `warning`은 송출은 가능하지만 다음 운영 정비 backlog로 올릴 문제다.
- `info`는 참고 신호다.

정밀 점검:

```powershell
python public-site\scripts\pipeline_feedback.py --run-source-healthcheck
```

보수적 자가복구:

```powershell
python public-site\scripts\pipeline_feedback.py --self-heal --run-source-healthcheck
```

자가복구는 누락된 날짜 감사/웹 HTML/source health를 재생성하고, 핵심 산출물이 없거나 배치 상태가 실패일 때 전체 배치를 1회 재실행한다.

## 9. 알림 송출

Entry points:

```powershell
python public-site\scripts\telegram_bot.py
python public-site\scripts\slack_bot.py
```

기본 운영에서는 `--skip-outbound-notifications`를 붙여 검증과 발행을 먼저 안정화한다. 외부 알림은 중복 송출 위험이 있으므로 별도 설정 확인 후 켠다.

## 10. Pages 패키징과 배포

Entry point:

```powershell
python public-site\scripts\prepare_pages_site.py --site-dir public-site\dist
```

출력:

- `public-site/dist/`

GitHub Pages prebuilt 배포는 로컬에서 생성된 `public-site/web/`와 runtime artifact를 기준으로 한다. prebuilt 배포 전에는 반드시 다음을 통과시킨다.

```powershell
python public-site\scripts\verify_site_artifacts.py --min-articles 1 --min-news-cards 0
python public-site\scripts\pipeline_feedback.py
```

## 운영 원칙

- 수집량 문제와 노출량 문제를 분리한다.
- 공식/지자체 자료는 원문 상세 URL identity를 보존한다.
- 날짜가 없는 자료는 최근성 UI에서 빠질 수 있으므로 수집 parser 단계에서 날짜를 최대한 확보한다. 공개 웹은 표시용 날짜를 `publisher_published_at -> published_date -> portal_published_at` 순서로 보완한다.
- warning은 무시하지 않고 다음 parser/source 개선 backlog로 보낸다.
- critical은 배치 실패로 보고, 사이트를 조용히 잘못 갱신하지 않는다.

## 11. 공개 기사 날짜 fallback 기준

- 공개 웹의 기사 노출, 정렬, 최근성 필터는 `publisher_published_at -> published_date -> portal_published_at` 순서로 표시용 날짜를 잡는다.
- `published_date`는 원문 발행일 의미를 유지한다. Google News처럼 원문 발행일을 확정하지 못하고 포털 수집 시각만 있는 기사는 `portal_published_at`으로 공개 페이지에 노출한다.
- “최근 기사 40개만 잡힘”처럼 보이면 수집량부터 의심하지 말고 `pipeline_status.json`의 collected/filtered 수와 `pipeline_feedback_report.md`의 `news cards`, `public news candidates with display date`, `public news fallback-date candidates`를 먼저 비교한다.
- `news_cards_below_candidate_pool` warning은 공개 후보는 충분한데 `news.html` 카드가 후보 풀의 기준 비율보다 적다는 뜻이다. 이때는 `web_updater.py`의 날짜 fallback, 뉴스/선거/정책 메뉴 분리 조건, `step3_classified.json`의 공개 후보를 함께 확인한다.
