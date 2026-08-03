"""SCM 4.13 Asset Management — the three COMPUTED report pages: ``pm-forecast/``, ``spare-parts/``
and ``asset-depreciation/``.

Each is a single GET page derived from rows that already exist — no new table, no new column, and
therefore no create/edit/delete route and no ``<int:pk>`` at all (the ``valuation_report`` /
``reorder_alerts`` / ``carbon_footprint_report`` precedent). Every option each page takes is a QUERY
STRING (``?days=`` on the forecast; ``?q=&category=&stock=&is_active=&date_from=&date_to=`` on the
storeroom; ``?q=&status=&asset_type=&criticality=&linked=&location=`` on the depreciation report),
so none of them adds a route beyond the one below.

COLLISION CHECK — all three prefixes checked against the WHOLE concatenated urlconf, not merely
against this block:

* ``pm-forecast/`` — nothing anywhere in ``scm`` starts with ``pm``.
* ``spare-parts/`` — nothing anywhere starts with ``spare``. Note 4.13's own
  ``asset-spare-parts/`` (the ``AssetSparePart`` child, in ``Assets.py``) is a SEPARATE whole path
  component: Django matches whole components and never splits one at a hyphen, so ``spare-parts``
  and ``asset-spare-parts`` are unrelated segments and neither can shadow the other. Do NOT "tidy"
  either one to match the other — they are also different things, the report being 4.3's item
  ledger filtered while the child is one machine's parts list.
* ``asset-depreciation/`` — a distinct component from ``assets/`` and ``asset-spare-parts/`` for the
  same reason. Nothing outside 4.13 starts with ``asset`` at all.

None of the three introduces a greedy ``<str:…>`` converter; 4.10's ``return-tracking/<str:token>/``
remains the app's only one. There is no ``<int:pk>`` route in this module, so there is nothing here
that could swallow a literal.

WHY THESE ARE REPORTS AND NOT TABLES. ``spare-parts/`` is **4.3's inventory, filtered** — a spare
part is an ``scm.Item`` flagged ``is_spare_part``, its on-hand is the live SUM of the append-only
``StockMove`` ledger, and its min/max come from the ``ReorderRule`` the buyer already maintains.
There is no ``SparePart`` table. ``asset-depreciation/`` READS acquisition cost, accumulated
depreciation and book value from the linked ``accounting.FixedAsset``; SCM stores none of them,
recomputes none of them and posts no ``JournalEntry`` (L29).
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # The PM board: what preventive work is owed inside ?days=N, plus the open-jobs dispatch queue.
    path("pm-forecast/", views.pm_forecast, name="pm_forecast"),
    # The MRO storeroom: derived on-hand + ReorderRule min/max + windowed maintenance consumption.
    path("spare-parts/", views.sparepart_list, name="sparepart_list"),
    # Repair vs replace: SCM maintenance spend against accounting's book value.
    path("asset-depreciation/", views.asset_depreciation_report, name="asset_depreciation_report"),
]
