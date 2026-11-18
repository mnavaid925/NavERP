from django.urls import path

from apps.quality.views.InProcessQuality import ProcessParameterLogs as views

urlpatterns = [
    path("process-parameter-logs/", views.process_parameter_log_list, name="process_parameter_log_list"),
    path("process-parameter-logs/create/", views.process_parameter_log_create, name="process_parameter_log_create"),
    path("process-parameter-logs/export/csv/", views.process_parameter_log_export_csv, name="process_parameter_log_export_csv"),
    path("process-parameter-logs/<int:pk>/", views.process_parameter_log_detail, name="process_parameter_log_detail"),
    path("process-parameter-logs/<int:pk>/edit/", views.process_parameter_log_edit, name="process_parameter_log_edit"),
    path("process-parameter-logs/<int:pk>/delete/", views.process_parameter_log_delete, name="process_parameter_log_delete"),
]
