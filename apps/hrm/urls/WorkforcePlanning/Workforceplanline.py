"""HRM 3.40 Workforce Planning — Workforceplanline URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("workforce/plans/<int:plan_pk>/lines/add/", views.workforceplanline_add, name="workforceplanline_add"),
    path("workforce/plan-lines/<int:pk>/edit/", views.workforceplanline_edit, name="workforceplanline_edit"),
    path("workforce/plan-lines/<int:pk>/delete/", views.workforceplanline_delete, name="workforceplanline_delete"),
]
