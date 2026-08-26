"""Procurement 6.9 Catalog Management — CatalogItem URL patterns.

``catalog-items/`` is this entity's first segment for every route.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("catalog-items/", views.catalog_item_list, name="catalog_item_list"),
    path("catalog-items/add/", views.catalog_item_create, name="catalog_item_create"),
    path("catalog-items/<int:pk>/", views.catalog_item_detail, name="catalog_item_detail"),
    path("catalog-items/<int:pk>/edit/", views.catalog_item_edit, name="catalog_item_edit"),
    path("catalog-items/<int:pk>/delete/", views.catalog_item_delete,
         name="catalog_item_delete"),
    path("catalog-items/<int:pk>/submit/", views.catalog_item_submit,
         name="catalog_item_submit"),
    path("catalog-items/<int:pk>/approve/", views.catalog_item_approve,
         name="catalog_item_approve"),
    path("catalog-items/<int:pk>/reject/", views.catalog_item_reject,
         name="catalog_item_reject"),
    path("catalog-items/<int:pk>/block/", views.catalog_item_block,
         name="catalog_item_block"),
]
