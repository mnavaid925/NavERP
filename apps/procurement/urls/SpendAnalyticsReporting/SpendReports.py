"""Procurement 6.14 Spend Analytics & Reporting — SpendReport + SpendReportSnapshot URL patterns.

Two first segments, ``spend-reports/`` and ``spend-report-snapshots/`` — both collision-checked
against the concatenated ``urls/__init__.py`` inventory as whole components, and the app registers
no greedy ``<str:…>`` converter, so nothing can shadow either.

Django is first-match-wins, so within each segment the literal route (``add/``) is declared BEFORE
the ``<int:pk>/`` one it would otherwise fall into.

Every verb route (``delete/``, ``run/``, ``snapshot/``, ``favorite/``) is POST-only through its
view decorator — there is no confirm template for any of them; the list and detail pages carry a
``{% csrf_token %}`` form with an ``onclick`` confirm instead.

``spend-report-snapshots/`` deliberately has NO list and NO ``add/`` route: a snapshot is minted
only by ``spendreport_snapshot`` and is reached from its parent report. That is the documented
CRUD exemption, recorded in the view module's docstring as well.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # -- the register ---------------------------------------------------------------------------
    path("spend-reports/", views.spendreport_list, name="spendreport_list"),
    path("spend-reports/add/", views.spendreport_create, name="spendreport_create"),
    # -- one report -----------------------------------------------------------------------------
    path("spend-reports/<int:pk>/", views.spendreport_detail, name="spendreport_detail"),
    path("spend-reports/<int:pk>/edit/", views.spendreport_edit, name="spendreport_edit"),
    path("spend-reports/<int:pk>/delete/", views.spendreport_delete, name="spendreport_delete"),
    # -- verbs ------------------------------------------------------------------------------------
    path("spend-reports/<int:pk>/run/", views.spendreport_run, name="spendreport_run"),
    path("spend-reports/<int:pk>/snapshot/", views.spendreport_snapshot,
         name="spendreport_snapshot"),
    path("spend-reports/<int:pk>/export/", views.spendreport_export, name="spendreport_export"),
    path("spend-reports/<int:pk>/favorite/", views.spendreport_favorite,
         name="spendreport_favorite"),
    # -- one frozen run (no list, no add — minted only by spendreport_snapshot) --------------------
    path("spend-report-snapshots/<int:pk>/", views.spendreportsnapshot_detail,
         name="spendreportsnapshot_detail"),
    path("spend-report-snapshots/<int:pk>/export/", views.spendreportsnapshot_export,
         name="spendreportsnapshot_export"),
    path("spend-report-snapshots/<int:pk>/delete/", views.spendreportsnapshot_delete,
         name="spendreportsnapshot_delete"),
]
