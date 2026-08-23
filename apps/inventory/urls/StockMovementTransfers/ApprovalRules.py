"""Inventory 5.7 Stock Movement & Transfers — TransferApprovalRule routes (prefix
``transfers/approval-rules/``)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("transfers/approval-rules/", views.transferapprovalrule_list,
         name="transferapprovalrule_list"),
    path("transfers/approval-rules/add/", views.transferapprovalrule_create,
         name="transferapprovalrule_create"),
    path("transfers/approval-rules/<int:pk>/", views.transferapprovalrule_detail,
         name="transferapprovalrule_detail"),
    path("transfers/approval-rules/<int:pk>/edit/", views.transferapprovalrule_edit,
         name="transferapprovalrule_edit"),
    path("transfers/approval-rules/<int:pk>/delete/", views.transferapprovalrule_delete,
         name="transferapprovalrule_delete"),
]
