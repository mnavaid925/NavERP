"""SCM 4.18 Finance & Accounting Integration — the report entity declares NO FORMS. Deliberately.

The four pages this entity owns —
``templates/scm/finance/payables.html``, ``receivables.html``, ``budget_variance.html`` and
``landed_cost_variance.html`` — are READ-ONLY. Nothing on them is submitted: every control in their
filter bars is a ``GET`` parameter read straight off ``request.GET`` in the view and echoed back into
the widget, which is the same shape ``crud_list``'s own filter spec takes and needs no ``Form``
class to validate.

Two consequences worth stating so nobody "completes" this file later:

1. **A filter is not a form.** Every GET parameter these reports accept is guarded at the point of
   use — choice params are checked against their own ``*_CHOICES`` set, the two pk params go through
   ``as_db_int`` (L11: ``?budget=abc``, ``?budget=²`` and a 21-digit value must all SKIP the filter
   rather than raise out of ``.filter()``), and the two date params go through a local ``_as_date``
   that returns ``None`` on anything that is not ``YYYY-MM-DD``. Junk narrows nothing and returns
   200. Wrapping that in a ``forms.Form`` would add a layer without adding a guard.

2. **There is no export/CSV action in this pass, deliberately.** An export is a new surface (a
   different content type, its own row cap, its own tenant assertion on every column it writes) and
   it is not what the 4.18 NavERP.md bullets ask for. When it lands it gets its own view and its own
   review — not a hidden ``POST`` bolted onto a read-only report.

The sub-module's real forms are ``LandedCostVoucherForm`` / ``LandedCostChargeForm``
(``forms/FinanceIntegration/LandedCostVouchers.py``) and ``DutyTariffForm``
(``forms/FinanceIntegration/DutyTariffs.py``). ``LandedCostAllocation`` has no form either — every
one of its columns is ``editable=False`` and ``LandedCostVoucher.allocate()`` is its only writer.
"""
#: Explicitly empty, and there is deliberately NO ``from apps.scm.forms._common import *`` here —
#: this module declares no form, so importing the toolkit would be dead weight that also re-exports
#: ``TenantModelForm`` and friends under this module's name. The ``apps/scm/forms/__init__.py``
#: re-export block has nothing to take from here.
__all__ = []
