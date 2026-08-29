"""Procurement 6.12 Goods Receipt & Inspection — ReturnToVendor URL patterns.

Segment: ``returns-to-vendor/`` — new, and a distinct whole component against the inventory in
``apps/procurement/urls/__init__.py`` (activity, alerts, amendments, analytics, approvals, asn,
auctions, awards, backorders, bids, catalog-items, catalog-tiers, catalog-uploads, clauses,
contract-amendments, contract-sign, contracts, delegations, delivery-confirmation,
delivery-schedules, escalations, events, inbound-tracking, milestones, po-changes, po-generation,
po-tracking, portal-access, punchout, quick-requisition, renewals, reports, requisitions, rfx,
submissions, suspensions, templates, vendor-portal, widgets). The app has no greedy ``<str:…>``
converter, so nothing can shadow it.

Django resolves FIRST-MATCH-WINS, so the literal ``returns-to-vendor/add/`` precedes every
``returns-to-vendor/<int:pk>/`` route. Ordering here is behaviour, not tidiness.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("returns-to-vendor/", views.rtv_list, name="rtv_list"),
    path("returns-to-vendor/add/", views.rtv_create, name="rtv_create"),
    path("returns-to-vendor/<int:pk>/", views.rtv_detail, name="rtv_detail"),
    path("returns-to-vendor/<int:pk>/edit/", views.rtv_edit, name="rtv_edit"),
    # The five below are POST-only (@require_POST); ``delete`` and ``authorize`` are additionally
    # tenant-admin gated.
    path("returns-to-vendor/<int:pk>/delete/", views.rtv_delete, name="rtv_delete"),
    path("returns-to-vendor/<int:pk>/authorize/", views.rtv_authorize, name="rtv_authorize"),
    path("returns-to-vendor/<int:pk>/ship/", views.rtv_ship, name="rtv_ship"),
    path("returns-to-vendor/<int:pk>/close/", views.rtv_close, name="rtv_close"),
    path("returns-to-vendor/<int:pk>/cancel/", views.rtv_cancel, name="rtv_cancel"),
]
