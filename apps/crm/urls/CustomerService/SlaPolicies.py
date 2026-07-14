"""CRM 1.4 Customer Service & Support — SlaPolicies URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # SLA policies (1.4)
    path("sla-policies/", views.slapolicy_list, name="slapolicy_list"),
    path("sla-policies/add/", views.slapolicy_create, name="slapolicy_create"),
    path("sla-policies/<int:pk>/", views.slapolicy_detail, name="slapolicy_detail"),
    path("sla-policies/<int:pk>/edit/", views.slapolicy_edit, name="slapolicy_edit"),
    path("sla-policies/<int:pk>/delete/", views.slapolicy_delete, name="slapolicy_delete"),
]
