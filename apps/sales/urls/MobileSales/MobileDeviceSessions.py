"""Sales 8.16 — MobileDeviceSession URL patterns."""
from django.urls import path

from apps.sales.views.MobileSales import MobileDeviceSessions as views

urlpatterns = [
    path("devices/", views.mobile_device_session_list, name="mobile_device_session_list"),
    path("devices/create/", views.mobile_device_session_create, name="mobile_device_session_create"),
    path("devices/<int:pk>/", views.mobile_device_session_detail, name="mobile_device_session_detail"),
    path("devices/<int:pk>/edit/", views.mobile_device_session_edit, name="mobile_device_session_edit"),
    path("devices/<int:pk>/delete/", views.mobile_device_session_delete, name="mobile_device_session_delete"),
    path("devices/<int:pk>/sync/", views.mobile_device_session_sync, name="mobile_device_session_sync"),
]
