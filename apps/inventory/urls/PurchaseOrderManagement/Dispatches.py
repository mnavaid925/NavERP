"""Inventory 5.3 Purchase Order (PO) Management — dispatch-log routes (prefix
``po/dispatches/``). No edit route by design: a transmission record is proof of what
left, and the model layer refuses nothing else — see the views module docstring."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("po/dispatches/", views.dispatch_list, name="dispatch_list"),
    path("po/dispatches/add/", views.dispatch_create, name="dispatch_create"),
    path("po/dispatches/<int:pk>/", views.dispatch_detail, name="dispatch_detail"),
    path("po/dispatches/<int:pk>/delete/", views.dispatch_delete, name="dispatch_delete"),
]
