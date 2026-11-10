from django.urls import path

from apps.assets.views.AssetWarrantyInsurance import AssetInsuranceClaims as views

urlpatterns = [
    path("warranty-insurance/insurance-claims/", views.asset_insurance_claim_list, name="asset_insurance_claim_list"),
    path("warranty-insurance/insurance-claims/create/", views.asset_insurance_claim_create, name="asset_insurance_claim_create"),
    path("warranty-insurance/insurance-claims/<int:pk>/", views.asset_insurance_claim_detail, name="asset_insurance_claim_detail"),
    path("warranty-insurance/insurance-claims/<int:pk>/edit/", views.asset_insurance_claim_edit, name="asset_insurance_claim_edit"),
    path("warranty-insurance/insurance-claims/<int:pk>/delete/", views.asset_insurance_claim_delete, name="asset_insurance_claim_delete"),
    path("warranty-insurance/insurance-claims/<int:pk>/assign-adjuster/", views.asset_insurance_claim_assign_adjuster, name="asset_insurance_claim_assign_adjuster"),
    path("warranty-insurance/insurance-claims/<int:pk>/file-proof/", views.asset_insurance_claim_file_proof, name="asset_insurance_claim_file_proof"),
    path("warranty-insurance/insurance-claims/<int:pk>/settle/", views.asset_insurance_claim_settle, name="asset_insurance_claim_settle"),
    path("warranty-insurance/insurance-claims/<int:pk>/deny/", views.asset_insurance_claim_deny, name="asset_insurance_claim_deny"),
]
