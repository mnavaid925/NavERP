"""Inventory ThirdPartyIntegrations URL patterns package (Sub-module 5.19)."""
from .IntegrationChannels import urlpatterns as _tpi_channels
from .ChannelListingMaps import urlpatterns as _tpi_listings
from .StockSyncRuns import urlpatterns as _tpi_runs
from .ApiClients import urlpatterns as _tpi_apiclients

urlpatterns = [
    *_tpi_channels,
    *_tpi_listings,
    *_tpi_runs,
    *_tpi_apiclients,
]
