"""URL patterns for CPQQuoteLine entity."""
from django.urls import path
from apps.sales.views.QuoteProposalCPQ import CPQQuoteLines as views

urlpatterns = [
    path("quotes/<int:quote_pk>/lines/", views.cpq_quote_line_list, name="cpq_quote_line_list"),
    path("quotes/<int:quote_pk>/lines/create/", views.cpq_quote_line_create, name="cpq_quote_line_create"),
    path("quotes/<int:quote_pk>/lines/<int:pk>/", views.cpq_quote_line_detail, name="cpq_quote_line_detail"),
    path("quotes/<int:quote_pk>/lines/<int:pk>/edit/", views.cpq_quote_line_edit, name="cpq_quote_line_edit"),
    path("quotes/<int:quote_pk>/lines/<int:pk>/delete/", views.cpq_quote_line_delete, name="cpq_quote_line_delete"),
]
