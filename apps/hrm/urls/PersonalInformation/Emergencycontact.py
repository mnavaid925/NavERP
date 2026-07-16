"""HRM 3.25 Personal Information — Emergencycontact URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Emergency Contacts (direct self-edit)
    path("emergency-contacts/", views.emergencycontact_list, name="emergencycontact_list"),
    path("emergency-contacts/add/", views.emergencycontact_create, name="emergencycontact_create"),
    path("emergency-contacts/<int:pk>/", views.emergencycontact_detail, name="emergencycontact_detail"),
    path("emergency-contacts/<int:pk>/edit/", views.emergencycontact_edit, name="emergencycontact_edit"),
    path("emergency-contacts/<int:pk>/delete/", views.emergencycontact_delete, name="emergencycontact_delete"),
]
