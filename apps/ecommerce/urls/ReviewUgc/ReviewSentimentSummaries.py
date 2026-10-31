from django.urls import path

from apps.ecommerce.views.ReviewUgc import ReviewSentimentSummaries as views

urlpatterns = [
    path("sentiment/", views.reviewsentimentsummary_list, name="reviewsentimentsummary_list"),
    path("sentiment/create/", views.reviewsentimentsummary_create, name="reviewsentimentsummary_create"),
    path("sentiment/<int:pk>/", views.reviewsentimentsummary_detail, name="reviewsentimentsummary_detail"),
    path("sentiment/<int:pk>/edit/", views.reviewsentimentsummary_edit, name="reviewsentimentsummary_edit"),
    path("sentiment/<int:pk>/delete/", views.reviewsentimentsummary_delete, name="reviewsentimentsummary_delete"),
    path("sentiment/<int:pk>/recalculate/", views.reviewsentimentsummary_recalculate, name="reviewsentimentsummary_recalculate"),
]
