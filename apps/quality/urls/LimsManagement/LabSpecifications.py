from django.urls import path

from apps.quality.views.LimsManagement import LabSpecifications as views

urlpatterns = [
    path("lims/specifications/", views.lab_specification_list, name="lab_specification_list"),
    path("lims/specifications/create/", views.lab_specification_create, name="lab_specification_create"),
    path("lims/specifications/<int:pk>/", views.lab_specification_detail, name="lab_specification_detail"),
    path("lims/specifications/<int:pk>/edit/", views.lab_specification_edit, name="lab_specification_edit"),
    path("lims/specifications/<int:pk>/delete/", views.lab_specification_delete, name="lab_specification_delete"),
]
