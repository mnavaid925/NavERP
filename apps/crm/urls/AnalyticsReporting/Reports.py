"""CRM 1.6 Analytics & Reporting — Reports URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Standard reports + point-in-time snapshots
    path("reports/", views.report_list, name="report_list"),
    path("reports/add/", views.report_create, name="report_create"),
    path("reports/<int:pk>/", views.report_detail, name="report_detail"),
    path("reports/<int:pk>/edit/", views.report_edit, name="report_edit"),
    path("reports/<int:pk>/delete/", views.report_delete, name="report_delete"),
    path("reports/<int:pk>/favorite/", views.report_favorite, name="report_favorite"),
    path("reports/<int:pk>/snapshot/", views.report_snapshot, name="report_snapshot"),
]
