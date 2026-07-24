"""SCM 4.7 Demand Planning — computed report routes (``safety-stock/``, ``forecast-accuracy/``).

``safety-stock/recalculate/`` is literal and MUST precede ``safety-stock/<int:pk>/apply/`` — the pk
route is narrower here (it has a trailing segment) but keeping literals first is the rule that stops
the next added route from silently shadowing it.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("safety-stock/", views.safety_stock_report, name="safety_stock_report"),
    path("safety-stock/recalculate/", views.safety_stock_recalculate,
         name="safety_stock_recalculate"),
    path("safety-stock/<int:pk>/apply/", views.safety_stock_apply, name="safety_stock_apply"),
    path("forecast-accuracy/", views.forecast_accuracy_report, name="forecast_accuracy_report"),
]
