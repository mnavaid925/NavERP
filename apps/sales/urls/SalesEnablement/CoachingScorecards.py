"""Sales 8.9 — URLs for `CoachingScorecard`."""
from django.urls import path

from apps.sales.views.SalesEnablement.CoachingScorecards import (
    coaching_scorecard_acknowledge,
    coaching_scorecard_create,
    coaching_scorecard_delete,
    coaching_scorecard_detail,
    coaching_scorecard_edit,
    coaching_scorecard_list,
)

urlpatterns = [
    path("enablement/coaching/", coaching_scorecard_list, name="coaching_scorecard_list"),
    path("enablement/coaching/new/", coaching_scorecard_create, name="coaching_scorecard_create"),
    path("enablement/coaching/<int:pk>/", coaching_scorecard_detail, name="coaching_scorecard_detail"),
    path("enablement/coaching/<int:pk>/edit/", coaching_scorecard_edit, name="coaching_scorecard_edit"),
    path("enablement/coaching/<int:pk>/delete/", coaching_scorecard_delete, name="coaching_scorecard_delete"),
    path("enablement/coaching/<int:pk>/acknowledge/", coaching_scorecard_acknowledge, name="coaching_scorecard_acknowledge"),
]
