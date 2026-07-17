"""SCM 4.3 Inventory Management — Item / ItemCategory / UOM URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    # Item
    path("items/", views.item_list, name="item_list"),
    path("items/add/", views.item_create, name="item_create"),
    path("items/<int:pk>/", views.item_detail, name="item_detail"),
    path("items/<int:pk>/edit/", views.item_edit, name="item_edit"),
    path("items/<int:pk>/delete/", views.item_delete, name="item_delete"),
    # ItemCategory
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    # UOM
    path("uoms/", views.uom_list, name="uom_list"),
    path("uoms/add/", views.uom_create, name="uom_create"),
    path("uoms/<int:pk>/edit/", views.uom_edit, name="uom_edit"),
    path("uoms/<int:pk>/delete/", views.uom_delete, name="uom_delete"),
]
