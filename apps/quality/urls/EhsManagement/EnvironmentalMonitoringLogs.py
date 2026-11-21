from django.urls import path

from apps.quality.views.EhsManagement import EnvironmentalMonitoringLogs as views

urlpatterns = [
    path("environmental-logs/", views.environmental_monitoring_log_list, name="environmental_monitoring_log_list"),
    path("environmental-logs/create/", views.environmental_monitoring_log_create, name="environmental_monitoring_log_create"),
    path("environmental-logs/export/", views.environmental_monitoring_log_export, name="environmental_monitoring_log_export"),
    path("environmental-logs/<int:pk>/", views.environmental_monitoring_log_detail, name="environmental_monitoring_log_detail"),
    path("environmental-logs/<int:pk>/edit/", views.environmental_monitoring_log_update, name="environmental_monitoring_log_update"),
    path("environmental-logs/<int:pk>/delete/", views.environmental_monitoring_log_delete, name="environmental_monitoring_log_delete"),
    path("environmental-logs/<int:pk>/evaluate/", views.environmental_monitoring_log_evaluate, name="environmental_monitoring_log_evaluate"),
]
