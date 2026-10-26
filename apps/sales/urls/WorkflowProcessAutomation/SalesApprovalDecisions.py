"""Sales 8.17 — SalesApprovalDecision URL patterns."""
from django.urls import path

from apps.sales.views.WorkflowProcessAutomation import SalesApprovalDecisions as views

# Order is behaviour (Django is first-match-wins): the literal `create/`, `approve/` and
# `reject/` routes MUST precede every `<int:pk>` route, or `<int:pk>` never sees them and
# `approval-decisions/approve/` is tried as a pk.
urlpatterns = [
    path("approval-decisions/", views.sales_approval_decision_list, name="sales_approval_decision_list"),
    path("approval-decisions/create/", views.sales_approval_decision_create, name="sales_approval_decision_create"),
    path("approval-decisions/approve/", views.sales_approval_decision_approve, name="sales_approval_decision_approve"),
    path("approval-decisions/reject/", views.sales_approval_decision_reject, name="sales_approval_decision_reject"),
    path("approval-decisions/<int:pk>/edit/", views.sales_approval_decision_edit, name="sales_approval_decision_edit"),
    path("approval-decisions/<int:pk>/delete/", views.sales_approval_decision_delete, name="sales_approval_decision_delete"),
    path("approval-decisions/<int:pk>/", views.sales_approval_decision_detail, name="sales_approval_decision_detail"),
]
