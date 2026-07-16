"""HRM 3.40 Workforce Planning — GapAnalysis URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ---- 3.40 Workforce Planning -----------------------------------------------------------------
    # Literal routes before the <int:pk> ones (first-match-wins).
    path("workforce/gap-analysis/", views.workforce_gap_analysis, name="workforce_gap_analysis"),
]
