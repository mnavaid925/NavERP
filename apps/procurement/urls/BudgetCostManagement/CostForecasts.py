"""Procurement 6.15 Budget & Cost Management — CostForecast URL patterns.

One first segment, ``cost-forecasts/``, collision-checked as a whole component against the
concatenated ``urls/__init__.py`` inventory.

There is NO ``<int:pk>/edit/`` route, by design: a forecast is a frozen projection, and a wrong
one is deleted and re-frozen rather than amended in place — the same documented CRUD exemption
``SpendReportSnapshot`` carries. ``delete/`` is POST-only through the view's decorator; the list
and detail pages carry a ``{% csrf_token %}`` form with an ``onclick`` confirm instead.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("cost-forecasts/", views.costforecast_list, name="costforecast_list"),
    path("cost-forecasts/add/", views.costforecast_create, name="costforecast_create"),
    path("cost-forecasts/<int:pk>/", views.costforecast_detail, name="costforecast_detail"),
    path("cost-forecasts/<int:pk>/delete/", views.costforecast_delete,
         name="costforecast_delete"),
]
