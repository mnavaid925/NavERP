from django.urls import path

from apps.quality.views.DesignControls import TraceabilityMatrix as views

urlpatterns = [
    path("design-controls/matrix/", views.traceability_matrix, name="traceability_matrix"),
    path("design-controls/matrix/export/", views.traceability_matrix_export, name="traceability_matrix_export"),
    path("design-controls/projects/<int:pk>/dhf/", views.design_project_dhf, name="design_project_dhf"),
    path("design-controls/projects/<int:pk>/dhf/export/", views.design_project_dhf_export, name="design_project_dhf_export"),
]
