"""Procurement 6.14 Spend Analytics & Reporting — MaverickSpendFinding URL patterns.

One first segment, ``maverick-findings/`` — collision-checked against the concatenated
``urls/__init__.py`` inventory (a new whole component; the app registers no greedy ``<str:…>``
converter, so nothing can shadow it). Within the segment the literal ``add/`` is declared BEFORE
the ``<int:pk>/`` routes it would otherwise fall into, because Django is first-match-wins.

``delete/`` and ``disposition/`` are POST-only through their view decorators — there is no confirm
template for either. ``disposition/`` is additionally ``@tenant_admin_required``.

**Not declared here.** ``procurement:maverick_dashboard`` (``spend/maverick/``) and
``procurement:maverick_scan`` (``spend/maverick/scan/``) are contracted to the sibling module
``urls/SpendAnalyticsReporting/MaverickDashboard.py``, which owns the ``spend/`` first segment
alongside the other computed pages of this sub-module. Nothing in this module reverses either
name, so this file resolves on its own.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # -- the register ---------------------------------------------------------------------------
    path("maverick-findings/", views.maverickfinding_list, name="maverickfinding_list"),
    # Literal BEFORE <int:pk>: otherwise "add" would be matched as a pk and 404 on conversion.
    path("maverick-findings/add/", views.maverickfinding_create, name="maverickfinding_create"),
    # -- one finding -----------------------------------------------------------------------------
    path("maverick-findings/<int:pk>/", views.maverickfinding_detail,
         name="maverickfinding_detail"),
    path("maverick-findings/<int:pk>/edit/", views.maverickfinding_edit,
         name="maverickfinding_edit"),
    path("maverick-findings/<int:pk>/delete/", views.maverickfinding_delete,
         name="maverickfinding_delete"),
    # -- disposition (POST only, tenant admin) ------------------------------------------------------
    path("maverick-findings/<int:pk>/disposition/", views.maverickfinding_disposition,
         name="maverickfinding_disposition"),
]
