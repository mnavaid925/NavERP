from django.urls import path
from apps.ecommerce.views.FraudRisk import FraudRules as views

urlpatterns = [
    path("fraud-risk/", views.fraud_risk_hub, name="fraud_risk_hub"),
    path("fraud-risk/rules/", views.fraud_rule_list, name="fraud_rule_list"),
    path("fraud-risk/rules/create/", views.fraud_rule_create, name="fraud_rule_create"),
    path("fraud-risk/rules/<int:pk>/", views.fraud_rule_detail, name="fraud_rule_detail"),
    path("fraud-risk/rules/<int:pk>/edit/", views.fraud_rule_edit, name="fraud_rule_edit"),
    path("fraud-risk/rules/<int:pk>/delete/", views.fraud_rule_delete, name="fraud_rule_delete"),
]
