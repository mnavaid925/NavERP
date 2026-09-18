"""Projects 7.15 Financial & Billing Management — ProjectBillingRun URLs.
"""
from django.urls import path

from apps.projects.views.FinancialBillingManagement import BillingRuns as views

urlpatterns = [
    path("financial/billing-runs/", views.pbr_list, name="pbr_list"),
    path("financial/billing-runs/create/", views.pbr_create, name="pbr_create"),
    path("financial/billing-runs/<int:pk>/", views.pbr_detail, name="pbr_detail"),
    path("financial/billing-runs/<int:pk>/edit/", views.pbr_edit, name="pbr_edit"),
    path("financial/billing-runs/<int:pk>/delete/", views.pbr_delete, name="pbr_delete"),
    path("financial/billing-runs/<int:pk>/approve/", views.pbr_approve, name="pbr_approve"),
    path("financial/billing-runs/<int:pk>/generate-invoice/", views.pbr_generate_invoice, name="pbr_generate_invoice"),
    path("financial/billing-runs/<int:pk>/dispatch/", views.pbr_dispatch, name="pbr_dispatch"),
    path("financial/billing-runs/<int:pk>/preview-pdf/", views.pbr_preview_pdf, name="pbr_preview_pdf"),
]
