"""SCM 4.2 SRM — SupplierScorecard URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("scorecards/", views.scorecard_list, name="scorecard_list"),
    path("scorecards/add/", views.scorecard_create, name="scorecard_create"),
    path("scorecards/<int:pk>/", views.scorecard_detail, name="scorecard_detail"),
    path("scorecards/<int:pk>/edit/", views.scorecard_edit, name="scorecard_edit"),
    path("scorecards/<int:pk>/delete/", views.scorecard_delete, name="scorecard_delete"),
    path("scorecards/<int:pk>/recompute/", views.scorecard_recompute, name="scorecard_recompute"),
    path("scorecards/<int:pk>/publish/", views.scorecard_publish, name="scorecard_publish"),
]
