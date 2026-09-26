"""URL patterns for CPQQuote entity."""
from django.urls import path
from apps.sales.views.QuoteProposalCPQ import CPQQuotes as views

urlpatterns = [
    path("quotes/", views.cpq_quote_list, name="cpq_quote_list"),
    path("quotes/create/", views.cpq_quote_create, name="cpq_quote_create"),
    path("quotes/<int:pk>/", views.cpq_quote_detail, name="cpq_quote_detail"),
    path("quotes/<int:pk>/edit/", views.cpq_quote_edit, name="cpq_quote_edit"),
    path("quotes/<int:pk>/delete/", views.cpq_quote_delete, name="cpq_quote_delete"),
]
