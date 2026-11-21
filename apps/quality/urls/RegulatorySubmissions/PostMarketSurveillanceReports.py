from django.urls import path

from apps.quality.views.RegulatorySubmissions import PostMarketSurveillanceReports as views

urlpatterns = [
    path("pms-reports/", views.post_market_surveillance_report_list, name="post_market_surveillance_report_list"),
    path("pms-reports/create/", views.post_market_surveillance_report_create, name="post_market_surveillance_report_create"),
    path("pms-reports/export/", views.post_market_surveillance_report_export, name="post_market_surveillance_report_export"),
    path("pms-reports/<int:pk>/", views.post_market_surveillance_report_detail, name="post_market_surveillance_report_detail"),
    path("pms-reports/<int:pk>/edit/", views.post_market_surveillance_report_edit, name="post_market_surveillance_report_edit"),
    path("pms-reports/<int:pk>/delete/", views.post_market_surveillance_report_delete, name="post_market_surveillance_report_delete"),
]
