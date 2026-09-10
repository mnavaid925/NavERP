"""Projects 7.6 — QualityPlan routes (prefix ``quality-plans/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``quality-plans/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("quality-plans/", views.qpl_list, name="qpl_list"),
    path("quality-plans/add/", views.qpl_create, name="qpl_create"),
    path("quality-plans/<int:pk>/", views.qpl_detail, name="qpl_detail"),
    path("quality-plans/<int:pk>/edit/", views.qpl_edit, name="qpl_edit"),
    path("quality-plans/<int:pk>/delete/", views.qpl_delete, name="qpl_delete"),
    path("quality-plans/<int:pk>/approve/", views.qpl_approve, name="qpl_approve"),
    path("quality-plans/<int:pk>/supersede/", views.qpl_supersede, name="qpl_supersede"),
]
