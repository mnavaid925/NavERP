from django.urls import path
from apps.documents.views.MetadataIndexing import MetadataIndexingDashboard as views

urlpatterns = [
    path("metadata-dashboard/", views.metadata_indexing_dashboard, name="metadata_indexing_dashboard"),
]
