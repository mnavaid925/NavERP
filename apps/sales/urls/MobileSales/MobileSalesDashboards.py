"""Sales 8.16 — MobileSalesDashboard URL patterns."""
from django.urls import path

from apps.sales.views.MobileSales import MobileSalesDashboards as views

urlpatterns = [
    path("mobile-sales-dashboard/", views.mobile_sales_dashboard, name="mobile_sales_dashboard"),
]
