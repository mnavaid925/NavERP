"""Inventory 5.14 Barcode & RFID Integration — BarcodeLabel URL patterns."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("labels/", views.barcodelabel_list, name="barcodelabel_list"),
    path("labels/add/", views.barcodelabel_create, name="barcodelabel_create"),
    path("labels/<int:pk>/", views.barcodelabel_detail, name="barcodelabel_detail"),
    path("labels/<int:pk>/edit/", views.barcodelabel_edit, name="barcodelabel_edit"),
    path("labels/<int:pk>/delete/", views.barcodelabel_delete, name="barcodelabel_delete"),
    path("labels/<int:pk>/print/", views.barcodelabel_print, name="barcodelabel_print"),
    path("labels/<int:pk>/void/", views.barcodelabel_void, name="barcodelabel_void"),
    path("labels/<int:pk>/render.", views.barcodelabel_render, name="barcodelabel_render"),
]
