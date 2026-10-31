from django.urls import path

from apps.ecommerce.views.MarketingCampaign import MarketingCampaigns as views

urlpatterns = [
    path("marketing/campaigns/", views.marketingcampaign_list, name="marketingcampaign_list"),
    path("marketing/campaigns/create/", views.marketingcampaign_create, name="marketingcampaign_create"),
    path("marketing/campaigns/<int:pk>/", views.marketingcampaign_detail, name="marketingcampaign_detail"),
    path("marketing/campaigns/<int:pk>/edit/", views.marketingcampaign_edit, name="marketingcampaign_edit"),
    path("marketing/campaigns/<int:pk>/delete/", views.marketingcampaign_delete, name="marketingcampaign_delete"),
    path("marketing/campaigns/<int:pk>/send/", views.marketingcampaign_send, name="marketingcampaign_send"),
]
