"""URL pattern for Master Data Configuration Overview dashboard."""
from django.urls import path
from apps.sales.views.MasterDataConfiguration.Overview import master_data_overview

urlpatterns = [
    path("master-data/", master_data_overview, name="master_data_overview"),
]
