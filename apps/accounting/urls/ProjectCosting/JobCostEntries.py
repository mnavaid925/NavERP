"""Accounting 2.9 Project/Job Costing — JobCostEntries URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("job-cost-entries/", views.job_cost_entry_list, name="job_cost_entry_list"),
    path("job-cost-entries/add/", views.job_cost_entry_create, name="job_cost_entry_create"),
    path("job-cost-entries/<int:pk>/", views.job_cost_entry_detail, name="job_cost_entry_detail"),
    path("job-cost-entries/<int:pk>/edit/", views.job_cost_entry_edit, name="job_cost_entry_edit"),
    path("job-cost-entries/<int:pk>/delete/", views.job_cost_entry_delete, name="job_cost_entry_delete"),
    path("job-cost-entries/<int:pk>/post/", views.job_cost_entry_post, name="job_cost_entry_post"),
]
