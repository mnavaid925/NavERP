"""Procurement 6.12 Goods Receipt & Inspection — computed board URL patterns.

Three NEW first segments — ``receiving-console/``, ``tolerance-exceptions/`` and
``receipt-audit/`` — each a distinct whole component against the inventory in
``apps/procurement/urls/__init__.py``. The app still registers no greedy ``<str:…>`` converter,
so there is no cross-module shadowing surface to reason about; Django resolves first-match-wins
and the literal ``receiving-console/`` is declared before its two ``<int:pk>/`` children.

The two ``<int:pk>`` routes take the **ASN's** pk, not a receipt's: both verbs act on a supplier
declaration, and the receipt is what one of them produces. Both are POST-only — they are the only
writes in a lane that is otherwise entirely read-only.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("receiving-console/", views.receiving_console, name="receiving_console"),
    path("receiving-console/<int:pk>/book/", views.receiving_console_book,
         name="receiving_console_book"),
    path("receiving-console/<int:pk>/mint-lots/", views.receiving_console_mint_lots,
         name="receiving_console_mint_lots"),
    path("tolerance-exceptions/", views.tolerance_exceptions, name="tolerance_exceptions"),
    path("receipt-audit/", views.receipt_audit, name="receipt_audit"),
]
