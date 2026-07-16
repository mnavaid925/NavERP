"""HRM 3.6 Candidate Management — CareersApply URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("careers/<str:token>/apply/", views.careers_apply, name="careers_apply"),
]
