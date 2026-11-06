from django.urls import path

from apps.bi.views.PerformanceScorecards import ScorecardKpiAssignments as views

urlpatterns = [
    path("assignments/", views.scorecard_kpi_assignment_list, name="scorecard_kpi_assignment_list"),
    path("assignments/create/", views.scorecard_kpi_assignment_create, name="scorecard_kpi_assignment_create"),
    path("assignments/<int:pk>/", views.scorecard_kpi_assignment_detail, name="scorecard_kpi_assignment_detail"),
    path("assignments/<int:pk>/edit/", views.scorecard_kpi_assignment_edit, name="scorecard_kpi_assignment_edit"),
    path("assignments/<int:pk>/delete/", views.scorecard_kpi_assignment_delete, name="scorecard_kpi_assignment_delete"),
    path("assignments/<int:pk>/record-actual/", views.scorecard_kpi_assignment_record_actual, name="scorecard_kpi_assignment_record_actual"),
]
