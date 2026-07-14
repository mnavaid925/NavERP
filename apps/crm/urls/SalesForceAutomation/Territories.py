"""CRM 1.2 Sales Force Automation — Territories URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Territories (1.2 Forecasting)
    path("territories/", views.territory_list, name="territory_list"),
    path("territories/add/", views.territory_create, name="territory_create"),
    path("territories/<int:pk>/", views.territory_detail, name="territory_detail"),
    path("territories/<int:pk>/edit/", views.territory_edit, name="territory_edit"),
    path("territories/<int:pk>/delete/", views.territory_delete, name="territory_delete"),
]
