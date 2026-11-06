from django.urls import path

from apps.bi.views.PerformanceScorecards import StrategicObjectives as views

urlpatterns = [
    path("objectives/", views.strategic_objective_list, name="strategic_objective_list"),
    path("objectives/create/", views.strategic_objective_create, name="strategic_objective_create"),
    path("objectives/<int:pk>/", views.strategic_objective_detail, name="strategic_objective_detail"),
    path("objectives/<int:pk>/edit/", views.strategic_objective_edit, name="strategic_objective_edit"),
    path("objectives/<int:pk>/delete/", views.strategic_objective_delete, name="strategic_objective_delete"),
]
