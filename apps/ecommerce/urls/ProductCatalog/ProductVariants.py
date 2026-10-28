from django.urls import path

from apps.ecommerce.views.ProductCatalog import ProductVariants as views

urlpatterns = [
    path("variants/", views.productvariant_list, name="productvariant_list"),
    path("variants/create/", views.productvariant_create, name="productvariant_create"),
    path("variants/<int:pk>/", views.productvariant_detail, name="productvariant_detail"),
    path("variants/<int:pk>/edit/", views.productvariant_edit, name="productvariant_edit"),
    path("variants/<int:pk>/delete/", views.productvariant_delete, name="productvariant_delete"),
]
