"""Sales 8.16 — FieldCheckIn URL patterns."""
from django.urls import path

from apps.sales.views.MobileSales import FieldCheckIns as views

urlpatterns = [
    path("check-ins/", views.field_check_in_list, name="field_check_in_list"),
    path("check-ins/create/", views.field_check_in_create, name="field_check_in_create"),
    path("check-ins/<int:pk>/", views.field_check_in_detail, name="field_check_in_detail"),
    path("check-ins/<int:pk>/edit/", views.field_check_in_edit, name="field_check_in_edit"),
    path("check-ins/<int:pk>/delete/", views.field_check_in_delete, name="field_check_in_delete"),
    path("check-ins/<int:pk>/checkout/", views.field_check_in_checkout, name="field_check_in_checkout"),
]
