"""HRM 3.10 Leave Management — Encashment URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Leave Encashment (3.10) — CRUD + workflow actions
    path("leave-encashments/", views.leaveencashment_list, name="leaveencashment_list"),
    path("leave-encashments/add/", views.leaveencashment_create, name="leaveencashment_create"),
    path("leave-encashments/<int:pk>/", views.leaveencashment_detail, name="leaveencashment_detail"),
    path("leave-encashments/<int:pk>/edit/", views.leaveencashment_edit, name="leaveencashment_edit"),
    path("leave-encashments/<int:pk>/delete/", views.leaveencashment_delete, name="leaveencashment_delete"),
    path("leave-encashments/<int:pk>/submit/", views.leaveencashment_submit, name="leaveencashment_submit"),
    path("leave-encashments/<int:pk>/approve/", views.leaveencashment_approve, name="leaveencashment_approve"),
    path("leave-encashments/<int:pk>/reject/", views.leaveencashment_reject, name="leaveencashment_reject"),
    path("leave-encashments/<int:pk>/mark-paid/", views.leaveencashment_mark_paid, name="leaveencashment_mark_paid"),
    path("leave-encashments/<int:pk>/cancel/", views.leaveencashment_cancel, name="leaveencashment_cancel"),
]
