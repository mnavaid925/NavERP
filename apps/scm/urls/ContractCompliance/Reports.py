"""SCM 4.12 Contract & Compliance — the computed carbon-footprint report routes.

COLLISION CHECK — ``carbon-footprint/`` was checked against the WHOLE concatenated urlconf: nothing
anywhere in ``scm`` starts with ``carbon``. ``carbon-footprint/export/`` is a literal sub-route of
that same segment, so this module adds exactly ONE new first segment in total.

``export/`` is literal and sits above no ``<int:pk>`` route here — the report takes no pk at all, it
is filtered entirely through the query string. Both views are ``@login_required`` GETs that write
nothing (the 4.11 report precedent: analytics reads, it never posts a StockMove or a JournalEntry).

This report is NOT a sixth ``LIVE_LINKS["4.12"]`` key — 4.12 has five NavERP.md bullets and the
sidebar mirrors that file exactly, so the page is reached from a chip in the Sustainability list
header instead.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("carbon-footprint/", views.carbon_footprint_report, name="carbon_footprint_report"),
    path("carbon-footprint/export/", views.carbon_footprint_report_export,
         name="carbon_footprint_report_export"),
]
