"""HRM 3.6 Candidate Management — Application URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Job Applications (3.6) — CRUD + pipeline stage actions + send-email
    path("applications/", views.application_list, name="application_list"),
    path("applications/add/", views.application_create, name="application_create"),
    path("applications/<int:pk>/", views.application_detail, name="application_detail"),
    path("applications/<int:pk>/edit/", views.application_edit, name="application_edit"),
    path("applications/<int:pk>/delete/", views.application_delete, name="application_delete"),
    path("applications/<int:pk>/advance/", views.application_advance_stage, name="application_advance_stage"),
    path("applications/<int:pk>/reject/", views.application_reject, name="application_reject"),
    path("applications/<int:pk>/withdraw/", views.application_withdraw, name="application_withdraw"),
    path("applications/<int:pk>/hold/", views.application_hold, name="application_hold"),
    path("applications/<int:pk>/send-email/", views.application_send_email, name="application_send_email"),
]
