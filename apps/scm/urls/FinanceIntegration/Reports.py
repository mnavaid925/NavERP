"""SCM 4.18 Finance & Accounting Integration — report URL patterns (computed, no CRUD, no models).

Four flat routes. No ``<int:pk>``, no verbs, no POST endpoint, and NO greedy ``<str:...>`` converter —
4.10's ``return-tracking/<str:token>/`` and 4.16's ``portal-documents/<str:token>/`` remain the only
two in the whole app.

--------------------------------------------------------------------------------------------------
COLLISION CHECK — against the WHOLE concatenated ``apps/scm/urls`` urlconf, not just this module
--------------------------------------------------------------------------------------------------
Django resolves first-match-wins over the concatenation of every entity module's ``urlpatterns``, so
a route is only safe once it has been checked against all of them.

* **Path prefixes.** Nothing anywhere in ``apps/scm/urls/`` starts with ``finance``. Near neighbours
  that were checked rather than assumed: 4.6's ``freight-invoices/``, 4.1's ``goods-receipts/``,
  4.17's ``billing-runs/``.
* **``landed-cost-variance/`` cannot shadow (or be shadowed by) 4.18's own
  ``landed-cost-vouchers/`` and ``landed-cost-charges/``.** Django matches WHOLE path components and
  never splits one at a hyphen, so these are three distinct first segments, not a shared
  ``landed-cost/`` parent with three children. **None of the three may ever be "tidied" into a
  ``landed-cost/<something>/`` parent** — that would introduce exactly the shared-prefix ordering
  problem this layout avoids, and would break every ``{% url %}`` and ``reverse()`` already written
  against them.
* **View names**, checked against the FLAT ``scm:`` namespace (every sub-module's report names share
  it). The shipped report names are ``valuation_report``, ``reorder_alerts``, ``cold_storage_report``,
  ``cold_chain_compliance_report``, ``labor_board``, ``sparepart_list``, ``logistics_kpis``,
  ``client_inventory_report``, ``client_space_report``, ``mrp_report``, ``coa_report``,
  ``carbon_footprint_report``, ``asset_depreciation_report``, ``safety_stock_report`` and
  ``forecast_accuracy_report``. ``finance_payables``, ``finance_receivables``,
  ``finance_budget_variance`` and ``landed_cost_variance`` collide with none of them.

All four are ``@login_required`` STAFF pages (L32) and all four are read-only — there is no delete,
no verb and nothing here that needs ``@require_POST``.
"""
from django.urls import path

# ABSOLUTE, and the package rather than the module: `views.<name>` resolves through the
# `apps/scm/views/__init__.py` re-export block, which the Integrate phase adds these four views to.
from apps.scm import views


urlpatterns = [
    path("finance-payables/", views.finance_payables, name="finance_payables"),
    path("finance-receivables/", views.finance_receivables, name="finance_receivables"),
    path("finance-budget-variance/", views.finance_budget_variance,
         name="finance_budget_variance"),
    path("landed-cost-variance/", views.landed_cost_variance, name="landed_cost_variance"),
]
