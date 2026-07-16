"""HRM 3.7 Interview Process — Feedbackcriterions URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("interview-feedback/<int:pk>/criteria/add/", views.feedbackcriterion_add, name="feedbackcriterion_add"),
    path("interview-feedback/<int:pk>/criteria/<int:criterion_pk>/delete/", views.feedbackcriterion_delete, name="feedbackcriterion_delete"),
]
