from django.urls import path

from apps.assets.views.AssetWarrantyInsurance import AssetWarrantyClaims as views

urlpatterns = [
    path("warranty-insurance/warranty-claims/", views.asset_warranty_claim_list, name="asset_warranty_claim_list"),
    path("warranty-insurance/warranty-claims/create/", views.asset_warranty_claim_create, name="asset_warranty_claim_create"),
    path("warranty-insurance/warranty-claims/<int:pk>/", views.asset_warranty_claim_detail, name="asset_warranty_claim_detail"),
    path("warranty-insurance/warranty-claims/<int:pk>/edit/", views.asset_warranty_claim_edit, name="asset_warranty_claim_edit"),
    path("warranty-insurance/warranty-claims/<int:pk>/delete/", views.asset_warranty_claim_delete, name="asset_warranty_claim_delete"),
    path("warranty-insurance/warranty-claims/<int:pk>/submit/", views.asset_warranty_claim_submit, name="asset_warranty_claim_submit"),
    path("warranty-insurance/warranty-claims/<int:pk>/review/", views.asset_warranty_claim_review, name="asset_warranty_claim_review"),
    path("warranty-insurance/warranty-claims/<int:pk>/settle/", views.asset_warranty_claim_settle, name="asset_warranty_claim_settle"),
    path("warranty-insurance/warranty-claims/<int:pk>/reject/", views.asset_warranty_claim_reject, name="asset_warranty_claim_reject"),
]
