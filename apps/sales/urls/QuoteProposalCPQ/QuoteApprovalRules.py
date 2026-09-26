"""URL patterns for QuoteApprovalRule entity."""
from django.urls import path
from apps.sales.views.QuoteProposalCPQ import QuoteApprovalRules as views

urlpatterns = [
    path("approval-rules/", views.quote_approval_rule_list, name="quote_approval_rule_list"),
    path("approval-rules/create/", views.quote_approval_rule_create, name="quote_approval_rule_create"),
    path("approval-rules/<int:pk>/", views.quote_approval_rule_detail, name="quote_approval_rule_detail"),
    path("approval-rules/<int:pk>/edit/", views.quote_approval_rule_edit, name="quote_approval_rule_edit"),
    path("approval-rules/<int:pk>/delete/", views.quote_approval_rule_delete, name="quote_approval_rule_delete"),
]
