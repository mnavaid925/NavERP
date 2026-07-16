"""HRM 3.10 Leave Management — Policy URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Leave Policy engine (3.10) — standalone page + admin run actions
    path("leave-policy/", views.leave_policy, name="leave_policy"),
    path("leave-policy/accrual-run/", views.leave_accrual_run, name="leave_accrual_run"),
    path("leave-policy/carry-forward-run/", views.leave_carryforward_run, name="leave_carryforward_run"),
]
