from django.urls import path

from apps.bi.views.AiAugmentedAnalytics import AugmentedInsights as views

urlpatterns = [
    path("augmented-insights/", views.augmented_insight_list, name="augmented_insight_list"),
    path("augmented-insights/feed/", views.augmented_insight_feed, name="augmented_insight_feed"),
    path("augmented-insights/new/", views.augmented_insight_create, name="augmented_insight_create"),
    path("augmented-insights/<int:pk>/", views.augmented_insight_detail, name="augmented_insight_detail"),
    path("augmented-insights/<int:pk>/edit/", views.augmented_insight_edit, name="augmented_insight_edit"),
    path("augmented-insights/<int:pk>/delete/", views.augmented_insight_delete, name="augmented_insight_delete"),
    path("augmented-insights/<int:pk>/triage/", views.augmented_insight_triage, name="augmented_insight_triage"),
]
