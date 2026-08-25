"""Inventory 5.18 — TaxRule routes (prefix ``tax-rules``)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("tax-rules/", views.taxrule_list, name="taxrule_list"),
    path("tax-rules/add/", views.taxrule_create, name="taxrule_create"),
    path("tax-rules/<int:pk>/", views.taxrule_detail, name="taxrule_detail"),
    path("tax-rules/<int:pk>/edit/", views.taxrule_edit, name="taxrule_edit"),
    path("tax-rules/<int:pk>/delete/", views.taxrule_delete, name="taxrule_delete"),
]
