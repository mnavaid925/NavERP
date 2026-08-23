"""Inventory 5.7 Stock Movement & Transfers — TransferRoute routes (prefix ``transfers/routes/``)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("transfers/routes/", views.transferroute_list, name="transferroute_list"),
    path("transfers/routes/add/", views.transferroute_create, name="transferroute_create"),
    path("transfers/routes/<int:pk>/", views.transferroute_detail, name="transferroute_detail"),
    path("transfers/routes/<int:pk>/edit/", views.transferroute_edit, name="transferroute_edit"),
    path("transfers/routes/<int:pk>/delete/", views.transferroute_delete,
         name="transferroute_delete"),
]
