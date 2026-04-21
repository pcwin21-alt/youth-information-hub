# Repo Layout

## Top-level folders

- `shared/`: 공통 Python 패키지. `youth_info_platform` 모듈과 runtime path helper를 포함한다.
- `public-site/`: 공개용 정적 사이트. 수집, 큐레이션, 발행, 배포 스크립트를 가진다.
- `institution-site/`: 기관 사용자용 Django 앱. 로그인, 개인화 데이터, runtime 동기화를 담당한다.
- `runtime/`: 공용 산출물 저장소.

## Runtime structure

```text
runtime/
  pipeline/   step1~step5, article_funnel, pipeline_status, 운영 상태 JSON
  db/         공유 SQLite
  logs/       scheduler, preview server, tunnel 로그
```

## Ownership

- `shared`는 공통 계약만 둔다.
- `public-site`는 정적 공개 경험과 배포를 소유한다.
- `institution-site`는 사용자 계정, 추적 지역, 저장 기사, 보고서 초안, export 이력을 소유한다.
