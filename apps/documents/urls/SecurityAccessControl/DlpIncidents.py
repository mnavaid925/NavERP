from django.urls import path

from apps.documents.views.SecurityAccessControl.DlpIncidents import (
    dlp_incident_detail,
    dlp_incident_list,
    dlp_incident_resolve,
)

urlpatterns = [
    path("dlp-incidents/", dlp_incident_list, name="dlp_incident_list"),
    path("dlp-incidents/<int:pk>/", dlp_incident_detail, name="dlp_incident_detail"),
    path("dlp-incidents/<int:pk>/resolve/", dlp_incident_resolve, name="dlp_incident_resolve"),
]
