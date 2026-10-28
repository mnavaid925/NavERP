from django.urls import path

from apps.ecommerce.views.ProductCatalog import CatalogProducts as views

urlpatterns = [
    path("products/", views.catalogproduct_list, name="catalogproduct_list"),
    path("products/create/", views.catalogproduct_create, name="catalogproduct_create"),
    path("products/<int:pk>/", views.catalogproduct_detail, name="catalogproduct_detail"),
    path("products/<int:pk>/edit/", views.catalogproduct_edit, name="catalogproduct_edit"),
    path("products/<int:pk>/delete/", views.catalogproduct_delete, name="catalogproduct_delete"),
    path("products/<int:pk>/publish/", views.catalogproduct_publish, name="catalogproduct_publish"),
]
