"""HRM 3.6 Candidate Management — Tag URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Candidate Tags (3.6) — catalog CRUD (no detail page)
    path("candidate-tags/", views.candidatetag_list, name="candidatetag_list"),
    path("candidate-tags/add/", views.candidatetag_create, name="candidatetag_create"),
    path("candidate-tags/<int:pk>/edit/", views.candidatetag_edit, name="candidatetag_edit"),
    path("candidate-tags/<int:pk>/delete/", views.candidatetag_delete, name="candidatetag_delete"),
]
