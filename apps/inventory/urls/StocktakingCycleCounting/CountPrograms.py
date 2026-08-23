"""Inventory 5.11 Stocktaking & Cycle Counting — CountProgram routes (prefix ``count-programs``).

``run`` is a literal segment before the ``<int:pk>`` patterns and ends in its own
token, so it cannot shadow detail/edit/delete.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("count-programs/", views.countprogram_list, name="countprogram_list"),
    path("count-programs/add/", views.countprogram_create, name="countprogram_create"),
    path("count-programs/<int:pk>/run/", views.countprogram_run, name="countprogram_run"),
    path("count-programs/<int:pk>/", views.countprogram_detail, name="countprogram_detail"),
    path("count-programs/<int:pk>/edit/", views.countprogram_edit, name="countprogram_edit"),
    path("count-programs/<int:pk>/delete/", views.countprogram_delete, name="countprogram_delete"),
]
