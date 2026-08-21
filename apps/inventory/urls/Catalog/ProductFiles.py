"""Inventory 5.1 Product & Catalog Management — ProductFile routes (prefix ``files/``)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("files/", views.productfile_list, name="productfile_list"),
    path("files/add/", views.productfile_create, name="productfile_create"),
    path("files/<int:pk>/", views.productfile_detail, name="productfile_detail"),
    path("files/<int:pk>/edit/", views.productfile_edit, name="productfile_edit"),
    path("files/<int:pk>/delete/", views.productfile_delete, name="productfile_delete"),
]
