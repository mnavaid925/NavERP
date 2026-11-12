"""URL pattern for the Infrastructure Asset Management Board (11.17)."""

from django.urls import path

from apps.assets.views.SpaceFacilityAsset import InfrastructureBoard as views

urlpatterns = [
    path(
        "infrastructure-board/",
        views.asset_infrastructure_board,
        name="asset_infrastructure_board",
    ),
]
