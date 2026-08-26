"""Procurement 6.9 Catalog Management — CatalogUploadBatch URL patterns."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("catalog-uploads/", views.catalog_upload_list, name="catalog_upload_list"),
    path("catalog-uploads/add/", views.catalog_upload_create, name="catalog_upload_create"),
    path("catalog-uploads/<int:pk>/", views.catalog_upload_detail, name="catalog_upload_detail"),
    path("catalog-uploads/<int:pk>/edit/", views.catalog_upload_edit, name="catalog_upload_edit"),
    path("catalog-uploads/<int:pk>/delete/", views.catalog_upload_delete,
         name="catalog_upload_delete"),
    path("catalog-uploads/<int:pk>/validate/", views.catalog_upload_validate,
         name="catalog_upload_validate"),
    path("catalog-uploads/<int:pk>/publish/", views.catalog_upload_publish,
         name="catalog_upload_publish"),
    path("catalog-uploads/<int:pk>/reject/", views.catalog_upload_reject,
         name="catalog_upload_reject"),
]
