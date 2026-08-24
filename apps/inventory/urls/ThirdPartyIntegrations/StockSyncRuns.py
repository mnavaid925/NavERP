"""Inventory 5.19 Third-Party Integrations & API — routes for the ``runs/`` block.

The append-only StockSyncRun register: list + detail + ONE admin retry POST. Literals before
``<int:pk>`` per the house first-match rule (trivially satisfied here — ``runs/`` shares no first
segment with the pk patterns). Imports the view module DIRECTLY rather than through the
package-root re-export: this file ships during the build wave, before
``apps/inventory/views/__init__.py`` gains its 5.19 lines, and attribute access through the
not-yet-wired package would raise at import time.
"""
from django.urls import path

from apps.inventory.views.ThirdPartyIntegrations import StockSyncRuns as views

urlpatterns = [
    path("runs/", views.stocksyncrun_list, name="stocksyncrun_list"),
    path("runs/<int:pk>/", views.stocksyncrun_detail, name="stocksyncrun_detail"),
    path("runs/<int:pk>/retry/", views.stocksyncrun_retry, name="stocksyncrun_retry"),
]
