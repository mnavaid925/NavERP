"""CRM 1.3 Marketing Automation — EmailCampaigns URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Email campaigns / blasts (1.3 Email Marketing — drip + A/B + tracking)
    path("email-campaigns/", views.emailcampaign_list, name="emailcampaign_list"),
    path("email-campaigns/add/", views.emailcampaign_create, name="emailcampaign_create"),
    path("email-campaigns/<int:pk>/", views.emailcampaign_detail, name="emailcampaign_detail"),
    path("email-campaigns/<int:pk>/edit/", views.emailcampaign_edit, name="emailcampaign_edit"),
    path("email-campaigns/<int:pk>/delete/", views.emailcampaign_delete, name="emailcampaign_delete"),
    path("email-campaigns/<int:pk>/send/", views.emailcampaign_send, name="emailcampaign_send"),
]
