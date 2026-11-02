from django.urls import path
from apps.ecommerce.views.FraudRisk import ChargebackDisputes as views

urlpatterns = [
    path("fraud-risk/disputes/", views.chargeback_dispute_list, name="chargeback_dispute_list"),
    path("fraud-risk/disputes/create/", views.chargeback_dispute_create, name="chargeback_dispute_create"),
    path("fraud-risk/disputes/<int:pk>/", views.chargeback_dispute_detail, name="chargeback_dispute_detail"),
    path("fraud-risk/disputes/<int:pk>/edit/", views.chargeback_dispute_edit, name="chargeback_dispute_edit"),
    path("fraud-risk/disputes/<int:pk>/delete/", views.chargeback_dispute_delete, name="chargeback_dispute_delete"),
]
