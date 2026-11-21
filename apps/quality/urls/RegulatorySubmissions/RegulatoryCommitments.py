from django.urls import path

from apps.quality.views.RegulatorySubmissions import RegulatoryCommitments as views

urlpatterns = [
    path("commitments/", views.regulatory_commitment_list, name="regulatory_commitment_list"),
    path("commitments/create/", views.regulatory_commitment_create, name="regulatory_commitment_create"),
    path("commitments/export/", views.regulatory_commitment_export, name="regulatory_commitment_export"),
    path("commitments/<int:pk>/", views.regulatory_commitment_detail, name="regulatory_commitment_detail"),
    path("commitments/<int:pk>/edit/", views.regulatory_commitment_edit, name="regulatory_commitment_edit"),
    path("commitments/<int:pk>/delete/", views.regulatory_commitment_delete, name="regulatory_commitment_delete"),
]
