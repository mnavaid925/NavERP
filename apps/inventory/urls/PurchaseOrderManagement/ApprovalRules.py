"""Inventory 5.3 Purchase Order (PO) Management — approval-rule routes (prefix
``po/approval-rules/``)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("po/approval-rules/", views.approvalrule_list, name="approvalrule_list"),
    path("po/approval-rules/add/", views.approvalrule_create, name="approvalrule_create"),
    path("po/approval-rules/<int:pk>/", views.approvalrule_detail, name="approvalrule_detail"),
    path("po/approval-rules/<int:pk>/edit/", views.approvalrule_edit, name="approvalrule_edit"),
    path("po/approval-rules/<int:pk>/delete/", views.approvalrule_delete, name="approvalrule_delete"),
]
