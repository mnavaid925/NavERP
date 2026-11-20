from django.urls import path

from apps.quality.views.CustomerComplaints import ComplaintInvestigations as views

urlpatterns = [
    path("investigations/", views.complaint_investigation_list, name="complaint_investigation_list"),
    path("investigations/create/", views.complaint_investigation_create, name="complaint_investigation_create"),
    path("investigations/export/csv/", views.complaint_investigation_export_csv, name="complaint_investigation_export_csv"),
    path("investigations/<int:pk>/", views.complaint_investigation_detail, name="complaint_investigation_detail"),
    path("investigations/<int:pk>/edit/", views.complaint_investigation_edit, name="complaint_investigation_edit"),
    path("investigations/<int:pk>/delete/", views.complaint_investigation_delete, name="complaint_investigation_delete"),
    path("investigations/<int:pk>/complete/", views.complaint_investigation_complete, name="complaint_investigation_complete"),
]
