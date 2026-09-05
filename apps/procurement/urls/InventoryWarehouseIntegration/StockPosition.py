"""Procurement 6.18 Inventory & Warehouse Integration — Stock Position URL pattern.

One route, one first segment: ``stock-position/``, collision-checked as a whole COMPONENT against
the concatenated ``urls/__init__.py`` inventory. Django matches path components, not strings, so
``stock-position/`` cannot reach ``replenishment-policies/`` or any other segment in this app
however similarly they read.

The page is derived and read-only — no model, no form, no verbs — so there is no ``<int:pk>``
route here for the literal one to be ordered before. First-match-wins still applies across the
concatenated list, and this segment is unique in it.

**Import shape.** The view function is imported from its ENTITY MODULE, not through
``from apps.procurement import views``. The app-level ``views/__init__.py`` re-export does not
exist until the Integrator lands it, and going through the package would be a star-import cycle at
URLconf import time — the same rule every other module in this sub-module follows. The alias keeps
the ``views.<name>`` reference idiom of every other urls module in this app, and resolves to the
identical function object once the re-export does land.
"""
from django.urls import path

from apps.procurement.views.InventoryWarehouseIntegration import StockPosition as views


urlpatterns = [
    path("stock-position/", views.stock_position, name="stock_position"),
]
