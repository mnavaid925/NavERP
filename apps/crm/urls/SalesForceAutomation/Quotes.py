"""CRM 1.2 Sales Force Automation — Quotes URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Quotes (1.2 Quoting)
    path("quotes/", views.quote_list, name="quote_list"),
    path("quotes/add/", views.quote_create, name="quote_create"),
    path("quotes/<int:pk>/", views.quote_detail, name="quote_detail"),
    path("quotes/<int:pk>/edit/", views.quote_edit, name="quote_edit"),
    path("quotes/<int:pk>/delete/", views.quote_delete, name="quote_delete"),
    path("quotes/<int:pk>/print/", views.quote_print, name="quote_print"),
    path("quotes/<int:pk>/add-line/", views.quoteline_add, name="quoteline_add"),
    path("quote-lines/<int:line_pk>/remove/", views.quoteline_remove, name="quoteline_remove"),
    path("quotes/<int:pk>/send/", views.quote_send, name="quote_send"),
    path("quotes/<int:pk>/accept/", views.quote_accept, name="quote_accept"),
    path("quotes/<int:pk>/decline/", views.quote_decline, name="quote_decline"),
]
