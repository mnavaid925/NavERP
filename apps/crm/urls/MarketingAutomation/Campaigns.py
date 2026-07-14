"""CRM 1.3 Marketing Automation — Campaigns URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Campaigns (1.3 Campaign Management)
    path("campaigns/", views.campaign_list, name="campaign_list"),
    path("campaigns/add/", views.campaign_create, name="campaign_create"),
    path("campaigns/<int:pk>/", views.campaign_detail, name="campaign_detail"),
    path("campaigns/<int:pk>/edit/", views.campaign_edit, name="campaign_edit"),
    path("campaigns/<int:pk>/delete/", views.campaign_delete, name="campaign_delete"),
]
