"""Inventory 5.9 Order Management & Fulfillment — routes (prefixes ``waves/`` and
``waves-board/``). Literals before ``<int:pk>``, per the house first-match rule; the two
``orders/…`` membership routes sit under the detail pk on purpose.

Imports the view module DIRECTLY rather than through the package-root re-export: this
file ships during the build wave, before ``apps/inventory/views/__init__.py`` gains its
5.9 lines (integrate phase), and attribute access through the not-yet-wired package
would raise at import time. After integration either spelling resolves to the same
function objects.
"""
from django.urls import path

from apps.inventory.views.FulfillmentOrchestration import FulfillmentWaves as views

urlpatterns = [
    path("waves-board/", views.wave_board, name="wave_board"),
    path("waves/", views.wave_list, name="wave_list"),
    path("waves/add/", views.wave_create, name="wave_create"),
    path("waves/<int:pk>/", views.wave_detail, name="wave_detail"),
    path("waves/<int:pk>/edit/", views.wave_edit, name="wave_edit"),
    path("waves/<int:pk>/delete/", views.wave_delete, name="wave_delete"),
    path("waves/<int:pk>/release/", views.wave_release, name="wave_release"),
    path("waves/<int:pk>/close/", views.wave_close, name="wave_close"),
    path("waves/<int:pk>/cancel/", views.wave_cancel, name="wave_cancel"),
    path("waves/<int:pk>/orders/add/", views.waveorder_add, name="waveorder_add"),
    path("waves/<int:pk>/orders/remove/<int:order_pk>/",
         views.waveorder_remove, name="waveorder_remove"),
]
