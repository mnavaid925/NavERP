"""HRM 3.6 Candidate Management — Emailtemplate URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Candidate Email Templates (3.6) — CRUD
    path("candidate-email-templates/", views.emailtemplate_list, name="emailtemplate_list"),
    path("candidate-email-templates/add/", views.emailtemplate_create, name="emailtemplate_create"),
    path("candidate-email-templates/<int:pk>/", views.emailtemplate_detail, name="emailtemplate_detail"),
    path("candidate-email-templates/<int:pk>/edit/", views.emailtemplate_edit, name="emailtemplate_edit"),
    path("candidate-email-templates/<int:pk>/delete/", views.emailtemplate_delete, name="emailtemplate_delete"),
]
