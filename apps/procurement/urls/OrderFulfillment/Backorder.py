"""Procurement 6.11 Order Fulfillment & Tracking — Backorder URL patterns.

Segment ``backorders/`` is NEW and distinct from every existing procurement segment (activity,
alerts, amendments, analytics, approvals, awards, bids, catalog-*, clauses, contract-*, contracts,
delegations, eauc, escalations, events, milestones, po-changes, po-generation, po-tracking,
portal-access, punchout, quick-requisition, renewals, reports, requisitions, rfx, submissions,
suspensions, templates, vendor-portal), and the app still has no greedy ``<str:...>`` route that
could swallow it.

Django is FIRST-MATCH-WINS, so the literal ``backorders/add/`` precedes ``backorders/<int:pk>/``.
It would not actually be shadowed (``add`` fails ``int`` conversion), but the ordering is the rule
that stays correct when a non-numeric converter is added later — and a reviewer checks it.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("backorders/", views.backorder_list, name="backorder_list"),
    path("backorders/add/", views.backorder_create, name="backorder_create"),
    path("backorders/<int:pk>/", views.backorder_detail, name="backorder_detail"),
    path("backorders/<int:pk>/edit/", views.backorder_edit, name="backorder_edit"),
    # POST-only from here down — every one of these mutates or deletes.
    path("backorders/<int:pk>/delete/", views.backorder_delete, name="backorder_delete"),
    path("backorders/<int:pk>/reschedule/", views.backorder_reschedule,
         name="backorder_reschedule"),
    path("backorders/<int:pk>/fulfil/", views.backorder_fulfil, name="backorder_fulfil"),
    path("backorders/<int:pk>/cancel/", views.backorder_cancel, name="backorder_cancel"),
    path("backorders/<int:pk>/raise-alert/", views.backorder_raise_alert,
         name="backorder_raise_alert"),
]
