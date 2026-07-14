"""CRM 1.12 Inventory & Vendor Management — PartnerPortalAccess URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Partner portal access — admin (1.12)
    path("partner-portal/", views.partnerportalaccess_list, name="partnerportalaccess_list"),
    path("partner-portal/add/", views.partnerportalaccess_create, name="partnerportalaccess_create"),
    path("partner-portal/<int:pk>/", views.partnerportalaccess_detail, name="partnerportalaccess_detail"),
    path("partner-portal/<int:pk>/edit/", views.partnerportalaccess_edit, name="partnerportalaccess_edit"),
    path("partner-portal/<int:pk>/delete/", views.partnerportalaccess_delete, name="partnerportalaccess_delete"),
]
