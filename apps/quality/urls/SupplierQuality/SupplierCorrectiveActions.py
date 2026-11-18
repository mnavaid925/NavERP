from django.urls import path

from apps.quality.views.SupplierQuality import SupplierCorrectiveActions as views

urlpatterns = [
    path("scars/", views.supplier_corrective_action_list, name="supplier_corrective_action_list"),
    path("scars/create/", views.supplier_corrective_action_create, name="supplier_corrective_action_create"),
    path("scars/export/", views.supplier_corrective_action_export, name="supplier_corrective_action_export"),
    path("scars/<int:pk>/", views.supplier_corrective_action_detail, name="supplier_corrective_action_detail"),
    path("scars/<int:pk>/edit/", views.supplier_corrective_action_edit, name="supplier_corrective_action_edit"),
    path("scars/<int:pk>/delete/", views.supplier_corrective_action_delete, name="supplier_corrective_action_delete"),
    path("scars/<int:pk>/status/", views.supplier_corrective_action_status, name="supplier_corrective_action_status"),
]
