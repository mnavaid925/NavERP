"""HRM 3.7 Interview Process — Interviewfeedback URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Interview feedback / scorecards (3.7) — CRUD + hub + submit + inline criteria
    path("interview-feedback/", views.interviewfeedback_list, name="interviewfeedback_list"),
    path("interview-feedback/add/", views.interviewfeedback_create, name="interviewfeedback_create"),
    path("interview-feedback/<int:pk>/", views.interviewfeedback_detail, name="interviewfeedback_detail"),
    path("interview-feedback/<int:pk>/edit/", views.interviewfeedback_edit, name="interviewfeedback_edit"),
    path("interview-feedback/<int:pk>/delete/", views.interviewfeedback_delete, name="interviewfeedback_delete"),
    path("interview-feedback/<int:pk>/submit/", views.interviewfeedback_submit, name="interviewfeedback_submit"),
]
