"""Projects 7.17 — ProjectApprovalGate URL patterns."""
from django.urls import path

from apps.projects.views.WorkflowAutomation import ApprovalGates as views

urlpatterns = [
    path("gates/", views.par_list, name="par_list"),
    path("gates/create/", views.par_create, name="par_create"),
    path("gates/<int:pk>/", views.par_detail, name="par_detail"),
    path("gates/<int:pk>/edit/", views.par_edit, name="par_edit"),
    path("gates/<int:pk>/delete/", views.par_delete, name="par_delete"),
    path("gates/<int:pk>/approve/", views.par_approve, name="par_approve"),
    path("gates/<int:pk>/reject/", views.par_reject, name="par_reject"),
    path("gates/<int:pk>/escalate/", views.par_escalate, name="par_escalate"),
    path("gates/<int:pk>/delegate/", views.par_delegate, name="par_delegate"),
    path("gates/<int:pk>/cancel/", views.par_cancel, name="par_cancel"),
]
