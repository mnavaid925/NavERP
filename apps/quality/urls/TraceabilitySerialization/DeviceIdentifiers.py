from django.urls import path

from apps.quality.views.TraceabilitySerialization import DeviceIdentifiers as views

urlpatterns = [
    path("traceability/udi/", views.device_identifier_list, name="device_identifier_list"),
    path("traceability/udi/create/", views.device_identifier_create, name="device_identifier_create"),
    path("traceability/udi/<int:pk>/", views.device_identifier_detail, name="device_identifier_detail"),
    path("traceability/udi/<int:pk>/edit/", views.device_identifier_edit, name="device_identifier_edit"),
    path("traceability/udi/<int:pk>/delete/", views.device_identifier_delete, name="device_identifier_delete"),
]
