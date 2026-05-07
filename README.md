# Youth Info Platform Monorepo

이 저장소는 공개용 정적 사이트와 기관용 Django 포털을 같은 데이터 파이프라인 위에서 함께 운영하기 위한 모노레포다.

## Layout

```text
shared/            공통 Python 패키지와 파이프라인 코어
public-site/       공개용 정적 사이트, 배포 스크립트, 검증 스크립트
institution-site/  기관용 Django 앱
runtime/           공용 런타임 산출물과 DB, 로그
docs/              운영 문서
```

## Quick Start

### 1. 공개용 파이프라인 실행

```powershell
python -m pip install -e .\\shared -e .\\public-site
python public-site\\scripts\\cron_runner.py --use-sample-data
python public-site\\scripts\\verify_site_artifacts.py --min-articles 1 --min-news-cards 1
```

### 2. 기관용 포털 실행

```powershell
python -m pip install -e .\\shared -e .\\institution-site
python institution-site\\manage.py migrate
python institution-site\\manage.py sync_runtime_articles
$env:DJANGO_DEBUG='1'
python institution-site\\manage.py runserver
```

## Runtime Contract

- 파이프라인 산출물: `runtime/pipeline/`
- 공유 SQLite: `runtime/db/articles.db`
- 공개용 HTML: `public-site/web/`
- 기관용 개인화 데이터: Django DB

## Operations Runbooks

- 전체 파이프라인 정의와 실행 계약: `docs/pipeline-operations.md`
- 정기 피드백 점검과 자가복구 루틴: `docs/pipeline-feedback-routine.md`
- 공개 사이트 스크립트 진입점: `public-site/scripts/README.md`

## Notes

- `shared` 수정은 공개용과 기관용에 모두 영향을 준다.
- `public-site` 수정은 공개용에만 영향을 준다.
- `institution-site` 수정은 기관용에만 영향을 준다.
- 이전 문서 중 일부는 레거시 경로를 설명할 수 있으니, 새 구조는 이 README와 각 사이트 폴더 README를 기준으로 본다.
