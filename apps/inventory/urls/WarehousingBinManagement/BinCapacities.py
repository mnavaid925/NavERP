"""Inventory 5.5 Warehousing & Bin Management — BinCapacity routes (prefix ``bin-capacity/``)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("bin-capacity/", views.bincapacity_list, name="bincapacity_list"),
    path("bin-capacity/add/", views.bincapacity_create, name="bincapacity_create"),
    path("bin-capacity/<int:pk>/", views.bincapacity_detail, name="bincapacity_detail"),
    path("bin-capacity/<int:pk>/edit/", views.bincapacity_edit, name="bincapacity_edit"),
    path("bin-capacity/<int:pk>/delete/", views.bincapacity_delete, name="bincapacity_delete"),
]
