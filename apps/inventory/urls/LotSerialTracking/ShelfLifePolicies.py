"""Inventory 5.8 Lot & Serial Number Tracking — ShelfLifePolicy routes (prefix ``shelf-life-policies``).

A distinct first segment from every other module in this app (``fefo-board/`` is its
own whole component), so nothing here can shadow or be shadowed.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("shelf-life-policies/", views.shelflifepolicy_list, name="shelflifepolicy_list"),
    path("shelf-life-policies/add/", views.shelflifepolicy_create, name="shelflifepolicy_create"),
    path("shelf-life-policies/<int:pk>/", views.shelflifepolicy_detail, name="shelflifepolicy_detail"),
    path("shelf-life-policies/<int:pk>/edit/", views.shelflifepolicy_edit, name="shelflifepolicy_edit"),
    path("shelf-life-policies/<int:pk>/delete/", views.shelflifepolicy_delete, name="shelflifepolicy_delete"),
]
