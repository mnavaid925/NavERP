from django.urls import path
from apps.ecommerce.views.MobileCommerce import MobileDeviceRegistrations as views

urlpatterns = [
    path("mobile/devices/", views.mobiledeviceregistration_list, name="mobiledeviceregistration_list"),
    path("mobile/devices/new/", views.mobiledeviceregistration_create, name="mobiledeviceregistration_create"),
    path("mobile/devices/<int:pk>/", views.mobiledeviceregistration_detail, name="mobiledeviceregistration_detail"),
    path("mobile/devices/<int:pk>/edit/", views.mobiledeviceregistration_edit, name="mobiledeviceregistration_edit"),
    path("mobile/devices/<int:pk>/delete/", views.mobiledeviceregistration_delete, name="mobiledeviceregistration_delete"),
    path("mobile/devices/<int:pk>/ping/", views.mobiledeviceregistration_ping, name="mobiledeviceregistration_ping"),
]
