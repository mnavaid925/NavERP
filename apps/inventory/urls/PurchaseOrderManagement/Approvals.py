"""Inventory 5.3 Purchase Order (PO) Management — approval-queue routes (prefix
``po/approvals/``). The tier verbs are literal routes with TWO int converters; no greedy
``<str:…>`` exists anywhere in this app, so there is no shadowing surface."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("po/approvals/", views.approval_queue, name="approval_queue"),
    path("po/approvals/<int:po_pk>/tier/<int:tier>/approve/",
         views.approval_tier_approve, name="approval_tier_approve"),
    path("po/approvals/<int:po_pk>/tier/<int:tier>/reject/",
         views.approval_tier_reject, name="approval_tier_reject"),
]
