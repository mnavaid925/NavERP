"""SCM 4.7 Demand Planning — DemandForecast routes (prefix ``forecasts/``).

``forecasts/add/`` is literal and MUST stay above ``forecasts/<int:pk>/`` — Django is
first-match-wins. The prefix is distinct from 4.1's ``orders/`` and 4.5's ``sales-orders/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("forecasts/", views.demandforecast_list, name="demandforecast_list"),
    path("forecasts/add/", views.demandforecast_create, name="demandforecast_create"),
    path("forecasts/<int:pk>/", views.demandforecast_detail, name="demandforecast_detail"),
    path("forecasts/<int:pk>/edit/", views.demandforecast_edit, name="demandforecast_edit"),
    path("forecasts/<int:pk>/delete/", views.demandforecast_delete, name="demandforecast_delete"),
    path("forecasts/<int:pk>/generate/", views.demandforecast_generate,
         name="demandforecast_generate"),
    path("forecasts/<int:pk>/submit-review/", views.demandforecast_submit_review,
         name="demandforecast_submit_review"),
    path("forecasts/<int:pk>/approve/", views.demandforecast_approve, name="demandforecast_approve"),
    path("forecasts/<int:pk>/archive/", views.demandforecast_archive, name="demandforecast_archive"),
    path("forecasts/<int:pk>/revise/", views.demandforecast_revise, name="demandforecast_revise"),
]
