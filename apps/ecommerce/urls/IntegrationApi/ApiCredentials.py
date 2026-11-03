from django.urls import path
from apps.ecommerce.views.IntegrationApi import ApiCredentials as views

urlpatterns = [
    path("integration-api/api-credentials/", views.api_credential_list, name="apicredential_list"),
    path("integration-api/api-credentials/create/", views.api_credential_create, name="apicredential_create"),
    path("integration-api/api-credentials/<int:pk>/", views.api_credential_detail, name="apicredential_detail"),
    path("integration-api/api-credentials/<int:pk>/edit/", views.api_credential_edit, name="apicredential_edit"),
    path("integration-api/api-credentials/<int:pk>/delete/", views.api_credential_delete, name="apicredential_delete"),
    path("integration-api/api-credentials/<int:pk>/revoke/", views.api_credential_revoke, name="apicredential_revoke"),
]
