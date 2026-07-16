"""HRM 3.36 Helpdesk — Helpdeskslapolicy URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.36 Helpdesk
    path("helpdesk/sla-policies/", views.helpdesksla_list, name="helpdesksla_list"),
    path("helpdesk/sla-policies/add/", views.helpdesksla_create, name="helpdesksla_create"),
    path("helpdesk/sla-policies/<int:pk>/", views.helpdesksla_detail, name="helpdesksla_detail"),
    path("helpdesk/sla-policies/<int:pk>/edit/", views.helpdesksla_edit, name="helpdesksla_edit"),
    path("helpdesk/sla-policies/<int:pk>/delete/", views.helpdesksla_delete, name="helpdesksla_delete"),
]
