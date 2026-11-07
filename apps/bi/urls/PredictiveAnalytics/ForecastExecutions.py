from django.urls import path

from apps.bi.views.PredictiveAnalytics import ForecastExecutions as views

urlpatterns = [
    path("forecast-executions/", views.forecast_execution_list, name="forecast_execution_list"),
    path("forecast-executions/create/", views.forecast_execution_create, name="forecast_execution_create"),
    path("forecast-executions/<int:pk>/", views.forecast_execution_detail, name="forecast_execution_detail"),
    path("forecast-executions/<int:pk>/edit/", views.forecast_execution_edit, name="forecast_execution_edit"),
    path("forecast-executions/<int:pk>/delete/", views.forecast_execution_delete, name="forecast_execution_delete"),
]
