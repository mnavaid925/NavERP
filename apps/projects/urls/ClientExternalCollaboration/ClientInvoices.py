"""Projects 7.14 Client & External Collaboration — ProjectClientInvoice URLs.
"""
from django.urls import path

from apps.projects.views.ClientExternalCollaboration import ClientInvoices as views

urlpatterns = [
    path("client-invoices/", views.pci_list, name="pci_list"),
    path("client-invoices/add/", views.pci_create, name="pci_create"),
    path("client-invoices/<int:pk>/", views.pci_detail, name="pci_detail"),
    path("client-invoices/<int:pk>/edit/", views.pci_edit, name="pci_edit"),
    path("client-invoices/<int:pk>/delete/", views.pci_delete, name="pci_delete"),
    path("client-invoices/<int:pk>/generate-invoice/", views.pci_generate_invoice, name="pci_generate_invoice"),
]
