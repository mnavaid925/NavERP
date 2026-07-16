"""HRM 3.37 Compensation & Benefits — Equitygrant URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("compensation/equity-grants/", views.equitygrant_list, name="equitygrant_list"),
    path("compensation/equity-grants/add/", views.equitygrant_create, name="equitygrant_create"),
    path("compensation/equity-grants/<int:pk>/", views.equitygrant_detail, name="equitygrant_detail"),
    path("compensation/equity-grants/<int:pk>/edit/", views.equitygrant_edit, name="equitygrant_edit"),
    path("compensation/equity-grants/<int:pk>/delete/", views.equitygrant_delete, name="equitygrant_delete"),
    path("compensation/equity-grants/<int:pk>/record-exercise/", views.equitygrant_record_exercise, name="equitygrant_record_exercise"),
]
