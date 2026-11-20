from django.urls import path

from apps.quality.views.TrainingCompetency import QualityTrainingCourses as views

urlpatterns = [
    path("training/courses/", views.training_course_list, name="training_course_list"),
    path("training/courses/create/", views.training_course_create, name="training_course_create"),
    path("training/courses/export/", views.training_course_export_csv, name="training_course_export_csv"),
    path("training/courses/<int:pk>/", views.training_course_detail, name="training_course_detail"),
    path("training/courses/<int:pk>/edit/", views.training_course_edit, name="training_course_edit"),
    path("training/courses/<int:pk>/delete/", views.training_course_delete, name="training_course_delete"),
    path("training/courses/<int:pk>/activate/", views.training_course_activate, name="training_course_activate"),
    path("training/courses/<int:pk>/retire/", views.training_course_retire, name="training_course_retire"),
]
