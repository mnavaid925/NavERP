from django.urls import path

from apps.ecommerce.views.ProductCatalog import BulkOperations as views

urlpatterns = [
    path("products/import/", views.product_import_csv, name="product_import_csv"),
    path("products/export/", views.product_export_csv, name="product_export_csv"),
]
