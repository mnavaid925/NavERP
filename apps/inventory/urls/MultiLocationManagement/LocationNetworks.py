"""Inventory 5.12 Multi-Location Management — routes (prefixes ``networks/`` and
``global-stock/``). Literals before ``<int:pk>``, per the house first-match rule;
the computed stock page is a literal too and goes FIRST.

Imports the view modules DIRECTLY rather than through the package-root re-export:
this file shipped during the build wave, before ``apps/inventory/views/__init__.py``
gained its 5.9-style wiring lines (integrate phase), and attribute access through
the not-yet-wired package would have raised at import time. After integration either
spelling resolves to the same function objects. CRUD comes from ``LocationNetworks``,
the computed page from its own ``GlobalStock`` module (C1 split).
"""
from django.urls import path

from apps.inventory.views.MultiLocationManagement import GlobalStock as gs_views
from apps.inventory.views.MultiLocationManagement import LocationNetworks as views

urlpatterns = [
    path("global-stock/", gs_views.global_stock, name="global_stock"),
    path("networks/", views.locationnetwork_list, name="locationnetwork_list"),
    path("networks/add/", views.locationnetwork_create, name="locationnetwork_create"),
    path("networks/<int:pk>/", views.locationnetwork_detail, name="locationnetwork_detail"),
    path("networks/<int:pk>/edit/", views.locationnetwork_edit, name="locationnetwork_edit"),
    path("networks/<int:pk>/delete/", views.locationnetwork_delete, name="locationnetwork_delete"),
]
