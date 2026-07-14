"""CRM 1.4 Customer Service & Support — CustomerPortalAccess URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Customer portal access — admin mapping (1.4)
    path("portal-access/", views.customerportalaccess_list, name="customerportalaccess_list"),
    path("portal-access/add/", views.customerportalaccess_create, name="customerportalaccess_create"),
    path("portal-access/<int:pk>/", views.customerportalaccess_detail, name="customerportalaccess_detail"),
    path("portal-access/<int:pk>/edit/", views.customerportalaccess_edit, name="customerportalaccess_edit"),
    path("portal-access/<int:pk>/delete/", views.customerportalaccess_delete, name="customerportalaccess_delete"),
]
