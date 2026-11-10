from django.urls import path

from apps.assets.views.AssetWarrantyInsurance import AssetInsurancePolicies as views

urlpatterns = [
    path("warranty-insurance/policies/", views.asset_insurance_policy_list, name="asset_insurance_policy_list"),
    path("warranty-insurance/policies/create/", views.asset_insurance_policy_create, name="asset_insurance_policy_create"),
    path("warranty-insurance/policies/<int:pk>/", views.asset_insurance_policy_detail, name="asset_insurance_policy_detail"),
    path("warranty-insurance/policies/<int:pk>/edit/", views.asset_insurance_policy_edit, name="asset_insurance_policy_edit"),
    path("warranty-insurance/policies/<int:pk>/delete/", views.asset_insurance_policy_delete, name="asset_insurance_policy_delete"),
    path("warranty-insurance/policies/<int:pk>/activate/", views.asset_insurance_policy_activate, name="asset_insurance_policy_activate"),
    path("warranty-insurance/policies/<int:pk>/renew/", views.asset_insurance_policy_renew, name="asset_insurance_policy_renew"),
    path("warranty-insurance/policies/<int:pk>/cancel/", views.asset_insurance_policy_cancel, name="asset_insurance_policy_cancel"),
]
