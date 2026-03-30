# GitHub Pages 배포 가이드

이 저장소는 GitHub Pages + GitHub Actions 기준으로 바로 배포할 수 있게 구성되어 있다.

## 포함된 구성

- `.github/workflows/deploy-pages.yml`
  - `push`
  - `workflow_dispatch`
  - 매일 3회 스케줄 실행
- `scripts/verify_site_artifacts.py`
  - 빈 결과물이나 실패한 파이프라인이 배포되지 않도록 검증
- `scripts/prepare_pages_site.py`
  - `web/` 산출물을 Pages 아티팩트로 패키징
  - `site-data/pipeline_status.json`
  - `site-data/selected.json`
  - `site-data/summarized.json`

## 스케줄

GitHub Actions 스케줄은 UTC 기준으로 설정되어 있다.

- `00:07 UTC` -> `09:07 Asia/Seoul`
- `06:07 UTC` -> `15:07 Asia/Seoul`
- `12:07 UTC` -> `21:07 Asia/Seoul`

정각 혼잡을 피하려고 `7분` 오프셋을 두었다.

## GitHub에서 해야 할 설정

1. 이 프로젝트를 GitHub 저장소로 올린다.
2. 기본 브랜치를 운영 브랜치로 정한다.
3. GitHub 저장소의 `Settings -> Pages` 로 이동한다.
4. `Source` 를 `GitHub Actions` 로 선택한다.
5. 기본 브랜치에 push 하거나 `Actions -> Build And Deploy Pages -> Run workflow` 로 수동 실행한다.
6. 첫 배포가 끝나면 Pages URL이 발급된다.

## 커스텀 도메인

커스텀 도메인을 붙이려면 저장소 변수 `PAGES_CNAME` 를 추가하면 된다.

- `Settings -> Secrets and variables -> Actions -> Variables`
- 이름: `PAGES_CNAME`
- 값 예시: `youth.example.com`

이 변수가 있으면 배포 시 `CNAME` 파일을 자동으로 생성한다.

## 로컬 확인 명령

파이프라인 생성:

```powershell
python .claude/skills/scheduler/scripts/cron_runner.py
```

배포 전 검증:

```powershell
python scripts/verify_site_artifacts.py --min-articles 1
```

Pages 아티팩트 준비:

```powershell
python scripts/prepare_pages_site.py --site-dir dist
```

## 배포 구조 메모

- `db/articles.db` 는 생성 과정에서만 쓰인다.
- 실제 GitHub Pages 공개 사이트는 `dist/` 안의 정적 파일만 배포된다.
- GitHub Actions 러너는 매 실행마다 새 환경이므로 서버에 DB가 남아 있지 않다.
- 따라서 운영 결과물은 `web/` 과 `site-data/` 를 기준으로 보는 것이 맞다.

## 주의 사항

- 기본 브랜치 push, 스케줄 실행, 수동 실행이 모두 동일한 배포 워크플로우를 사용한다.
- 워크플로우가 실패하면 기존 Pages 배포는 유지된다.
- `config/*.local.json`, `output/`, `db/*.db`, 생성된 `web/*.html` 은 `.gitignore` 로 제외되어 있다.
