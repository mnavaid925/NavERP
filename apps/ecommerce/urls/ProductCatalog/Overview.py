from django.urls import path

from apps.ecommerce.views.ProductCatalog import Overview as views

urlpatterns = [
    path("overview/", views.catalog_overview, name="catalog_overview"),
    path("", views.catalog_overview, name="dashboard"),
]
