"""CRM 1.9 Document & Contract Management — DocTemplates URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Document templates (1.9)
    path("doc-templates/", views.doctemplate_list, name="doctemplate_list"),
    path("doc-templates/add/", views.doctemplate_create, name="doctemplate_create"),
    path("doc-templates/<int:pk>/", views.doctemplate_detail, name="doctemplate_detail"),
    path("doc-templates/<int:pk>/edit/", views.doctemplate_edit, name="doctemplate_edit"),
    path("doc-templates/<int:pk>/delete/", views.doctemplate_delete, name="doctemplate_delete"),
]
