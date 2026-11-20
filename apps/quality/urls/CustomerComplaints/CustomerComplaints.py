from django.urls import path

from apps.quality.views.CustomerComplaints import CustomerComplaints as views

urlpatterns = [
    path("complaints/", views.customer_complaint_list, name="customer_complaint_list"),
    path("complaints/create/", views.customer_complaint_create, name="customer_complaint_create"),
    path("complaints/export/csv/", views.customer_complaint_export_csv, name="customer_complaint_export_csv"),
    path("complaints/<int:pk>/", views.customer_complaint_detail, name="customer_complaint_detail"),
    path("complaints/<int:pk>/edit/", views.customer_complaint_edit, name="customer_complaint_edit"),
    path("complaints/<int:pk>/delete/", views.customer_complaint_delete, name="customer_complaint_delete"),
    path("complaints/<int:pk>/triage/", views.customer_complaint_triage, name="customer_complaint_triage"),
    path("complaints/<int:pk>/close/", views.customer_complaint_close, name="customer_complaint_close"),
]
