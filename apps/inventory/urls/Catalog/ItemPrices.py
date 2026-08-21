"""Inventory 5.1 Product & Catalog Management — ItemPrice routes (prefix ``prices/``)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("prices/", views.itemprice_list, name="itemprice_list"),
    path("prices/add/", views.itemprice_create, name="itemprice_create"),
    path("prices/<int:pk>/", views.itemprice_detail, name="itemprice_detail"),
    path("prices/<int:pk>/edit/", views.itemprice_edit, name="itemprice_edit"),
    path("prices/<int:pk>/delete/", views.itemprice_delete, name="itemprice_delete"),
]
