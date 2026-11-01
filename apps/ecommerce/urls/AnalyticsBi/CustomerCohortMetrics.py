from django.urls import path

from apps.ecommerce.views.AnalyticsBi import CustomerCohortMetrics as views

urlpatterns = [
    path("analytics/cohorts/", views.customercohortmetric_list, name="customercohortmetric_list"),
    path("analytics/cohorts/create/", views.customercohortmetric_create, name="customercohortmetric_create"),
    path("analytics/cohorts/recalculate/", views.customercohortmetric_recalculate, name="customercohortmetric_recalculate"),
    path("analytics/cohorts/<int:pk>/", views.customercohortmetric_detail, name="customercohortmetric_detail"),
    path("analytics/cohorts/<int:pk>/edit/", views.customercohortmetric_edit, name="customercohortmetric_edit"),
    path("analytics/cohorts/<int:pk>/delete/", views.customercohortmetric_delete, name="customercohortmetric_delete"),
]
