"""Accounting 2.15 Integration & API — IntegrationConfigs URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.15 Integration & API
    path("integrations/", views.integration_list, name="integration_list"),
    path("integrations/add/", views.integration_create, name="integration_create"),
    path("integrations/<int:pk>/", views.integration_detail, name="integration_detail"),
    path("integrations/<int:pk>/edit/", views.integration_edit, name="integration_edit"),
    path("integrations/<int:pk>/delete/", views.integration_delete, name="integration_delete"),
    path("integrations/<int:pk>/rotate-key/", views.integration_rotate_key, name="integration_rotate_key"),
]
