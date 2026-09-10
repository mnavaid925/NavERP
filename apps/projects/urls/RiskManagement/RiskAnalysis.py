"""Projects 7.5 — the Qualitative & Quantitative Analysis route (computed page, no model)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("risk-analysis/", views.risk_analysis, name="risk_analysis"),
]
