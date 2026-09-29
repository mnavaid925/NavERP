# FROZEN BUILD CONTRACT — Sales 8.7 · Territory & Quota Management

**App:** `sales` (EXTENDING an existing app — 8.1–8.6 are live)
**Sub-module slug:** `TerritoryQuotaManagement` (packages) / `territoryquotamanagement` (templates)
**Migration:** `0013` (incremental; the leaf today is `0012_orderamendment_orderamendmentline_and_more.py`)
**Source of truth:** `.claude/tasks/todo.md` lines 11–709 (the `### 8.7` block), written from
`.claude/tasks/research-sales-8.7.md` (Phase 1, 583 lines).
**Scope:** 4 models + 4 derived read-only boards. Prefixes `TRG` / `TAS` / `TMB` / `QPA`.

**NO scaffold step. NO `config/settings.py` edit. NO `config/urls.py` edit.**

Status: **FROZEN / READ-ONLY.** An implementer follows this file without re-reading the plan.
No file outside this one is written by the spec phase.

---

## 0. THE OWNERSHIP RULING — read before writing a single line (L29 / L36 / L37)

**This is not a variant question and it is not negotiable.**

`crm.Territory` (`NUMBER_PREFIX = "TER"`, `apps/crm/models/SalesForceAutomation/Territories.py:14`) and
`crm.SalesQuota` (`NUMBER_PREFIX = "QTA"`, `…/SalesForceAutomation/SalesQuotas.py:9`) are **CRM 1.2's**.
They are load-bearing today:

| CRM model | Already carries (do not disturb) |
|---|---|
| `crm.Territory` | `sales_routing_rules` (`LeadRoutingRule.territory`) · `sales_forecast_submissions` (`ForecastSubmission.territory`) · `sales_quotas` (`SalesQuota.territory`) |
| `crm.SalesQuota` | `owner` · `territory` · `period_type` · `period_year` · `period_number` · `target_amount` · `notes` |

**8.7 EXTENDS both by FK and declares NEITHER again.**

### 0.1 There is NO `class Territory` and NO `class SalesQuota` anywhere in `apps/sales`

A class by either name in this app is a **bug, not a variant** — it is exactly the parallel-schema
failure L29/L36/L37 exist to prevent. `sales.SalesTerritory` / `sales.TerritoryQuota` / a
private-territory `TerritoryMember` host are **the same bug wearing a hat**.

**The grep that must return ZERO hits (run at the Integrate step):**

```
Select-String 'apps\sales\models\TerritoryQuotaManagement\*.py' -Pattern '^class (Territory|SalesQuota)\b'
```

**Two further proof checks (8.7-10):**

1. A sweep for `NUMBER_PREFIX = "TER"` / `NUMBER_PREFIX = "QTA"` under `apps\sales` → **zero hits**.

2. `venv\Scripts\python.exe manage.py check` → **no `fields.E304` / `fields.E305`** reverse-accessor
   clash raised by any of the ten new `related_name`s.

### 0.2 The ruling is recorded in exactly THREE durable places

| # | Durable place | What it must carry |
|---|---|---|
| 1 | `apps/sales/models/TerritoryQuotaManagement/__init__.py` **module docstring** | the "no `class Territory` here" sentence, verbatim |
| 2 | the `LIVE_LINKS["8.7"]` **comment** in `apps/core/navigation.py` | the same ownership ruling |
| 3 | `.claude/tasks/lessons.md` | the ruling as a codified lesson |

The sentence repeated verbatim in (1) and (2):

> `crm.Territory` / `crm.SalesQuota` are CRM 1.2's. 8.7 EXTENDS both by FK and declares NEITHER again.
> There is NO `class Territory` and NO `class SalesQuota` anywhere in `apps/sales` — a class by either
> name in this app is a **bug, not a variant**. A grep for `^class (Territory|SalesQuota)\b` under
> `apps\sales\models` must return zero hits at the Integrate step.

### 0.3 Read / write posture (the same rule in three more words)

* 8.7 **reads** `crm.Territory` / `crm.SalesQuota` and **never writes** them. `QuotaPlan` records *how*
  a quota was derived; **the amount itself is edited on the CRM quota, in CRM's form, by CRM's
  permission set.** `ForecastSubmission.quota_amount` already snapshots by value for exactly this
  reason — honour that posture.
* Every 8.7 FK to `crm.Territory` / `crm.SalesQuota` is declared **by string** (`'crm.Territory'`),
  **never** by a module-scope class import where a cycle is possible.
* `QuotaPlan` does **NOT** re-spell year / quarter / month. `forecast_period` FKs
  `sales.ForecastPeriod` (8.4) and the plan inherits the window, the type vocabulary and the reporting
  currency from it.

### 0.4 Repo facts this contract relies on (re-verified by grep at plan time — L28)

| Claim | Verified fact |
|---|---|
| Base class | `apps\sales\models\_base.py` — `TenantOwned` = `tenant` FK(`core.Tenant`, CASCADE, `related_name="+"`, `db_index=True`) + `created_at` + `updated_at`; `TenantNumbered` adds `NUMBER_PREFIX` + `number = CharField(max_length=20, editable=False)`. **Base for all four models.** |
| CRM ownership | `Territories.py:14` `NUMBER_PREFIX = "TER"`; `SalesQuotas.py:9` `NUMBER_PREFIX = "QTA"` |
| Next migration | leaf today is `0012_orderamendment_orderamendmentline_and_more.py` → **8.7 claims `0013`** |
| Prefix collisions | sweep of `NUMBER_PREFIX` across `apps\*\*\models\**\*.py`: `TRG`, `TAS`, `TMB`, `QPA` → **zero hits, all four free** |
| `related_name` collisions | `sales_territory_rules`, `sales_account_assignments`, `generated_assignments`, `sales_territory_assignments`, `sales_territory_assignments_made`, `sales_members`, `sales_territory_memberships`, `sales_paired_territory_members`, `sales_quota_plans`, `quota_plans` → **zero hits, free today**. ⚠️ **Re-verify all ten with `manage.py check` at Integrate, not at spec (L43: a parallel session can take one first).** |
| `sales:` url prefixes in use | `account-classifications, account-plans, accounts, account-stakeholders, approval-rules, bundles, enrichment-events, forecast, leads, nurture-enrollments, opportunity, overview, qualifications, quotes, routing-rules, score-events` — **every 8.7 prefix is free** |
| 8.7 packages absent | `models/TerritoryQuotaManagement` · `forms/…` · `views/…` · `urls/…` · `templates/sales/territoryquotamanagement` → all **False**. Nothing to overwrite. |
| 8.3 board-name collision | `name="account_coverage"` / `name="account_white_space"` **already exist** in `apps/sales/urls/ContactAccountManagement/AccountBoards.py`. 8.7's boards are **territory**-scoped, take **different** url names, and **must not modify 8.3's files** (research §5.10). |
| `ForecastPeriod` guard | `ForecastPeriods.py:194-203` `_optional_sales_model` guards `ForecastSubmission` + `ForecastScenario` **by name only** — it does **not** know `QuotaPlan`, so a `PROTECT` delete raises a raw `IntegrityError`. **Accepted this pass (research §5.7 option (a)); the fix is a surgical edit to 8.4's file and therefore an L43-gated follow-up.** |
| Badge classes | exactly `.badge-amber .badge-green .badge-info .badge-muted .badge-red .badge-slate` exist. **`badge-success` / `badge-warning` / `badge-danger` DO NOT EXIST — never emit them.** |
| Single-writer files | `apps\sales\admin.py` and `seed_sales.py` (1,377 lines) are **main-session-only** (L43). 8.7 appends surgically; it never rewrites. |
| `territories/` prefix | CRM already serves `territories/` under the **`crm:`** namespace (`crm:territory_list`). The 8.7 `territories/` prefix is a **different namespace** and is **free under `sales:`**. Re-verify at Integrate alongside the `related_name` sweep. |

---

## 1. NON-GOALS (8.7-0) — pinned so a later pass cannot "helpfully" add them

Each is a deliberate decline in the research with a named future owner. **Adding one is a regression
against that owner, not an improvement.**

| # | Non-goal | Owner / note |
|---|---|---|
| 1 | **NO geospatial anything** — no map rendering, no drive-time / distance balancing, no shapefile import, no routing engine | stays a third-party tool that writes into `AccountTerritoryAssignment(assignment_source="manual")` (research §4.1) |
| 2 | **NO design-time territory store** — no proposed territories, no parallel hierarchy, no scenario sandbox | a proposal persists as `AccountTerritoryAssignment` rows with a **future** `effective_from`; the "see it before you commit" value is `territory_rebalance_preview` (§4.2) |
| 3 | **NO quota distribution cube** — no quota × product × account × period grid | 8.7 ships `allocation_basis` + `parameters`; the cube is a planning grid, not an ERP entity (§4.3) |
| 4 | **NO quota phasing / seasonality factor tables** | the weights live in `QuotaPlan.parameters`; a reusable factor library is **8.19 Master Data** (§4.4) |
| 5 | **NO open-headcount / position planning, NO cost-per-position** | (§4.5) |
| 6 | **NO incentive compensation, commission, payout, or deal-credit attribution** | **8.10** owns all of it; 8.7 must not store a "credit" figure (§4.6) |
| 7 | **NO scheduled / background jobs** | the "Run Allocation" verb is a POST view; the scheduler is `core.JobScheduler` under **8.17 / 8.18** (§4.7) |
| 8 | **NO round-robin / load-balancing engine** | `LeadRoutingRule.assignment_mode` + the routing engine in `apps/sales/services.py` own it — **8.1**. 8.7 resolves *which territory*; 8.1 resolves *which rep*. This is the single most likely place for 8.7 to fork 8.1's engine, so it is named here (§4.8). |
| 9 | **NO account hierarchy, stakeholder maps, account plans, account-level white space, health scores** | **8.3** owns these, including `sales:account_coverage` and `sales:account_white_space` (§4.9) |
| 10 | **NO forecast submissions / categories / adjustments / scenarios / accuracy** | **8.4** (§4.10) |
| 11 | **NO territory price lists, NO territory-scoped row-level security** | pricing is **8.5**; visibility policy is Module 0 `core`. 8.7 stores the assignment; it does not implement visibility (§4.11, §4.13) |
| 12 | **NO customer / account / opportunity / sales-order master** | `core.Party`, `crm.Opportunity`, `scm.SalesOrder` (§4.12) |
| 13 | **The four boards get NO table, NO seeder row, NO admin registration** | a board is a pure function of tables that already have owners. `8.4 ForecastBoards.py` and `8.3 AccountBoards.py` are the precedent — 8.7 is the third module in a row to make this call (§3.2) |

---

## 2. BACKEND LAYOUT (8.7-1) — the MANDATORY package structure

`apps/sales` is a Python-package app; 8.7 adds one sub-module folder per layer and one file per entity.
**Every file is its own commit — ONE FILE PER COMMIT, PowerShell-safe (`;` separator, never `&&`).**

```
apps/sales/models/TerritoryQuotaManagement/__init__.py        docstring records the OWNERSHIP ruling VERBATIM
                                                                 + re-exports all four models + __all__
apps/sales/models/TerritoryQuotaManagement/TerritoryRules.py           TerritoryRule, TERRITORY_FIELDS,
                                                                 validate_territory_conditions,
                                                                 SEGMENT_TYPE_CHOICES, ALIGNMENT_TYPE_CHOICES,
                                                                 ASSIGNMENT_SCOPE_CHOICES, MATCH_MODE_CHOICES
apps/sales/models/TerritoryQuotaManagement/AccountTerritoryAssignments.py  AccountTerritoryAssignment,
                                                                 ASSIGNMENT_SOURCE_CHOICES
apps/sales/models/TerritoryQuotaManagement/TerritoryMembers.py          TerritoryMember, MEMBER_ROLE_CHOICES,
                                                                 ASSIGNMENT_TYPE_CHOICES
apps/sales/models/TerritoryQuotaManagement/QuotaPlans.py                QuotaPlan, METHOD_CHOICES,
                                                                 ALLOCATION_BASIS_CHOICES, BASELINE_SOURCE_CHOICES,
                                                                 TARGET_TYPE_CHOICES, PHASING_CHOICES, FROZEN_STATES

---

## 3. MODEL (1) — `TerritoryRule` — `TRG` — `TerritoryRules.py`

Serves bullet 1 (territory-model type + the industry / account-size / named-account axes) and bullet 2
(the typed assignment rule set). **Mirrors `apps/sales/models/LeadManagement/LeadRoutingRules.py` field
for field in shape. DO NOT WRITE A SECOND RULE ENGINE.**

* `class TerritoryRule(TenantNumbered)`, `NUMBER_PREFIX = "TRG"`.
* Base supplies: `tenant` (FK `core.Tenant`, CASCADE, `related_name="+"`, `db_index=True`),
  `created_at`, `updated_at`, `number = CharField(max_length=20, editable=False)`.

### 3.1 CHOICES — verbatim

```python
SEGMENT_TYPE_CHOICES = [("geographic","Geographic"),("industry","Industry"),("account_size","Account Size"),("product_line","Product Line"),("named_account","Named Account"),("mixed","Mixed")]

ALIGNMENT_TYPE_CHOICES = [("primary","Primary"),("secondary","Secondary"),("overlay","Overlay")]

ASSIGNMENT_SCOPE_CHOICES = [("exact","This Territory Only"),("subtree","This Territory And Children")]

# IMPORTED from LeadRoutingRule, NEVER re-spelled:
MATCH_MODE_CHOICES = LeadRoutingRule.MATCH_MODE_CHOICES
# as-built value: [("all","All conditions"), ("any","Any condition")]
```

* `segment_type` **IS the territory-model-type declaration** — research §5.1 rules *infer*, so 8.7 needs
  **zero** change to `crm.Territory`. A territory is geographic because its active rules are geographic.
* `ALIGNMENT_TYPE_CHOICES` defined here is the **single source of truth**; `AccountTerritoryAssignment`
  reuses it verbatim rather than re-spelling it.

### 3.2 Reused verbatim from `LeadRoutingRules.py` — do NOT re-invent

`ROUTING_OPERATORS`, `MAX_ROUTING_CONDITIONS = 20`, `MAX_ROUTING_JSON_BYTES = 16 * 1024`,
`_reject_json_constant`, `_is_scalar`, and the whole body-shape of `validate_routing_conditions` — a list
of `{field, operator, value}` dicts **and nothing else**, the empty-rule-requires-`is_catch_all` rule, and
the two caps. (`ROUTING_OPERATORS` as-built = `{"eq","ne","in","not_in","contains","icontains","gt","gte","lt","lte","is_set","is_empty"}`.)

### 3.3 `TERRITORY_FIELDS` — a NEW closed allow-list

Mirrors how `ROUTING_FIELDS` is closed, over the entities the evaluator actually reads:

```python
TERRITORY_FIELDS = {"industry", "annual_revenue", "employee_count", "tier",
                    "lifecycle_stage", "country", "city", "state", "postal_code",
                    "is_named_account", "has_open_opportunity", "account_name"}
```

Sources: `crm.AccountProfile.industry / .annual_revenue / .employee_count / .address_country /
.address_city / .address_state / .address_postal_code`; `sales.AccountClassification.tier /
.lifecycle_stage`; a `crm.Opportunity` open-deal probe; `core.Party.name`.

### 3.4 `validate_territory_conditions(value, is_catch_all=False)`

**Same shape and same caps as `validate_routing_conditions`**; the only difference is the allow-list it
checks `field` against. It is a *sibling*, not a second engine: **import and reuse** the caps, the
constant rejector and the scalar predicate rather than duplicating them.

### 3.5 Fields — the COMPLETE list, in `Meta.ordering` order

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(max_length=160)` | `unique_together("tenant","name")` |
| `description` | `TextField(blank=True)` | |
| `segment_type` | `CharField(max_length=20, choices=SEGMENT_TYPE_CHOICES, default="geographic")` | **this IS the territory-model-type declaration** |
| `match_mode` | `CharField(max_length=8, choices=MATCH_MODE_CHOICES, default="all")` | |
| `conditions` | `JSONField(default=list)` | validated by `validate_territory_conditions` |
| `is_catch_all` | `BooleanField(default=False)` | |
| `alignment_type` | `CharField(max_length=8, choices=ALIGNMENT_TYPE_CHOICES, default="primary")` | |
| `assignment_scope` | `CharField(max_length=10, choices=ASSIGNMENT_SCOPE_CHOICES, default="exact")` | |
| `target_territory` | `FK("crm.Territory", SET_NULL, null=True, blank=True, related_name="sales_territory_rules")` | **required by `clean()`** even though the column is nullable |
| `is_active` | `BooleanField(default=True)` | |
| `priority` | `PositiveIntegerField(default=100, validators=[MinValueValidator(1)])` | lower wins |
| `effective_from` | `DateField(default=timezone.localdate)` | |
| `effective_to` | `DateField(null=True, blank=True)` | `None` = open-ended |
| `last_run_at` | `DateTimeField(null=True, blank=True, editable=False)` | **FROZEN EVIDENCE — off every form (L22)** |
| `last_run_matched_count` | `PositiveIntegerField(null=True, blank=True, editable=False)` | **FROZEN EVIDENCE — off every form (L22)** |

### 3.6 `class Meta`

`ordering = ["priority", "id"]` · `unique_together = ("tenant", "name")` · indexes
`(tenant, is_active, priority)` and `(tenant, segment_type)`.

### 3.7 `clean()` — every rule, in Python

Each `ValidationError` is keyed to a **real form field**:

1. `target_territory` is set — a rule assigns **to** a territory; "no territory" is a coverage **gap**,
   not a rule outcome — and is same-tenant.
2. Every condition `field` is in `TERRITORY_FIELDS`.
3. Every condition `operator` is in `ROUTING_OPERATORS`.
4. `effective_to >= effective_from`.
5. `segment_type == "named_account"` may **NOT** carry `conditions` — named accounts are hand-picked,
   and that is what makes them named (research §2 row 1.4).

### 3.8 Frozen evidence is never authorable

`last_run_at` / `last_run_matched_count` are `editable=False`, which auto-excludes them from every
`ModelForm` (L22). They are written **only** by the `territory_rule_run` POST view, **inside the same
transaction that writes the assignment rows**.

### 3.9 Computed properties

**None.** `TerritoryRule` declares no `@property` and no stored-method. Anything a template shows beyond
the fields above is a **view-computed** context key (§7), never a model method.

apps/sales/forms/TerritoryQuotaManagement/{TerritoryRules,AccountTerritoryAssignments,TerritoryMembers,QuotaPlans}.py + __init__.py
apps/sales/views/TerritoryQuotaManagement/{TerritoryRules,AccountTerritoryAssignments,TerritoryMembers,QuotaPlans,TerritoryBoards}.py + __init__.py
apps/sales/urls/TerritoryQuotaManagement/{TerritoryRules,AccountTerritoryAssignments,TerritoryMembers,QuotaPlans,TerritoryBoards}.py + __init__.py
```

* Imports inside the packages are **ABSOLUTE** (`from apps.sales.models import …`). Entity modules pull
  the toolkit from `models/_base.py` / `forms/_common.py` / `views/_common.py` via `import *`. A relative
  `from .models import X` resolves one level too deep.
* Template folders are **LOWERCASE with no underscore** (matches as-built `forecastperiod/`,
  `accountstakeholder/`) and the page is the **bare filename**. **Never** a flat
  `territoryrule_list.html`.


---

## 4. MODEL (2) — `AccountTerritoryAssignment` — `TAS` — `AccountTerritoryAssignments.py`

Serves bullet 1 (named-account territory), bullet 2 (the explicit ledger, coverage gaps, rebalance
commit) and bullet 5 (the input to every derived board).

* `class AccountTerritoryAssignment(TenantNumbered)`, `NUMBER_PREFIX = "TAS"`.

### 4.1 CHOICES — verbatim

```python
ASSIGNMENT_SOURCE_CHOICES = [("manual","Manual"),("rule","Assignment Rule"),("named_account","Named Account"),("inherited","Inherited From Parent")]

# alignment_type reuses TerritoryRule.ALIGNMENT_TYPE_CHOICES VERBATIM — never re-spelled:
alignment_type = models.CharField(max_length=8, choices=TerritoryRule.ALIGNMENT_TYPE_CHOICES, default="primary")
```

### 4.2 Fields — the COMPLETE list

| Field | Type | Notes |
|---|---|---|
| `account` | `FK("core.Party", PROTECT, related_name="sales_territory_assignments")` | **No new customer table (L29).** `kind="organization"` enforced in `clean()`. |
| `territory` | `FK("crm.Territory", SET_NULL, null=True, blank=True, related_name="sales_account_assignments")` | **`SET_NULL` ON PURPOSE** — matches `crm.Opportunity.territory` and `crm.SalesQuota.territory` exactly, so deleting a territory orphans assignments rather than cascading away a book's worth of coverage history. `territory_coverage_gap` surfaces the orphans explicitly instead of hiding them (research §5.6). |
| `rule` | `FK("sales.TerritoryRule", SET_NULL, null=True, blank=True, related_name="generated_assignments")` | |
| `owner` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_territory_assignments")` | the rep holding it |
| `alignment_type` | `CharField(max_length=8, choices=TerritoryRule.ALIGNMENT_TYPE_CHOICES, default="primary")` | |
| `assignment_source` | `CharField(max_length=16, choices=ASSIGNMENT_SOURCE_CHOICES, default="manual")` | |
| `effective_from` | `DateField(default=timezone.localdate)` | |
| `effective_to` | `DateField(null=True, blank=True)` | `None` = current |
| `notes` | `TextField(blank=True)` | |
| `assigned_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="sales_territory_assignments_made")` | **FROZEN EVIDENCE — off every form (L22)** |

### 4.3 `class Meta`

`unique_together = ("tenant", "account", "territory")` · indexes `(tenant, account)`,
`(tenant, territory, alignment_type)`, `(tenant, effective_to)`.

**`Meta.ordering` is not pinned by the plan** — see §12 OPEN.

### 4.4 `_relation_belongs_to_tenant(self, field_name)`

The exact helper from `OpportunityTeams.py:56-65` / `OrderValidationRules.py:319`:
**one FK, one check.** Do not write a variant.

### 4.5 `clean()` — every rule, in Python

1. `account` is a same-tenant `core.Party` with `kind="organization"`.
2. `territory`, `rule`, `owner` and `assigned_by` are all same-tenant via `_relation_belongs_to_tenant`.
3. `effective_to >= effective_from`.
4. **At most ONE active `alignment_type="primary"` row per account** across the tenant
   (active = `effective_to IS NULL`, excluding `self.pk`).
5. **`assignment_source="rule"` REQUIRES a `rule`; the other three FORBID one.** A row reaching `save()`
   with `rule` set and `assignment_source="manual"` is the shape that makes an audit trail lie about how
   an account was assigned.


### 4.6 Computed properties

**None declared.** The "is this assignment current?" question is answered in the view, not on the model —
the list filter `coverage_choices` (`current` / `expired` / `all`) and the `unassigned_rows` /
`over_assigned_rows` boards derive it from `effective_to IS NULL` in Python.


---

## 5. MODEL (3) — `TerritoryMember` — `TMB` — `TerritoryMembers.py`

Serves bullet 4 in full (hunter/farmer, SDR/AE pairing, overlay specialists, split percentages) plus the
team roll-up read side of bullet 3 row 3.4. **This table genuinely does not exist yet:** `crm.Territory.manager`
is a *single* manager and cannot express a team.

* `class TerritoryMember(TenantNumbered)`, `NUMBER_PREFIX = "TMB"`.

### 5.1 CHOICES — verbatim

```python
MEMBER_ROLE_CHOICES = [("hunter","Hunter / New Business"),("farmer","Farmer / Existing Business"),("sdr","SDR / Business Development"),("ae","Account Executive"),("overlay_specialist","Overlay Specialist"),("sales_engineer","Sales Engineer")]

ASSIGNMENT_TYPE_CHOICES = [("direct","Direct Coverage"),("shared","Shared / Split Coverage"),("overlay","Overlay Coverage")]
```

**`manager` is deliberately NOT a `member_role` value.** `crm.Territory.manager` is CRM's single
accountable manager; a second management field here is a second source of truth for the same fact. **This
is the whole "a member list is not a board" answer to bullet 4 — the model carries coverage membership
only.**

### 5.2 Fields — the COMPLETE list

| Field | Type | Notes |
|---|---|---|
| `territory` | `FK("crm.Territory", CASCADE, related_name="sales_members")` | **`CASCADE`** — unlike the assignment, a membership in a deleted territory is meaningless |
| `user` | `FK(settings.AUTH_USER_MODEL, CASCADE, related_name="sales_territory_memberships")` | must be **active** |
| `member_role` | `CharField(max_length=20, choices=MEMBER_ROLE_CHOICES)` | **NO default** — a member must declare its role |
| `assignment_type` | `CharField(max_length=12, choices=ASSIGNMENT_TYPE_CHOICES, default="direct")` | |
| `coverage_split_pct` | `DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"), validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))])` | |
| `paired_user` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_paired_territory_members")` | SDR→AE. **A nullable FK is the whole feature — do not build a pairing *graph*.** |
| `is_primary` | `BooleanField(default=True)` | |
| `effective_from` | `DateField(default=timezone.localdate)` | |
| `effective_to` | `DateField(null=True, blank=True)` | |
| `notes` | `CharField(max_length=255, blank=True)` | |

### 5.3 `class Meta`

`unique_together = ("tenant", "territory", "user", "member_role")` · indexes `(tenant, user)` and
`(tenant, territory, is_primary)`. **`Meta.ordering` is not pinned by the plan** — see §12 OPEN.

### 5.4 `clean()` — every rule, in Python

1. `territory`, `user`, `paired_user` are same-tenant.
2. `user` is **active** — mirrors `LeadRoutingRule.clean`'s `default_owner` / `fallback_owner` check.
   Message (verbatim): `"Choose an active user from this workspace."`
3. `paired_user`, if set, is same-tenant, **is not equal to `user`**, and its `member_role` must be
   `"ae"` — a pairing is SDR→AE, and saying so in the validator is cheaper than saying it in prose.
4. `effective_to >= effective_from`.
5. **The `coverage_split_pct` of the `direct` members on one territory sums to EXACTLY 100 when any
   sibling has `assignment_type="shared"`.**

### 5.5 The split sum is `Decimal` in PYTHON over the fetched sibling rows — NEVER `Sum()` in SQL

The SQLite integer-division trap **drops fractional cents silently instead of raising**, so a SQL
`Sum("coverage_split_pct")` comparison is a **wrong answer, not a slow one**. Enforce the sum **only when a
`shared` sibling exists**, so the common single-rep `direct` case costs nothing (research §5.9).

### 5.6 `paired_user` is `SET_NULL` — orphaning is accepted and intended

Deleting/deactivating the AE silently orphans the pairing. An orphaned SDR is allowed, and
`territory_coverage_gap` **shows** it rather than hiding it (research §5.9).

### 5.7 Overlays are NOT a second territory subtree

An overlay is `AccountTerritoryAssignment(alignment_type="overlay")` **plus** a
`TerritoryMember(member_role="overlay_specialist")` against the **base** territory. SAP's own finding —
"overlay quotas don't roll up with base territory quotas" — is reproduced by the **data shape**, not by a
second hierarchy (research §2 row 4.4).

### 5.8 Computed properties

**None declared.** `is_frozen` (True when `effective_to` has passed) is a **view-computed** context key
(§9.8), not a model method.


---

## 6. MODEL (4) — `QuotaPlan` — `QPA` — `QuotaPlans.py`

Serves bullet 3 in full. **Extends `crm.SalesQuota` AND `sales.ForecastPeriod` by FK — owns neither.**

* `class QuotaPlan(TenantNumbered)`, `NUMBER_PREFIX = "QPA"`.

### 6.1 CHOICES and constants — verbatim

```python
METHOD_CHOICES = [("top_down","Top-Down"),("bottom_up","Bottom-Up")]

ALLOCATION_BASIS_CHOICES = [("historical_revenue","Historical Revenue"),("pipeline","Open Pipeline"),("account_count","Account Count"),("territory_potential","Territory Potential"),("manual","Manual")]

BASELINE_SOURCE_CHOICES = [("previous_period","Previous Period"),("previous_year","Previous Year"),("custom","Custom")]

# IMPORTED from ForecastSubmission, NEVER re-spelled:
STATUS_CHOICES = ForecastSubmission.STATUS_CHOICES   # draft|submitted|approved|rejected|locked

TARGET_TYPE_CHOICES = [("revenue","Revenue"),("units","Units"),("bookings","Bookings")]

PHASING_CHOICES = [("equal","Equal"),("seasonal","Seasonal")]

FROZEN_STATES = frozenset({"approved", "locked"})
```

`FROZEN_STATES` is **the same constant name and meaning** as `ForecastSubmission.FROZEN_STATES`. The form
disables every field in these states **and the views re-check server-side**, so hiding the Edit button is
never the only guard (research §5.5, R9).


### 6.2 Fields — the COMPLETE list

| Field | Type | Notes |
|---|---|---|
| `quota_ref` | `FK("crm.SalesQuota", PROTECT, related_name="sales_quota_plans")` | **CRM 1.2's. 8.7 NEVER writes `target_amount`.** |
| `forecast_period` | `FK("sales.ForecastPeriod", PROTECT, related_name="quota_plans")` | **8.7 does NOT re-spell year/quarter/month** — the window, the type vocabulary and the reporting currency are all inherited from 8.4. |
| `owner` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="sales_quota_plans")` | the team/rep this plan is for |
| `territory` | `FK("crm.Territory", SET_NULL, null=True, blank=True, related_name="sales_quota_plans")` | mirrors the quota's own territory |
| `method` | `CharField(max_length=10, choices=METHOD_CHOICES)` | **NO default** — a plan must declare its method |
| `allocation_basis` | `CharField(max_length=20, choices=ALLOCATION_BASIS_CHOICES, default="historical_revenue")` | |
| `baseline_source` | `CharField(max_length=16, choices=BASELINE_SOURCE_CHOICES, default="previous_year")` | |
| `growth_target_pct` | `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))` | |
| `attrition_relief_pct` | `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))` | |
| `stretch_target_pct` | `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)` | a **percentage uplift**, deliberately NOT a second money column — a second money column is a second source of truth for the target |
| `uplift_allowed` | `BooleanField(default=False)` | |
| `target_type` | `CharField(max_length=10, choices=TARGET_TYPE_CHOICES, default="revenue")` | the **label for what the CRM money number means**. It adds **no** unit-count column to the quota. |
| `phasing` | `CharField(max_length=8, choices=PHASING_CHOICES, default="equal")` | the weights live in `parameters` |
| `parameters` | `JSONField(default=dict, blank=True)` | seasonal weights, cut-off day, custom baseline |
| `status` | `CharField(max_length=10, choices=STATUS_CHOICES, default="draft")` | **action-driven — OFF the form** |
| `is_active` | `BooleanField(default=True)` | |
| `notes` | `TextField(blank=True)` | |
| `submitted_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="sales_submitted_quota_plans")` | **FROZEN EVIDENCE (L22)** |
| `approved_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, editable=False, related_name="sales_approved_quota_plans")` | **FROZEN EVIDENCE (L22)** |
| `submitted_at` | `DateTimeField(null=True, blank=True, editable=False)` | **FROZEN EVIDENCE (L22)** |
| `approved_at` | `DateTimeField(null=True, blank=True, editable=False)` | **FROZEN EVIDENCE (L22)** |
| `calculated_at` | `DateTimeField(null=True, blank=True, editable=False)` | **FROZEN EVIDENCE (L22)** |

### 6.3 `class Meta`

* `unique_together = ("tenant", "quota_ref")` — **deliberately stricter than CRM's six-column key**: one
  quota gets one plan, which makes "how was this target derived?" answerable and makes a second competing
  derivation for the same number impossible.
* `ordering = ["-forecast_period__period_year", "owner"]`
* indexes `(tenant, method)`, `(tenant, territory)`, `(tenant, status)`.

### 6.4 `_relation_belongs_to_tenant(self, field_name)`

The same one-FK-one-check helper as the other three models.


### 6.5 `clean()` — every rule, in Python

1. `quota_ref`, `forecast_period`, `owner`, `territory` are all same-tenant.
2. `territory`, if set, **equals `quota_ref.territory_id`** — a plan may not point at a different
   territory than the quota it annotates.
3. **⚠️ THE BINDING CROSS-CHECK — the single most important line in this contract (research §5.3):**
   `quota_ref.period_type == forecast_period.period_type` **AND**
   `quota_ref.period_year == forecast_period.period_year` **AND**
   `quota_ref.period_number == forecast_period.period_number`. A mismatch raises `ValidationError` keyed
   to **`forecast_period`** whose message **names both sides**.
   *Why this is the load-bearing one:* these two tables each carry their own year/quarter/month and
   **nothing in either schema prevents them disagreeing** — a mismatch does **not fail loudly**, it
   produces an attainment board quietly comparing a Q2 quota against a Q1 forecast, and it will read as a
   *data* problem rather than a schema one.
   **The exact ValidationError key is `forecast_period`. Pinned here and again in test (b).**
4. `method == "bottom_up"` **FORBIDS** `uplift_allowed` (SAP: uplift is a top-down-only setting).
5. `stretch_target_pct` **REQUIRES** `uplift_allowed`.
6. `parameters` is validated with the same discipline as `OrderValidationRule.parameters`: must be a
   `dict` (a bare string or list is a **form error, never a 500**), a closed dict per `method`, and
   **unknown keys IGNORED rather than rejected**, so a row written by a newer build survives a rollback.
7. `status in FROZEN_STATES` freezes editing.

### 6.6 ⚠️ Do NOT assume `(tenant, owner, period)` is unique on `crm.SalesQuota`

CRM's `unique_together` contains a **nullable** `territory` and SQLite treats NULLs as distinct, so two
null-territory quotas for the same period **can both exist at the DB level** — CRM's own form is the only
thing preventing it. `territory_performance` therefore **REPORTS** a duplicate `(owner, period)` quota as
a **`caveats` entry, never as a doubled figure, and never refuses** (research §5.2).

### 6.7 `QuotaPlan` carries NO `accounting.Currency` and none may be added

The reporting currency is **inherited from `ForecastPeriod.reporting_currency`**, and
`accounting.Currency` is a GLOBAL master with no `tenant` FK — so it is **never tenant-checked** (L29).
The board only sums amounts when the fetched rows share one reporting currency; **anything else becomes a
caveat, not a number.**

### 6.8 Computed properties

**None declared on the model.** The two derived money figures are context keys on
`quota_plan_detail`, computed in Python in the view: `derived_baseline` and `derived_stretch_amount`
(§7.11). They are **never stored columns and never `F()` expressions.**


---

## 7. FORMS (8.7-6) — `Meta.fields` and the REASON for every exclusion

All four inherit **`(TenantUniqueMixin, TenantModelForm)`** from `apps.sales.forms._common`.

* **`TenantUniqueMixin` is MANDATORY on all four** — a stock `validate_unique` cannot see a composite
  `(tenant, …)` constraint, so without it the list view 500s the moment a duplicate is submitted.
* `TenantModelForm` auto-scopes every FK dropdown to `self.tenant`. Where a field needs a *narrower*
  queryset (active users only, organizations only) **narrow it explicitly in `__init__`**.

### 7.1 `TerritoryRuleForm`

```python
Meta.fields = ["name","description","segment_type","match_mode","conditions","is_catch_all",
               "alignment_type","assignment_scope","target_territory","is_active","priority",
               "effective_from","effective_to"]
```

| Excluded field | REASON |
|---|---|
| `tenant` | set from `request.tenant` by the form, **never authored** |
| `number` | `editable=False` on the base, allocated by `next_number` (L22) |
| `last_run_at` | **frozen evidence, `editable=False`, must never be authorable by a human (L22)** |
| `last_run_matched_count` | **frozen evidence, `editable=False`, must never be authorable by a human (L22)** |

`__init__` also sets
`self.fields["target_territory"].queryset = crm.Territory.objects.filter(tenant=tenant, is_active=True).order_by("name")`
and **disables `conditions` when `segment_type == "named_account"`**, because `clean()` refuses that
combination.

### 7.2 `AccountTerritoryAssignmentForm`

```python
Meta.fields = ["account","territory","rule","owner","alignment_type","assignment_source",
               "effective_from","effective_to","notes"]
```

| Excluded field | REASON |
|---|---|
| `tenant` | set from `request.tenant` by the form, never authored |
| `number` | `editable=False` on the base, allocated by `next_number` (L22) |
| `assigned_by` | **frozen evidence, `editable=False` (L22)** — written by the view from `request.user` |

`__init__` sets
`self.fields["account"].queryset = core.Party.objects.filter(tenant=tenant, kind="organization").order_by("name")`
(a person is not assignable to a territory), `territory` to **active same-tenant territories**, and `rule`
to `TerritoryRule.objects.filter(tenant=tenant, is_active=True)`.

### 7.3 `TerritoryMemberForm`

```python
Meta.fields = ["territory","user","member_role","assignment_type","coverage_split_pct",
               "paired_user","is_primary","effective_from","effective_to","notes"]
```

| Excluded field | REASON |
|---|---|
| `tenant` | set from `request.tenant` by the form, never authored |
| `number` | `editable=False` on the base, allocated by `next_number` (L22) |

`__init__` sets `user` **and** `paired_user` to **`tenant_users(tenant)`** from `forms/_common.py`
(as-built: already `tenant=tenant, is_active=True`) so **a deactivated rep can never be paired**, and adds
a `help_text` on `coverage_split_pct` stating the *"direct members must sum to 100 when any sibling is
shared"* rule.

### 7.4 `QuotaPlanForm`

```python
Meta.fields = ["quota_ref","forecast_period","owner","territory","method","allocation_basis",
               "baseline_source","growth_target_pct","attrition_relief_pct","stretch_target_pct",
               "uplift_allowed","target_type","phasing","parameters","is_active","notes"]
```

| Excluded field | REASON |
|---|---|
| `tenant` | set from `request.tenant` by the form, never authored |
| `number` | `editable=False` on the base, allocated by `next_number` (L22) |
| **`status`** | **action-driven** — moved ONLY by the submit / approve / reject / lock POST views, **never typed** (mirrors `scm.SalesOrder.status` being `editable=False`) |
| `submitted_by` | **frozen evidence, `editable=False` (L22)** |
| `submitted_at` | **frozen evidence, `editable=False` (L22)** |
| `approved_by` | **frozen evidence, `editable=False` (L22)** |
| `approved_at` | **frozen evidence, `editable=False` (L22)** |
| `calculated_at` | **frozen evidence, `editable=False` (L22)** |

`__init__` sets `quota_ref` to `crm.SalesQuota.objects.filter(tenant=tenant)` and `forecast_period` to
`ForecastPeriod.objects.filter(tenant=tenant)`, and **when `self.instance.pk and self.instance.status in
QuotaPlan.FROZEN_STATES`, disables every field on the form** — with the **edit view re-checking the same
rule server-side**, because a disabled field is a UI affordance, not a guard.


---

## 8. URL NAMES and ROUTES (8.7-7) — first-match-wins, so order is behaviour

`apps/sales/urls/TerritoryQuotaManagement/__init__.py` concatenates in this order, with
**`board_patterns` FIRST** because the boards carry the literal routes (mirrors 8.5's
`QuoteOperations`-first and 8.6's `board_patterns`-first precedent):

```python
board_patterns + rule_patterns + assignment_patterns + member_patterns + plan_patterns
```

### 8.1 Boards — `TerritoryBoards.py` (no `<int:pk>` anywhere, so nothing to shadow)

| Path under `sales:` | url name |
|---|---|
| `territories/rebalance-preview/` | `territory_rebalance_preview` |
| `territories/coverage-gap/` | `territory_coverage_gap` |
| `territories/performance/` | `territory_performance` |
| `territories/white-space/` | `territory_white_space` |

### 8.2 Rules — `TerritoryRules.py` (**literals before `<int:pk>`**)

| Path under `sales:` | url name | Method |
|---|---|---|
| `territories/rules/` | `territory_rule_list` | GET |
| `territories/rules/add/` | `territory_rule_create` | GET/POST |
| `territories/rules/<int:pk>/run/` | `territory_rule_run` | **POST-only** |
| `territories/rules/<int:pk>/toggle/` | `territory_rule_toggle` | **POST-only** |
| `territories/rules/<int:pk>/edit/` | `territory_rule_edit` | GET/POST |
| `territories/rules/<int:pk>/delete/` | `territory_rule_delete` | **POST-only** |
| `territories/rules/<int:pk>/` | `territory_rule_detail` | GET |

### 8.3 Assignments — `AccountTerritoryAssignments.py`

| Path under `sales:` | url name |
|---|---|
| `territories/assignments/` | `account_territory_assignment_list` |
| `territories/assignments/add/` | `account_territory_assignment_create` |
| `territories/assignments/<int:pk>/edit/` | `account_territory_assignment_edit` |
| `territories/assignments/<int:pk>/delete/` | `account_territory_assignment_delete` |
| `territories/assignments/<int:pk>/` | `account_territory_assignment_detail` |

### 8.4 Members — `TerritoryMembers.py`

| Path under `sales:` | url name |
|---|---|
| `territories/members/` | `territory_member_list` |
| `territories/members/add/` | `territory_member_create` |
| `territories/members/<int:pk>/edit/` | `territory_member_edit` |
| `territories/members/<int:pk>/delete/` | `territory_member_delete` |
| `territories/members/<int:pk>/` | `territory_member_detail` |

### 8.5 Plans — `QuotaPlans.py`

| Path under `sales:` | url name | Method |
|---|---|---|
| `quota-plans/` | `quota_plan_list` | GET |
| `quota-plans/add/` | `quota_plan_create` | GET/POST |
| `quota-plans/<int:pk>/submit/` | `quota_plan_submit` | **POST** |
| `quota-plans/<int:pk>/approve/` | `quota_plan_approve` | **POST** |
| `quota-plans/<int:pk>/reject/` | `quota_plan_reject` | **POST** |
| `quota-plans/<int:pk>/lock/` | `quota_plan_lock` | **POST** |
| `quota-plans/<int:pk>/edit/` | `quota_plan_edit` | GET/POST |
| `quota-plans/<int:pk>/delete/` | `quota_plan_delete` | **POST-only** |
| `quota-plans/<int:pk>/` | `quota_plan_detail` | GET |

### 8.6 Shadowing check — a STANDING OBLIGATION, not a one-off

Before wiring, diff the **whole** concatenated `sales:urlpatterns` list. 8.5 ships
`quotes/portal/<str:token>/` — a greedy `<str>` that captures anything not already claimed above it.
Verify the new prefixes (`territories/`, `quota-plans/`) against **all** mounted prefixes, not just
against 8.7's own module.

### 8.7 Every delete view

`@require_POST` + `@login_required` + `@tenant_admin_required`, mutates only inside
`if request.method == "POST"`, and its list-row button is a POST form carrying `{% csrf_token %}` and
`onclick="return confirm('…')"`. **A GET on a delete URL is a no-op redirect — never a mutation, never a
500.**


---

## 9. EVERY VIEW CONTEXT KEY, pinned (L7 — an unpinned name is a blank page or a `NoReverseMatch`)

**The template is written FROM this table, not the reverse.** Every view is `@login_required`, every
queryset is `Model.objects.filter(tenant=request.tenant)`, and the tenantless superuser gets an **empty**
result, never a 500.

Every list view returns the `crud` contract `object_list` + `page_obj` + `q`, plus its own filter
choices. (`apps/core/crud.py` pins that contract: list → `object_list` + `page_obj` + `q`; detail/edit
object → `obj`; form → `form` + `is_edit`.)

**Shared GET-filter guard (L11):** every int-FK filter goes through **`as_db_int`**
(`apps/core/crud.py`); **junk enum values reset to `""`; a junk or oversized int id is SKIPPED, never
handed to the driver.**

### 9.1 `territory_rule_list`

| Context key | Value |
|---|---|
| `object_list` | the `crud` list var |
| `page_obj` | the `crud` pager |
| `q` | the `crud` search string |
| `page_size` | per-page value |
| `segment_type_choices` | `= TerritoryRule.SEGMENT_TYPE_CHOICES` |
| `match_mode_choices` | `= TerritoryRule.MATCH_MODE_CHOICES` |
| `alignment_type_choices` | `= TerritoryRule.ALIGNMENT_TYPE_CHOICES` |
| `assignment_scope_choices` | `= TerritoryRule.ASSIGNMENT_SCOPE_CHOICES` |
| `active_choices` | `[("active","Active"),("inactive","Inactive")]` |
| `territories` | **active same-tenant `crm.Territory` queryset** for the `?target_territory=` dropdown, compared with `\|stringformat:"d"` |
| `stats` | dict with keys `total`, `active`, `catch_all`, `never_run` |

**GET filters:** `q`, `segment_type`, `match_mode`, `alignment_type`, `assignment_scope`,
`target_territory` (via `as_db_int`), `active`.

### 9.2 `territory_rule_detail`

| Context key | Value |
|---|---|
| `obj` | the `TerritoryRule` |
| `segment_type_choices` | `= TerritoryRule.SEGMENT_TYPE_CHOICES` |
| `match_mode_choices` | `= TerritoryRule.MATCH_MODE_CHOICES` |
| `alignment_type_choices` | `= TerritoryRule.ALIGNMENT_TYPE_CHOICES` |
| `assignment_scope_choices` | `= TerritoryRule.ASSIGNMENT_SCOPE_CHOICES` |
| `generated_assignments` | the rule's `AccountTerritoryAssignment` rows, **tenant-scoped, `[:200]`** |
| `is_runnable` | bool |
| `caveats` | list of `str` |

### 9.3 `territory_rule_create` / `territory_rule_edit`

| Context key | Value |
|---|---|
| `form` | the form instance |
| `obj` | the rule (None on create) |
| `is_edit` | bool |
| `segment_type_choices` | `= TerritoryRule.SEGMENT_TYPE_CHOICES` |
| `match_mode_choices` | `= TerritoryRule.MATCH_MODE_CHOICES` |
| `alignment_type_choices` | `= TerritoryRule.ALIGNMENT_TYPE_CHOICES` |
| `assignment_scope_choices` | `= TerritoryRule.ASSIGNMENT_SCOPE_CHOICES` |
| `territories` | **active same-tenant `crm.Territory` queryset** |

### 9.4 `account_territory_assignment_list`

| Context key | Value |
|---|---|
| `object_list` | the `crud` list var |
| `page_obj` | the `crud` pager |
| `q` | the `crud` search string |
| `page_size` | per-page value |
| `alignment_type_choices` | `= TerritoryRule.ALIGNMENT_TYPE_CHOICES` |
| `assignment_source_choices` | `= AccountTerritoryAssignment.ASSIGNMENT_SOURCE_CHOICES` |
| `coverage_choices` | `[("current","Current"),("expired","Expired"),("all","All")]` |
| `territories` | **active same-tenant `crm.Territory` queryset** |
| `users` | **active same-tenant users** |
| `stats` | dict with keys `total`, `current`, `unassigned`, `overlay` |

**GET filters:** `q`, `alignment_type`, `assignment_source`, `coverage`, `territory` (`as_db_int`),
`owner` (`as_db_int`).

### 9.5 `account_territory_assignment_detail`

| Context key | Value |
|---|---|
| `obj` | the `AccountTerritoryAssignment` |
| `alignment_type_choices` | `= TerritoryRule.ALIGNMENT_TYPE_CHOICES` |
| `assignment_source_choices` | `= AccountTerritoryAssignment.ASSIGNMENT_SOURCE_CHOICES` |
| `rule` | the originating `TerritoryRule` (or `None`) |
| `siblings` | the account's other active alignments, **`[:50]`** |
| `caveats` | list of `str` |

### 9.6 `account_territory_assignment_create` / `_edit`

| Context key | Value |
|---|---|
| `form` | the form instance |
| `obj` | the assignment (None on create) |
| `is_edit` | bool |
| `alignment_type_choices` | `= TerritoryRule.ALIGNMENT_TYPE_CHOICES` |
| `assignment_source_choices` | `= AccountTerritoryAssignment.ASSIGNMENT_SOURCE_CHOICES` |
| `territories` | **active same-tenant `crm.Territory` queryset** |
| `users` | **active same-tenant users** |
| `rules` | **same-tenant `TerritoryRule` queryset** (active) |


### 9.7 `territory_member_list`

| Context key | Value |
|---|---|
| `object_list` | the `crud` list var |
| `page_obj` | the `crud` pager |
| `q` | the `crud` search string |
| `page_size` | per-page value |
| `member_role_choices` | `= TerritoryMember.MEMBER_ROLE_CHOICES` |
| `assignment_type_choices` | `= TerritoryMember.ASSIGNMENT_TYPE_CHOICES` |
| `active_choices` | `[("active","Active"),("inactive","Inactive")]` |
| `territories` | **active same-tenant `crm.Territory` queryset** |
| `users` | **active same-tenant users** |
| `stats` | dict with keys `total`, `direct`, `shared`, `overlay`, `orphaned_pairs` |

**GET filters:** `q`, `member_role`, `assignment_type`, `territory`, `user`, `active`.

### 9.8 `territory_member_detail`

| Context key | Value |
|---|---|
| `obj` | the `TerritoryMember` |
| `member_role_choices` | `= TerritoryMember.MEMBER_ROLE_CHOICES` |
| `assignment_type_choices` | `= TerritoryMember.ASSIGNMENT_TYPE_CHOICES` |
| `territory_peers` | the other members of the same territory, **`[:100]`** |
| `paired_user` | the paired user (or `None`) |
| `is_frozen` | **True when `effective_to` has passed** |
| `caveats` | list of `str` |

### 9.9 `territory_member_create` / `territory_member_edit`

| Context key | Value |
|---|---|
| `form` | the form instance |
| `obj` | the member (None on create) |
| `is_edit` | bool |
| `member_role_choices` | `= TerritoryMember.MEMBER_ROLE_CHOICES` |
| `assignment_type_choices` | `= TerritoryMember.ASSIGNMENT_TYPE_CHOICES` |
| `territories` | **active same-tenant `crm.Territory` queryset** |
| `users` | **active same-tenant users** |

### 9.10 `quota_plan_list`

| Context key | Value |
|---|---|
| `object_list` | the `crud` list var |
| `page_obj` | the `crud` pager |
| `q` | the `crud` search string |
| `page_size` | per-page value |
| `status_choices` | `= QuotaPlan.STATUS_CHOICES` |
| `method_choices` | `= QuotaPlan.METHOD_CHOICES` |
| `allocation_basis_choices` | `= QuotaPlan.ALLOCATION_BASIS_CHOICES` |
| `baseline_source_choices` | `= QuotaPlan.BASELINE_SOURCE_CHOICES` |
| `target_type_choices` | `= QuotaPlan.TARGET_TYPE_CHOICES` |
| `phasing_choices` | `= QuotaPlan.PHASING_CHOICES` |
| `active_choices` | `[("active","Active"),("inactive","Inactive")]` |
| `territories` | **active same-tenant `crm.Territory` queryset** |
| `owners` | **active same-tenant users** (the `owner` FK dropdown) |
| `periods` | **same-tenant `ForecastPeriod` queryset** for the `?forecast_period=` dropdown |
| `stats` | dict with keys `total`, `draft`, `in_approval`, `approved`, `frozen` |

**GET filters:** `q`, `status`, `method`, `allocation_basis`, `baseline_source`, `target_type`, `phasing`,
`territory`, `owner`, `forecast_period`, `active`.

### 9.11 `quota_plan_detail`

| Context key | Value |
|---|---|
| `obj` | the `QuotaPlan` |
| `status_choices` | `= QuotaPlan.STATUS_CHOICES` |
| `method_choices` | `= QuotaPlan.METHOD_CHOICES` |
| `allocation_basis_choices` | `= QuotaPlan.ALLOCATION_BASIS_CHOICES` |
| `baseline_source_choices` | `= QuotaPlan.BASELINE_SOURCE_CHOICES` |
| `target_type_choices` | `= QuotaPlan.TARGET_TYPE_CHOICES` |
| `phasing_choices` | `= QuotaPlan.PHASING_CHOICES` |
| `quota_ref` | the `crm.SalesQuota` (read-only) |
| `forecast_period` | the `sales.ForecastPeriod` (read-only) |
| `is_frozen` | bool |
| `can_approve` | the tenant-admin predicate — **as-built symbol is `is_tenant_admin(request.user)` from `apps/sales/views/_helpers.py`** (the plan spells it `_is_tenant_admin`; the real name in the tree has no leading underscore) |
| `derived_baseline` | **`Decimal` computed in Python in the view** |
| `derived_stretch_amount` | **`Decimal` computed in Python in the view** |
| `caveats` | list of `str` |

**The two `derived_*` figures are `Decimal` computed in Python in the view; they are NEVER stored
columns and NEVER `F()` expressions.**

### 9.12 `quota_plan_create` / `quota_plan_edit`

| Context key | Value |
|---|---|
| `form` | the form instance |
| `obj` | the plan (None on create) |
| `is_edit` | bool |
| `status_choices` | `= QuotaPlan.STATUS_CHOICES` |
| `method_choices` | `= QuotaPlan.METHOD_CHOICES` |
| `allocation_basis_choices` | `= QuotaPlan.ALLOCATION_BASIS_CHOICES` |
| `baseline_source_choices` | `= QuotaPlan.BASELINE_SOURCE_CHOICES` |
| `target_type_choices` | `= QuotaPlan.TARGET_TYPE_CHOICES` |
| `phasing_choices` | `= QuotaPlan.PHASING_CHOICES` |
| `territories` | **active same-tenant `crm.Territory` queryset** |
| `owners` | **active same-tenant users** |
| `periods` | **same-tenant `ForecastPeriod` queryset** |


---

## 10. THE FOUR DERIVED BOARDS (8.7-8) — `read` vs `computed`, per key

All four are **read-only**, all in `TerritoryBoards.py`, all `@login_required`, all tenant-scoped, and all
**bounded by `MAX_BOARD_ACCOUNTS` / `MAX_ROWS`** in the style of `AccountBoards.py` so a huge workspace
cannot pull an unbounded set into memory. (As-built precedents: `AccountBoards.py:30`
`MAX_BOARD_ACCOUNTS = 500`; `ForecastBoards.py:62-63` `MAX_PERIODS = 200`, `MAX_ROWS = 200`.)

**`read`** = the key's value is a live column/relation read straight off a fetched model instance.
**`computed`** = the key's value is **derived in the view, in Python**, over a fetched set.

### 10.1 `territory_rebalance_preview` — template `boards/rebalance_preview.html`

| Context key | read / computed | Notes |
|---|---|---|
| `rules` | read | same-tenant `TerritoryRule` queryset, bounded |
| `territories` | read | **active same-tenant `crm.Territory` queryset** |
| `segment_type_choices` | read | `= TerritoryRule.SEGMENT_TYPE_CHOICES` (a constant, not a row) |
| `selected_rule_id` | read | the `?rule=` selection, `as_db_int`-guarded |
| `q` | read | the search string |
| `segment_type` | read | the `?segment_type=` selection |
| `diff_rows` | **computed** | each row: `account`, `profile`, `classification`, `current_territory`, `proposed_territory`, `rule`, `action` ∈ `unchanged\|move\|add\|remove` |
| `unmatched_rows` | **computed** | accounts no rule claimed |
| `stats` | **computed** | keys `accounts_scanned`, `moves`, `adds`, `removes`, `unchanged` |
| `caveats` | **computed** | list of `str` |
| `can_run` | **computed** | bool gate on the commit verb |

**READ-ONLY: this board NEVER writes. It is the dry run; `territory_rule_run` is the commit.**

### 10.2 `territory_coverage_gap` — template `boards/coverage_gap.html`

| Context key | read / computed | Notes |
|---|---|---|
| `uncovered_rows` | **computed** | accounts no active rule matched |
| `unassigned_rows` | **computed** | **no active assignment at all** |
| `over_assigned_rows` | **computed** | `>1` active primary, or an active secondary/overlay count over the cap |
| `manager_less_rows` | read | active `crm.Territory` with **`manager IS NULL`** (field is `crm.Territory.manager`) |
| `orphan_rows` | **computed** | **`territory IS NULL`** — the `SET_NULL` orphan, **surfaced rather than hidden** (research §5.6) |
| `orphaned_pair_rows` | **computed** | active `TerritoryMember` whose `paired_user` is inactive or `NULL` |
| `territories` | read | **same-tenant `crm.Territory` queryset** |
| `q` | read | the search string |
| `stats` | **computed** | keys `accounts_total`, `uncovered`, `unassigned`, `over_assigned`, `manager_less`, `orphans` |
| `caveats` | **computed** | list of `str` |

### 10.3 `territory_performance` — template `boards/performance.html`

| Context key | read / computed | Notes |
|---|---|---|
| `period` | read | the selected `sales.ForecastPeriod` |
| `periods` | read | **same-tenant `ForecastPeriod` queryset**, bounded |
| `period_choices` | read | `(pk, label)` pairs for the period dropdown |
| `selected_period_id` | read | the `?period=` selection, `as_db_int`-guarded |
| `rows` | **computed** | each row: `territory`, `quota_amount`, `attainment_amount`, `pipeline_amount`, `attribution_pct`, `attainment_pct`, `pacing_pct`, `elapsed_pct`, `account_count`, `member_count`, `balance_profile` |
| `summary` | **computed** | keys `attainment_amount`, `quota_amount`, `overall_attainment_pct`, `period_elapsed_pct` |
| `top_bottom` | **computed** | the ranked highs and lows |
| `territories` | read | **same-tenant `crm.Territory` queryset** |
| `q` | read | the search string |
| `caveats` | **computed** | list of `str`, **including any cross-currency or duplicate-quota warning** |

**`summary["period_elapsed_pct"]` is READ from `ForecastPeriod` (8.4, already as-built —
`ForecastPeriod.period_elapsed_pct` is a 0-100 `Decimal` property). NEVER re-derived here.** It is the
one value in this board that is read, not computed.

`quota_amount` comes from **`crm.SalesQuota.target_amount`** (read, never written by 8.7).

### 10.4 `territory_white_space` — template `boards/white_space.html`

| Context key | read / computed | Notes |
|---|---|---|
| `rows` | **computed** | each row: `account`, `profile`, `classification`, `covered_territories`, `coverage_state` ∈ `covered\|uncovered\|overlay_only`, `opportunity_count`, `pipeline_amount`, `classification_gap` |
| `segments` | **computed** | the grouped segment breakdown |
| `tier_choices` | read | `= sales.AccountClassification.TIER_CHOICES` |
| `lifecycle_stage_choices` | read | `= sales.AccountClassification.LIFECYCLE_STAGE_CHOICES` |
| `selected_tier` | read | the `?tier=` selection |
| `selected_lifecycle_stage` | read | the `?lifecycle_stage=` selection |
| `q` | read | the search string |
| `stats` | **computed** | keys `accounts_scanned`, `covered`, `uncovered`, `overlay_only` |
| `caveats` | **computed** | list of `str` |
| `account_white_space_url` | read | the **8.3** cross-link — `reverse("sales:account_white_space")` |

### 10.5 THE MONEY RULE, stated per board (not once in a preamble)

**Every money and percentage figure on every board is `Decimal` in PYTHON over a fetched set — never
`F()`, never `Sum(...)/Sum(...)`, never a DB-side division, never a float.** The board queries are exactly
where the temptation appears, because an aggregate queryset is one line and a Python loop is ten; the
SQLite integer-division trap **silently drops fractional cents rather than raising**, so a board that
renders is a board that is quietly wrong.

**`balance_profile` is an acceptance spec, not a score.** The Salesforce "Balance Your Territories"
narrative requires **reporting every axis** (account count, geographic spread, company size, industry,
open pipeline) and **never pretending a single balance metric exists** — equalising on one factor is the
documented failure mode.


---

## 11. TEMPLATE INVENTORY (8.7-9) — 16 files: 12 entity pages + 4 boards

All under `templates/sales/territoryquotamanagement/`. Folder names are **LOWERCASE with no underscore**;
the page is the **bare filename**. `{% extends "base.html" %}`, `{% include "partials/…" %}`.

| # | Path | Must contain |
|---|---|---|
| 1 | `territoryrule/list.html` | search box + GET filter form (segment type, match mode, alignment type, scope, territory, active) + an **Actions column (view / edit / delete)** per row + pagination + a "New Rule" button |
| 2 | `territoryrule/detail.html` | full field read-out; the frozen `last_run_at` / `last_run_matched_count` block rendered as **read-only evidence**; a `generated_assignments` table; an Actions sidebar (Edit / Run / Toggle / Delete-as-POST / Back to List) |
| 3 | `territoryrule/form.html` | **one template for create AND edit**, driven by `is_edit` |
| 4–6 | `accountterritoryassignment/{list,detail,form}.html` | same triple, same Actions column, same GET filter form |
| 7–9 | `territorymember/{list,detail,form}.html` | same triple, same Actions column, same GET filter form |
| 10–12 | `quotaplan/{list,detail,form}.html` | same triple, same Actions column, same GET filter form |
| 13 | `boards/rebalance_preview.html` | read-only; states it is a **live derivation, not a snapshot**; links to the 8.7 rule list + the **8.3** boards |
| 14 | `boards/coverage_gap.html` | read-only; same banner; links across |
| 15 | `boards/performance.html` | read-only; same banner; links across |
| 16 | `boards/white_space.html` | read-only; same banner; links across |

**NEVER a flat `territoryrule_list.html`.**

### 11.1 Filter rules (AGENTS.md, non-negotiable)

1. Every status/enum dropdown is populated **only** from the `*_choices` context key pinned in §9/§10.
2. String comparisons: `{% if request.GET.status == value %}`.
3. **pk comparisons: `{% if request.GET.territory == territory.pk|stringformat:"d" %}` — NEVER `|slugify` for a pk.**
4. Badge conditions use the **exact model choice values**, and **every badge has an
   `{% else %}` `{{ obj.get_field_display }}` fallback**.
5. The only six CSS classes that exist are
   `.badge-amber .badge-green .badge-info .badge-muted .badge-red .badge-slate` —
   **`badge-success` / `badge-warning` / `badge-danger` must never be emitted.**

---

## 12. FROZEN EVIDENCE — every `editable=False` field and its SOLE writer

`editable=False` auto-excludes a field from every `ModelForm` (L22). **A frozen-evidence field is written
by exactly one caller and by nothing else.**

| Model | Field | SOLE writer | Notes |
|---|---|---|---|
| `TerritoryRule` | `last_run_at` | `territory_rule_run` POST view | inside the **same transaction** that writes the assignment rows |
| `TerritoryRule` | `last_run_matched_count` | `territory_rule_run` POST view | same transaction |
| `AccountTerritoryAssignment` | `assigned_by` | the create/edit view, **from `request.user`** | never typed |
| `QuotaPlan` | `status` *(not `editable=False` — **off the form by decision**)* | the `quota_plan_submit` / `_approve` / `_reject` / `_lock` POST views | mirrors `scm.SalesOrder.status`; action-driven, never typed |
| `QuotaPlan` | `submitted_by` | `quota_plan_submit` POST view | from `request.user` |
| `QuotaPlan` | `submitted_at` | `quota_plan_submit` POST view | `timezone.now()` |
| `QuotaPlan` | `approved_by` | `quota_plan_approve` POST view | from `request.user` |
| `QuotaPlan` | `approved_at` | `quota_plan_approve` POST view | `timezone.now()` |
| `QuotaPlan` | `calculated_at` | the allocation/run path only | never a form field |

Plus, on every model, inherited from the base: **`number`** (`editable=False` on `TenantNumbered`),
allocated by `next_number`.

**Test (c) enforces this**: none of `last_run_at`, `last_run_matched_count`, `assigned_by`,
`submitted_by` / `submitted_at`, `approved_by` / `approved_at`, `calculated_at` appears in **any** form's
fields.


---

## 13. INTEGRATE WIRING (8.7-10) — single writer, main session only (L43)

**Verify every expected file actually landed BEFORE wiring anything** — a missing entity module surfaces as
an `ImportError` three layers away, and the check-after-edit hook blocks a premature `urls.py` edit (L12).

| # | File | The edit | Rule |
|---|---|---|---|
| 1 | `apps/sales/models/__init__.py` | **surgical `Edit`**: append four `from .TerritoryQuotaManagement… import …` lines and four `"…"` entries to `__all__` | **NEVER full-rewrite this shared file** — another session may be building a different sub-module in this same checkout |
| 2 | `apps/sales/forms/__init__.py` | same: four form imports + four `__all__` entries | surgical only |
| 3 | `apps/sales/views/__init__.py` | `from .TerritoryQuotaManagement import *`, **and add the 8.7 prefixes to the `__all__` comprehension's `name.startswith((...))` tuple** | ⚠️ **a view missing from that tuple is an `AttributeError` at URLconf time** — this repo's `__all__` is a *filter*, not a documentation list |
| 4 | `apps/sales/urls/__init__.py` | `from .TerritoryQuotaManagement import urlpatterns as _territory_quota` and splice `*_territory_quota` into the concatenated list **after `*_order_management`** | surgical only |
| 5 | `apps/sales/admin.py` | register **all four models only** (`@admin.register` each; `list_display` including `number` and `tenant`; `list_filter` on the choice columns) | **the four boards get NO admin registration** — they are not models |
| 6 | `seed_sales.py` | add `_seed_territory_quota(self, tenant, owner)` and call it from `_seed_tenant` | **idempotent: `get_or_create` throughout, safe twice with no `--flush`** |
| 7 | `apps/core/navigation.py` | the **one** `LIVE_LINKS["8.7"]` entry, placed after `"8.6"`, with a comment repeating the ownership ruling | see §13.1 |

### 13.0 The eight prefixes to add to `apps/sales/views/__init__.py`'s `__all__` `startswith` tuple

```python
"territory_rule_", "account_territory_assignment_", "territory_member_", "quota_plan_",
"territory_rebalance_preview", "territory_coverage_gap", "territory_performance", "territory_white_space"
```

### 13.0b The seeder must NOT violate the ownership ruling

`_seed_territory_quota` **REUSES** the existing `crm.Territory` and `crm.SalesQuota` rows (fetch or
`get_or_create` them) and **NEVER creates a second territory or quota** — the seeder is the most likely
place for the ownership ruling to be violated by accident.

Seed content: **3 rules** (geographic / account_size / one catch-all) · **4–6 assignments** (one
`named_account`, one `overlay`, one expired) · **3–4 members** (a hunter, a farmer, an SDR paired to an
AE, one overlay specialist) · **2 quota plans** (one `top_down`/`approved`, one `bottom_up`/`draft`).

### 13.1 `LIVE_LINKS["8.7"]` — the five NavERP.md bullet strings, VERBATIM

A typo produces a silently dead bullet, because `parse_catalog()` keys the module tree off them.

| Label (VERBATIM) | url |
|---|---|
| `"Territory Design & Mapping"` | `sales:territory_rule_list` |
| `"Territory Assignment & Rebalancing"` | `sales:account_territory_assignment_list` |
| `"Quota Planning & Allocation"` | `sales:quota_plan_list` |
| `"Coverage Model Optimization"` | `sales:territory_member_list` |
| `"Territory Performance Analytics"` | `sales:territory_performance` |

**Extra live leaves (not NavERP.md bullets):**

| Label | url |
|---|---|
| `"Territory Rules"` | `sales:territory_rule_list` |
| `"Territory Members"` | `sales:territory_member_list` |
| `"Quota Plans"` | `sales:quota_plan_list` |
| `"Rebalance Preview"` | `sales:territory_rebalance_preview` |
| `"Coverage Gaps"` | `sales:territory_coverage_gap` |
| `"Territory White Space"` | `sales:territory_white_space` |

**Every value must be a staff-reachable management page, never a login-gated portal view (L32).**

### 13.2 The migration sequence, in order

1. `venv\Scripts\python.exe manage.py makemigrations sales` → **inspect the generated `0013`**: it must
   touch **`sales` only** and must name **no `crm`, `core`, `scm` or `accounting`** operation.
2. `… manage.py migrate`
3. `… manage.py seed_sales`
4. **`… manage.py seed_sales` AGAIN** — the idempotency check; a second run must report the same counts
   and create nothing.
5. `… manage.py check` clean
6. `… manage.py makemigrations sales --check` reporting **"No changes detected"** (Django still derives
   `app_label` from the app config, so a correct package split needs no migration of its own).

### 13.3 The three greps that prove the ruling held

1. `Select-String 'apps\sales\models\TerritoryQuotaManagement\*.py' -Pattern '^class (Territory|SalesQuota)\b'` → **zero hits**
2. A sweep for `NUMBER_PREFIX = "TER"` / `"QTA"` under `apps\sales` → **zero hits**
3. `manage.py check` → **no `fields.E304/E305`** reverse-accessor clash from the new `related_name`s


---

## 14. SMOKE GATE (8.7-11) — `qa-smoke-tester`, the gate that catches contract drift

1. Render **every** 8.7 page as `admin_acme` and **assert content, not just status 200** — a mismatched
   context var returns 200 and renders blank (L8). Per list page: assert the seeded row names appear. Per
   detail: assert the number, the FK names and the frozen-evidence values. Per board: assert at least one
   derived row **and the caveat region**.
2. **Junk-param pass** on every list and board: `?segment_type=bogus`, `?status=1`, `?territory=abc`,
   `?territory=99999999999999999999999999`, `?page=99999` — all must render the unfiltered page (or 404 on
   a cross-tenant id), **never a 500**.
3. **Page 2** exists and paginates on the seeded dataset.
4. **Cross-tenant IDOR → 404**: log in as `admin_globex` and request every 8.7 detail / edit / delete URL
   for an `admin_acme` pk. **Every one is 404**, never a 200 rendering another tenant's row.
5. **POST-only verbs**: GET on `…/run/`, `…/toggle/`, `…/submit/`, `…/approve/`, `…/reject/`, `…/lock/`
   and every `…/delete/` **mutates nothing**.
6. **`territory_rebalance_preview` writes nothing** — snapshot the assignment count before and after
   rendering it; it must be identical.
7. **Fix any drift against THIS contract, not by inventing a new context key in the template.** A context
   key added in Phase 3 to make a template work **is a contract change** and must be recorded here.

---

## 15. THE FOUR RULINGS THE TESTS MUST COVER (8.7-14)

Test files, committed on their own as each lands:
`test_territoryquotamanagement_models.py` → `test_territoryquotamanagement_forms.py` →
`test_territoryquotamanagement_views.py` → `test_territoryquotamanagement_security.py`.

Every test function is `test_territoryquotamanagement_*`; every module-level helper is
`_territoryquotamanagement_*`. Tests run on SQLite in-memory. `apps/sales/tests/conftest.py` gets a new
8.7 section via a **surgical `Edit`** — ⚠️ **a previous session truncated the shared `conftest.py` and
committed it, deleting every other sub-module's fixtures. NEVER full-rewrite it; Edit only, and check the
line count before and after.** Finally run the **FULL, UNFILTERED** sales suite — **never a `-k` filter**
(L47).

| # | Ruling | Assertion |
|---|---|---|
| (a) | **the ownership ruling** | **no `sales.Territory` and no `sales.SalesQuota` exist** |
| (b) | **the binding cross-check** | a `QuotaPlan` whose `quota_ref.period_year` differs from its `forecast_period.period_year` **raises and never saves** — error key `forecast_period` |
| (c) | **frozen evidence is unauthorable** | none of `last_run_at`, `last_run_matched_count`, `assigned_by`, `submitted_by`/`submitted_at`, `approved_by`/`approved_at`, `calculated_at` appears in **any** form's fields |
| (d) | **`Decimal`, not floats and not SQL division** | a `coverage_split_pct` sibling sum that is not exactly 100 raises, and a fractional-cent attainment figure is **not truncated** |

Plus: cross-tenant FK rejection on **every** model · the one-active-primary rule ·
`assignment_source="rule"` ⟺ `rule` present · the **20-condition / 16 KiB** caps.

---

## 16. CLOSE-OUT (8.7-16) — one sentence per model, never re-declared

* `TerritoryRule` **does not define a territory**.
* `AccountTerritoryAssignment` **does not define a customer or a territory**.
* `TerritoryMember` **does not define a territory, a team hierarchy or a second manager field**.
* `QuotaPlan` **does not define a quota, a target amount, a currency or a period**.

### 16.1 `NavERP-ERD.md` reconciliation for BOTH rows — **not optional (L36 step 2)**

* The **CRM** row gains the note that 8.7 **extends `crm.Territory` / `crm.SalesQuota` by FK and declares
  neither again**.
* **Row 8 (Sales)** gains the as-built 8.7 set (`TerritoryRule`, `AccountTerritoryAssignment`,
  `TerritoryMember`, `QuotaPlan`) marked *as-built* in its **"Adds"** column, and a **"Reuses"** entry
  naming `crm.Territory` / `crm.SalesQuota` / `sales.ForecastPeriod` / `core.Party`.

Leaving either row stale re-creates the exact contradiction L36 step 2 exists to prevent — and the
territory is the most likely thing for a future reader to assume Sales owns, because the sub-module has it
in its title.

### 16.2 The three ACCEPTED limitations, recorded in the module docstring

| Research | Limitation | Status |
|---|---|---|
| §5.8 | `crm.Territory` is unversioned, so "what did Territory West contain in March?" is answerable from assignment history but **not** from the territory itself | accepted; revisit with **8.19** |
| §5.7 | deleting a `ForecastPeriod` with a `QuotaPlan` raises a raw `IntegrityError` from the `PROTECT` rather than 8.4's friendly `ValidationError` (`_optional_sales_model` guards by name only) | accepted this pass; the fix is a **surgical edit to 8.4's file**, therefore an **L43-gated follow-up** |
| §5.9 | an orphaned `paired_user` is allowed and surfaced by `territory_coverage_gap` rather than blocked | accepted and intended |

---


## 17. OPEN — decide at build time (the plan does NOT pin these; do not invent a name)

These are deliberately **not** answered here. The plan did not give them, so guessing a name would be a
silent contract change. Each is listed with the nearest pinned fact so the decision is cheap.

| # | Open item | Nearest pinned fact / guidance |
|---|---|---|
| 1 | **`Meta.ordering` for `AccountTerritoryAssignment`** | `TerritoryRule` = `["priority","id"]`; `QuotaPlan` = `["-forecast_period__period_year","owner"]`. The plan pins neither for the assignment or the member. Pick one, write it down here. |
| 2 | **`Meta.ordering` for `TerritoryMember`** | same as above |
| 3 | **Django index `name=` values** for every new `Index(...)` | MariaDB caps index names at **30 characters**. The plan gives the index *fields* only. Name them `<30` chars, following the as-built `sales_lrr_tnt_mode_idx` pattern. |
| 4 | **The exact `filters=` tuples for each `crud_list`** | the plan pins the **GET param names** (§9) and says int FKs go through `as_db_int`; the `(get_param, orm_lookup, is_int)` triple per param is a build-time choice consistent with those two. |
| 5 | **`MAX_BOARD_ACCOUNTS` / `MAX_ROWS` numeric values for 8.7** | as-built precedents: `AccountBoards.py` `MAX_BOARD_ACCOUNTS = 500`; `ForecastBoards.py` `MAX_PERIODS = 200`, `MAX_ROWS = 200`. Reuse the precedents; do not invent a new scale. |
| 6 | **The exact `search_fields` per list view** | the plan pins `q` but not the fields. Keep them to the entity's own text columns + the number. |
| 7 | **The formula behind `derived_baseline` and `derived_stretch_amount`** | the plan pins that they are **`Decimal`, computed in Python in the view, never stored, never `F()`**, and that `stretch_target_pct` is a **percentage uplift** on the CRM money number. The arithmetic itself is a build-time decision. |
| 8 | **The row-dict shape of `balance_profile`** | the plan pins the **axes** — account count, geographic spread, company size, industry, open pipeline — and the rule that no single balance metric may be presented as the answer. The dict keys are a build-time choice. |
| 9 | **`segments` shape on `territory_white_space`** | derived from the same fetched set; the plan pins no key names. |
| 10 | **The message text of the binding cross-check `ValidationError`** | the **key** is pinned (`forecast_period`); the message must **name both sides** (e.g. both years / both period numbers). Exact wording is a build-time choice. |
| 11 | **The `parameters` closed-dict keys per `method`** | the plan pins the *discipline* (must be a `dict`, closed per `method`, **unknown keys IGNORED not rejected**) and that phasing weights live there. The key names are a build-time choice. |
| 12 | **The list-row "Actions" column icon set** | pinned as view / edit / delete (plus Run / Toggle on the rule detail sidebar). Exact markup follows the `/frontend-design` skill. |


---

## 18. NAME-BY-NAME INDEX (nothing renamed, nothing invented)

**Models (4):** `TerritoryRule` · `AccountTerritoryAssignment` · `TerritoryMember` · `QuotaPlan`

**Number prefixes:** `TRG` · `TAS` · `TMB` · `QPA` (`TER` and `QTA` are CRM's and stay CRM's)

**`related_name`s (10, all verified free):** `sales_territory_rules` · `sales_account_assignments` ·
`generated_assignments` · `sales_territory_assignments` · `sales_territory_assignments_made` ·
`sales_members` · `sales_territory_memberships` · `sales_paired_territory_members` ·
`sales_quota_plans` · `quota_plans`

**Choice constants DEFINED by 8.7:** `SEGMENT_TYPE_CHOICES` · `ALIGNMENT_TYPE_CHOICES` ·
`ASSIGNMENT_SCOPE_CHOICES` · `ASSIGNMENT_SOURCE_CHOICES` · `MEMBER_ROLE_CHOICES` ·
`ASSIGNMENT_TYPE_CHOICES` · `METHOD_CHOICES` · `ALLOCATION_BASIS_CHOICES` · `BASELINE_SOURCE_CHOICES` ·
`TARGET_TYPE_CHOICES` · `PHASING_CHOICES` · `FROZEN_STATES` · `TERRITORY_FIELDS` ·
`validate_territory_conditions`

**Choice constants IMPORTED, never re-spelled:** `MATCH_MODE_CHOICES` (from `LeadRoutingRule`) ·
`STATUS_CHOICES` (from `ForecastSubmission`) · `ROUTING_OPERATORS` · `MAX_ROUTING_CONDITIONS` ·
`MAX_ROUTING_JSON_BYTES` · `_reject_json_constant` · `_is_scalar`

**url names (31):**
`territory_rebalance_preview` · `territory_coverage_gap` · `territory_performance` ·
`territory_white_space` ·
`territory_rule_list` · `territory_rule_create` · `territory_rule_run` · `territory_rule_toggle` ·
`territory_rule_edit` · `territory_rule_delete` · `territory_rule_detail` ·
`account_territory_assignment_list` · `account_territory_assignment_create` ·
`account_territory_assignment_edit` · `account_territory_assignment_delete` ·
`account_territory_assignment_detail` ·
`territory_member_list` · `territory_member_create` · `territory_member_edit` ·
`territory_member_delete` · `territory_member_detail` ·
`quota_plan_list` · `quota_plan_create` · `quota_plan_submit` · `quota_plan_approve` ·
`quota_plan_reject` · `quota_plan_lock` · `quota_plan_edit` · `quota_plan_delete` · `quota_plan_detail`

**Cross-module reads (never written by 8.7):** `crm.Territory` · `crm.SalesQuota` · `crm.AccountProfile` ·
`crm.Opportunity` · `LeadRoutingRule` · `sales.ForecastPeriod` · `sales.ForecastSubmission` ·
`sales.AccountClassification` · `core.Party` · `core.Tenant` · `settings.AUTH_USER_MODEL`

**8.3 cross-links (8.7 must NOT modify 8.3's files):** `sales:account_coverage` ·
`sales:account_white_space`

---

## 19. THE ONE-PARAGRAPH SUMMARY

8.7 adds **four** tables to the live `sales` app — `TerritoryRule` (`TRG`),
`AccountTerritoryAssignment` (`TAS`), `TerritoryMember` (`TMB`), `QuotaPlan` (`QPA`) — and **four
read-only derived boards** with no table, no seeder row and no admin entry. It **declares neither
`Territory` nor `SalesQuota`**: both belong to CRM 1.2, both are read-only to 8.7, and the grep
`^class (Territory|SalesQuota)\b` under `apps\sales\models` must return **zero hits**. The migration is
**0013**; there is no scaffold step and no `config/` edit. Every context key in §9 and §10 is pinned, and
every money figure on every board is `Decimal` computed in Python — never `F()`, never a DB-side division,
never a float.

