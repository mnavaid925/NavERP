"""SCM 4.7 Demand Planning — ForecastAdjustment routes (prefix ``forecast-adjustments/``).

A distinct prefix from ``forecasts/`` — ``forecast-adjustments/`` cannot be matched by
``forecasts/<int:pk>/`` (different first segment), so ordering between the two modules is free.
Literal routes still come before ``<int:pk>/`` within this module.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("forecast-adjustments/", views.forecastadjustment_list, name="forecastadjustment_list"),
    path("forecast-adjustments/add/", views.forecastadjustment_create,
         name="forecastadjustment_create"),
    path("forecast-adjustments/<int:pk>/", views.forecastadjustment_detail,
         name="forecastadjustment_detail"),
    path("forecast-adjustments/<int:pk>/edit/", views.forecastadjustment_edit,
         name="forecastadjustment_edit"),
    path("forecast-adjustments/<int:pk>/delete/", views.forecastadjustment_delete,
         name="forecastadjustment_delete"),
    path("forecast-adjustments/<int:pk>/accept/", views.forecastadjustment_accept,
         name="forecastadjustment_accept"),
    path("forecast-adjustments/<int:pk>/reject/", views.forecastadjustment_reject,
         name="forecastadjustment_reject"),
]
