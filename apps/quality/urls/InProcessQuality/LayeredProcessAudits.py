from django.urls import path

from apps.quality.views.InProcessQuality import LayeredProcessAudits as views

urlpatterns = [
    path("layered-process-audits/", views.layered_process_audit_list, name="layered_process_audit_list"),
    path("layered-process-audits/create/", views.layered_process_audit_create, name="layered_process_audit_create"),
    path("layered-process-audits/export/csv/", views.layered_process_audit_export_csv, name="layered_process_audit_export_csv"),
    path("layered-process-audits/<int:pk>/", views.layered_process_audit_detail, name="layered_process_audit_detail"),
    path("layered-process-audits/<int:pk>/edit/", views.layered_process_audit_edit, name="layered_process_audit_edit"),
    path("layered-process-audits/<int:pk>/delete/", views.layered_process_audit_delete, name="layered_process_audit_delete"),
]
