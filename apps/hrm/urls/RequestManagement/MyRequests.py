"""HRM 3.26 Request Management — MyRequests URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.26 Request Management (Self-Service)
    path("my-requests/", views.my_requests, name="my_requests"),
]
