"""HRM 3.1 Employee Management — Detail URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("employees/<int:pk>/", views.employee_detail, name="employee_detail"),
]
