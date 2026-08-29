"""Procurement 6.12 Goods Receipt & Inspection — ReceiptDiscrepancy URL patterns.

Segment: ``receipt-discrepancies/`` — new, and a distinct whole component against every existing
procurement segment (activity, alerts, amendments, analytics, approvals, asn, awards, backorders,
bids, catalog-*, clauses, contract-*, contracts, delegations, delivery-*, eauc, escalations,
events, inbound-tracking, milestones, po-changes, po-generation, po-tracking, portal-access,
punchout, quick-requisition, renewals, reports, requisitions, rfx, submissions, suspensions,
templates, vendor-portal). The app has no greedy ``<str:…>`` route, so nothing can shadow it.

Django resolves FIRST-MATCH-WINS, so the literal ``receipt-discrepancies/add/`` precedes every
``receipt-discrepancies/<int:pk>/`` route. Ordering here is behaviour, not tidiness.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("receipt-discrepancies/", views.discrepancy_list, name="discrepancy_list"),
    path("receipt-discrepancies/add/", views.discrepancy_create, name="discrepancy_create"),
    path("receipt-discrepancies/<int:pk>/", views.discrepancy_detail, name="discrepancy_detail"),
    path("receipt-discrepancies/<int:pk>/edit/", views.discrepancy_edit,
         name="discrepancy_edit"),
    # The four below are POST-only (@require_POST); ``delete`` is additionally tenant-admin gated.
    path("receipt-discrepancies/<int:pk>/delete/", views.discrepancy_delete,
         name="discrepancy_delete"),
    path("receipt-discrepancies/<int:pk>/notify-vendor/", views.discrepancy_notify_vendor,
         name="discrepancy_notify_vendor"),
    path("receipt-discrepancies/<int:pk>/resolve/", views.discrepancy_resolve,
         name="discrepancy_resolve"),
    path("receipt-discrepancies/<int:pk>/cancel/", views.discrepancy_cancel,
         name="discrepancy_cancel"),
]
