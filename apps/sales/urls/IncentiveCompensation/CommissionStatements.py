"""Sales 8.10 — URLs for `CommissionStatement`."""
from django.urls import path

from apps.sales.views.IncentiveCompensation import CommissionStatements as views

urlpatterns = [
    path("compensation/statements/", views.commission_statement_list, name="commission_statement_list"),
    path("compensation/statements/add/", views.commission_statement_create, name="commission_statement_create"),
    path("compensation/statements/generate-batch/", views.commission_statement_generate_batch, name="commission_statement_generate_batch"),
    path("compensation/statements/<int:pk>/edit/", views.commission_statement_edit, name="commission_statement_edit"),
    path("compensation/statements/<int:pk>/delete/", views.commission_statement_delete, name="commission_statement_delete"),
    path("compensation/statements/<int:pk>/approve/", views.commission_statement_approve, name="commission_statement_approve"),
    path("compensation/statements/<int:pk>/lock/", views.commission_statement_lock, name="commission_statement_lock"),
    path("compensation/statements/<int:pk>/", views.commission_statement_detail, name="commission_statement_detail"),
]
