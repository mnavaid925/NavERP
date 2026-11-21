from django.urls import path

from apps.quality.views.ProcessValidation import ComputerSystemValidations as views

urlpatterns = [
    path("validation/computer-systems/", views.computer_system_validation_list, name="computer_system_validation_list"),
    path("validation/computer-systems/create/", views.computer_system_validation_create, name="computer_system_validation_create"),
    path("validation/computer-systems/export/", views.computer_system_validation_export, name="computer_system_validation_export"),
    path("validation/computer-systems/<int:pk>/", views.computer_system_validation_detail, name="computer_system_validation_detail"),
    path("validation/computer-systems/<int:pk>/edit/", views.computer_system_validation_edit, name="computer_system_validation_edit"),
    path("validation/computer-systems/<int:pk>/delete/", views.computer_system_validation_delete, name="computer_system_validation_delete"),
]
