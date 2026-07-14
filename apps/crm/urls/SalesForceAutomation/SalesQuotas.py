"""CRM 1.2 Sales Force Automation — SalesQuotas URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Sales quotas (1.2 Forecasting)
    path("sales-quotas/", views.salesquota_list, name="salesquota_list"),
    path("sales-quotas/add/", views.salesquota_create, name="salesquota_create"),
    path("sales-quotas/<int:pk>/", views.salesquota_detail, name="salesquota_detail"),
    path("sales-quotas/<int:pk>/edit/", views.salesquota_edit, name="salesquota_edit"),
    path("sales-quotas/<int:pk>/delete/", views.salesquota_delete, name="salesquota_delete"),
]
