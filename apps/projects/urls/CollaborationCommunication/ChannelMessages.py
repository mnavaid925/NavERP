"""Projects 7.9 — ChannelMessage routes (prefix ``messages/``).

Literal routes (``add/``) precede the ``<int:pk>/`` ones — Django is first-match-wins. The first
segment ``messages/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("messages/", views.msg_list, name="msg_list"),
    path("messages/add/", views.msg_create, name="msg_create"),
    path("messages/<int:pk>/edit/", views.msg_edit, name="msg_edit"),
    path("messages/<int:pk>/delete/", views.msg_delete, name="msg_delete"),
]
