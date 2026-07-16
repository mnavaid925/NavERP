"""HRM 3.6 Candidate Management — Communication URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Candidate Communications (3.6) — append-only log (list + detail only)
    path("candidate-communications/", views.communication_list, name="communication_list"),
    path("candidate-communications/<int:pk>/", views.communication_detail, name="communication_detail"),
]
