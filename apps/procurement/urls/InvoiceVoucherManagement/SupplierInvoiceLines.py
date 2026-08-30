"""Procurement 6.13 Invoice & Voucher Management — SupplierInvoiceLine + Payment Schedule URL patterns.

Two first segments — ``supplier-invoice-lines/`` and ``payment-schedule/`` — both collision-checked
against the concatenated ``urls/__init__.py``. Django resolves first-match-wins and this app
registers no greedy ``<str:…>`` converter, so ordering here matters only within the segment: the
literal ``add/`` is declared BEFORE the ``<int:pk>/`` route that would otherwise swallow it.

The line register's create route takes its parent invoice from the query string
(``?invoice=<pk>``) because a line cannot exist without one; the delete route is POST-only
through its view decorator.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # -- line register ------------------------------------------------------------------------
    path("supplier-invoice-lines/", views.supplierinvoiceline_list, name="supplierinvoiceline_list"),
    path("supplier-invoice-lines/add/", views.supplierinvoiceline_create,
         name="supplierinvoiceline_create"),
    path("supplier-invoice-lines/<int:pk>/", views.supplierinvoiceline_detail,
         name="supplierinvoiceline_detail"),
    path("supplier-invoice-lines/<int:pk>/edit/", views.supplierinvoiceline_edit,
         name="supplierinvoiceline_edit"),
    path("supplier-invoice-lines/<int:pk>/delete/", views.supplierinvoiceline_delete,
         name="supplierinvoiceline_delete"),
    # -- standalone board -------------------------------------------------------------------------
    path("payment-schedule/", views.paymentschedule_list, name="paymentschedule_list"),
]
