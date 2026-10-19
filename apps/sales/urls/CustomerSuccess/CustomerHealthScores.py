"""Sales 8.11 — URLs for `CustomerHealthScore`."""
from django.urls import path

from apps.sales.views.CustomerSuccess import CustomerHealthScores as views

urlpatterns = [
    path("customer-success/health-scores/", views.customer_health_score_list, name="customer_health_score_list"),
    path("customer-success/health-scores/create/", views.customer_health_score_create, name="customer_health_score_create"),
    path("customer-success/health-scores/<int:pk>/", views.customer_health_score_detail, name="customer_health_score_detail"),
    path("customer-success/health-scores/<int:pk>/edit/", views.customer_health_score_edit, name="customer_health_score_edit"),
    path("customer-success/health-scores/<int:pk>/delete/", views.customer_health_score_delete, name="customer_health_score_delete"),
    path("customer-success/health-console/", views.customer_health_console, name="customer_health_console"),
]
