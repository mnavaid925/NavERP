from django.urls import path

from apps.ecommerce.views.ProductCatalog import StoreCategories as views

urlpatterns = [
    path("categories/", views.storecategory_list, name="storecategory_list"),
    path("categories/create/", views.storecategory_create, name="storecategory_create"),
    path("categories/<int:pk>/", views.storecategory_detail, name="storecategory_detail"),
    path("categories/<int:pk>/edit/", views.storecategory_edit, name="storecategory_edit"),
    path("categories/<int:pk>/delete/", views.storecategory_delete, name="storecategory_delete"),
]
