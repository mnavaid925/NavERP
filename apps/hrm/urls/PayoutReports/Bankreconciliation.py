"""HRM 3.17 Payout & Reports — Bankreconciliation URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Bank reconciliation (match batch payments to the statement by UTR)
    path("bank-reconciliations/", views.bankreconciliation_list, name="bankreconciliation_list"),
    path("bank-reconciliations/add/", views.bankreconciliation_create, name="bankreconciliation_create"),
    path("bank-reconciliations/<int:pk>/", views.bankreconciliation_detail, name="bankreconciliation_detail"),
    path("bank-reconciliations/<int:pk>/edit/", views.bankreconciliation_edit, name="bankreconciliation_edit"),
    path("bank-reconciliations/<int:pk>/delete/", views.bankreconciliation_delete, name="bankreconciliation_delete"),
    path("bank-reconciliations/<int:pk>/reconcile/", views.bankreconciliation_reconcile, name="bankreconciliation_reconcile"),
]
