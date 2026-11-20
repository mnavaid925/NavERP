from django.urls import path

from apps.quality.views.TrainingCompetency import CompetencyMatrices as views

urlpatterns = [
    path("training/matrices/", views.competency_matrix_list, name="competency_matrix_list"),
    path("training/matrices/create/", views.competency_matrix_create, name="competency_matrix_create"),
    path("training/matrices/export/", views.competency_matrix_export_csv, name="competency_matrix_export_csv"),
    path("training/matrices/<int:pk>/", views.competency_matrix_detail, name="competency_matrix_detail"),
    path("training/matrices/<int:pk>/edit/", views.competency_matrix_edit, name="competency_matrix_edit"),
    path("training/matrices/<int:pk>/delete/", views.competency_matrix_delete, name="competency_matrix_delete"),
    path("training/matrices/<int:pk>/approve/", views.competency_matrix_approve, name="competency_matrix_approve"),
    path("training/matrices/<int:pk>/retire/", views.competency_matrix_retire, name="competency_matrix_retire"),
]
