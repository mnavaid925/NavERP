"""Inventory 5.8 Lot & Serial Number Tracking — Traceability route (computed page).

The picker renders on ``traceability/`` itself; a traced lot is a GET parameter
(``?lot=<pk>``), not a path segment — so this module needs exactly one route and
introduces no converter at all.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("traceability/", views.traceability, name="traceability"),
]
