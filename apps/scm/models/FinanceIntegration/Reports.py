"""SCM 4.18 Finance & Accounting Integration — the report entity declares NO MODELS. Deliberately.

--------------------------------------------------------------------------------------------------
WHY THIS FILE IS EMPTY OF MODELS (L29 — the second-source-of-truth rule)
--------------------------------------------------------------------------------------------------
Three of 4.18's five NavERP.md bullets — **Accounts Payable**, **Accounts Receivable** and
**Budgeting** — are delivered as READ-ONLY COMPUTED REPORTS over tables that already shipped. There
is no ``ScmPayable``, no ``ScmReceivable`` and no ``ScmBudget`` here, and adding one later is a
defect, not a feature:

* **Accounts Payable** already exists three times over as a *pointer*, not a copy —
  ``scm.GoodsReceiptNote.bill`` (4.1's three-way match), ``scm.FreightInvoice.bill`` (4.6's freight
  audit) and ``scm.LandedCostVoucher.bill`` (4.18's own hand-off). All three FK the SAME
  ``accounting.Bill``. The payables report is the union of those three pointers; a fourth table
  holding its own copy of "what we owe" would drift from ``accounting.Bill`` the first time AP voided
  something in Module 2.
* **Accounts Receivable** is likewise ``scm.SalesOrder.invoice`` (4.5), ``scm.ClientBillingRun.invoice``
  (4.17) and ``scm.ReturnAuthorization.credit_note`` (4.10), all pointing at ``accounting.Invoice``.
* **Budgeting** is ``accounting.Budget`` / ``accounting.BudgetLine``, whose ``org_unit`` FK to
  ``core.OrgUnit`` IS the supply-chain department dimension. 4.1's
  ``PurchaseRequisition.budget_check()`` already reads it as a *view-time* check rather than a stored
  encumbrance, for exactly this reason. The budget-variance report extends that posture to the whole
  module; it stores nothing.

The one thing 4.18 genuinely could not reuse is a customs master — ``accounting.TaxCode`` has
``TAX_TYPE_CHOICES`` of sales/vat/gst/use with no customs member, no ``hs_code`` and no
origin-country pair — so ``DutyTariff`` is a real table in
``apps/scm/models/FinanceIntegration/DutyTariffs.py``. Sales/VAT/GST stays ``accounting.TaxCode`` and
is FK'd, never re-declared. The landed-cost trio (``LandedCostVoucher`` / ``LandedCostCharge`` /
``LandedCostAllocation``) lives in ``LandedCostVouchers.py``. Between them those two files are the
whole of 4.18's schema; this file adds nothing to it and contributes no migration rows.

--------------------------------------------------------------------------------------------------
THE ACCOUNTING BOUNDARY (repeated verbatim, as the package contract requires)
--------------------------------------------------------------------------------------------------
**SCM POSTS NO JournalEntry. draft_bill() creates a DRAFT accounting.Bill and stops; accounting posts
the entry.**

Everything after that draft — approval, tax treatment, payment, aging, the journal itself — belongs
to ``apps/accounting``. The four report views in ``apps/scm/views/FinanceIntegration/Reports.py``
only READ; not one of them writes a row of any kind, in scm or in accounting.

--------------------------------------------------------------------------------------------------
FOLDER-NAME ASYMMETRY — DO NOT "FIX" IT
--------------------------------------------------------------------------------------------------
The backend package is ``FinanceIntegration/`` while the template folder is ``templates/scm/finance/``
— that asymmetry IS the house rule (every shipped scm template folder uses a short slug:
``3pl/``, ``portal/``, ``coldchain/``, ``srm/``, …). Renaming ``templates/scm/finance/`` to
``financeintegration/`` would break every ``render()`` in this sub-module.
"""
#: Explicitly empty, and there is deliberately NO ``from apps.scm.models._base import *`` here —
#: every other entity module in this package needs the toolkit to declare fields, and this one
#: declares none, so importing it would be dead weight that also re-exports ``_base``'s names under
#: this module. The ``apps/scm/models/__init__.py`` re-export block has nothing to take from here.
#:
#: If you are here to add a model, re-read the L29 section above first: AP, AR and Budget are
#: pointers into ``apps/accounting``, not tables of our own.
__all__ = []
