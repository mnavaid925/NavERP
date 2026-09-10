"""Projects 7.5 — ProjectRisk routes (prefix ``risks/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``risks/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("risks/", views.rsk_list, name="rsk_list"),
    path("risks/add/", views.rsk_create, name="rsk_create"),
    path("risks/<int:pk>/", views.rsk_detail, name="rsk_detail"),
    path("risks/<int:pk>/edit/", views.rsk_edit, name="rsk_edit"),
    path("risks/<int:pk>/delete/", views.rsk_delete, name="rsk_delete"),
    path("risks/<int:pk>/realize/", views.rsk_realize, name="rsk_realize"),
    path("risks/<int:pk>/close/", views.rsk_close, name="rsk_close"),
    path("risks/<int:pk>/reopen/", views.rsk_reopen, name="rsk_reopen"),
]
