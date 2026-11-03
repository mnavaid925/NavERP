from django.urls import path
from apps.ecommerce.views.MultiStore import StorefrontCatalogAssignments as views

urlpatterns = [
    path("multi-store/catalog-assignments/", views.storefront_catalog_assignment_list, name="storefront_catalog_assignment_list"),
    path("multi-store/catalog-assignments/create/", views.storefront_catalog_assignment_create, name="storefront_catalog_assignment_create"),
    path("multi-store/catalog-assignments/<int:pk>/", views.storefront_catalog_assignment_detail, name="storefront_catalog_assignment_detail"),
    path("multi-store/catalog-assignments/<int:pk>/edit/", views.storefront_catalog_assignment_edit, name="storefront_catalog_assignment_edit"),
    path("multi-store/catalog-assignments/<int:pk>/delete/", views.storefront_catalog_assignment_delete, name="storefront_catalog_assignment_delete"),
]
