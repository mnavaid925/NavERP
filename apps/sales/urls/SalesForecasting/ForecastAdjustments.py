from django.urls import path

from apps.sales.views.SalesForecasting.ForecastAdjustments import (
    forecast_adjustment_create,
    forecast_adjustment_delete,
    forecast_adjustment_detail,
    forecast_adjustment_edit,
    forecast_adjustment_export,
    forecast_adjustment_list,
    forecast_adjustment_revert,
)

# Literal routes first, `<int:pk>` last: Django resolves first-match-wins (package rule 6).
# `export/` and `add/` must stay ahead of `<int:pk>/`, or `?export/` would never resolve.
urlpatterns = [
    path("forecast/adjustments/", forecast_adjustment_list, name="forecast_adjustment_list"),
    path("forecast/adjustments/add/", forecast_adjustment_create, name="forecast_adjustment_create"),
    path("forecast/adjustments/export/", forecast_adjustment_export, name="forecast_adjustment_export"),
    path("forecast/adjustments/<int:pk>/revert/", forecast_adjustment_revert, name="forecast_adjustment_revert"),
    path("forecast/adjustments/<int:pk>/edit/", forecast_adjustment_edit, name="forecast_adjustment_edit"),
    path("forecast/adjustments/<int:pk>/delete/", forecast_adjustment_delete, name="forecast_adjustment_delete"),
    path("forecast/adjustments/<int:pk>/", forecast_adjustment_detail, name="forecast_adjustment_detail"),
]
