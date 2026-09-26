from django.urls import path

from apps.sales.views.SalesForecasting.ForecastSubmissions import (
    forecast_submission_approve,
    forecast_submission_create,
    forecast_submission_delete,
    forecast_submission_detail,
    forecast_submission_edit,
    forecast_submission_export,
    forecast_submission_list,
    forecast_submission_reject,
    forecast_submission_submit,
)

# Literal routes first, `<int:pk>` last: Django resolves first-match-wins (package rule 6).
# `forecast/` is a brand-new literal prefix — no existing sales route is a `<str:…>` catch-all.
urlpatterns = [
    path("forecast/submissions/", forecast_submission_list, name="forecast_submission_list"),
    path("forecast/submissions/add/", forecast_submission_create, name="forecast_submission_create"),
    path("forecast/submissions/export/", forecast_submission_export, name="forecast_submission_export"),
    path("forecast/submissions/<int:pk>/submit/", forecast_submission_submit, name="forecast_submission_submit"),
    path("forecast/submissions/<int:pk>/approve/", forecast_submission_approve, name="forecast_submission_approve"),
    path("forecast/submissions/<int:pk>/reject/", forecast_submission_reject, name="forecast_submission_reject"),
    path("forecast/submissions/<int:pk>/edit/", forecast_submission_edit, name="forecast_submission_edit"),
    path("forecast/submissions/<int:pk>/delete/", forecast_submission_delete, name="forecast_submission_delete"),
    path("forecast/submissions/<int:pk>/", forecast_submission_detail, name="forecast_submission_detail"),
]
