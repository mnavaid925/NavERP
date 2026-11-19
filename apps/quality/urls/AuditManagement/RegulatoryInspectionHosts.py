from django.urls import path

from apps.quality.views.AuditManagement.RegulatoryInspectionHosts import (
    regulatory_inspection_host_close,
    regulatory_inspection_host_create,
    regulatory_inspection_host_delete,
    regulatory_inspection_host_detail,
    regulatory_inspection_host_edit,
    regulatory_inspection_host_export_csv,
    regulatory_inspection_host_fulfill_request,
    regulatory_inspection_host_list,
    regulatory_inspection_host_log_request,
)

urlpatterns = [
    path("audits/inspections/", regulatory_inspection_host_list, name="regulatory_inspection_host_list"),
    path("audits/inspections/create/", regulatory_inspection_host_create, name="regulatory_inspection_host_create"),
    path("audits/inspections/export/", regulatory_inspection_host_export_csv, name="regulatory_inspection_host_export_csv"),
    path("audits/inspections/<int:pk>/", regulatory_inspection_host_detail, name="regulatory_inspection_host_detail"),
    path("audits/inspections/<int:pk>/edit/", regulatory_inspection_host_edit, name="regulatory_inspection_host_edit"),
    path("audits/inspections/<int:pk>/delete/", regulatory_inspection_host_delete, name="regulatory_inspection_host_delete"),
    path("audits/inspections/<int:pk>/log-request/", regulatory_inspection_host_log_request, name="regulatory_inspection_host_log_request"),
    path("audits/inspections/<int:pk>/fulfill-request/", regulatory_inspection_host_fulfill_request, name="regulatory_inspection_host_fulfill_request"),
    path("audits/inspections/<int:pk>/close/", regulatory_inspection_host_close, name="regulatory_inspection_host_close"),
]
