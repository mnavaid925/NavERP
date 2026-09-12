"""Projects 7.8 — TaskChecklistItem routes (prefix ``checklist-items/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``checklist-items/`` is a disjoint literal from every other module's in this app (and
from 7.2's ``tasks/`` segment, which the six task verbs reuse with disjoint leaf literals).
"""
from django.urls import path

# Direct sub-module import: the views package re-export lands in the Integrate step (the
# sibling modules' ``from apps.projects import views`` idiom resolves through it).
from apps.projects.views.TaskWorkManagement.TaskChecklistItems import (
    tcl_check,
    tcl_create,
    tcl_delete,
    tcl_detail,
    tcl_edit,
    tcl_list,
)

urlpatterns = [
    path("checklist-items/", tcl_list, name="tcl_list"),
    path("checklist-items/add/", tcl_create, name="tcl_create"),
    path("checklist-items/<int:pk>/", tcl_detail, name="tcl_detail"),
    path("checklist-items/<int:pk>/edit/", tcl_edit, name="tcl_edit"),
    path("checklist-items/<int:pk>/delete/", tcl_delete, name="tcl_delete"),
    path("checklist-items/<int:pk>/check/", tcl_check, name="tcl_check"),
]
