from django.urls import path

from apps.quality.views.DataIntegrity import SystemChangeControls as views

urlpatterns = [
    path("change-controls/", views.system_change_control_list, name="system_change_control_list"),
    path("change-controls/create/", views.system_change_control_create, name="system_change_control_create"),
    path("change-controls/<int:pk>/", views.system_change_control_detail, name="system_change_control_detail"),
    path("change-controls/<int:pk>/edit/", views.system_change_control_edit, name="system_change_control_edit"),
    path("change-controls/<int:pk>/delete/", views.system_change_control_delete, name="system_change_control_delete"),
]
