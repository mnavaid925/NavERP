from django.urls import path

from apps.quality.views.CapaManagement import CapaActions as views

urlpatterns = [
    path("capa/actions/", views.capa_action_list, name="capa_action_list"),
    path("capa/actions/create/", views.capa_action_create, name="capa_action_create"),
    path("capa/actions/export/", views.capa_action_export, name="capa_action_export"),
    path("capa/actions/<int:pk>/", views.capa_action_detail, name="capa_action_detail"),
    path("capa/actions/<int:pk>/edit/", views.capa_action_edit, name="capa_action_edit"),
    path("capa/actions/<int:pk>/delete/", views.capa_action_delete, name="capa_action_delete"),
    path("capa/actions/<int:pk>/complete/", views.capa_action_mark_completed, name="capa_action_mark_completed"),
    path("capa/actions/<int:pk>/verify/", views.capa_action_verify, name="capa_action_verify"),
]
