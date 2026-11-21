from django.urls import path

from apps.quality.views.ProcessValidation import ProcessValidationDashboard as views

urlpatterns = [
    path("validation/dashboard/", views.process_validation_dashboard, name="process_validation_dashboard"),
]
