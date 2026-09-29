"""NavERP 8.7 Territory & Quota Management — the Sales-side layer over CRM 1.2's territory & quota.

**OWNERSHIP (L29/L36/L37) — the one thing to read before changing anything in this package.**
`crm.Territory` (`TER-`, `region`/`segment`/`parent` roll-up/`manager`) and `crm.SalesQuota` (`QTA-`,
`owner`/`territory`/`period_*`/`target_amount`) are **OWNED by CRM 1.2** and live in
`apps/crm/models/SalesForceAutomation/`. CRM shipped first, so CRM owns them. **Every model in this
package reaches a territory through a `ForeignKey("crm.Territory", ...)` and none of them declares a
second territory or quota master.** A `class Territory` or `class SalesQuota` under `apps/sales/`
would be a bug, not a variant — the parallel-schema failure L29/L37 exist to prevent. `QuotaPlan`
likewise extends 8.4's `sales.ForecastPeriod` and never re-spells year/quarter/month.

What 8.7 adds is the commercial layer CRM deliberately declined:

* `TerritoryRule` (`TRG-`) — the typed, tenant-configurable rule set that resolves *which territory*,
  a sibling of 8.1's `LeadRoutingRule` rather than a second rule engine.
* `AccountTerritoryAssignment` (`TAS-`) — the effective-dated assignment LEDGER, so an annual
  rebalance supersedes rather than overwrites and last March stays answerable.
* `TerritoryMember` (`TMB-`) — the coverage roster: hunter/farmer roles, SDR→AE pairing, overlay
  specialists, split percentages.
* `QuotaPlan` (`QPA-`) — the quota DERIVATION. It annotates a CRM quota with the method, baseline,
  growth, relief and uplift that produced it, and carries **no money column of its own**.

The four **boards** (`territory_rebalance_preview`, `territory_coverage_gap`,
`territory_performance`, `territory_white_space`) are pure functions over these tables plus CRM's and
SCM's — **no board table, no seeder row, no admin registration**, because a materialised board is a
*copy* that is either stale between runs or a second source of truth that falls out of date the
moment any input is edited outside it (L37: derive, don't remember).

Three rules run through all of it: **frozen evidence is never authorable** (every `editable=False`
field is off every form, L22), **all money arithmetic is `Decimal` in Python over a fetched set**,
never an `F()` expression — the SQLite integer-division trap silently drops fractional cents rather
than raising — and **8.7 posts no `JournalEntry`** (L29).
"""
from .AccountTerritoryAssignments import AccountTerritoryAssignment
from .QuotaPlans import PLAN_PARAMETER_KEYS, QuotaPlan
from .TerritoryMembers import TerritoryMember
from .TerritoryRules import (
    TERRITORY_FIELDS,
    TerritoryRule,
    validate_territory_conditions,
)

__all__ = [
    "TerritoryRule",
    "TERRITORY_FIELDS",
    "validate_territory_conditions",
    "AccountTerritoryAssignment",
    "TerritoryMember",
    "QuotaPlan",
    "PLAN_PARAMETER_KEYS",
]
