"""HRM 3.24 Training Administration — Budget URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Training budget (computed aggregate view)
    path("training-budget/", views.training_budget, name="training_budget"),
]
