"""Inventory 5.5 Warehousing & Bin Management — CrossDockOrder routes (prefix ``cross-dock/``).

The lifecycle verbs are literal segments BEFORE the ``<int:pk>`` routes, and each ends
in its own token (``/receive/`` vs ``/ship/`` vs ``/cancel/``), so none can shadow the
detail/edit/delete patterns.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("cross-dock/", views.crossdockorder_list, name="crossdockorder_list"),
    path("cross-dock/add/", views.crossdockorder_create, name="crossdockorder_create"),
    path("cross-dock/<int:pk>/receive/", views.crossdockorder_receive, name="crossdockorder_receive"),
    path("cross-dock/<int:pk>/ship/", views.crossdockorder_ship, name="crossdockorder_ship"),
    path("cross-dock/<int:pk>/cancel/", views.crossdockorder_cancel, name="crossdockorder_cancel"),
    path("cross-dock/<int:pk>/", views.crossdockorder_detail, name="crossdockorder_detail"),
    path("cross-dock/<int:pk>/edit/", views.crossdockorder_edit, name="crossdockorder_edit"),
    path("cross-dock/<int:pk>/delete/", views.crossdockorder_delete, name="crossdockorder_delete"),
]
