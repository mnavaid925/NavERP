from django.urls import path

from apps.assets.views.AssetProcurement.AssetAcquisitionReceipts import (
    asset_acquisition_receipt_create,
    asset_acquisition_receipt_delete,
    asset_acquisition_receipt_detail,
    asset_acquisition_receipt_edit,
    asset_acquisition_receipt_inspect,
    asset_acquisition_receipt_list,
    asset_acquisition_receipt_quarantine,
)

urlpatterns = [
    path("receipts/", asset_acquisition_receipt_list, name="asset_acquisition_receipt_list"),
    path("receipts/create/", asset_acquisition_receipt_create, name="asset_acquisition_receipt_create"),
    path("receipts/<int:pk>/", asset_acquisition_receipt_detail, name="asset_acquisition_receipt_detail"),
    path("receipts/<int:pk>/edit/", asset_acquisition_receipt_edit, name="asset_acquisition_receipt_edit"),
    path("receipts/<int:pk>/delete/", asset_acquisition_receipt_delete, name="asset_acquisition_receipt_delete"),
    path("receipts/<int:pk>/inspect/", asset_acquisition_receipt_inspect, name="asset_acquisition_receipt_inspect"),
    path("receipts/<int:pk>/quarantine/", asset_acquisition_receipt_quarantine, name="asset_acquisition_receipt_quarantine"),
]
