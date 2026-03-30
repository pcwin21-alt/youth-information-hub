# Youth Info Platform

청년 정보 통합 플랫폼의 첫 구현 골격입니다.

현재 포함 범위:
- 뉴스 수집(RSS + 샘플 폴백)
- 중복 제거 및 기본 필터링
- 규칙 기반 분류/선별/요약
- SQLite 저장
- 단순 HTML 다이제스트 생성

빠른 실행:

```powershell
python .claude/skills/scheduler/scripts/cron_runner.py --use-sample-data
```

진행 현황 확인:

```powershell
python scripts/status_report.py
```

절전/최대절전 자동 깨우기 설정:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\configure_sleep_wake.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_windows_scheduler.ps1 -WakeToRun -Force
```

로컬 미리보기 서버 백그라운드 실행:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_preview_servers.ps1
```

임시 외부 공유 링크 시작:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_public_tunnel.ps1 -InstallIfMissing
```

미리보기 서버/외부 터널 상태 확인:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\preview_servers_status.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\public_tunnel_status.ps1
```

소스 상태 점검:

```powershell
python scripts/source_healthcheck.py
```

배포 준비도 점검:

```powershell
python scripts/deployment_readiness.py
```

생성 결과:
- `output/step1_raw_articles.json`
- `output/step2_filtered.json`
- `output/step3_classified.json`
- `output/step4_selected.json`
- `output/step5_summarized.json`
- `output/pipeline_status.json`
- `db/articles.db`
- `web/index.html`

다음 구현 단계:
- 실제 RSS/정책브리핑 소스 확정
- LLM 기반 content-curator 연동
- Next.js 프론트엔드 전환

운영/배포 문서:
- `docs/always-on-deployment.md`
- `docs/deployment-rollout-plan.md`
- `docs/lightsail-staging-deployment.md`
- `docs/github-pages-deployment.md`
