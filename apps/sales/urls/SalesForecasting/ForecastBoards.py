from django.urls import path

from apps.sales.views.SalesForecasting.ForecastBoards import (
    forecast_accuracy,
    forecast_attainment,
    forecast_board,
    forecast_call,
)

#: The four derived reports. No `<int:pk>` route lives here, so there is nothing
#: to shadow and nothing for a greedy sibling to collide with (package rule 6).
urlpatterns = [
    path("forecast/board/", forecast_board, name="forecast_board"),
    path("forecast/attainment/", forecast_attainment, name="forecast_attainment"),
    path("forecast/accuracy/", forecast_accuracy, name="forecast_accuracy"),
    path("forecast/call/", forecast_call, name="forecast_call"),
]