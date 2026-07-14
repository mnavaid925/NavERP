"""CRM 1.4 Customer Service & Support — CustomerPortal URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Customer self-service portal — customer-facing (1.4)
    path("portal/cases/", views.portal_case_list, name="portal_case_list"),
    path("portal/cases/new/", views.portal_case_create, name="portal_case_create"),
    path("portal/cases/<int:pk>/", views.portal_case_detail, name="portal_case_detail"),
]
