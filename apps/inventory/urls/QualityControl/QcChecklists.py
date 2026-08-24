"""Inventory 5.15 — QcChecklist URL patterns (prefix ``qc-checklists/``).

Literal routes precede the ``<int:pk>`` ones (first-match-wins).
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("qc-checklists/", views.qcchecklist_list, name="qcchecklist_list"),
    path("qc-checklists/add/", views.qcchecklist_create, name="qcchecklist_create"),
    path("qc-checklists/<int:pk>/", views.qcchecklist_detail, name="qcchecklist_detail"),
    path("qc-checklists/<int:pk>/edit/", views.qcchecklist_edit, name="qcchecklist_edit"),
    path("qc-checklists/<int:pk>/delete/", views.qcchecklist_delete, name="qcchecklist_delete"),
]
