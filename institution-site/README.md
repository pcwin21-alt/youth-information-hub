# Institution Site

`institution-site`는 Django 기반 기관 사용자 포털이다.

## Quick Start

```powershell
python -m pip install -e ..\\shared -e .
python manage.py migrate
python manage.py sync_runtime_articles
python manage.py createsuperuser
python manage.py runserver
```

## Runtime Contract

- 공용 기사/정책 데이터: `../runtime/pipeline/step5_summarized.json`
- 공용 상태 파일: `../runtime/pipeline/pipeline_status.json`
- 개인화 데이터: Django DB
