from django.urls import path

from apps.assets.views.AssetProcurement.AssetRequisitions import (
    asset_requisition_approve,
    asset_requisition_create,
    asset_requisition_delete,
    asset_requisition_detail,
    asset_requisition_edit,
    asset_requisition_list,
    asset_requisition_reject,
    asset_requisition_submit,
)

urlpatterns = [
    path("requisitions/", asset_requisition_list, name="asset_requisition_list"),
    path("requisitions/create/", asset_requisition_create, name="asset_requisition_create"),
    path("requisitions/<int:pk>/", asset_requisition_detail, name="asset_requisition_detail"),
    path("requisitions/<int:pk>/edit/", asset_requisition_edit, name="asset_requisition_edit"),
    path("requisitions/<int:pk>/delete/", asset_requisition_delete, name="asset_requisition_delete"),
    path("requisitions/<int:pk>/submit/", asset_requisition_submit, name="asset_requisition_submit"),
    path("requisitions/<int:pk>/approve/", asset_requisition_approve, name="asset_requisition_approve"),
    path("requisitions/<int:pk>/reject/", asset_requisition_reject, name="asset_requisition_reject"),
]
