"""URL pattern for Master Data Configuration Overview dashboard."""
from django.urls import path
from apps.sales.views.MasterDataConfiguration import Overview as views

urlpatterns = [
    path("master-data/", views.master_data_overview, name="master_data_overview"),
]
