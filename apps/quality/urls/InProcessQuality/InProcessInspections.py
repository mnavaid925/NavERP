from django.urls import path

from apps.quality.views.InProcessQuality import InProcessInspections as views

urlpatterns = [
    path("in-process-inspections/", views.in_process_inspection_list, name="in_process_inspection_list"),
    path("in-process-inspections/create/", views.in_process_inspection_create, name="in_process_inspection_create"),
    path("in-process-inspections/export/csv/", views.in_process_inspection_export_csv, name="in_process_inspection_export_csv"),
    path("in-process-inspections/<int:pk>/", views.in_process_inspection_detail, name="in_process_inspection_detail"),
    path("in-process-inspections/<int:pk>/edit/", views.in_process_inspection_edit, name="in_process_inspection_edit"),
    path("in-process-inspections/<int:pk>/delete/", views.in_process_inspection_delete, name="in_process_inspection_delete"),
]
