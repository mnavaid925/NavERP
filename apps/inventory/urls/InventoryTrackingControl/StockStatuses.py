"""Inventory 5.6 Inventory Tracking & Control — StockStatus routes (prefix ``tracking/stock-status``).

Literal routes precede the ``<int:pk>`` ones; the module introduces no greedy
``<str:…>`` converter, so there is nothing for another module's patterns to shadow.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("tracking/stock-status/", views.stockstatus_list, name="stockstatus_list"),
    path("tracking/stock-status/add/", views.stockstatus_create, name="stockstatus_create"),
    path("tracking/stock-status/<int:pk>/", views.stockstatus_detail, name="stockstatus_detail"),
    path("tracking/stock-status/<int:pk>/edit/", views.stockstatus_edit, name="stockstatus_edit"),
    path("tracking/stock-status/<int:pk>/delete/", views.stockstatus_delete, name="stockstatus_delete"),
]
