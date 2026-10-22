"""Sales 8.15 — UsageMeterRecord URL patterns."""
from django.urls import path

from apps.sales.views.ContractSubscriptionManagement import UsageMeterRecords as views

urlpatterns = [
    path("usage-meters/", views.usage_meter_record_list, name="usage_meter_record_list"),
    path("usage-meters/create/", views.usage_meter_record_create, name="usage_meter_record_create"),
    path("usage-meters/<int:pk>/", views.usage_meter_record_detail, name="usage_meter_record_detail"),
    path("usage-meters/<int:pk>/edit/", views.usage_meter_record_edit, name="usage_meter_record_edit"),
    path("usage-meters/<int:pk>/delete/", views.usage_meter_record_delete, name="usage_meter_record_delete"),
    path("usage-meters/<int:pk>/calculate/", views.usage_meter_record_calculate, name="usage_meter_record_calculate"),
    path("usage-meters/<int:pk>/invoice/", views.usage_meter_record_invoice, name="usage_meter_record_invoice"),
]
