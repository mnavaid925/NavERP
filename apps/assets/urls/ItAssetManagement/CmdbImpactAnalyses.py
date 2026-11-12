"""URL patterns for CMDB Impact Analysis Workbench (11.18)."""

from django.urls import path

from apps.assets.views.ItAssetManagement.CmdbImpactAnalyses import (
    cmdb_impact_analysis,
    cmdb_impact_analysis_export_csv,
)

urlpatterns = [
    path("cmdb/impact-analysis/", cmdb_impact_analysis, name="cmdb_impact_analysis"),
    path("cmdb/impact-analysis/export-csv/", cmdb_impact_analysis_export_csv, name="cmdb_impact_analysis_export_csv"),
]
