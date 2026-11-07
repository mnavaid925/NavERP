from django.urls import path

from apps.bi.views.AiAugmentedAnalytics import AnalyticsRecommendations as views

urlpatterns = [
    path("recommendations/", views.analytics_recommendation_list, name="analytics_recommendation_list"),
    path("recommendations/new/", views.analytics_recommendation_create, name="analytics_recommendation_create"),
    path("recommendations/<int:pk>/", views.analytics_recommendation_detail, name="analytics_recommendation_detail"),
    path("recommendations/<int:pk>/edit/", views.analytics_recommendation_edit, name="analytics_recommendation_edit"),
    path("recommendations/<int:pk>/delete/", views.analytics_recommendation_delete, name="analytics_recommendation_delete"),
    path("recommendations/<int:pk>/interact/", views.analytics_recommendation_interact, name="analytics_recommendation_interact"),
]
