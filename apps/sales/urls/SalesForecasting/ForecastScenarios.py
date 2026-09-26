from django.urls import path

from apps.sales.views.SalesForecasting.ForecastScenarios import (
    forecast_scenario_apply,
    forecast_scenario_create,
    forecast_scenario_delete,
    forecast_scenario_detail,
    forecast_scenario_edit,
    forecast_scenario_list,
    forecast_scenario_select,
)

# Literal routes first, `<int:pk>` last: Django resolves first-match-wins (package rule 6).
# `add/` and `apply/` must stay ahead of `<int:pk>/`, or neither would ever resolve. There is
# deliberately NO export route -- scenarios ship no export action (contract 5.4 / 13.10).
urlpatterns = [
    path("forecast/scenarios/", forecast_scenario_list, name="forecast_scenario_list"),
    path("forecast/scenarios/add/", forecast_scenario_create, name="forecast_scenario_create"),
    path("forecast/scenarios/apply/", forecast_scenario_apply, name="forecast_scenario_apply"),
    path("forecast/scenarios/<int:pk>/select/", forecast_scenario_select, name="forecast_scenario_select"),
    path("forecast/scenarios/<int:pk>/edit/", forecast_scenario_edit, name="forecast_scenario_edit"),
    path("forecast/scenarios/<int:pk>/delete/", forecast_scenario_delete, name="forecast_scenario_delete"),
    path("forecast/scenarios/<int:pk>/", forecast_scenario_detail, name="forecast_scenario_detail"),
]
