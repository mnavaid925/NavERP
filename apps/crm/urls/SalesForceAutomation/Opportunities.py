"""CRM 1.2 Sales Force Automation — Opportunities URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Opportunities (1.2 Opportunity Management)
    path("opportunities/", views.opportunity_list, name="opportunity_list"),
    path("opportunities/board/", views.opportunity_board, name="opportunity_board"),  # Kanban
    path("opportunities/add/", views.opportunity_create, name="opportunity_create"),
    path("opportunities/<int:pk>/", views.opportunity_detail, name="opportunity_detail"),
    path("opportunities/<int:pk>/edit/", views.opportunity_edit, name="opportunity_edit"),
    path("opportunities/<int:pk>/delete/", views.opportunity_delete, name="opportunity_delete"),
    path("opportunities/<int:pk>/advance/", views.opportunity_advance, name="opportunity_advance"),
    path("opportunities/<int:pk>/add-split/", views.opportunitysplit_add, name="opportunitysplit_add"),
    path("opportunity-splits/<int:split_pk>/remove/", views.opportunitysplit_remove, name="opportunitysplit_remove"),
]
