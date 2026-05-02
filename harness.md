# 청년 투게더 HARNESS

Last updated: 2026-04-24

이 문서는 청년 투게더 저장소의 작업 맥락, 운영 규칙, 재발 방지 지침, 실제 장애 기록을 한 곳에 모아둔 살아 있는 운영 문서다.

목적은 세 가지다.

1. 다음 작업자가 현재 시스템의 진짜 기준점을 빠르게 파악할 것
2. 이미 겪은 오류를 다시 밟지 않을 것
3. 기능 변경과 배포를 할 때 무엇을 건드려야 하고 무엇을 건드리면 안 되는지 명확히 남길 것

이 문서는 기능 추가나 장애 수정이 끝날 때마다 반드시 갱신한다. 특히 아래 중 하나가 있었으면 업데이트한다.

- 수집 누락, 잘못된 필터링, 제목/요약 파손, 잘못된 배지/홈 노출
- 관리자 기능 추가/권한 변경
- 배포 경로 변경
- 운영 규칙 변경
- 사용자에게 직접 설명했던 예외 처리나 정책 완화/강화

## 1. 현재 제품 맥락

### 1-1. 서비스 정체성

- 서비스명: `청년 투게더`
- 메인 문구: `오늘의 청년 정책과 이슈를 한곳에`
- 운영 주체 표기: `유스사이드(Youthside)`
- `유쾌한청년들` 명칭은 더 이상 사용하지 않는다.

### 1-2. 현재 운영 우선순위

- 기관용 관리자 진입점은 `institution-site` Django다.
- 공개 사이트는 `public-site`에서 정적 HTML로 생성되어 GitHub Pages에 배포된다.
- 뉴스 수집 품질은 `기사 수 최대화`보다 `정밀도 우선`이다.
- 다만 `청년 공약/정책 기사`는 완전 배제하지 않는다.
  - 전체 뉴스/아카이브에는 남길 수 있다.
  - 홈 메인에서는 선거성 공방 기사를 약하게 다룬다.
- `청년센터`, `청년공간`, `청년허브`, 기관 운영 변화, 예산/조례/지원사업, 모집/공고 계열은 놓치지 않는 것이 핵심이다.
- `청년유니온`은 현재 우선 수집 키워드로 강하게 밀지 않는다.

### 1-3. 현재 홈 운영 원칙

- 홈에는 `대표 하이라이트`가 있으면 최상단 별도 카드로 노출한다.
- 홈 메인 핵심 리스트는 `오늘 놓치면 안되는 뉴스` 중심으로 운영한다.
- 한때 `이번 주 계속 볼 기사` 실험이 있었지만 현재 공개 홈에서는 제거된 상태다.
- 정치성/선거성 기사 전체를 없애는 것이 아니라, 홈 메인의 즉시성 리스트에서만 보수적으로 다룬다.

## 2. 저장소 구조와 source of truth

### 2-1. 핵심 디렉터리

- `shared/`
  - 공용 파이썬 패키지
  - 수집/메타데이터/큐레이션/편집 오버라이드/ops radar 등의 핵심 로직
- `public-site/`
  - 공개 사이트 생성 스크립트와 정적 결과물
- `institution-site/`
  - Django 관리자 콘솔
- `runtime/`
  - 파이프라인 산출물, DB, 상태 파일, lock 파일

### 2-2. 실무상 중요한 파일

- 수집 소스 설정: `public-site/config/source_config.yaml`
- 메타데이터 해석: `shared/src/youth_info_platform/article_metadata.py`
- 큐레이션/선정 규칙: `shared/src/youth_info_platform/curation.py`
- 편집 오버라이드/수동 기사 병합: `shared/src/youth_info_platform/editorial.py`
- ops radar 계산: `shared/src/youth_info_platform/ops_radar.py`
- 공개 렌더러: `public-site/scripts/web_updater.py`
- 공개 큐레이터 실행: `public-site/scripts/run_curator.py`
- 수집기: `public-site/scripts/rss_fetcher.py`
- 헬스체크: `public-site/scripts/source_healthcheck.py`
- Pages용 정적 사이트 패키징: `public-site/scripts/prepare_pages_site.py`
- 산출물 검증: `public-site/scripts/verify_site_artifacts.py`
- Django 운영 뷰: `institution-site/briefings/views.py`
- Django 운영 편집 로직: `institution-site/briefings/editorial.py`
- 동기화 명령: `institution-site/briefings/management/commands/sync_runtime_articles.py`

### 2-3. 데이터 계약

- 공개 사이트 웹 루트: `public-site/web/`
- GitHub Pages 배포 대상: `public-site/dist/`
- 파이프라인 산출물: `runtime/pipeline/`
- 공용 DB: `runtime/db/articles.db`
- 문의/연락처 설정 JSON: `public-site/content/contact_settings.json`
- 자동 반영 상태 파일: `runtime/pipeline/auto_update_status.json`
- 중복 실행 방지 lock: `runtime/pipeline/pipeline.lock`

### 2-4. 매우 중요한 배포 규칙

GitHub Pages는 `public-site/web/`를 직접 배포하지 않는다.

실제 흐름은 아래다.

1. `public-site/web/`를 생성/수정한다.
2. `python public-site/scripts/prepare_pages_site.py --site-dir public-site/dist`
3. 워크플로우가 `public-site/dist/`를 Pages 아티팩트로 업로드한다.

즉, `web`만 고치고 `dist`를 다시 만들지 않으면 라이브에 반영되지 않는다.

## 3. 현재 운영 기능 기준

### 3-1. 관리자 콘솔

주요 경로:

- `/editorial/`
  - 기사 운영
  - 수동 기사 URL 추가
  - `기본 / 포함 / 배제`
  - 대표 하이라이트 1건 지정
  - `지금 수집 및 반영`
  - `공개 반영`
- `/editorial/settings/`
  - 자동 반영 설정
  - 문의/연락처 설정
  - 자동 반영 상태 해석
- `/editorial/history/`
  - 감사 로그/반영 이력
- `/editorial/analytics/`
  - 방문자/유입 통계

권한 기준:

- `superuser`, `platform_admin`: 편집/실행 가능
- `staff`: 열람 중심, 주요 실행/설정 변경 불가

### 3-2. 자동 반영 운영 기준

- 주력 자동 반영은 `노트북이 켜져 있고 러너가 실행 중일 때만` 동작한다.
- 웹에서 ON/OFF를 바꾼다고 프로세스가 시작되지는 않는다.
- 실제 시작/중지는 아래 스크립트가 운영 표준이다.
  - `public-site/scripts/start_auto_update.ps1`
  - `public-site/scripts/stop_auto_update.ps1`
- 어드민 서버가 내려가 있어도 로컬에서는 `powershell -ExecutionPolicy Bypass -File public-site/scripts/refresh_public_site_now.ps1`로 전체 파이프라인을 직접 실행할 수 있다.
- 로컬 PC를 쓰지 못하는 상황에서는 GitHub Actions `Build And Deploy Pages`의 `Run workflow`를 수동 실행하는 경로를 백업으로 둔다.
- GitHub Pages 정시 배포는 백업 경로로 유지한다.

### 3-3. 기사 운영 계약

현재 기사 편집 필드 핵심:

- `editorial_decision = default | include | exclude`
- `editorial_is_highlighted = bool`
- `is_manual_entry = bool`
- `clean_score = int`
- `clean_labels = list[str]`

원칙:

- 하이라이트는 전역 1건만 허용
- 하이라이트 지정 시 자동으로 `include`
- `exclude`로 바꾸면 하이라이트 자동 해제
- 수동 URL 추가 기사는 `manual_articles`로 export되어 런타임 기사와 병합된다

## 4. 검색/수집 엔진에 대한 현재 합의

### 4-1. 기본 방향

- `Google News RSS 중심`이 아니라 `Naver 뉴스검색 직접 크롤링 중심`
- `Google News RSS`는 완전 제거가 아니라 백업 엔진
- YTN은 깨진 RSS를 고치려고 매달리지 않고 `Naver 기반 전용 소스`로 복구
- 연합뉴스는 직접 RSS 기본 경로를 내리고 `Naver 전용 + Google 보조`로 보강

### 4-2. 수집 품질 규칙

- `청년` 단독 언급 기사에 과하게 관대하면 정치성/잡음이 많이 들어온다.
- 강한 청년 기사 신호는 아래 계열을 우선 본다.
  - 실질 이슈: 고용, 주거, 부채, 금융, 노동, 복지, 은둔
  - 기관/현장: 청년센터, 청년공간, 청년허브, 운영, 위탁, 개소, 폐지
  - 정책/행정: 조례, 예산, 계획, 시행, 사업, 모집, 발표
- 선거/후보/유세/공천/지지율/단일화는 `campaign_political`
- 위 요소가 있어도 청년센터/예산/조례/운영/시행 같은 정책 신호가 함께 있으면 `substantive_promise`

실무 해석:

- `campaign_political`
  - 홈 메인에는 기본적으로 약하게 반영하거나 제외
- `substantive_promise`
  - 뉴스 본문/아카이브에는 유지 가능
  - 홈에서는 더 신중하게 다룬다

### 4-3. 키워드 관련 현재 주의점

- `청년센터`는 반드시 수집 축에 포함되어야 한다.
- 현재 `source_config.yaml`에 `청년센터`, `청년센터장` 등 관련 키워드가 포함되어 있다.
- `청년`만 들어간 기사라고 해서 모두 좋은 결과는 아니다.
- 반대로, 청년센터/기관 운영/예산/사업성 기사는 선거 맥락이 섞여 있어도 아예 버리면 안 된다.

## 5. 운영 레이더(ops radar) 해석

관리자 화면의 `레이더 후보 / 놓침 후보 / 상위 노출 포함 / critical`은 아래 의미다.

- 레이더 후보
  - 운영적으로 챙겨볼 가치가 있는 기사로 radar lane에 매칭된 전체 기사 수
- 놓침 후보
  - radar에는 걸렸지만 메인 selection에는 들지 못한 기사 수
- 상위 노출 포함
  - radar 매칭 기사 중 실제 selection에 포함된 수
- `critical`
  - `ops_radar_score >= 18`
  - 보통 아래가 겹치면 올라간다.
    - 청년센터/기관 운영 변화
    - 모집/공고/거버넌스/리스크 키워드 다중 매칭
    - 최신성
    - 지역/이슈 태그/공공성
    - selection에서 놓친 기사일 경우 가산점

현재 radar lane 대표 범주:

- 청년센터 운영
- 기관/사업 공고
- 거버넌스/인사
- 정치/공약
- 리스크/갈등/감사/예산 삭감

주의:

- ops radar는 `홈 노출 결정기`가 아니라 `운영 감시 보조판`이다.
- `critical`이라고 자동으로 홈 메인에 올라가는 것은 아니다.

## 6. 재발 방지용 장애 기록

아래는 현재까지 확인된 주요 오류와 운영상 실수, 그리고 방지 규칙이다.

### Incident 01. Google RSS 중심 수집으로 누락/저품질 발생

증상:

- YTN RSS가 깨져 안정적으로 수집되지 않음
- 연합뉴스 RSS는 파싱은 되더라도 실질 통과 건수가 거의 없었음
- `청년센터`나 기관 운영 기사 누락이 잦았음
- Google RSS 광범위 쿼리에서 `청년`만 들어간 약한 기사, 정치성 기사, 포털성 잡음이 많이 섞였음

원인:

- RSS 엔드포인트 품질 편차가 큼
- `청년` 단일 키워드 의존도가 높음
- source-specific precision 통제가 부족했음

조치:

- `Naver 뉴스검색 직접 크롤링`을 주력으로 재설계
- `BeautifulSoup` 기반 파서 추가
- `allowed_domain_suffixes`, `blocked_domain_suffixes`, `allowed_publishers`, `blocked_publishers` 도입
- YTN/연합뉴스를 Naver 전용 소스로 재편
- Google RSS는 보조 엔진으로 축소

재발 방지:

- 새로운 뉴스 소스는 domain/publisher allowlist 없이는 주력 소스로 올리지 않는다.
- `청년` 단독 키워드 쿼리는 반드시 더 구체적인 신호와 함께 평가한다.
- `청년센터`, `청년공간`, `청년허브`, 예산/조례/사업 신호는 누락 여부를 우선 모니터링한다.

### Incident 02. 수집기와 헬스체크의 parser map 불일치

증상:

- 실제 수집은 되는데 `source_healthcheck`에서는 `unsupported_parser`가 뜨는 불일치가 있었음

원인:

- `collect_articles`와 `source_healthcheck`가 서로 다른 parser 맵을 참조함

조치:

- 공용 parser registry를 도입해 둘 다 같은 registry를 사용하도록 정리

재발 방지:

- 파서를 추가/삭제할 때는 registry 기준으로만 변경한다.
- 신규 parser를 넣은 뒤 `source_healthcheck.py`에서 `unsupported_parser`가 남으면 배포하지 않는다.

### Incident 03. 홈 메인에 정치성/선거성 기사 과다 노출

증상:

- 지방선거 시기 기사에서 `청년`만 들어가도 홈 메인에 과하게 올라옴
- 후보 동정, 유세, 공천, 단일화, 공방성 기사도 체감상 많이 보였음
- 사용자 입장에서는 `오늘 놓치면 안 되는 뉴스`가 너무 자주 흔들리거나 중요도 대비 산만하게 느껴짐

원인:

- `청년` 단독 신호의 가중치가 높았음
- 홈 메인용 별도 억제 로직이 부족했음

조치:

- `campaign_political`, `substantive_promise` 내부 신호 도입
- 홈 전용 필터/감점 강화
- 청년센터/예산/조례/지원사업/운영 변화 기사 우대
- 완전 배제가 아니라 `홈 위치 조정` 중심으로 재설계
- `이번 주 계속 볼 기사` 실험을 거쳤으나 현재는 제거

재발 방지:

- 선거성 기사 전체를 없애지 말고 `홈`과 `전체 뉴스`의 역할을 분리한다.
- `공약형 기사`는 정책 실질성이 있으면 유지 가능하다.
- 다만 `오늘 놓치면 안 되는 뉴스`는 즉시성/공공성/운영 체감성을 더 엄격히 본다.

### Incident 04. 관리자 수동 개입 경로 부족

증상:

- 놓친 기사를 운영자가 직접 넣기 어려웠음
- 포함/배제와 대표 노출을 분리해서 다루기 어려웠음
- 문의/연락처 설정이 별도 Basic Auth 서버에 의존해 운영 경로가 분산되었음

원인:

- 초기 운영도구가 자동 파이프라인 중심이었고, 수동 운영 시나리오가 얕았음

조치:

- Django 관리 화면을 운영 허브로 확정
- `/editorial/`에서 수동 URL 추가, 포함/기본/배제, 대표 하이라이트 1건 운영 가능하게 확장
- `clean_score`, `clean_labels` 추가
- 문의/연락처 설정을 Django로 흡수
- 감사 로그 `AdminAuditLog` 추가

재발 방지:

- “자동이 못 잡으면 운영자가 바로 넣을 수 있어야 한다”를 기본 원칙으로 유지한다.
- 새 운영 기능은 가능한 한 Django 안으로 수렴시킨다.
- 별도 Basic Auth mini server를 새 운영 표준으로 다시 도입하지 않는다.

### Incident 05. 자동 반영에 대한 오해

증상:

- 사용자가 “실시간 자동 반영”으로 기대했지만 실제로는 정시/수동 업데이트 중심으로 이해가 엇갈렸음
- 노트북이 꺼져 있을 때는 자동 반영이 되지 않는 구조를 명확히 설명할 필요가 생김

원인:

- GitHub Pages 자체는 상시 서버가 아니고
- 로컬 laptop runner 기반 자동 반영은 프로세스가 실행 중일 때만 동작함

조치:

- 운영 기준을 `노트북이 켜져 있을 때만 동작하는 polling`으로 명문화
- 관리자 화면에 상태 해석을 보강
- `지금 수집 및 반영` 수동 전체 파이프라인 버튼 추가
- `pipeline.lock` 존재 시 중복 실행 방지

재발 방지:

- 자동 반영 상태를 말할 때는 항상 아래 둘을 구분한다.
  - 설정이 ON인지
  - 러너가 실제로 살아 있는지
- “웹에서 ON했다 = 실행 중”으로 설명하지 않는다.
- 수동 실행 경로는 계속 관리자 전용으로 유지한다.

### Incident 06. 단일 기사 수정 시 전체 큐레이션이 흔들리는 배포 실수 위험

증상:

- 특정 기사 한 건만 고치고 싶어도 `run_curator.py`, `web_updater.py`를 다시 돌리면 unrelated 기사들이 같이 바뀔 수 있음
- 작은 렌더링 수정과 전체 selection 변경이 한 커밋에 섞일 위험이 있었음

원인:

- 정적 산출물이 큐레이션 결과와 묶여 있어, 전체 재생성이 곧 콘텐츠 전체 변경으로 이어질 수 있음

조치:

- “작은 표시 오류”와 “파이프라인 재생성”을 구분해서 다루는 운영 원칙을 세움
- 단일 카드/문구 수정 시에는 필요한 범위만 패치
- GitHub Pages 배포 시 `[deploy-prebuilt]` 커밋 메시지로 prebuilt 산출물 배포 경로 사용

재발 방지:

- 먼저 `runtime/pipeline/`과 `public-site/web/`를 비교해 문제 층위를 판별한다.
- selection/data가 이미 맞고 HTML만 틀리면 전체 큐레이션 재실행을 피한다.
- generated 파일을 커밋할 때는 `git diff --cached --name-only`로 의도한 파일만 올라가는지 확인한다.

### Incident 07. NGO News 기사 제목이 `경실련,`으로 잘리는 문제

사례 URL:

- `https://www.ngonews.kr/news/articleView.html?idxno=228784`

증상:

- 사이트 카드에 제목이 전체가 아니라 `경실련,`만 표시됨

확인 결과:

- `step1_raw_articles.json`, `step2_filtered.json`에는 제목이 정상이었음
- 파손은 메타데이터 enrichment 단계에서 발생했음

원인:

- `article_metadata.py`의 `extract_meta_content()`가
  - `content="경실련, '봄 후원회' 행사 ..."` 같은 값을 읽을 때
  - 이중따옴표 안에 있는 작은따옴표를 잘못 종료 지점으로 인식함
- 그 결과 `og:title`을 `경실련,`까지만 읽음

조치:

- `<meta ...>` 태그의 속성을 quote-aware 방식으로 파싱하도록 수정
- 제목 뒤에 붙는 ` - 한국NGO신문` 같은 source suffix를 제거하는 보정 추가
- 회귀 테스트 추가
  - 작은따옴표 포함 meta title
  - `parse_generic_article_page()` 전체 title 추출
  - `resolve_article_metadata()`의 source suffix 제거

관련 파일:

- `shared/src/youth_info_platform/article_metadata.py`
- `shared/tests/test_article_metadata.py`

재발 방지:

- meta 파서는 quote type을 보존하는 방식으로 테스트되어야 한다.
- 제목이 한두 단어로 비정상 축약되면 raw -> filtered -> classified -> web 렌더링 순서로 층위를 확인한다.

### Incident 08. 오래된 선정 기사가 홈 `오늘` 리스트에 재진입한 문제

문제 URL:

- `https://www.newsis.com/view/NISX20260418_0003596702`

증상:

- 2026-04-24 홈 `오늘 놓치면 안되는 뉴스 5가지`에 2026-04-18 뉴시스 기사 `김 총리, 신임 청년보좌역들과 소통...`이 3위로 노출됨
- 뉴스 페이지/아카이브에는 남아도 되지만, 오늘성/즉시성이 필요한 홈 상위 리스트에는 맞지 않았음

확인 결과:

- 해당 기사는 `step5_summarized.json`까지 정상 선정된 기사였고, 홈 후보 병합 과정에서 `_home_primary_candidate=True`가 붙어 있었음
- `home_update_snapshot.json`의 `today_entries`에도 해당 URL이 저장되어 있었음

원인:

- 홈의 `오늘` 후보 판정이 7일짜리 `NEWS_WINDOW_HOURS`를 그대로 사용하고 있었음
- `_home_primary_candidate` 보너스가 24점이라, 오래된 거버넌스/정책 기사도 새 기사보다 높게 랭크될 수 있었음
- 그 결과 7일 안의 오래된 선정 기사와 24시간 sticky 로직이 결합해 `오늘` 리스트에 남을 수 있었음

조치:

- `HOME_TODAY_MAX_AGE_HOURS = 48`을 별도로 두고, `오늘`/`오늘 보충` 후보는 이 문턱을 넘으면 제외하도록 수정
- `_home_primary_candidate` 보너스도 48시간 이내 기사에만 적용하도록 제한
- 회귀 테스트를 추가해 4~6일 지난 primary 선정 기사가 홈 `오늘` 리스트에 들어오지 못하게 고정

재발 방지:

- `오늘 놓치면 안되는 뉴스`는 절대 7일 뉴스 창을 직접 쓰지 않는다.
- 오래된 기사가 뉴스 페이지, 선거·공약 페이지, 주간/아카이브에 남는 것과 홈 `오늘` 진입은 분리해서 판단한다.
- 비슷한 문제가 보이면 아래 순서로 본다.
  1. `runtime/pipeline/step5_summarized.json`의 `published_date`, `importance_score`, `clean_score`
  2. `_home_primary_candidate` 여부
  3. `home_update_snapshot.json`의 `today_entries`
  4. `is_home_today_candidate()`, `is_home_today_fill_candidate()`의 날짜 문턱

### Incident 09. `403 Forbidden` 오류 페이지 제목이 기사 제목으로 오염된 문제

날짜:

- 2026-04-29

증상:

- 공개 사이트 기사 카드 제목에 실제 기사 제목 대신 `403 Forbidden`이 노출됨
- 예시 화면에서 `서울경제 · 2026-04-28 21:00` 기사 제목이 `403 Forbidden`으로 표시됨

확인 결과:

- 최신 `runtime/pipeline/*.json`과 `public-site/web/news.html`의 같은 서울경제 기사는 정상 제목을 가지고 있었음
- 원문 URL은 실행 시점과 접근 방식에 따라 정상 `200 OK`를 주기도 하고, `403 Forbidden` HTML을 줄 수 있었음
- 문제가 생기는 흐름은 원문 보강 단계에서 오류 페이지의 `<title>`을 정상 기사 메타데이터처럼 읽어 기존 제목을 덮는 경우였음

원인:

- `fetch_url()`의 `curl` fallback이 HTTP 4xx/5xx를 실패로 보지 않고 본문을 반환할 수 있었음
- `parse_generic_article_page()`와 `resolve_article_metadata()`가 `403 Forbidden` 같은 오류 페이지 제목을 기사 제목 후보에서 제외하지 않았음

조치:

- `shared/src/youth_info_platform/collect.py`
  - `curl` fallback에 `--fail --show-error`를 추가해 HTTP 오류 응답을 실패로 처리
- `shared/src/youth_info_platform/article_metadata.py`
  - `401/403/404/429/5xx`, `access denied`, `forbidden` 등 오류 페이지 제목을 감지
  - 오류 페이지 제목은 새 기사 제목으로 병합하지 않도록 방어
- `shared/tests/test_collect.py`, `shared/tests/test_article_metadata.py`
  - `curl --fail` 사용 여부와 오류 제목 병합 방지 회귀 테스트 추가

검증:

- `python -m unittest shared.tests.test_collect shared.tests.test_article_metadata`
- `python public-site/scripts/article_debug.py --url "https://www.sedaily.com/article/20038288" --limit 3`

재발 방지:

- HTTP 오류 페이지의 본문이 HTML처럼 보여도 기사 본문/제목으로 신뢰하지 않는다.
- 외부 기사 제목이 갑자기 `403`, `404`, `Access Denied`, `Forbidden` 계열로 바뀌면 원문 접근성보다 먼저 메타데이터 병합 방어를 확인한다.
- 비슷한 제목 오염은 아래 순서로 본다.
  1. `runtime/pipeline/step1_raw_articles.json`의 원 수집 제목
  2. `runtime/pipeline/step2_filtered.json`의 정규화 제목
  3. `runtime/pipeline/step3_classified.json`의 `resolved_at`, `publisher_url`, `body_text`, `title`
  4. `runtime/pipeline/article_funnel.json`의 `pipeline_flags.resolved_url`, `body_enriched`
  5. `public-site/web/news.html`와 `public-site/dist/news.html`

## 7. 문제 발생 시 진단 순서

### 7-1. 기사 수집/선정 문제

아래 순서로 확인한다.

1. 원문 URL이 실제로 접근 가능한가
2. `runtime/pipeline/step1_raw_articles.json`
3. `runtime/pipeline/step2_filtered.json`
4. `runtime/pipeline/step3_classified.json`
5. `runtime/pipeline/step4_selected.json`
6. `runtime/pipeline/step5_summarized.json`
7. `public-site/web/news.html`
8. `public-site/dist/news.html`
9. 라이브 페이지

핵심:

- `step1`부터 없으면 수집 문제
- `step1`은 있는데 `step2`에서 사라지면 필터 문제
- `step3`에서 이상하면 메타데이터/분류 문제
- `step4/5`에서 사라지면 selection 문제
- `public-site/web/` 또는 `public-site/dist/`만 이상하면 렌더링 또는 packaging 문제

### 7-2. 관리자 화면 문제

확인 순서:

1. 권한(`superuser`, `platform_admin`, `staff`)
2. Django 뷰 처리
3. audit log 생성 여부
4. export JSON 갱신 여부
5. `sync_runtime_articles` 반영 여부

### 7-3. 자동 반영 문제

확인 순서:

1. `/editorial/settings/`에서 설정값
2. `runtime/pipeline/auto_update_status.json`
3. `runner_pid`, `last_checked_at`, `last_published_at`, `next_check_at`
4. 실제로 `start_auto_update.ps1`로 러너를 켰는지
5. `pipeline.lock`이 남아 있지 않은지

## 8. 배포 전 체크리스트

작업이 끝나면 최소한 아래를 확인한다.

### 8-1. 기능 수정

- 관련 테스트 실행
- 변경 범위와 무관한 generated churn이 없는지 확인
- 관리 콘솔과 공개 사이트 중 어느 쪽에 영향이 있는지 분리해서 확인

### 8-2. 공개 사이트 배포

기본 순서:

1. 필요한 경우 파이프라인 실행
   - `python public-site/scripts/rss_fetcher.py`
   - `python public-site/scripts/run_curator.py`
   - `python public-site/scripts/web_updater.py`
2. Pages 패키징
   - `python public-site/scripts/prepare_pages_site.py --site-dir public-site/dist`
3. 산출물 검증
   - `python public-site/scripts/verify_site_artifacts.py --min-articles 1 --min-news-cards 0`
4. 스테이징 파일 확인
   - `git diff --cached --name-only`
5. 배포 커밋/푸시

단일 UI/문구/카드 수정처럼 selection 전체를 흔들 필요가 없는 경우에는 필요한 파일만 수정하고 `prepare_pages_site.py`만 다시 돌리는 편이 안전하다.

## 9. 앞으로 이 문서를 갱신하는 규칙

작업 후 아래 항목을 빠뜨리지 말고 덧붙인다.

- 발생 날짜
- 증상
- 실제 원인
- 수정 파일
- 테스트/검증 방법
- 앞으로의 방지 규칙

권장 템플릿:

```md
### Incident XX. 제목

날짜:

증상:

원인:

조치:

재발 방지:
```

## 10. 다음 작업자가 반드시 기억할 것

- 이 저장소는 `공개 정적 사이트 + Django 운영 콘솔 + runtime 산출물`의 3층 구조다.
- `public-site/web/`와 `public-site/dist/`를 혼동하면 배포가 빗나간다.
- `청년` 단독 키워드는 위험하다. `청년센터/기관 운영/예산/사업` 신호를 더 중시한다.
- 정치성 기사 처리는 `완전 배제`보다 `홈 위치 조정`이 현재 원칙이다.
- 자동 반영은 상시 서버가 아니라 `노트북 러너 기반 best effort`다.
- 작은 기사 1건 수정 때문에 전체 큐레이션을 흔들지 말 것.
- `403 Forbidden` 같은 HTTP 오류 페이지 제목은 기사 제목으로 병합하면 안 된다.
- 이 문서는 메모가 아니라 운영 기준서다. 작업이 바뀌면 같이 바뀌어야 한다.
