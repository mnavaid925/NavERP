"""HRM 3.39 Compliance & Legal — Policyacknowledgment URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("compliance/acknowledgments/", views.policyacknowledgment_list, name="policyacknowledgment_list"),
    path("compliance/acknowledgments/<int:pk>/acknowledge/", views.policyacknowledgment_acknowledge, name="policyacknowledgment_acknowledge"),
]
