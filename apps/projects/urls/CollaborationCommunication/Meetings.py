"""Projects 7.9 — Meeting routes (prefixes ``meetings/``, ``agenda-items/``, ``action-items/``).

Literal routes precede the ``<int:pk>/`` ones — Django is first-match-wins. ``meetings/add/`` is
listed before ``meetings/<int:pk>/`` for that reason, and the two child-add routes
(``meetings/<int:pk>/agenda/add/`` and ``meetings/<int:pk>/actions/add/``) are literal leaves
below the int converter, so they can never be swallowed by it. The three first segments here are
disjoint literals from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("meetings/", views.mtg_list, name="mtg_list"),
    path("meetings/add/", views.mtg_create, name="mtg_create"),
    path("meetings/<int:pk>/", views.mtg_detail, name="mtg_detail"),
    path("meetings/<int:pk>/edit/", views.mtg_edit, name="mtg_edit"),
    path("meetings/<int:pk>/delete/", views.mtg_delete, name="mtg_delete"),
    path("meetings/<int:pk>/start/", views.mtg_start, name="mtg_start"),
    path("meetings/<int:pk>/complete/", views.mtg_complete, name="mtg_complete"),
    path("meetings/<int:pk>/cancel/", views.mtg_cancel, name="mtg_cancel"),
    path("meetings/<int:pk>/minutes/", views.mtg_minutes, name="mtg_minutes"),
    path("meetings/<int:pk>/agenda/add/", views.agi_create, name="agi_create"),
    path("meetings/<int:pk>/actions/add/", views.mai_create, name="mai_create"),
    path("agenda-items/<int:pk>/edit/", views.agi_edit, name="agi_edit"),
    path("agenda-items/<int:pk>/delete/", views.agi_delete, name="agi_delete"),
    path("agenda-items/<int:pk>/cover/", views.agi_cover, name="agi_cover"),
    path("action-items/<int:pk>/edit/", views.mai_edit, name="mai_edit"),
    path("action-items/<int:pk>/delete/", views.mai_delete, name="mai_delete"),
    path("action-items/<int:pk>/toggle/", views.mai_toggle, name="mai_toggle"),
]
