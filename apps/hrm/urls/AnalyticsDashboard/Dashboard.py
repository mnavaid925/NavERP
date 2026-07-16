"""HRM 3.32 Analytics Dashboard — Dashboard URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("analytics/dashboards/", views.hr_dashboard_list, name="hr_dashboard_list"),
    path("analytics/dashboards/add/", views.hr_dashboard_create, name="hr_dashboard_create"),
    path("analytics/dashboards/<int:pk>/", views.hr_dashboard_detail, name="hr_dashboard_detail"),
    path("analytics/dashboards/<int:pk>/edit/", views.hr_dashboard_edit, name="hr_dashboard_edit"),
    path("analytics/dashboards/<int:pk>/delete/", views.hr_dashboard_delete, name="hr_dashboard_delete"),
]
