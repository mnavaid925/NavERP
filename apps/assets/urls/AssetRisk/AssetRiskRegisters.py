from django.urls import path

from apps.assets.views.AssetRisk import AssetRiskRegisters as views

urlpatterns = [
    path("risk/registers/", views.asset_risk_register_list, name="asset_risk_register_list"),
    path("risk/registers/create/", views.asset_risk_register_create, name="asset_risk_register_create"),
    path("risk/registers/<int:pk>/", views.asset_risk_register_detail, name="asset_risk_register_detail"),
    path("risk/registers/<int:pk>/edit/", views.asset_risk_register_edit, name="asset_risk_register_edit"),
    path("risk/registers/<int:pk>/delete/", views.asset_risk_register_delete, name="asset_risk_register_delete"),
    path("risk/registers/<int:pk>/assess/", views.asset_risk_register_assess, name="asset_risk_register_assess"),
    path("risk/registers/<int:pk>/close/", views.asset_risk_register_close, name="asset_risk_register_close"),
]
