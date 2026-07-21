"""SCM 4.6 Transportation Management System — FreightInvoice routes (prefix ``freight-invoices/``).

Literal routes before ``<int:pk>/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("freight-invoices/", views.freightinvoice_list, name="freightinvoice_list"),
    path("freight-invoices/add/", views.freightinvoice_create, name="freightinvoice_create"),
    path("freight-invoices/<int:pk>/", views.freightinvoice_detail, name="freightinvoice_detail"),
    path("freight-invoices/<int:pk>/edit/", views.freightinvoice_edit, name="freightinvoice_edit"),
    path("freight-invoices/<int:pk>/delete/", views.freightinvoice_delete, name="freightinvoice_delete"),
    path("freight-invoices/<int:pk>/run-audit/", views.freightinvoice_run_audit,
         name="freightinvoice_run_audit"),
    path("freight-invoices/<int:pk>/dispute/", views.freightinvoice_dispute,
         name="freightinvoice_dispute"),
    path("freight-invoices/<int:pk>/approve/", views.freightinvoice_approve,
         name="freightinvoice_approve"),
    path("freight-invoices/<int:pk>/reject/", views.freightinvoice_reject,
         name="freightinvoice_reject"),
    path("freight-invoices/<int:pk>/handoff/", views.freightinvoice_handoff,
         name="freightinvoice_handoff"),
]
