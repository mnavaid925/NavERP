"""HRM 3.5 Job Requisition — Jobrequisition URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Job Requisitions (3.5) — CRUD + approval state machine + utilities
    path("requisitions/", views.jobrequisition_list, name="jobrequisition_list"),
    path("requisitions/add/", views.jobrequisition_create, name="jobrequisition_create"),
    path("requisitions/<int:pk>/", views.jobrequisition_detail, name="jobrequisition_detail"),
    path("requisitions/<int:pk>/edit/", views.jobrequisition_edit, name="jobrequisition_edit"),
    path("requisitions/<int:pk>/delete/", views.jobrequisition_delete, name="jobrequisition_delete"),
    path("requisitions/<int:pk>/submit/", views.jobrequisition_submit, name="jobrequisition_submit"),
    path("requisitions/<int:pk>/approve-step/", views.jobrequisition_approve_step, name="jobrequisition_approve_step"),
    path("requisitions/<int:pk>/reject/", views.jobrequisition_reject, name="jobrequisition_reject"),
    path("requisitions/<int:pk>/return/", views.jobrequisition_return, name="jobrequisition_return"),
    path("requisitions/<int:pk>/post/", views.jobrequisition_post, name="jobrequisition_post"),
    path("requisitions/<int:pk>/hold/", views.jobrequisition_hold, name="jobrequisition_hold"),
    path("requisitions/<int:pk>/fill/", views.jobrequisition_mark_filled, name="jobrequisition_mark_filled"),
    path("requisitions/<int:pk>/cancel/", views.jobrequisition_cancel, name="jobrequisition_cancel"),
    path("requisitions/<int:pk>/apply-template/", views.jobrequisition_apply_template, name="jobrequisition_apply_template"),
    path("requisitions/<int:pk>/clone/", views.jobrequisition_clone, name="jobrequisition_clone"),
]
