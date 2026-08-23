"""Inventory 5.8 Lot & Serial Number Tracking — LotNumberRule routes (prefix ``lot-rules``).

``lot-generate/`` is a different first segment from ``lot-rules/``, so the literal
generate route cannot shadow anything; within ``lot-rules/`` the literal ``add/``
precedes the ``<int:pk>`` patterns.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("lot-rules/", views.lotrule_list, name="lotrule_list"),
    path("lot-rules/add/", views.lotrule_create, name="lotrule_create"),
    path("lot-generate/", views.lot_generate, name="lot_generate"),
    path("lot-rules/<int:pk>/", views.lotrule_detail, name="lotrule_detail"),
    path("lot-rules/<int:pk>/edit/", views.lotrule_edit, name="lotrule_edit"),
    path("lot-rules/<int:pk>/delete/", views.lotrule_delete, name="lotrule_delete"),
]
