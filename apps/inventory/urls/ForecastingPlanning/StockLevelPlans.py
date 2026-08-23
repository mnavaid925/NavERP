"""Inventory 5.13 Inventory Forecasting & Planning — StockLevelPlan routes (prefix ``stock-level-plans``).

Lifecycle verbs are literal segments before the ``<int:pk>`` routes and end in their
own tokens, so none can shadow detail/edit/delete.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("stock-level-plans/", views.stocklevelplan_list, name="stocklevelplan_list"),
    path("stock-level-plans/add/", views.stocklevelplan_create, name="stocklevelplan_create"),
    path("stock-level-plans/<int:pk>/activate/", views.stocklevelplan_activate, name="stocklevelplan_activate"),
    path("stock-level-plans/<int:pk>/archive/", views.stocklevelplan_archive, name="stocklevelplan_archive"),
    path("stock-level-plans/<int:pk>/", views.stocklevelplan_detail, name="stocklevelplan_detail"),
    path("stock-level-plans/<int:pk>/edit/", views.stocklevelplan_edit, name="stocklevelplan_edit"),
    path("stock-level-plans/<int:pk>/delete/", views.stocklevelplan_delete, name="stocklevelplan_delete"),
]
