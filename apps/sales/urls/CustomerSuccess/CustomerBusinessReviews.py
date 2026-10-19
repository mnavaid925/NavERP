"""Sales 8.11 — URLs for `CustomerBusinessReview`."""
from django.urls import path

from apps.sales.views.CustomerSuccess import CustomerBusinessReviews as views

urlpatterns = [
    path("customer-success/business-reviews/", views.customer_business_review_list, name="customer_business_review_list"),
    path("customer-success/business-reviews/create/", views.customer_business_review_create, name="customer_business_review_create"),
    path("customer-success/business-reviews/<int:pk>/", views.customer_business_review_detail, name="customer_business_review_detail"),
    path("customer-success/business-reviews/<int:pk>/edit/", views.customer_business_review_edit, name="customer_business_review_edit"),
    path("customer-success/business-reviews/<int:pk>/delete/", views.customer_business_review_delete, name="customer_business_review_delete"),
    path("customer-success/qbr-studio/", views.customer_qbr_studio, name="customer_qbr_studio"),
    path("customer-success/advocacy-hub/", views.customer_advocacy_hub, name="customer_advocacy_hub"),
]
