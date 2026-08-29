"""Procurement 6.11 Order Fulfillment & Tracking — AdvancedShipmentNotice URL patterns.

Segment: ``asn/`` — new, and distinct from every existing procurement segment (activity, alerts,
amendments, analytics, approvals, awards, bids, catalog-*, clauses, contract-*, contracts,
delegations, eauc, escalations, events, milestones, po-changes, po-generation, po-tracking,
portal-access, punchout, quick-requisition, renewals, reports, requisitions, rfx, submissions,
suspensions, templates, vendor-portal). The app has no greedy ``<str:…>`` route, so nothing can
shadow it.

Django resolves FIRST-MATCH-WINS, so the literal ``asn/add/`` precedes every ``asn/<int:pk>/``
route. Ordering here is behaviour, not tidiness.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("asn/", views.asn_list, name="asn_list"),
    path("asn/add/", views.asn_create, name="asn_create"),
    path("asn/<int:pk>/", views.asn_detail, name="asn_detail"),
    path("asn/<int:pk>/edit/", views.asn_edit, name="asn_edit"),
    # The five below are POST-only (@require_POST); ``delete`` is additionally tenant-admin gated.
    path("asn/<int:pk>/delete/", views.asn_delete, name="asn_delete"),
    path("asn/<int:pk>/submit/", views.asn_submit, name="asn_submit"),
    path("asn/<int:pk>/in-transit/", views.asn_mark_in_transit, name="asn_mark_in_transit"),
    path("asn/<int:pk>/confirm-delivery/", views.asn_confirm_delivery,
         name="asn_confirm_delivery"),
    path("asn/<int:pk>/cancel/", views.asn_cancel, name="asn_cancel"),
]
