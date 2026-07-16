"""HRM 3.6 Candidate Management — Candidate URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Candidates (3.6) — CRUD + candidate hub + inline skill/tag actions
    path("candidates/", views.candidate_list, name="candidate_list"),
    path("candidates/add/", views.candidate_create, name="candidate_create"),
    path("candidates/<int:pk>/", views.candidate_detail, name="candidate_detail"),
    path("candidates/<int:pk>/edit/", views.candidate_edit, name="candidate_edit"),
    path("candidates/<int:pk>/delete/", views.candidate_delete, name="candidate_delete"),
    path("candidates/<int:pk>/hire/", views.candidate_mark_hired, name="candidate_mark_hired"),
    path("candidates/<int:pk>/blacklist/", views.candidate_blacklist, name="candidate_blacklist"),
    path("candidates/<int:pk>/restore/", views.candidate_restore, name="candidate_restore"),
    path("candidates/<int:pk>/skills/add/", views.candidate_skill_add, name="candidate_skill_add"),
    path("candidates/<int:pk>/skills/<int:skill_pk>/delete/", views.candidate_skill_delete, name="candidate_skill_delete"),
    path("candidates/<int:pk>/tags/add/", views.candidate_tag_add, name="candidate_tag_add"),
    path("candidates/<int:pk>/tags/<int:tag_pk>/remove/", views.candidate_tag_remove, name="candidate_tag_remove"),
]
