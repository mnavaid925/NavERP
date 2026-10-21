"""Sales 8.14 — URLs for `ChannelConflict`."""
from django.urls import path

from apps.sales.views.PartnerChannel import ChannelConflicts as views

urlpatterns = [
    path("partner-channel/conflicts/", views.channel_conflict_list, name="channel_conflict_list"),
    path("partner-channel/conflicts/new/", views.channel_conflict_create, name="channel_conflict_create"),
    path("partner-channel/conflicts/create/", views.channel_conflict_create),
    path("partner-channel/conflicts/<int:pk>/", views.channel_conflict_detail, name="channel_conflict_detail"),
    path("partner-channel/conflicts/<int:pk>/edit/", views.channel_conflict_edit, name="channel_conflict_edit"),
    path("partner-channel/conflicts/<int:pk>/delete/", views.channel_conflict_delete, name="channel_conflict_delete"),
]
