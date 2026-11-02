from django.urls import path
from apps.ecommerce.views.MobileCommerce import MobilePushCampaigns as views

urlpatterns = [
    path("mobile/push-campaigns/", views.mobilepushcampaign_list, name="mobilepushcampaign_list"),
    path("mobile/push-campaigns/new/", views.mobilepushcampaign_create, name="mobilepushcampaign_create"),
    path("mobile/push-campaigns/<int:pk>/", views.mobilepushcampaign_detail, name="mobilepushcampaign_detail"),
    path("mobile/push-campaigns/<int:pk>/edit/", views.mobilepushcampaign_edit, name="mobilepushcampaign_edit"),
    path("mobile/push-campaigns/<int:pk>/delete/", views.mobilepushcampaign_delete, name="mobilepushcampaign_delete"),
    path("mobile/push-campaigns/<int:pk>/test-send/", views.mobilepushcampaign_test_send, name="mobilepushcampaign_test_send"),
]
