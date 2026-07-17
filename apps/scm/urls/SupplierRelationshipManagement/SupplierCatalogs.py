"""SCM 4.2 SRM — SupplierCatalog URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("catalogs/", views.catalog_list, name="catalog_list"),
    path("catalogs/add/", views.catalog_create, name="catalog_create"),
    path("catalogs/<int:pk>/", views.catalog_detail, name="catalog_detail"),
    path("catalogs/<int:pk>/edit/", views.catalog_edit, name="catalog_edit"),
    path("catalogs/<int:pk>/delete/", views.catalog_delete, name="catalog_delete"),
    path("catalogs/<int:pk>/activate/", views.catalog_activate, name="catalog_activate"),
]
