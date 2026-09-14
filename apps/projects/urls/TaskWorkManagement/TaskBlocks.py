"""Projects 7.8 — TaskBlock routes (prefix ``blocks/``).

TWO routes only — the evidence-row ruling ships no ``tbk_create``/``tbk_edit``/``tbk_delete``:
rows are minted ONLY by the task verb ``tsk_block`` and closed ONLY by ``tsk_unblock``, both of
which live on the ``tasks/`` segment (the ``ProjectTasks.py`` module). The literal ``blocks/``
precedes the ``<int:pk>/`` one — Django is first-match-wins — and the first segment ``blocks/``
is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("blocks/", views.tbk_list, name="tbk_list"),
    path("blocks/<int:pk>/", views.tbk_detail, name="tbk_detail"),
]
