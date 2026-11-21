from django.urls import path

from apps.quality.views.ProcessValidation import ProcessCapabilityStudies as views

urlpatterns = [
    path("validation/capability-studies/", views.process_capability_study_list, name="process_capability_study_list"),
    path("validation/capability-studies/create/", views.process_capability_study_create, name="process_capability_study_create"),
    path("validation/capability-studies/export/", views.process_capability_study_export, name="process_capability_study_export"),
    path("validation/capability-studies/<int:pk>/", views.process_capability_study_detail, name="process_capability_study_detail"),
    path("validation/capability-studies/<int:pk>/edit/", views.process_capability_study_edit, name="process_capability_study_edit"),
    path("validation/capability-studies/<int:pk>/delete/", views.process_capability_study_delete, name="process_capability_study_delete"),
]
