from django.urls import path

from apps.quality.views.EhsManagement import HazardousMaterials as views

urlpatterns = [
    path("hazardous-materials/", views.hazardous_material_list, name="hazardous_material_list"),
    path("hazardous-materials/create/", views.hazardous_material_create, name="hazardous_material_create"),
    path("hazardous-materials/export/", views.hazardous_material_export, name="hazardous_material_export"),
    path("hazardous-materials/<int:pk>/", views.hazardous_material_detail, name="hazardous_material_detail"),
    path("hazardous-materials/<int:pk>/edit/", views.hazardous_material_update, name="hazardous_material_update"),
    path("hazardous-materials/<int:pk>/delete/", views.hazardous_material_delete, name="hazardous_material_delete"),
    path("hazardous-materials/<int:pk>/label/", views.hazardous_material_label, name="hazardous_material_label"),
]
