"""Sales 8.17 — SalesAssignmentRule URL patterns."""
from django.urls import path

from apps.sales.views.WorkflowProcessAutomation import SalesAssignmentRules as views

urlpatterns = [
    path("assignment-rules/", views.sales_assignment_rule_list, name="sales_assignment_rule_list"),
    path("assignment-rules/create/", views.sales_assignment_rule_create, name="sales_assignment_rule_create"),
    path("assignment-rules/<int:pk>/edit/", views.sales_assignment_rule_edit, name="sales_assignment_rule_edit"),
    path("assignment-rules/<int:pk>/delete/", views.sales_assignment_rule_delete, name="sales_assignment_rule_delete"),
    path("assignment-rules/<int:pk>/", views.sales_assignment_rule_detail, name="sales_assignment_rule_detail"),
]
