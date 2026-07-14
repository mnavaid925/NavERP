"""CRM 1.9 Document & Contract Management — DocumentVersions URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    path("document-versions/<int:pk>/", views.documentversion_detail, name="documentversion_detail"),
    path("document-repository/", views.document_repository, name="document_repository"),
]
