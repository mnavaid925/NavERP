"""SCM 4.6 Transportation Management System — Load routes (prefix ``loads/``).

Literal routes before ``<int:pk>/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("loads/", views.load_list, name="load_list"),
    path("loads/add/", views.load_create, name="load_create"),
    path("loads/<int:pk>/", views.load_detail, name="load_detail"),
    path("loads/<int:pk>/edit/", views.load_edit, name="load_edit"),
    path("loads/<int:pk>/delete/", views.load_delete, name="load_delete"),
    path("loads/<int:pk>/tender/", views.load_tender, name="load_tender"),
    path("loads/<int:pk>/book/", views.load_book, name="load_book"),
    path("loads/<int:pk>/dispatch/", views.load_dispatch, name="load_dispatch"),
    path("loads/<int:pk>/deliver/", views.load_deliver, name="load_deliver"),
    path("loads/<int:pk>/cancel/", views.load_cancel, name="load_cancel"),
]
