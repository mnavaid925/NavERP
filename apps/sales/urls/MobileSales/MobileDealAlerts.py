"""Sales 8.16 — MobileDealAlert URL patterns."""
from django.urls import path

from apps.sales.views.MobileSales import MobileDealAlerts as views

urlpatterns = [
    path("alerts/", views.mobile_deal_alert_list, name="mobile_deal_alert_list"),
    path("alerts/create/", views.mobile_deal_alert_create, name="mobile_deal_alert_create"),
    path("alerts/<int:pk>/", views.mobile_deal_alert_detail, name="mobile_deal_alert_detail"),
    path("alerts/<int:pk>/edit/", views.mobile_deal_alert_edit, name="mobile_deal_alert_edit"),
    path("alerts/<int:pk>/delete/", views.mobile_deal_alert_delete, name="mobile_deal_alert_delete"),
    path("alerts/<int:pk>/read/", views.mobile_deal_alert_mark_read, name="mobile_deal_alert_mark_read"),
]
