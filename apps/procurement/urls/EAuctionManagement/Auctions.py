"""Procurement 6.7 E-Auction Management — Eauction URL patterns."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("eauc/", views.eauc_list, name="eauc_list"),
    path("eauc/add/", views.eauc_create, name="eauc_create"),
    path("eauc/floor/", views.eauc_floor, name="eauc_floor"),
    path("eauc/rules/", views.eauc_rules, name="eauc_rules"),
    path("eauc/<int:pk>/", views.eauc_detail, name="eauc_detail"),
    path("eauc/<int:pk>/edit/", views.eauc_edit, name="eauc_edit"),
    path("eauc/<int:pk>/delete/", views.eauc_delete, name="eauc_delete"),
    path("eauc/<int:pk>/publish/", views.eauc_publish, name="eauc_publish"),
    path("eauc/<int:pk>/cancel/", views.eauc_cancel, name="eauc_cancel"),
    path("eauc/<int:pk>/close/", views.eauc_close, name="eauc_close"),
    path("eauc/<int:pk>/invite/", views.eauc_invite_add, name="eauc_invite_add"),
    path("eauc/<int:pk>/invites/<int:i_pk>/remove/", views.eauc_invite_remove,
         name="eauc_invite_remove"),
    path("eauc/<int:pk>/console/", views.eauc_console, name="eauc_console"),
    path("eauc/<int:pk>/board/", views.eauc_board, name="eauc_board"),
]
