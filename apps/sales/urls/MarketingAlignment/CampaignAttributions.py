"""Sales 8.13 — URLs for `CampaignAttribution`."""
from django.urls import path

from apps.sales.views.MarketingAlignment import CampaignAttributions as views

urlpatterns = [
    path("marketing-alignment/attributions/", views.campaign_attribution_list, name="campaign_attribution_list"),
    path("marketing-alignment/attributions/create/", views.campaign_attribution_create, name="campaign_attribution_create"),
    path("marketing-alignment/attributions/<int:pk>/", views.campaign_attribution_detail, name="campaign_attribution_detail"),
    path("marketing-alignment/attributions/<int:pk>/edit/", views.campaign_attribution_edit, name="campaign_attribution_edit"),
    path("marketing-alignment/attributions/<int:pk>/delete/", views.campaign_attribution_delete, name="campaign_attribution_delete"),
]
