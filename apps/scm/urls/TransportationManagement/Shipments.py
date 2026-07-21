"""SCM 4.6 Transportation Management System — Shipment routes (prefix ``shipments/``).

Literal routes before ``<int:pk>/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("shipments/", views.shipment_list, name="shipment_list"),
    path("shipments/add/", views.shipment_create, name="shipment_create"),
    path("shipments/<int:pk>/", views.shipment_detail, name="shipment_detail"),
    path("shipments/<int:pk>/edit/", views.shipment_edit, name="shipment_edit"),
    path("shipments/<int:pk>/delete/", views.shipment_delete, name="shipment_delete"),
    path("shipments/<int:pk>/book/", views.shipment_book, name="shipment_book"),
    path("shipments/<int:pk>/add-event/", views.shipment_add_event, name="shipment_add_event"),
    path("shipments/<int:pk>/cancel/", views.shipment_cancel, name="shipment_cancel"),
]
