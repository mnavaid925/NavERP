from django.urls import path

from apps.quality.views.DesignControls import DesignInputs as views

urlpatterns = [
    path("design-controls/inputs/", views.design_input_list, name="design_input_list"),
    path("design-controls/inputs/export/", views.design_input_export, name="design_input_export"),
    path("design-controls/inputs/create/", views.design_input_create, name="design_input_create"),
    path("design-controls/inputs/<int:pk>/", views.design_input_detail, name="design_input_detail"),
    path("design-controls/inputs/<int:pk>/edit/", views.design_input_edit, name="design_input_edit"),
    path("design-controls/inputs/<int:pk>/delete/", views.design_input_delete, name="design_input_delete"),
]
