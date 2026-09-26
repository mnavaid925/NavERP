from django.urls import path

from apps.sales.views.SalesForecasting.ForecastPeriods import (
    forecast_period_create,
    forecast_period_delete,
    forecast_period_detail,
    forecast_period_edit,
    forecast_period_export,
    forecast_period_list,
    forecast_period_lock,
    forecast_period_unlock,
)

# Literal routes first, `<int:pk>` last: Django resolves first-match-wins (package rule 6).
urlpatterns = [
    path("forecast/periods/", forecast_period_list, name="forecast_period_list"),
    path("forecast/periods/add/", forecast_period_create, name="forecast_period_create"),
    path("forecast/periods/export/", forecast_period_export, name="forecast_period_export"),
    path("forecast/periods/<int:pk>/lock/", forecast_period_lock, name="forecast_period_lock"),
    path("forecast/periods/<int:pk>/unlock/", forecast_period_unlock, name="forecast_period_unlock"),
    path("forecast/periods/<int:pk>/edit/", forecast_period_edit, name="forecast_period_edit"),
    path("forecast/periods/<int:pk>/delete/", forecast_period_delete, name="forecast_period_delete"),
    path("forecast/periods/<int:pk>/", forecast_period_detail, name="forecast_period_detail"),
]
