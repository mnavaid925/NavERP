"""CRM 1.8 Project & Delivery Management — Projects URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Projects (1.8)
    path("projects/", views.crmproject_list, name="crmproject_list"),
    path("projects/add/", views.crmproject_create, name="crmproject_create"),
    path("projects/board/", views.crmproject_board, name="crmproject_board"),  # literal before <int:pk>
    path("projects/<int:pk>/", views.crmproject_detail, name="crmproject_detail"),
    path("projects/<int:pk>/edit/", views.crmproject_edit, name="crmproject_edit"),
    path("projects/<int:pk>/delete/", views.crmproject_delete, name="crmproject_delete"),
    path("opportunities/<int:pk>/to-project/", views.opportunity_to_project, name="opportunity_to_project"),
]
