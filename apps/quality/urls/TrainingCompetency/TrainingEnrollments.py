from django.urls import path

from apps.quality.views.TrainingCompetency import TrainingEnrollments as views

urlpatterns = [
    path("training/enrollments/", views.training_enrollment_list, name="training_enrollment_list"),
    path("training/enrollments/create/", views.training_enrollment_create, name="training_enrollment_create"),
    path("training/enrollments/export/", views.training_enrollment_export_csv, name="training_enrollment_export_csv"),
    path("training/enrollments/<int:pk>/", views.training_enrollment_detail, name="training_enrollment_detail"),
    path("training/enrollments/<int:pk>/edit/", views.training_enrollment_edit, name="training_enrollment_edit"),
    path("training/enrollments/<int:pk>/delete/", views.training_enrollment_delete, name="training_enrollment_delete"),
    path("training/enrollments/<int:pk>/complete/", views.training_enrollment_complete, name="training_enrollment_complete"),
    path("training/enrollments/<int:pk>/verify/", views.training_enrollment_verify, name="training_enrollment_verify"),
    path("training/enrollments/<int:pk>/waive/", views.training_enrollment_waive, name="training_enrollment_waive"),
]
