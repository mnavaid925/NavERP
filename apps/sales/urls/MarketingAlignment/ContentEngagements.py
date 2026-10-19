"""Sales 8.13 — URLs for `ContentEngagement`."""
from django.urls import path

from apps.sales.views.MarketingAlignment import ContentEngagements as views

urlpatterns = [
    path("marketing-alignment/content-engagements/", views.content_engagement_list, name="content_engagement_list"),
    path("marketing-alignment/content-engagements/create/", views.content_engagement_create, name="content_engagement_create"),
    path("marketing-alignment/content-engagements/<int:pk>/", views.content_engagement_detail, name="content_engagement_detail"),
    path("marketing-alignment/content-engagements/<int:pk>/edit/", views.content_engagement_edit, name="content_engagement_edit"),
    path("marketing-alignment/content-engagements/<int:pk>/delete/", views.content_engagement_delete, name="content_engagement_delete"),
]
