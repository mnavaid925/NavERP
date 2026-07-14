"""CRM 1.1 Core Data Management — Leads URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Leads (1.1)
    path("leads/", views.lead_list, name="lead_list"),
    path("leads/add/", views.lead_create, name="lead_create"),
    path("leads/<int:pk>/", views.lead_detail, name="lead_detail"),
    path("leads/<int:pk>/edit/", views.lead_edit, name="lead_edit"),
    path("leads/<int:pk>/delete/", views.lead_delete, name="lead_delete"),
    path("leads/<int:pk>/convert/", views.lead_convert, name="lead_convert"),
]
