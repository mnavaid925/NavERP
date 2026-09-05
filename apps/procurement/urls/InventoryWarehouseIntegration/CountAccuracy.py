"""Procurement 6.18 Inventory & Warehouse Integration — Count Accuracy URL pattern.

One route, one first segment: ``count-accuracy/``, collision-checked as a whole COMPONENT against
the concatenated ``urls/__init__.py`` inventory. Django matches path components, not strings, so
this segment cannot reach ``replenishment-runs/`` or any other in this app however similarly they
read.

The page is derived and read-only — no model, no form, no verbs — so there is no ``<int:pk>`` route
here for the literal one to be ordered before. First-match-wins still applies across the
concatenated list, and this segment is unique in it.

**Import shape.** The view function is imported from its ENTITY MODULE, not through
``from apps.procurement import views``: the app-level ``views/__init__.py`` re-export does not exist
until the Integrator lands it, and going through the package would be a star-import cycle at
URLconf import time. The alias keeps the ``views.<name>`` reference idiom of every other urls module
in this app, and resolves to the identical function object once the re-export does land.
"""
from django.urls import path

from apps.procurement.views.InventoryWarehouseIntegration import CountAccuracy as views


urlpatterns = [
    path("count-accuracy/", views.count_accuracy, name="count_accuracy"),
]
