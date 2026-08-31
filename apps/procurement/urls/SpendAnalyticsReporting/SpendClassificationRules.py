"""Procurement 6.14 Spend Analytics & Reporting — SpendClassificationRule routes.

First segment claimed: ``spend-rules/`` — a new whole component, collision-checked against the
inventory in ``apps/procurement/urls/__init__.py``. This app declares no greedy ``<str:...>``
converter, so nothing upstream can swallow these paths.

The register has **no sidebar key** by design (the ``ReceiptTolerancePolicy`` / ``KpiTarget``
precedent): it is reached from ``procurement:category_spend`` and from the classification
workbench, because a rule table is configuration behind an analysis page rather than a
destination of its own.
"""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal routes BEFORE the <int:pk> ones — Django resolves first-match-wins, so
    # ``spend-rules/add/`` must be declared above ``spend-rules/<int:pk>/``.
    path("spend-rules/", views.spendrule_list, name="spendrule_list"),
    path("spend-rules/add/", views.spendrule_create, name="spendrule_create"),
    path("spend-rules/<int:pk>/", views.spendrule_detail, name="spendrule_detail"),
    path("spend-rules/<int:pk>/edit/", views.spendrule_edit, name="spendrule_edit"),
    # POST-only (@require_POST on the view) — a GET here is a 405, never a deletion.
    path("spend-rules/<int:pk>/delete/", views.spendrule_delete, name="spendrule_delete"),
    # POST-only: it stamps match_count / last_matched_at and writes an audit row.
    path("spend-rules/<int:pk>/preview/", views.spendrule_preview, name="spendrule_preview"),
]
