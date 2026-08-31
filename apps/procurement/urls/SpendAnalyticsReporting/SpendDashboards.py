"""Procurement 6.14 Spend Analytics & Reporting — computed spend page URL patterns.

ONE new first segment, ``spend/``, and every route in this module is a literal whole component
under it: ``spend/``, ``spend/categories/``, ``spend/export/`` and ``spend/export/download/``.
Checked against the first-segment inventory in ``apps/procurement/urls/__init__.py`` — ``spend/``
is new (``spend-reports/``, ``spend-report-snapshots/`` and ``spend-rules/`` are distinct whole
components, not prefixes of it, because Django matches path segments and not string prefixes).

There is no ``<int:pk>`` route here and no greedy ``<str:…>`` converter anywhere in this app, so
Django's first-match-wins resolution has no shadowing surface to reason about. Ordering below is
therefore documentation rather than behaviour: the parent page precedes its children, and
``spend/export/download/`` is declared before ``spend/export/`` would be able to hide it (it could
not — they differ by a whole segment — but the habit is what keeps the next module safe).

The sibling modules of this sub-module claim ``spend/classification/`` (the classification
workbench) and ``spend/maverick/`` + ``spend/maverick/scan/`` (the maverick board). Those are
literal children of the same ``spend/`` segment declared in their own modules; none of them
collides with the four below.

All four views are ``@login_required`` staff pages and all four are READ-ONLY — there is no POST
route in this lane, because nothing here writes.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("spend/", views.spend_dashboard, name="spend_dashboard"),
    path("spend/categories/", views.category_spend, name="category_spend"),
    # The download is declared before its page purely for readability — they are distinct whole
    # segments, so neither can shadow the other.
    path("spend/export/download/", views.spend_export_download, name="spend_export_download"),
    path("spend/export/", views.spend_export, name="spend_export"),
]
