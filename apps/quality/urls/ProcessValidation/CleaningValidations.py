from django.urls import path

from apps.quality.views.ProcessValidation import CleaningValidations as views

urlpatterns = [
    path("validation/cleaning/", views.cleaning_validation_list, name="cleaning_validation_list"),
    path("validation/cleaning/create/", views.cleaning_validation_create, name="cleaning_validation_create"),
    path("validation/cleaning/export/", views.cleaning_validation_export, name="cleaning_validation_export"),
    path("validation/cleaning/<int:pk>/", views.cleaning_validation_detail, name="cleaning_validation_detail"),
    path("validation/cleaning/<int:pk>/edit/", views.cleaning_validation_edit, name="cleaning_validation_edit"),
    path("validation/cleaning/<int:pk>/delete/", views.cleaning_validation_delete, name="cleaning_validation_delete"),
]
