from django.urls import path

from apps.quality.views.RegulatorySubmissions import ProductRegistrations as views

urlpatterns = [
    path("registrations/", views.product_registration_list, name="product_registration_list"),
    path("registrations/create/", views.product_registration_create, name="product_registration_create"),
    path("registrations/export/", views.product_registration_export, name="product_registration_export"),
    path("registrations/<int:pk>/", views.product_registration_detail, name="product_registration_detail"),
    path("registrations/<int:pk>/edit/", views.product_registration_edit, name="product_registration_edit"),
    path("registrations/<int:pk>/delete/", views.product_registration_delete, name="product_registration_delete"),
]
