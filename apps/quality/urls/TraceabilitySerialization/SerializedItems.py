from django.urls import path

from apps.quality.views.TraceabilitySerialization import SerializedItems as views

urlpatterns = [
    path("traceability/serialized-items/", views.serialized_item_list, name="serialized_item_list"),
    path("traceability/serialized-items/create/", views.serialized_item_create, name="serialized_item_create"),
    path("traceability/serialized-items/<int:pk>/", views.serialized_item_detail, name="serialized_item_detail"),
    path("traceability/serialized-items/<int:pk>/edit/", views.serialized_item_edit, name="serialized_item_edit"),
    path("traceability/serialized-items/<int:pk>/delete/", views.serialized_item_delete, name="serialized_item_delete"),
]
