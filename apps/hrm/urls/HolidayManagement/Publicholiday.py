"""HRM 3.12 Holiday Management — Publicholiday URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Public Holidays (3.12)
    path("holidays/", views.publicholiday_list, name="publicholiday_list"),
    path("holidays/add/", views.publicholiday_create, name="publicholiday_create"),
    path("holidays/<int:pk>/", views.publicholiday_detail, name="publicholiday_detail"),
    path("holidays/<int:pk>/edit/", views.publicholiday_edit, name="publicholiday_edit"),
    path("holidays/<int:pk>/delete/", views.publicholiday_delete, name="publicholiday_delete"),
]
