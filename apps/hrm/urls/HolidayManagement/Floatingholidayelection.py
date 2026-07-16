"""HRM 3.12 Holiday Management — Floatingholidayelection URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Floating Holiday Elections (3.12)
    path("floating-holidays/", views.floatingholidayelection_list, name="floatingholidayelection_list"),
    path("floating-holidays/add/", views.floatingholidayelection_create, name="floatingholidayelection_create"),
    path("floating-holidays/<int:pk>/", views.floatingholidayelection_detail, name="floatingholidayelection_detail"),
    path("floating-holidays/<int:pk>/edit/", views.floatingholidayelection_edit, name="floatingholidayelection_edit"),
    path("floating-holidays/<int:pk>/delete/", views.floatingholidayelection_delete, name="floatingholidayelection_delete"),
    path("floating-holidays/<int:pk>/approve/", views.floatingholidayelection_approve, name="floatingholidayelection_approve"),
    path("floating-holidays/<int:pk>/reject/", views.floatingholidayelection_reject, name="floatingholidayelection_reject"),
]
