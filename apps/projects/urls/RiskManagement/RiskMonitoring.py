"""Projects 7.5 — the Risk Monitoring & Reporting route (computed page, no model; GET-only)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("risk-monitoring/", views.risk_monitoring, name="risk_monitoring"),
]
