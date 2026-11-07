from django.urls import path

from apps.bi.views.PredictiveAnalytics import OptimizationScenarios as views

urlpatterns = [
    path("optimization-scenarios/", views.optimization_scenario_list, name="optimization_scenario_list"),
    path("optimization-scenarios/create/", views.optimization_scenario_create, name="optimization_scenario_create"),
    path("optimization-scenarios/<int:pk>/", views.optimization_scenario_detail, name="optimization_scenario_detail"),
    path("optimization-scenarios/<int:pk>/edit/", views.optimization_scenario_edit, name="optimization_scenario_edit"),
    path("optimization-scenarios/<int:pk>/delete/", views.optimization_scenario_delete, name="optimization_scenario_delete"),
    path("optimization-scenarios/<int:pk>/solve/", views.optimization_scenario_solve, name="optimization_scenario_solve"),
]
