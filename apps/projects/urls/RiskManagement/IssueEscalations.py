"""Projects 7.5 — IssueEscalation routes (prefix ``escalations/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``escalations/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("escalations/", views.esc_list, name="esc_list"),
    path("escalations/add/", views.esc_create, name="esc_create"),
    path("escalations/<int:pk>/", views.esc_detail, name="esc_detail"),
    path("escalations/<int:pk>/edit/", views.esc_edit, name="esc_edit"),
    path("escalations/<int:pk>/delete/", views.esc_delete, name="esc_delete"),
]
