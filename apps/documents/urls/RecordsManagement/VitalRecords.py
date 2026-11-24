from django.urls import path

from apps.documents.views.RecordsManagement import VitalRecords as views

urlpatterns = [
    path("records/vital-register/", views.vital_records_list, name="vital_records_list"),
]
