"""Projects 7.19 — ConfigurationHub URLs."""
from django.urls import path

from apps.projects.views.MasterDataConfiguration import ConfigurationHub as views

urlpatterns = [
    path("master-data/hub/", views.configuration_hub, name="configuration_hub"),
]
