"""Sales 8.7 — Territory & Quota Management: the views sub-package.

Re-exports every 8.7 view so `apps.sales.views.__init__` and the URLconf can reach them by name,
and nothing else. Adding a view WITHOUT adding it here is an `AttributeError` at URLconf time, not
a warning (backend-package rule 3).

**The ownership ruling, recorded here as well as in the models package and `apps/core/navigation.py`:**

    `crm.Territory` / `crm.SalesQuota` are CRM 1.2's. 8.7 EXTENDS both by FK and declares NEITHER again.
    There is NO `class Territory` and NO `class SalesQuota` anywhere in `apps/sales` — a class by either
    name in this app is a **bug, not a variant**. A grep for `^class (Territory|SalesQuota)\b` under
    `apps\sales\models` must return zero hits at the Integrate step.

`territory_boards` reads `crm.Territory` and `crm.SalesQuota`. No view in this sub-module writes
either one: the quota amount is edited in CRM's form, by CRM's permission set (§0.3).

It also holds the ONE place 8.7 evaluates a rule against an account (`TerritoryBoards`), so the
preview board and the commit verb cannot disagree about which accounts a rule claims. It reuses
8.1's operator evaluator rather than forking it.
"""
from .AccountTerritoryAssignments import (
    account_territory_assignment_create,
    account_territory_assignment_delete,
    account_territory_assignment_detail,
    account_territory_assignment_edit,
    account_territory_assignment_list,
)
from .QuotaPlans import (
    quota_plan_approve,
    quota_plan_create,
    quota_plan_delete,
    quota_plan_detail,
    quota_plan_edit,
    quota_plan_list,
    quota_plan_lock,
    quota_plan_reject,
    quota_plan_submit,
)
from .TerritoryBoards import (
    territory_coverage_gap,
    territory_performance,
    territory_rebalance_preview,
    territory_white_space,
)
from .TerritoryMembers import (
    territory_member_create,
    territory_member_delete,
    territory_member_detail,
    territory_member_edit,
    territory_member_list,
)
from .TerritoryRules import (
    territory_rule_create,
    territory_rule_delete,
    territory_rule_detail,
    territory_rule_edit,
    territory_rule_list,
    territory_rule_run,
    territory_rule_toggle,
)

__all__ = [
    # Boards — read-only, no <int:pk> route, so nothing to shadow (§8.1).
    "territory_rebalance_preview",
    "territory_coverage_gap",
    "territory_performance",
    "territory_white_space",
    # Rules (§8.2). The two verbs are POST-only.
    "territory_rule_list",
    "territory_rule_create",
    "territory_rule_detail",
    "territory_rule_edit",
    "territory_rule_delete",
    "territory_rule_run",
    "territory_rule_toggle",
    # Assignments (§8.3).
    "account_territory_assignment_list",
    "account_territory_assignment_create",
    "account_territory_assignment_detail",
    "account_territory_assignment_edit",
    "account_territory_assignment_delete",
    # Members (§8.4).
    "territory_member_list",
    "territory_member_create",
    "territory_member_detail",
    "territory_member_edit",
    "territory_member_delete",
    # Quota plans (§8.5). The four verbs are POST-only.
    "quota_plan_list",
    "quota_plan_create",
    "quota_plan_detail",
    "quota_plan_edit",
    "quota_plan_delete",
    "quota_plan_submit",
    "quota_plan_approve",
    "quota_plan_reject",
    "quota_plan_lock",
]
