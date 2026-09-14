"""Projects 7.9 — Channel routes (prefix ``channels/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``channels/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("channels/", views.chn_list, name="chn_list"),
    path("channels/add/", views.chn_create, name="chn_create"),
    path("channels/<int:pk>/", views.chn_detail, name="chn_detail"),
    path("channels/<int:pk>/edit/", views.chn_edit, name="chn_edit"),
    path("channels/<int:pk>/delete/", views.chn_delete, name="chn_delete"),
    path("channels/<int:pk>/archive/", views.chn_archive, name="chn_archive"),
]
