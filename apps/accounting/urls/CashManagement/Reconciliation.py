"""Accounting 2.5 Cash Management — Reconciliation URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.5 Cash — Reconciliation
    path("reconciliation/", views.reconciliation_list, name="reconciliation_list"),
    path("reconciliation/add/", views.reconciliation_create, name="reconciliation_create"),
    path("reconciliation/<int:pk>/", views.reconciliation_detail, name="reconciliation_detail"),
    path("reconciliation/<int:pk>/edit/", views.reconciliation_edit, name="reconciliation_edit"),
    path("reconciliation/<int:pk>/delete/", views.reconciliation_delete, name="reconciliation_delete"),
    path("reconciliation/<int:pk>/confirm/", views.reconciliation_confirm, name="reconciliation_confirm"),
]
