"""Inventory 5.15 — QuarantineOrder URL patterns (prefix ``quarantine/``).

Literal routes precede the ``<int:pk>`` ones (first-match-wins); the lifecycle verbs are
literal segments BEFORE the ``<int:pk>`` routes, each ending in its own token, so none can
shadow detail/edit/delete.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("quarantine/", views.quarantineorder_list, name="quarantineorder_list"),
    path("quarantine/add/", views.quarantineorder_create, name="quarantineorder_create"),
    path("quarantine/<int:pk>/", views.quarantineorder_detail, name="quarantineorder_detail"),
    path("quarantine/<int:pk>/edit/", views.quarantineorder_edit, name="quarantineorder_edit"),
    path("quarantine/<int:pk>/delete/", views.quarantineorder_delete, name="quarantineorder_delete"),
    path("quarantine/<int:pk>/quarantine/", views.quarantineorder_quarantine, name="quarantineorder_quarantine"),
    path("quarantine/<int:pk>/release/", views.quarantineorder_release, name="quarantineorder_release"),
    path("quarantine/<int:pk>/scrap/", views.quarantineorder_scrap, name="quarantineorder_scrap"),
    path("quarantine/<int:pk>/cancel/", views.quarantineorder_cancel, name="quarantineorder_cancel"),
]
