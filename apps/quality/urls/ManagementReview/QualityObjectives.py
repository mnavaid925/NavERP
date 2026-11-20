from django.urls import path

from apps.quality.views.ManagementReview import QualityObjectives as views

urlpatterns = [
    path("objectives/", views.quality_objective_list, name="quality_objective_list"),
    path("objectives/create/", views.quality_objective_create, name="quality_objective_create"),
    path("objectives/export/csv/", views.quality_objective_export_csv, name="quality_objective_export_csv"),
    path("objectives/<int:pk>/", views.quality_objective_detail, name="quality_objective_detail"),
    path("objectives/<int:pk>/edit/", views.quality_objective_edit, name="quality_objective_edit"),
    path("objectives/<int:pk>/delete/", views.quality_objective_delete, name="quality_objective_delete"),
    path("objectives/<int:pk>/evaluate/", views.quality_objective_evaluate, name="quality_objective_evaluate"),
]
