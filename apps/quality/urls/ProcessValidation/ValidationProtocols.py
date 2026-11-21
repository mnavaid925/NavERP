from django.urls import path

from apps.quality.views.ProcessValidation import ValidationProtocols as views

urlpatterns = [
    path("validation/protocols/", views.validation_protocol_list, name="validation_protocol_list"),
    path("validation/protocols/create/", views.validation_protocol_create, name="validation_protocol_create"),
    path("validation/protocols/export/", views.validation_protocol_export, name="validation_protocol_export"),
    path("validation/protocols/<int:pk>/", views.validation_protocol_detail, name="validation_protocol_detail"),
    path("validation/protocols/<int:pk>/edit/", views.validation_protocol_edit, name="validation_protocol_edit"),
    path("validation/protocols/<int:pk>/delete/", views.validation_protocol_delete, name="validation_protocol_delete"),
]
