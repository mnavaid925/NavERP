"""CRM 1.3 Marketing Automation — EmailTemplates URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Email templates (1.3 Email Marketing)
    path("email-templates/", views.emailtemplate_list, name="emailtemplate_list"),
    path("email-templates/add/", views.emailtemplate_create, name="emailtemplate_create"),
    path("email-templates/<int:pk>/", views.emailtemplate_detail, name="emailtemplate_detail"),
    path("email-templates/<int:pk>/edit/", views.emailtemplate_edit, name="emailtemplate_edit"),
    path("email-templates/<int:pk>/delete/", views.emailtemplate_delete, name="emailtemplate_delete"),
]
