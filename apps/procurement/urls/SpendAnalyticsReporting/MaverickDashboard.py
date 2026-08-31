"""Procurement 6.14 Spend Analytics & Reporting — maverick board + scan routes.

Two literal routes under the ``spend/`` first segment this sub-module's computed pages share:
``spend/maverick/`` (the board) and ``spend/maverick/scan/`` (the detector run). They differ by a
whole path component from each other and from ``spend/``, ``spend/categories/``,
``spend/classification/``, ``spend/export/`` and ``spend/export/download/``, so Django's
first-match-wins resolution has nothing to disambiguate. The register itself lives on its own
first segment, ``maverick-findings/`` (``MaverickFindings.py``).

``spend/maverick/scan/`` is POST-only and ``@tenant_admin_required`` through its view decorators
(L27) — a scan re-reads a whole window of spend, so it must not be reachable by following a link.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("spend/maverick/", views.maverick_dashboard, name="maverick_dashboard"),
    # POST-only + tenant admin. Declared after its board purely for readability; they are distinct
    # whole components, so neither could shadow the other in any order.
    path("spend/maverick/scan/", views.maverick_scan, name="maverick_scan"),
]
