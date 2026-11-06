from django.urls import path

from apps.bi.views.OlapAnalysis import WhatIfScenarios as views

urlpatterns = [
    path("olap/scenarios/", views.what_if_scenario_list, name="what_if_scenario_list"),
    path("olap/scenarios/create/", views.what_if_scenario_create, name="what_if_scenario_create"),
    path("olap/scenarios/<int:pk>/", views.what_if_scenario_detail, name="what_if_scenario_detail"),
    path("olap/scenarios/<int:pk>/edit/", views.what_if_scenario_edit, name="what_if_scenario_edit"),
    path("olap/scenarios/<int:pk>/delete/", views.what_if_scenario_delete, name="what_if_scenario_delete"),
    path("olap/scenarios/<int:pk>/simulate/", views.what_if_scenario_simulate, name="what_if_scenario_simulate"),
    path("olap/scenarios/<int:pk>/commit/", views.what_if_scenario_commit, name="what_if_scenario_commit"),
]
