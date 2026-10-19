"""Sales 8.12 — URLs for `FunnelConversionRecord`."""
from django.urls import path

from apps.sales.views.SalesAnalytics import FunnelConversionRecords as views

urlpatterns = [
    path("sales-analytics/funnel-records/", views.funnel_conversion_record_list, name="funnel_conversion_record_list"),
    path("sales-analytics/funnel-records/create/", views.funnel_conversion_record_create, name="funnel_conversion_record_create"),
    path("sales-analytics/funnel-records/<int:pk>/", views.funnel_conversion_record_detail, name="funnel_conversion_record_detail"),
    path("sales-analytics/funnel-records/<int:pk>/edit/", views.funnel_conversion_record_edit, name="funnel_conversion_record_edit"),
    path("sales-analytics/funnel-records/<int:pk>/delete/", views.funnel_conversion_record_delete, name="funnel_conversion_record_delete"),
]
