from django.urls import path

from apps.ecommerce.views.ProductCatalog import ProductRelationships as views

urlpatterns = [
    path("relationships/", views.productrelationship_list, name="productrelationship_list"),
    path("relationships/create/", views.productrelationship_create, name="productrelationship_create"),
    path("relationships/<int:pk>/", views.productrelationship_detail, name="productrelationship_detail"),
    path("relationships/<int:pk>/edit/", views.productrelationship_edit, name="productrelationship_edit"),
    path("relationships/<int:pk>/delete/", views.productrelationship_delete, name="productrelationship_delete"),
]
