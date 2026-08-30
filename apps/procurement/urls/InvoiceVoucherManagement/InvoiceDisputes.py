"""Procurement 6.13 Invoice & Voucher Management — InvoiceDispute + Dispute Aging URL patterns.

One first segment, ``invoice-disputes/`` — collision-checked against the concatenated
``urls/__init__.py``, and the app registers no greedy ``<str:…>`` converter, so nothing can
shadow it. Within the segment the three literals (``add/``, ``aging/``) are declared BEFORE the
``<int:pk>/`` routes they would otherwise fall into.

Every verb route (``resolve/``, ``escalate/``, ``await-supplier/``, ``await-internal/``,
``close/``, ``delete/``) is POST-only through its view decorator — there is no confirm template
for any of them.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # -- the register ---------------------------------------------------------------------------
    path("invoice-disputes/", views.invoicedispute_list, name="invoicedispute_list"),
    path("invoice-disputes/add/", views.invoicedispute_create, name="invoicedispute_create"),
    # -- standalone board ------------------------------------------------------------------------
    path("invoice-disputes/aging/", views.invoicedispute_aging, name="invoicedispute_aging"),
    # -- one dispute -----------------------------------------------------------------------------
    path("invoice-disputes/<int:pk>/", views.invoicedispute_detail, name="invoicedispute_detail"),
    path("invoice-disputes/<int:pk>/edit/", views.invoicedispute_edit, name="invoicedispute_edit"),
    path("invoice-disputes/<int:pk>/delete/", views.invoicedispute_delete,
         name="invoicedispute_delete"),
    # -- verbs -------------------------------------------------------------------------------------
    path("invoice-disputes/<int:pk>/resolve/", views.invoicedispute_resolve,
         name="invoicedispute_resolve"),
    path("invoice-disputes/<int:pk>/escalate/", views.invoicedispute_escalate,
         name="invoicedispute_escalate"),
    path("invoice-disputes/<int:pk>/await-supplier/", views.invoicedispute_await_supplier,
         name="invoicedispute_await_supplier"),
    path("invoice-disputes/<int:pk>/await-internal/", views.invoicedispute_await_internal,
         name="invoicedispute_await_internal"),
    path("invoice-disputes/<int:pk>/close/", views.invoicedispute_close,
         name="invoicedispute_close"),
]
