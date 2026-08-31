"""Procurement 6.14 Spend Analytics & Reporting — the computed-page lane declares NO TABLE.

**Spend Dashboards**, **Category Spend Analysis** and **Data Export & Visualization** are the three
NavERP.md 6.14 bullets that describe a *view over spend that already exists*, not a new document.
They are therefore built exactly the way 6.11's ``views/OrderFulfillment/FulfillmentBoards.py`` and
6.12's ``views/GoodsReceiptInspection/ReceiptBoards.py`` are built: read-only pages over rows other
sub-modules already own, with **zero new state, zero writes and zero migration impact**.

This module exists so the four-layer package structure stays symmetrical and so a reviewer looking
for ``models/SpendAnalyticsReporting/SpendDashboards.py`` finds a stated reason rather than a gap.
It declares no model, contributes nothing to ``makemigrations``, and exports nothing — the package
``__init__`` has nothing to re-export from here.

**Where the numbers come from.** Every figure the three pages render is an aggregate over rows that
belong to somebody else:

* recognised (invoiced) spend  -> ``procurement.SupplierInvoiceLine`` (6.13 owns it)
* committed (PO) spend         -> ``scm.PurchaseOrderLine`` (SCM 4.1 owns it)
* the category axis            -> ``scm.ItemCategory`` via ``item.category`` passthrough, then
  ``procurement.SpendClassificationRule`` (this sub-module's rules entity), then "(Unclassified)"
* the maverick rate            -> ``procurement.MaverickSpendFinding`` (this sub-module)

The population definitions themselves — ``RECOGNISED_INVOICE_STATUSES``, ``SPEND_PO_STATUSES``,
``invoiced_line_window()``, ``committed_line_window()`` — are declared ONCE in
``models/SpendAnalyticsReporting/SpendClassificationRules.py`` and imported from there by the view
layer. There is deliberately no second copy here: two answers to "what is spend?" is the one defect
this sub-module cannot afford.

**No money is written and no ledger is touched (L29).** 6.14 posts no ``accounting.Bill``, no
``JournalEntry``, no ``Budget`` and no ``Payment``. Budget-vs-actual is 6.15, supplier scorecards
are 6.16, fraud patterns are 6.17, and the PO-based savings/cycle-time cube is already SCM 4.11
(``scm:spend_analytics``) — which the dashboard LINKS to rather than restating.
"""

#: Nothing to re-export. Stated explicitly so the Integrate phase's ``__init__`` block for this
#: sub-module skips this module rather than importing a name that was never here.
__all__ = []
