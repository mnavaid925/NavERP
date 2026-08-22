"""Inventory 5.6 Inventory Tracking & Control — Real-Time Stock Levels route.

A computed page (no CRUD entity): no create/edit/delete routes and no ``<int:pk>`` at
all — the ``valuation_report`` / ``warehousemap`` precedent.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("tracking/stock-levels/", views.stocklevels, name="stocklevels"),
]
