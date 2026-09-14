"""Projects 7.8 — TaskChecklistItem routes (prefix ``checklist-items/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``checklist-items/`` is a disjoint literal from every other module's in this app (and
from 7.2's ``tasks/`` segment, which the six task verbs reuse with disjoint leaf literals).
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("checklist-items/", views.tcl_list, name="tcl_list"),
    path("checklist-items/add/", views.tcl_create, name="tcl_create"),
    path("checklist-items/<int:pk>/", views.tcl_detail, name="tcl_detail"),
    path("checklist-items/<int:pk>/edit/", views.tcl_edit, name="tcl_edit"),
    path("checklist-items/<int:pk>/delete/", views.tcl_delete, name="tcl_delete"),
    path("checklist-items/<int:pk>/check/", views.tcl_check, name="tcl_check"),
]
