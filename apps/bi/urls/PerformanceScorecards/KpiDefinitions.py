from django.urls import path

from apps.bi.views.PerformanceScorecards import KpiDefinitions as views

urlpatterns = [
    path("kpis/", views.kpi_definition_list, name="kpi_definition_list"),
    path("kpis/create/", views.kpi_definition_create, name="kpi_definition_create"),
    path("kpis/<int:pk>/", views.kpi_definition_detail, name="kpi_definition_detail"),
    path("kpis/<int:pk>/edit/", views.kpi_definition_edit, name="kpi_definition_edit"),
    path("kpis/<int:pk>/delete/", views.kpi_definition_delete, name="kpi_definition_delete"),
    path("kpis/<int:pk>/refresh/", views.kpi_definition_refresh, name="kpi_definition_refresh"),
]
