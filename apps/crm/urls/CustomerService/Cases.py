"""CRM 1.4 Customer Service & Support — Cases URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Cases / Tickets (1.4 Case / Ticket Management)
    path("cases/", views.case_list, name="case_list"),
    path("cases/add/", views.case_create, name="case_create"),
    path("cases/<int:pk>/", views.case_detail, name="case_detail"),
    path("cases/<int:pk>/edit/", views.case_edit, name="case_edit"),
    path("cases/<int:pk>/delete/", views.case_delete, name="case_delete"),
    path("cases/<int:pk>/add-comment/", views.case_comment_add, name="case_comment_add"),
]
