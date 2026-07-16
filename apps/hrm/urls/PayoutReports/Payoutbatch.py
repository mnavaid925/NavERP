"""HRM 3.17 Payout & Reports — Payoutbatch URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ===================== 3.17 Payout & Reports =====================
    # Payout batches (+ generate/approve/disburse from a locked cycle) + payment register
    path("payout-batches/", views.payoutbatch_list, name="payoutbatch_list"),
    path("payout-batches/add/", views.payoutbatch_create, name="payoutbatch_create"),
    path("payout-batches/<int:pk>/", views.payoutbatch_detail, name="payoutbatch_detail"),
    path("payout-batches/<int:pk>/edit/", views.payoutbatch_edit, name="payoutbatch_edit"),
    path("payout-batches/<int:pk>/delete/", views.payoutbatch_delete, name="payoutbatch_delete"),
    path("payout-batches/<int:pk>/generate/", views.payoutbatch_generate, name="payoutbatch_generate"),
    path("payout-batches/<int:pk>/approve/", views.payoutbatch_approve, name="payoutbatch_approve"),
    path("payout-batches/<int:pk>/disburse/", views.payoutbatch_disburse, name="payoutbatch_disburse"),
]
