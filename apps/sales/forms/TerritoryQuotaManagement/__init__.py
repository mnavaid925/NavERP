"""Sales 8.7 Territory & Quota Management — the four entity forms.

**OWNERSHIP (L29/L36/L37) — the one thing to read before changing anything in this package.**
Every territory dropdown here reads `crm.Territory` and every quota dropdown reads
`crm.SalesQuota`; both are **owned by CRM 1.2** and live in
`apps/crm/models/SalesForceAutomation/`. **8.7 EXTENDS both by FK and declares NEITHER again.**
A `class Territory` or `class SalesQuota` under `apps/sales/` would be a bug, not a variant — the
parallel-schema failure L29/L37 exist to prevent. The same ruling is recorded in the models
package docstring and in the `LIVE_LINKS["8.7"]` comment in `apps/core/navigation.py`. Here it
shows up as a single, boring fact: **no form in this package declares a territory master or a
quota master** — they are all `apps.crm.models` reads.

Every form here inherits **`(TenantUniqueMixin, TenantModelForm)`**, in that order:

* `TenantModelForm` takes `tenant=` from the view and narrows every FK dropdown to it, so a form
  can only ever be pointed at this workspace's own rows.
* `TenantUniqueMixin` re-runs `validate_unique` with `tenant` put back INTO the exclusion set. A
  stock check cannot see a composite `(tenant, …)` UniqueConstraint, so without the mixin the
  list view 500s the moment a duplicate is submitted.

`tenant` is therefore **never a form field**. The view constructs the form as
`SomeForm(request.POST, tenant=request.tenant)` and `TenantUniqueMixin` writes that tenant onto
the instance — the same mechanism every other sub-module in this app uses.

**No frozen evidence is authorable (L22).** `last_run_at` / `last_run_matched_count` /
`assigned_by` / `submitted_by` / `submitted_at` / `approved_by` / `approved_at` / `calculated_at`
are `editable=False` on their models and appear in **no** `Meta.fields` here; `number` is
`editable=False` on the `TenantNumbered` base; and `QuotaPlan.status` is off the form **by
decision** — it is action-driven, moved only by the submit / approve / reject / lock POST views,
never typed.
"""
from .AccountTerritoryAssignments import AccountTerritoryAssignmentForm
from .QuotaPlans import QuotaPlanForm
from .TerritoryMembers import TerritoryMemberForm
from .TerritoryRules import TerritoryRuleForm

__all__ = [
    "TerritoryRuleForm",
    "AccountTerritoryAssignmentForm",
    "TerritoryMemberForm",
    "QuotaPlanForm",
]
