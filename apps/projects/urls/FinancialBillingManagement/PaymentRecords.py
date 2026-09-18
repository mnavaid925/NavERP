"""Projects 7.15 Financial & Billing Management — ProjectPaymentRecord URLs.
"""
from django.urls import path

from apps.projects.views.FinancialBillingManagement import PaymentRecords as views

urlpatterns = [
    path("financial/payment-records/", views.ppr_list, name="ppr_list"),
    path("financial/payment-records/create/", views.ppr_create, name="ppr_create"),
    path("financial/payment-records/<int:pk>/", views.ppr_detail, name="ppr_detail"),
    path("financial/payment-records/<int:pk>/edit/", views.ppr_edit, name="ppr_edit"),
    path("financial/payment-records/<int:pk>/delete/", views.ppr_delete, name="ppr_delete"),
    path("financial/payment-records/<int:pk>/log-contact/", views.ppr_log_contact, name="ppr_log_contact"),
    path("financial/payment-records/<int:pk>/record-promise/", views.ppr_record_promise, name="ppr_record_promise"),
    path("financial/payment-records/<int:pk>/escalate/", views.ppr_escalate, name="ppr_escalate"),
    path("financial/payment-records/<int:pk>/resolve/", views.ppr_resolve, name="ppr_resolve"),
]
