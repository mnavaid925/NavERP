"""Projects 7.8 — ProjectTask execution + verb routes.

These six routes deliberately REUSE 7.2's existing ``tasks/`` first segment with disjoint leaf
literals (``execute|start|complete|block|unblock|bulk-update`` cannot collide with 7.2's
``tree|add|edit|delete`` literals nor with its ``<int:pk>/`` route — an int converter never
matches them), so no new ``tasks/`` segment is declared and nothing can shadow 7.2.

The literal ``tasks/bulk-update/`` is listed FIRST — Django is first-match-wins, and a
``<int:pk>`` route could otherwise never shadow it here, but the discipline keeps every module's
literals ahead of its converters.
"""
from django.urls import path

# Direct sub-module import: the views package re-export lands in the Integrate step (the
# sibling modules' ``from apps.projects import views`` idiom resolves through it).
from apps.projects.views.TaskWorkManagement.ProjectTasks import (
    tsk_block,
    tsk_bulk_update,
    tsk_complete,
    tsk_execute,
    tsk_start,
    tsk_unblock,
)

urlpatterns = [
    path("tasks/bulk-update/", tsk_bulk_update, name="tsk_bulk_update"),
    path("tasks/<int:pk>/execute/", tsk_execute, name="tsk_execute"),
    path("tasks/<int:pk>/start/", tsk_start, name="tsk_start"),
    path("tasks/<int:pk>/complete/", tsk_complete, name="tsk_complete"),
    path("tasks/<int:pk>/block/", tsk_block, name="tsk_block"),
    path("tasks/<int:pk>/unblock/", tsk_unblock, name="tsk_unblock"),
]
