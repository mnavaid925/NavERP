"""Procurement 6.13 Invoice & Voucher Management — SupplierInvoice URL patterns.

Three NEW first segments — ``supplier-invoices/``, ``capture/`` and ``invoice-vouchers/`` — each
collision-checked against the concatenated ``urls/__init__.py``. The app registers no greedy
``<str:…>`` converter, so there is no cross-module shadowing surface to reason about; Django
resolves first-match-wins and every literal child (``add/``, ``duplicates/``, ``revalidate/``) is
declared BEFORE its parent's ``<int:pk>/`` route.

Every write that is not ordinary CRUD is POST-only and admin-gated in the view it points at; the
URLconf cannot enforce that, so the ordering here is about resolution, not authorization.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # -- register ---------------------------------------------------------------------------
    path("supplier-invoices/", views.supplierinvoice_list, name="supplierinvoice_list"),
    path("supplier-invoices/add/", views.supplierinvoice_create, name="supplierinvoice_create"),
    path("supplier-invoices/duplicates/", views.supplierinvoice_duplicates,
         name="supplierinvoice_duplicates"),
    path("supplier-invoices/revalidate/", views.supplierinvoice_revalidate,
         name="supplierinvoice_revalidate"),
    path("supplier-invoices/<int:pk>/", views.supplierinvoice_detail, name="supplierinvoice_detail"),
    path("supplier-invoices/<int:pk>/edit/", views.supplierinvoice_edit,
         name="supplierinvoice_edit"),
    path("supplier-invoices/<int:pk>/delete/", views.supplierinvoice_delete,
         name="supplierinvoice_delete"),
    # -- match verbs -------------------------------------------------------------------------
    path("supplier-invoices/<int:pk>/match/", views.supplierinvoice_match,
         name="supplierinvoice_match"),
    path("supplier-invoices/<int:pk>/approve/", views.supplierinvoice_approve,
         name="supplierinvoice_approve"),
    path("supplier-invoices/<int:pk>/override/", views.supplierinvoice_override,
         name="supplierinvoice_override"),
    path("supplier-invoices/<int:pk>/void/", views.supplierinvoice_void,
         name="supplierinvoice_void"),
    path("supplier-invoices/<int:pk>/reverse/", views.supplierinvoice_reverse,
         name="supplierinvoice_reverse"),
    # -- payment scheduling ---------------------------------------------------------------------
    path("supplier-invoices/<int:pk>/schedule/", views.supplierinvoice_schedule,
         name="supplierinvoice_schedule"),
    path("supplier-invoices/<int:pk>/mark-paid/", views.supplierinvoice_mark_paid,
         name="supplierinvoice_mark_paid"),
    # -- standalone pages ---------------------------------------------------------------------
    path("capture/", views.supplierinvoice_capture, name="supplierinvoice_capture"),
    path("invoice-vouchers/", views.invoicevoucher_dashboard, name="invoicevoucher_dashboard"),
]
