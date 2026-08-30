"""Procurement 6.13 Invoice & Voucher Management — InvoiceMatchVariance + Match Board URL patterns.

Two first segments — ``match-variances/`` and ``match-board/`` — both collision-checked against
the concatenated ``urls/__init__.py``. Django resolves first-match-wins and this app registers
no greedy ``<str:…>`` converter, so ordering matters only within the segment: the literal
``accept/`` is declared AFTER the ``<int:pk>/`` route that it extends, and neither can shadow
the other because the detail route ends there.

**There is no ``add/``, ``edit/`` or ``delete/`` route in this module, by design.** Variances are
system-generated evidence; the only human route is the POST-only ``accept/`` verb.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # -- exceptions register -------------------------------------------------------------------
    path("match-variances/", views.matchvariance_list, name="matchvariance_list"),
    path("match-variances/<int:pk>/", views.matchvariance_detail, name="matchvariance_detail"),
    # POST-only through its view decorator.
    path("match-variances/<int:pk>/accept/", views.matchvariance_accept,
         name="matchvariance_accept"),
    # -- standalone board -------------------------------------------------------------------------
    path("match-board/", views.invoice_match_board, name="invoice_match_board"),
]
