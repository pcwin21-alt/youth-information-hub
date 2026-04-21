from __future__ import annotations

from django.urls import path

from .views import analytics_collect, dashboard, editorial_analytics, editorial_dashboard, editorial_history, editorial_settings


urlpatterns = [
    path("analytics/collect/", analytics_collect, name="analytics_collect"),
    path("", dashboard, name="dashboard"),
    path("editorial/", editorial_dashboard, name="editorial_dashboard"),
    path("editorial/settings/", editorial_settings, name="editorial_settings"),
    path("editorial/history/", editorial_history, name="editorial_history"),
    path("editorial/analytics/", editorial_analytics, name="editorial_analytics"),
]
