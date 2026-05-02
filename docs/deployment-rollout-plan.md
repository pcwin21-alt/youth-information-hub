# Production Rollout Plan

이 문서는 실제 운영 서버 공개 전환을 위한 순서와 중단 조건을 정리한다.

## Strategy

- v1 배포 단위는 `단일 Linux VM + systemd timer + nginx`다.
- staging에서 충분히 검증한 뒤 도메인 또는 reverse proxy를 production으로 전환한다.
- rollback은 정적 HTML 이전 버전, SQLite 백업, 직전 정상 커밋을 기준으로 한다.

## Pre-Deployment

- VM, OS, DNS, 운영 URL, 연락 채널을 확정한다.
- 로컬에서 입력값을 점검한다.

```powershell
python public-site\scripts\deployment_readiness.py
```

- 서버에 저장소를 배치하고 의존성을 설치한다.
- `public-site/deploy/systemd/`, `public-site/deploy/nginx/`, `public-site/deploy/env/` 템플릿의 경로와 계정을 실제 환경에 맞춘다.
- 수동 배치를 1회 실행해 `public-site/web/index.html`과 `runtime/pipeline/pipeline_status.json`을 확인한다.

## Staging Validation

- 실제 스케줄 또는 임시 단축 스케줄로 최소 3회 연속 성공을 확인한다.
- 확인 대상:
  - `systemctl status youth-together-pipeline.timer`
  - `systemctl status youth-together-pipeline.service`
  - `runtime/pipeline/pipeline_status.json`
  - `runtime/logs/`
  - 공개 홈, 뉴스, 정책, 허브 페이지
- 중단 조건:
  - 파이프라인이 서버 환경에서 반복 실패
  - `public-site/web/*.html`이 생성되지 않음
  - nginx 정적 서빙 실패
  - 최신 기사 날짜나 주요 페이지 렌더링이 명백히 이상함

## D-Day

1. 마지막 수동 배치를 실행한다.
2. `pipeline_status.json` 성공 상태를 확인한다.
3. 공개 페이지를 모바일/데스크톱에서 확인한다.
4. DNS 또는 reverse proxy를 production으로 전환한다.
5. HTTPS, 404, CSS/assets, 외부 링크를 확인한다.
6. 공개 직후 30분, 2시간 단위로 로그와 배치 상태를 확인한다.

## Rollback

1차 rollback:

- nginx가 바라보는 `public-site/web/`를 배포 전 스냅샷으로 교체한다.
- 최신 배치 실행을 중지한다.
- 운영 채널로 임시 안내한다.

2차 rollback:

- `runtime/db/articles.db`를 백업에서 복원한다.
- 직전 정상 커밋으로 되돌린다.
- systemd timer를 일시 중지한다.

Rollback 준비물:

- 배포 전 `runtime/db/articles.db` 백업
- 배포 전 `public-site/web/` 스냅샷
- 직전 정상 `runtime/pipeline/pipeline_status.json`
- 직전 정상 커밋 SHA

## Daily Checks After Launch

- 마지막 성공 시각
- 다음 배치 예약 시각
- 최종 기사 수
- 허브/정책/뉴스 분류 상태
- 실패 로그 존재 여부
- 특정 소스가 계속 비어 있는지 여부

## Path Rules

- 구버전 루트 경로 `scripts/`, `web/`, `output/`, `deploy/`를 새 문서에 쓰지 않는다.
- 현재 표준 경로는 `public-site/scripts/`, `public-site/web/`, `runtime/pipeline/`, `public-site/deploy/`다.
- GitHub Pages 배포와 VM 배포의 artifact 경로는 다르다. Pages는 `public-site/dist/`, VM은 보통 `public-site/web/`를 사용한다.
