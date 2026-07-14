"""CRM 1.1 Core Data Management — Accounts URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Accounts — core.Party (organization) + AccountProfile (1.1)
    path("accounts/", views.account_list, name="account_list"),
    path("accounts/add/", views.account_create, name="account_create"),
    path("accounts/<int:pk>/", views.account_detail, name="account_detail"),
    path("accounts/<int:pk>/edit/", views.account_edit, name="account_edit"),
    path("accounts/<int:pk>/delete/", views.account_delete, name="account_delete"),
]
