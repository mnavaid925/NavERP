from django.urls import path

from apps.sales import views

urlpatterns = [
    path("enrichment-events/", views.party_enrichment_list, name="party_enrichment_list"),
    path("enrichment-events/request/", views.party_enrichment_request, name="party_enrichment_request"),
    path("enrichment-events/export/", views.party_enrichment_export, name="party_enrichment_export"),
    path("enrichment-events/<int:pk>/", views.party_enrichment_detail, name="party_enrichment_detail"),
    path("enrichment-events/<int:pk>/apply/", views.party_enrichment_apply, name="party_enrichment_apply"),
    path("enrichment-events/<int:pk>/reject/", views.party_enrichment_reject, name="party_enrichment_reject"),
]
