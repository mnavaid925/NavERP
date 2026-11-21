from django.urls import path

from apps.quality.views.EhsManagement import WasteDisposalManifests as views

urlpatterns = [
    path("waste-manifests/", views.waste_disposal_manifest_list, name="waste_disposal_manifest_list"),
    path("waste-manifests/create/", views.waste_disposal_manifest_create, name="waste_disposal_manifest_create"),
    path("waste-manifests/export/", views.waste_disposal_manifest_export, name="waste_disposal_manifest_export"),
    path("waste-manifests/<int:pk>/", views.waste_disposal_manifest_detail, name="waste_disposal_manifest_detail"),
    path("waste-manifests/<int:pk>/edit/", views.waste_disposal_manifest_update, name="waste_disposal_manifest_update"),
    path("waste-manifests/<int:pk>/delete/", views.waste_disposal_manifest_delete, name="waste_disposal_manifest_delete"),
    path("waste-manifests/<int:pk>/certify/", views.waste_disposal_manifest_certify, name="waste_disposal_manifest_certify"),
]
