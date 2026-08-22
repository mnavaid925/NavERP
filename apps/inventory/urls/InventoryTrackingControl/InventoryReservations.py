"""Inventory 5.6 Inventory Tracking & Control — InventoryReservation routes (prefix ``tracking/reservations``).

The lifecycle verbs are literal segments BEFORE the ``<int:pk>`` routes, and each ends
in its own token (``/release/`` vs ``/consume/`` vs ``/cancel/``), so none can shadow
the detail/edit/delete patterns.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("tracking/reservations/", views.reservation_list, name="reservation_list"),
    path("tracking/reservations/add/", views.reservation_create, name="reservation_create"),
    path("tracking/reservations/<int:pk>/release/", views.reservation_release, name="reservation_release"),
    path("tracking/reservations/<int:pk>/consume/", views.reservation_consume, name="reservation_consume"),
    path("tracking/reservations/<int:pk>/cancel/", views.reservation_cancel, name="reservation_cancel"),
    path("tracking/reservations/<int:pk>/", views.reservation_detail, name="reservation_detail"),
    path("tracking/reservations/<int:pk>/edit/", views.reservation_edit, name="reservation_edit"),
    path("tracking/reservations/<int:pk>/delete/", views.reservation_delete, name="reservation_delete"),
]
