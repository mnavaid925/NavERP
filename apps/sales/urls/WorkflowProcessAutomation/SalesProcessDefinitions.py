"""Sales 8.17 — SalesProcessDefinition URL patterns."""
from django.urls import path

from apps.sales.views.WorkflowProcessAutomation import SalesProcessDefinitions as views

urlpatterns = [
    path("processes/", views.sales_process_definition_list, name="sales_process_definition_list"),
    path("processes/create/", views.sales_process_definition_create, name="sales_process_definition_create"),
    path("processes/<int:pk>/run/", views.sales_process_definition_run, name="sales_process_definition_run"),
    path("processes/<int:pk>/edit/", views.sales_process_definition_edit, name="sales_process_definition_edit"),
    path("processes/<int:pk>/delete/", views.sales_process_definition_delete, name="sales_process_definition_delete"),
    path("processes/<int:pk>/", views.sales_process_definition_detail, name="sales_process_definition_detail"),
]
