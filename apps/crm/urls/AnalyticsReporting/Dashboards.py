"""CRM 1.6 Analytics & Reporting — Dashboards URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # ===== 1.6 Analytics & Reporting =====================================
    # Dashboards (saved per-user) + their live widgets
    path("dashboards/", views.dashboard_list, name="dashboard_list"),
    path("dashboards/add/", views.dashboard_create, name="dashboard_create"),
    path("dashboards/<int:pk>/", views.dashboard_detail, name="dashboard_detail"),
    path("dashboards/<int:pk>/edit/", views.dashboard_edit, name="dashboard_edit"),
    path("dashboards/<int:pk>/delete/", views.dashboard_delete, name="dashboard_delete"),
]
