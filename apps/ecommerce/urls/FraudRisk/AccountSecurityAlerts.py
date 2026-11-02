from django.urls import path
from apps.ecommerce.views.FraudRisk import AccountSecurityAlerts as views

urlpatterns = [
    path("fraud-risk/alerts/", views.account_security_alert_list, name="account_security_alert_list"),
    path("fraud-risk/alerts/create/", views.account_security_alert_create, name="account_security_alert_create"),
    path("fraud-risk/alerts/<int:pk>/", views.account_security_alert_detail, name="account_security_alert_detail"),
    path("fraud-risk/alerts/<int:pk>/edit/", views.account_security_alert_edit, name="account_security_alert_edit"),
    path("fraud-risk/alerts/<int:pk>/delete/", views.account_security_alert_delete, name="account_security_alert_delete"),
]
