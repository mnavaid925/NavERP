from django.urls import path

from apps.bi.views.PredictiveAnalytics import StatisticalAnomalies as views

urlpatterns = [
    path("statistical-anomalies/", views.statistical_anomaly_list, name="statistical_anomaly_list"),
    path("statistical-anomalies/create/", views.statistical_anomaly_create, name="statistical_anomaly_create"),
    path("statistical-anomalies/<int:pk>/", views.statistical_anomaly_detail, name="statistical_anomaly_detail"),
    path("statistical-anomalies/<int:pk>/edit/", views.statistical_anomaly_edit, name="statistical_anomaly_edit"),
    path("statistical-anomalies/<int:pk>/delete/", views.statistical_anomaly_delete, name="statistical_anomaly_delete"),
    path("statistical-anomalies/<int:pk>/triage/", views.statistical_anomaly_triage, name="statistical_anomaly_triage"),
]
