"""HRM 3.26 Request Management — Suggestions URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("suggestions/<int:pk>/delete/", views.suggestion_delete, name="suggestion_delete"),
    path("suggestions/<int:pk>/submit/", views.suggestion_submit, name="suggestion_submit"),
    path("suggestions/<int:pk>/cancel/", views.suggestion_cancel, name="suggestion_cancel"),
    path("suggestions/<int:pk>/approve/", views.suggestion_approve, name="suggestion_approve"),
    path("suggestions/<int:pk>/reject/", views.suggestion_reject, name="suggestion_reject"),
    path("suggestions/<int:pk>/implement/", views.suggestion_implement, name="suggestion_implement"),
]
