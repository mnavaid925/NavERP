from django.urls import path

from apps.assets.views.AssetRisk import AssetRiskMitigationActions as views

urlpatterns = [
    path("risk/mitigations/", views.asset_risk_mitigation_action_list, name="asset_risk_mitigation_action_list"),
    path("risk/mitigations/create/", views.asset_risk_mitigation_action_create, name="asset_risk_mitigation_action_create"),
    path("risk/mitigations/<int:pk>/", views.asset_risk_mitigation_action_detail, name="asset_risk_mitigation_action_detail"),
    path("risk/mitigations/<int:pk>/edit/", views.asset_risk_mitigation_action_edit, name="asset_risk_mitigation_action_edit"),
    path("risk/mitigations/<int:pk>/delete/", views.asset_risk_mitigation_action_delete, name="asset_risk_mitigation_action_delete"),
    path("risk/mitigations/<int:pk>/complete/", views.asset_risk_mitigation_action_complete, name="asset_risk_mitigation_action_complete"),
    path("risk/mitigations/<int:pk>/verify/", views.asset_risk_mitigation_action_verify, name="asset_risk_mitigation_action_verify"),
]
