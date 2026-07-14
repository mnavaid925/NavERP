"""CRM 1.3 Marketing Automation — CampaignMembers URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    path("campaigns/<int:pk>/add-member/", views.campaignmember_add, name="campaignmember_add"),
    # Campaign members — target-list segmentation (1.3)
    path("campaign-members/", views.campaignmember_list, name="campaignmember_list"),
    path("campaign-members/add/", views.campaignmember_create, name="campaignmember_create"),
    path("campaign-members/<int:pk>/", views.campaignmember_detail, name="campaignmember_detail"),
    path("campaign-members/<int:pk>/edit/", views.campaignmember_edit, name="campaignmember_edit"),
    path("campaign-members/<int:pk>/delete/", views.campaignmember_delete, name="campaignmember_delete"),
    path("campaign-members/<int:member_pk>/remove/", views.campaignmember_remove, name="campaignmember_remove"),
]
