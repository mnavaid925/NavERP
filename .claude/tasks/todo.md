> **How to read this file — checkboxes are only tracked for recent plans.** Plans for **7.14 and later**
> (and the procurement plans from 6.9 on) use `- [ ]` / `- [x]` tick-boxes, newest plan first at the top.
> Plans older than that were never ticked: their completion is recorded in a prose
> `### <Module> N.M — <Title> (close-out YYYY-MM-DD)` section instead. **An unticked box in an old plan is
> not evidence of missing work** — procurement 6.9's block, for example, carries 17 unticked boxes while
> 6.9 is shipped, in `LIVE_LINKS` and closed out in prose. For ground truth on what is built, read
> `LIVE_LINKS` in `apps/core/navigation.py` and run `venv\Scripts\python.exe temp\audit_integrity.py`.
> Do not mass-tick the backlog.
---

### 8.6 — Order Management — CLOSE-OUT 2026-09-29 (shipped)

**Status: COMPLETE.** 6 models, 49 routes, 23 templates, 91 tests across four lanes, migration
`0012`. `manage.py check` clean · `makemigrations sales --check` "No changes detected" ·
`seed_sales` idempotent on re-run · full unfiltered `apps/sales/tests/` suite green.

**What it owns, and what it deliberately does not.** SCM 4.5 keeps `scm.SalesOrder`,
`scm.SalesOrderLine` and `scm.SalesOrderAllocation`; 8.6 adds six related commercial records that
all carry a `ForeignKey` to that order. No `apps/scm/` file was touched, no second `SalesOrder`
was declared, and **no `JournalEntry` is posted** — `RevenueSchedule.journal_entry` is a
`SET_NULL`, `editable=False` column reserved for Accounting, and a test asserts it stays `None`
through a recognition.

**Six reviewers ran one at a time** and every pass wrote its findings to
`.claude/tasks/review-sales-8.6.md` before the next began. Passes 2–6 ran in the main session
because the sub-agent service was returning auth errors; the read-only contract and the
one-agent-in-flight rule were preserved. **Result: 3 CRITICALs, all one species — a guard the
prose promised and the code did not deliver.** The docstrings state each invariant correctly and
in detail, and the sibling module violates it anyway:

| | Defect | Fix |
|---|---|---|
| C1 | `recompute()` raised `TypeError` on any schedule mixing dated and undated obligations | `UNSCHEDULED` is now a real `date`, and `date.max` specifically so undated rows sort **last** |
| C2 | `OrderHold.clean()` keyed a message on `evaluation_snapshot`, which is off the form → `ValueError` 500 on create *and* edit | repair moved into `save()`; `clean()` never touches the field |
| C3 | an APPROVED amendment stayed editable, re-freezing the impact snapshot the approver signed | `EDITABLE_STATUSES` split from `OPEN_STATUSES` |

**Two things the review could not have found, both found by writing the tests:**

1. A **shared-file violation I committed myself.** While adding the 8.6 conftest section I
   truncated the 2,707-line shared `conftest.py` to 343 lines and committed it, deleting every
   8.1–8.5 fixture. Nothing caught it because I had only ever run my *own* lane, which imported
   cleanly from my rewritten copy. Restored from git, 8.6's section moved strictly below a marker
   comment, and the 8.4/8.5 lanes re-run to prove it. **L59.**
2. A **harness defect that would have produced a false report** — a `hasattr` guard spelling a
   name one way and the access it guarded spelling it another, so the guard passed and the access
   raised. The partial output read as "sections B and C are clean" when the script had simply
   died. **L60.**

**Filed, not fixed — deliberately out of scope:**

- A whole-database `seed_sales` can abort on a later tenant with `ValidationError: ["That
  idempotency key was already used for different enrichment evidence."]` from
  `apps/sales/services.py` `create_enrichment_event` (8.3-era code). It reproduces with no 8.6
  file involved and 8.6's own seeder block is byte-stable. One file, separate change — widening
  this changeset to repair an unrelated 8.3 bug would have been the wrong call.
- `apps/sales/models/_base.py` `TenantNumbered` numbering exhaustion (contract §12), out of scope
  by contract.

**The transferable lesson:** the checks that catch an *absent* or *contradicted* guard have to be
written from the contract, not from the code. Every one of C1–C3 is documented correctly in a
docstring two files away, so no amount of re-reading the prose finds it — only a test that
asserts the invariant independently does.

---

---

### 8.6 — Order Management (app `sales`, extends `scm.SalesOrder`)

> **This plan EXTENDS an existing app.** `apps/sales/` is live with 8.1 `LeadManagement`, 8.2 `OpportunityPipeline`,
> 8.3 `ContactAccountManagement`, 8.4 `SalesForecasting`, 8.5 `QuoteProposalCPQ`.
> **NO scaffold step. NO `config/settings.py` edit. NO `config/urls.py` edit.**
> Migration is **incremental**: the leaf today is `0011_cpqquote_signer_ip_address.py`, so **8.6 claims `0012`**.
> Plan written from `.claude/tasks/research-sales-8.6.md` (Phase 1, 836 lines). **Every load-bearing claim below
> was re-verified by grep at plan time, not taken from the research prose.**

**Repo state re-verified by the todo agent — L28, the grep is the truth**

| Claim | Verification | Result |
|---|---|---|
| `TenantNumbered` base | `Select-String 'apps\sales\models\_base.py' -Pattern '.'` | `TenantOwned` = `tenant` FK(`core.Tenant`, CASCADE, `related_name="+"`, `db_index=True`) + `created_at`(auto_now_add) + `updated_at`(auto_now). `TenantNumbered(TenantOwned)` adds `NUMBER_PREFIX = ""` and `number = CharField(max_length=20, editable=False)`. **Base for all four numbered models confirmed.** |
| SCM owns the order | `Select-String 'apps\scm\models\OrderManagement\*.py' -Pattern 'NUMBER_PREFIX\|^class '` | `SalesOrder` (`:20`, `NUMBER_PREFIX = "SO"`, `TenantNumbered`) · `SalesOrderLine` (`:185`, plain `models.Model` — **tenant-less**) · `SalesOrderAllocation` (`:15`, `TenantOwned`, **no** prefix). **Exactly three order classes, all SCM's.** |
| Next migration | `Get-ChildItem 'apps\sales\migrations\*.py'` | `0001`…`0011_cpqquote_signer_ip_address.py`. **8.6 = `0012`.** |
| Prefix collisions | sweep of every `NUMBER_PREFIX` in `apps\*\models\**\*.py` | **`OVR`, `OHD`, `AMD`, `RVS` — zero hits. All four FREE.** |
| `related_name` collisions | grep across `apps\**\models\**\*.py` | `revenue_schedules` is taken ONLY on `projects.Project` / `projects.ProjectMilestone` (`apps/projects/models/FinancialBillingManagement/RevenueSchedules.py:38,45`) — a **different target model**, so `related_name="revenue_schedules"` on `scm.SalesOrder` does **not** clash. `sales_revenue_schedules` on `accounting.FiscalPeriod`/`accounting.Currency`: **zero hits, free.** `order_holds`, `order_amendments`, `order_validation_rules`, `raised_holds`, `obligations`: **zero hits, free.** |
| FK targets | recursive grep | `scm.Item` `InventoryManagement/Items.py:73` · `scm.SalesOrderAllocation` `OrderManagement/SalesOrderAllocations.py:15` · `scm.Shipment`/`TrackingEvent` `TransportationManagement/Shipments.py:22,152` · `core.Party` `core/models/Party.py:5` · `core.Document` `core/models/Document.py:5` · `core.AuditLog` `core/models/AuditLog.py:5` · `accounting.CustomerProfile` `AccountsReceivable/CustomerProfiles.py:5` (carries `credit_limit`) · `accounting.Currency` `GeneralLedger/Currencies.py:6` · `accounting.FiscalPeriod` `GeneralLedger/FiscalPeriods.py:5` · `accounting.JournalEntry` `GeneralLedger/JournalEntries.py:5` · `accounting.Invoice` `AccountsReceivable/Invoices.py:6`. **All EXIST.** |
| 8.6 packages absent | `Test-Path` | `apps/sales/models/OrderManagement` **False** · `apps/sales/urls/OrderManagement` **False** · `templates/sales/ordermanagement` **False**. **Nothing to overwrite.** |
| Badge classes | grep `static/css/*.css` | Exactly `.badge-amber .badge-green .badge-info .badge-muted .badge-red .badge-slate`. **`badge-success` / `badge-warning` / `badge-danger` DO NOT EXIST.** |
| `sales` url prefixes in use | grep `path\("([a-z-]+)/` | `account-classifications, account-plans, accounts, account-stakeholders, approval-rules, bundles, enrichment-events, forecast, leads, nurture-enrollments, opportunity, overview, qualifications, quotes, routing-rules, score-events`. **Every 8.6 prefix below is free.** |
| conftest policy | grep `apps\sales\tests\conftest.py` for `CPQ`/`QUOTE_` | **Zero hits.** 8.5 added **no** contract constants to conftest. **8.6 follows 8.5: zero conftest edits.** |

**conftest policy, stated explicitly.** `apps/sales/tests/conftest.py` is 2707 lines and is the contract for 8.1
(`LEADMANAGEMENT_*`), 8.2 (`OPPORTUNITYPIPELINE_*`) and 8.4 (`SALESFORECASTING_*`) only. 8.5 did **not** extend it:
its record factories and vocabulary assertions live in `test_quote_proposal_cpq_models.py` under the
`_quoteproposalcpq_*` / `quoteproposalcpq_*` prefix. **8.6 does the same — no conftest edit at all.** All six
record factories, every vocabulary assertion and every prefix assertion go into `test_ordermanagement_models.py`
under the `_ordermanagement_*` / `ordermanagement_*` namespace, so a future 8.7 appending nearby cannot shadow
them.

---

#### 1. Ownership & boundary (L36 / L37) — the ruling this whole build obeys

- [ ] **State the ruling in the build, in the three durable encodings (L36 step 3), all in the same pass:**
  1. A comment block on the new `LIVE_LINKS["8.6"]` entry in `apps/core/navigation.py`.
  2. A header docstring on `apps/sales/models/OrderManagement/__init__.py` naming `scm.SalesOrder` as the owner and
     quoting `apps/scm/models/OrderManagement/SalesOrders.py:1-16` verbatim.
  3. This plan block, plus a line appended to `.claude/tasks/lessons.md` if the ruling is refined during the build.
- [ ] **`scm.SalesOrder`, `scm.SalesOrderLine` and `scm.SalesOrderAllocation` are OWNED BY SCM 4.5.** 8.6 **EXTENDS
  them by `ForeignKey` and declares NO second order master, NO order line and NO allocation.** A second `SalesOrder`
  in `apps/sales` is a bug, not a variant — `SalesOrders.py:1-16` says so in as many words ("Modules 8 and 9 do not
  exist. Under the ships-first rule … Module 8.6 'Order Management' is a DIFFERENT, later feature set … that will FK
  INTO this order rather than declare a second one"), and `SalesOrders.py:44-47` reserves the amend/cancel flow for
  exactly this sub-module ("There is deliberately NO amendment flow here — amend/cancel with impact analysis is
  Module 8.6's job, not something to half-build now").
- [ ] **The exact existing models 8.6 reuses, and the FK direction (8.6 → spine, never spine → 8.6):**

  | Spine model 8.6 points at | Location | Direction | What 8.6 does with it |
  |---|---|---|---|
  | `scm.SalesOrder` | `apps/scm/models/OrderManagement/SalesOrders.py:20` | `OrderHold.sales_order` / `OrderAmendment.sales_order` / `RevenueSchedule.sales_order` **→** `scm.SalesOrder` | parent. **Read** status, totals, `credit_hold`/`fraud_flag`/`hold_reason`, `source_channel`, `ship_to_address`, `source_quote`, `promised_date`/`requested_date`, `invoice`. **Write** only `credit_hold` and `hold_reason`, and only from the hold-clear views. |
  | `scm.SalesOrderLine` | same file `:185` (tenant-less) | `OrderAmendmentLine.sales_order_line` (SET_NULL) and `PerformanceObligation.sales_order_line` (PROTECT) **→** `scm.SalesOrderLine` | parent for the two child rows. **Read** `item`, `quantity_ordered`, `unit_price` and the derived `quantity_allocated()` / `quantity_backordered()` / `is_unmapped` / `is_backordered`. **Never re-declared, re-derived or shadowed.** |
  | `scm.SalesOrderAllocation` | `SalesOrderAllocations.py:15` | **NO FK.** 8.6 does not model it. | Read-only via `sales_order.allocations`; bullet 2's "warehouse allocation" **is** this table. Resolution verbs go through 4.5's own `salesorderallocation_release` / `salesorderallocation_cancel` — never a new writer. |
  | `scm.Item` | `InventoryManagement/Items.py:73` | `OrderAmendmentLine.item`, `PerformanceObligation.item` **→** `scm.Item` | Read `is_active` (rule `inactive_item`) and `standard_cost` (margin delta). |
  | `scm.Shipment` / `scm.TrackingEvent` | `TransportationManagement/Shipments.py:22,152` | **NO FK.** Read-only. | Shipped %, POD (`pod_received` / `pod_received_at`) and the timeline, all projected — never re-captured. |
  | `accounting.CustomerProfile` | `AccountsReceivable/CustomerProfiles.py:5` | **NO FK.** Read-only. | `credit_limit` for rule `credit_limit`. |
  | `accounting.Invoice` | `AccountsReceivable/Invoices.py:6` | **NO FK.** Read via `sales_order.invoice`. | Open AR for the credit rule; the invoiced side of the asset/liability position. |
  | `accounting.FiscalPeriod` | `GeneralLedger/FiscalPeriods.py:5` | `RevenueSchedule.fiscal_period`, `PerformanceObligation.fiscal_period` **→** `accounting.FiscalPeriod` | Recognition period. |
  | `accounting.Currency` | `GeneralLedger/Currencies.py:6` | `RevenueSchedule.currency` **→** `accounting.Currency` | Carried from the order; multi-currency revaluation is accounting's. |
  | `accounting.JournalEntry` | `GeneralLedger/JournalEntries.py:5` | `PerformanceObligation.journal_entry` (SET_NULL, **reference only**) **→** `accounting.JournalEntry` | **8.6 posts NO journal entry, ever** (L29). |
  | `core.Party` | `core/models/Party.py:5` | `OrderValidationRule.party`, `OrderHold.party` **→** `core.Party` | Per-customer rule scoping; the hold's customer. |
  | `core.Document` | `core/models/Document.py:5` | `OrderAmendment.document` **→** `core.Document` | The signed change order. |
  | `core.AuditLog` | `core/models/AuditLog.py:5` | **NO FK.** | Written by `write_audit_log()` on every 8.6 state transition. |
  | `accounting.RecurringInvoice` | (`RINV-`, accounting) | **NO FK.** Read-only. | The renewals-due board reads it. **8.6 builds no second cadence engine.** |

  - **Never re-declared, one sentence per model, for the close-out notes:** `OrderValidationRule` does **not**
    define a parallel hold flag (it *reads* `SalesOrder.credit_hold`) · `OrderHold` adds no hold column, no hold
    status and no second writer of the order's state machine · `OrderAmendment` adds no order line and no cancel
    verb · `RevenueSchedule` adds no shipment, no invoice, no ledger entry and no backorder table.
- [ ] **L36 step-2 close-out — `NavERP-ERD.md` reconciled for BOTH rows. Not optional, and row 4 must be left alone.**
  - **Row 4 (SCM, line 466) is already correct** — it reads *"SalesOrder, SalesOrderLine, SalesOrderAllocation
    (4.5 OMS, as-built — SCM ships the sales order FIRST, so it OWNS it here; Modules 8/9 EXTEND it by FK rather
    than re-declaring …)"*. **Confirm it and do not "helpfully" edit it.**
  - **Row 8 (Sales, line 470) is STALE** — verified by reading it: it stops at 8.3, mentions neither 8.4, 8.5 nor
    8.6, and its "Reuses" column already names `scm.SalesOrder` without saying how Sales uses it. Its **"Adds"**
    column must gain the 8.6 as-built set — `OrderValidationRule`, `OrderHold`, `OrderAmendment` +
    `OrderAmendmentLine`, `RevenueSchedule` + `PerformanceObligation` — marked *as-built*, and its **"Reuses"**
    column must state that Sales **extends `scm.SalesOrder` (4.5) by FK and declares no second order master**.
    Leaving row 8 stale re-creates the exact contradiction L36 step 2 exists to prevent, and it is the trap this
    sub-module is most likely to fall into because the order *looks* like it belongs to Sales.
- [ ] **Migration `0012` touches `sales` only.** No operation may name an `scm`, `accounting`, `core`, `crm` or
  `projects` model. A `scm` field added by 8.6 is a forked spine — grep the generated `0012_*.py` and fail the build
  if it contains one.
- [ ] **Every FK to a spine model is by STRING** (`"scm.SalesOrder"`, `"scm.SalesOrderLine"`, `"scm.Item"`,
  `"accounting.FiscalPeriod"`, `"accounting.Currency"`, `"accounting.JournalEntry"`, `"core.Party"`,
  `"core.Document"`) and **every import inside the four packages is ABSOLUTE** (`from apps.sales.models._base
  import *`, `from apps.sales.views._common import *`).
- [ ] **The single-writer rules, checked in the smoke pass:** no view in `apps/sales` writes `SalesOrder.status`
  directly · `OrderHold` writes back only `SalesOrder.credit_hold` / `hold_reason`, and 4.5's
  `salesorder_release_hold` stays the release verb · `OrderAmendment.apply()` is the only writer of
  `SalesOrderLine.quantity_ordered` / `unit_price` and it calls 4.5's own `sales_order.recalc_totals()` ·
  `RevenueSchedule` posts **no** `JournalEntry`.

#### 2. Models — one entity per file, all four layers

Four numbered models + two tenant-less children, all under `apps/sales/models/OrderManagement/` (the NavERP.md 8.6
sub-module title in PascalCase), re-exported by that package's `__init__.py`.

| # | Class | File | Base | `NUMBER_PREFIX` | `number` `max_length` |
|---|---|---|---|---|---|
| 1 | `OrderValidationRule` | `OrderValidationRules.py` | `TenantNumbered` | **`"OVR"`** | 20 (inherited) |
| 2 | `OrderHold` | `OrderHolds.py` | `TenantNumbered` | **`"OHD"`** | 20 (inherited) |
| 3 | `OrderAmendment` | `OrderAmendments.py` | `TenantNumbered` | **`"AMD"`** | 20 (inherited) |
| 3b | `OrderAmendmentLine` | `OrderAmendments.py` | plain `models.Model` (**tenant-less**) | **NONE** | — |
| 4 | `RevenueSchedule` | `RevenueSchedules.py` | `TenantNumbered` | **`"RVS"`** | 20 (inherited) |
| 4b | `PerformanceObligation` | `RevenueSchedules.py` | plain `models.Model` (**tenant-less**) | **NONE** | — |

All four prefixes are ≤ 3 chars, so `XXX-00001` is 9 characters against `max_length=20` — room for a 6-digit
sequence. `MST` is **taken** by `projects.ProjectMilestone`, a second reason milestones here are child rows and not
a numbered master. `SO`, `SHP`, `BKO`, `RMA`, `PRS`, `CPQ`, `BND`, `QAR`, `RINV`, `MST` are all taken; `OVR` /
`OHD` / `AMD` / `RVS` are all free (verified above).

##### 2.1 `OrderValidationRule` — `models/OrderManagement/OrderValidationRules.py`

Replaces 4.5's two hard-coded hold checks with a tenant-configurable, typed rule set. **Fields, in this order:**

- `tenant` — inherited from `TenantOwned` (`core.Tenant`, CASCADE, `related_name="+"`, `db_index=True`)
- `created_at` / `updated_at` — inherited from `TenantOwned`
- `number` — inherited from `TenantNumbered` (`CharField(max_length=20, editable=False)`)
- `name` — `CharField(max_length=255)`
- `rule_type` — `CharField(max_length=24, choices=RULE_TYPE_CHOICES, default="credit_limit")`
- `severity` — `CharField(max_length=12, choices=SEVERITY_CHOICES, default="hold")`
- `active_on` — `CharField(max_length=12, choices=ACTIVE_ON_CHOICES, default="submit")`
- `parameters` — `JSONField(default=dict, blank=True)` — per-rule-type thresholds (`{"amount": 5000}`, `{"pct": 20}`).
  **A JSON blob, not a column per rule type**, so a new rule type is data, not a migration.
- `party` — `ForeignKey("core.Party", on_delete=models.CASCADE, null=True, blank=True, related_name="order_validation_rules")`
  — blank = applies to every customer
- `priority` — `PositiveIntegerField(default=10)`
- `is_active` — `BooleanField(default=True)`
- `description` — `TextField(blank=True)`

**CHOICES, spelled out in full, in this exact order:**

- `RULE_TYPE_CHOICES = [("credit_limit", "Credit Limit Exceeded"), ("order_value", "Order Value Ceiling"), ("margin_floor", "Margin Floor"), ("discount_ceiling", "Line Discount Ceiling"), ("unmapped_item", "Unmapped Item Present"), ("missing_ship_to", "Missing Ship-To Address"), ("expired_quote", "Source Quote Expired"), ("inactive_item", "Inactive Item On Order")]`
- `SEVERITY_CHOICES = [("block", "Block Submission"), ("hold", "Hold For Review"), ("warn", "Warn Only")]`
- `ACTIVE_ON_CHOICES = [("submit", "On Submit"), ("confirm", "On Confirm"), ("allocate", "Before Allocation")]`

**`Meta`:** `ordering = ["priority", "name", "-id"]` ·
`constraints = [models.UniqueConstraint(fields=["tenant", "number"], name="sales_ovr_tenant_number_uniq")]` ·
`indexes = [models.Index(fields=["tenant", "rule_type"], name="sales_ovr_tenant_type_idx"), models.Index(fields=["tenant", "is_active"], name="sales_ovr_tenant_active_idx"), models.Index(fields=["party"], name="sales_ovr_party_idx")]`

**Key method — `evaluate(order)` → `list[dict]`, returning findings and writing NOTHING.** Each finding is
`{"rule": <number str>, "rule_id": <int>, "rule_type": <str>, "severity": <str>, "message": <str>, "snapshot": <dict>}`.
The caller (a 8.6 view) decides what to do with them — the same split as 4.5's `_evaluate_hold`, which is view-layer
on purpose. Evaluation order is `Meta.ordering` (priority first), and a rule scoped to a `party` applies only when
`order.customer_id == party_id`. **It returns every failure, not just the first** — a rule set that stops at the
first finding hides the rest of the problem from the person fixing it.

##### 2.2 `OrderHold` — `models/OrderManagement/OrderHolds.py`

Turns `SalesOrder.credit_hold` / `hold_reason` from a transient flag into a checkout-able, per-rule, frozen-snapshot
record — the D365 order-hold workbench. **Fields, in this order:**

- `tenant` / `created_at` / `updated_at` / `number` — inherited
- `sales_order` — `ForeignKey("scm.SalesOrder", on_delete=models.CASCADE, related_name="order_holds")`
- `rule` — `ForeignKey("sales.OrderValidationRule", on_delete=models.SET_NULL, null=True, blank=True, related_name="raised_holds")`
  — **SET_NULL, not PROTECT**: deactivating a rule must not orphan the holds it raised
- `party` — `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_holds")`
  — the customer, set from `sales_order.customer` on raise
- `hold_type` — `CharField(max_length=16, choices=HOLD_TYPE_CHOICES, default="validation")`
- `severity` — `CharField(max_length=12, choices=SEVERITY_CHOICES, default="hold", editable=False)` — the rule's
  severity **at the moment it fired**; `editable=False` so re-tuning a rule never rewrites history
- `reason` — `TextField(help_text="Why this order is held, in one sentence.")`
- `evaluation_snapshot` — `TextField(blank=True, editable=False)` — frozen JSON evidence, copying 4.10's
  `ReturnAuthorization.policy_snapshot` pattern verbatim
- `status` — `CharField(max_length=12, choices=STATUS_CHOICES, default="open", editable=False)`
- `raised_at` — `DateTimeField(auto_now_add=True, editable=False)`
- `raised_by` — `ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+", editable=False)`
- `checked_out_by` — `ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+", editable=False)`
- `checked_out_at` — `DateTimeField(null=True, blank=True, editable=False)`
- `cleared_by` — `ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+", editable=False)`
- `cleared_at` — `DateTimeField(null=True, blank=True, editable=False)`
- `clear_note` — `CharField(max_length=255, blank=True)`

**CHOICES, in full:** `HOLD_TYPE_CHOICES = [("credit", "Credit"), ("fraud", "Fraud / New Customer"),
("validation", "Validation Rule"), ("manual", "Manual Hold")]` — the first two are 4.5's existing vocabulary
(`credit_hold` / `fraud_flag`), so 8.6 records *which* of them fired rather than inventing a new axis ·
`SEVERITY_CHOICES` (identical to the rule's, above) · `STATUS_CHOICES = [("open", "Open"), ("cleared", "Cleared"),
("superseded", "Superseded By A New Rule")]`

**Class constant:** `OPEN_STATUSES = ("open",)`

**`Meta`:** `ordering = ["-raised_at", "-id"]` · `constraints = [models.UniqueConstraint(fields=["tenant",
"number"], name="sales_ohd_tenant_number_uniq")]` · `indexes = [models.Index(fields=["tenant", "status"],
name="sales_ohd_tenant_status_idx"), models.Index(fields=["sales_order", "status"], name="sales_ohd_order_status_idx")]`

**`@property is_checked_out`** → `self.checked_out_by_id is not None and self.status == "open"` — the workbench's
"pause symbol" column.

**`write_back` is NOT a model method.** Clearing the last open hold writes `SalesOrder.credit_hold = False` and
`hold_reason = ""` **from the view**, so 8.6 never owns the order's state machine. 4.5's `salesorder_release_hold`
remains the release verb.

##### 2.3 `OrderAmendment` + `OrderAmendmentLine` — `models/OrderManagement/OrderAmendments.py`

The change-order workflow `SalesOrders.py:44-47` explicitly reserved for 8.6. **`OrderAmendment` fields, in order:**

- `tenant` / `created_at` / `updated_at` / `number` — inherited
- `sales_order` — `ForeignKey("scm.SalesOrder", on_delete=models.CASCADE, related_name="order_amendments")`
- `change_type` — `CharField(max_length=16, choices=CHANGE_TYPE_CHOICES, default="quantity")`
- `reason` — `TextField(help_text="Required. The documented case for this change.")` (ERPNext's "documented case",
  same rule as procurement 6.8's amendment)
- `status` — `CharField(max_length=12, choices=STATUS_CHOICES, default="pending", editable=False)`
- `impact_snapshot` — `TextField(blank=True, editable=False)` — frozen JSON: allocated / shipped / invoiced / margin
  delta / promise-date consequence / recognition consequence
- `requested_by` — `ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+", editable=False)`
- `decided_by` — `ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+", editable=False)`
- `decided_at` — `DateTimeField(null=True, blank=True, editable=False)`
- `applied_at` — `DateTimeField(null=True, blank=True, editable=False)`
- `decision_note` — `TextField(blank=True)`
- `document` — `ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_amendments")`
  — the signed change order

**CHOICES, in full, in this exact order:**
- `CHANGE_TYPE_CHOICES = [("quantity", "Quantity Change"), ("price", "Price / Discount Change"), ("item", "Item Substitution"), ("ship_to", "Ship-To Change"), ("requested_date", "Requested Date Change"), ("add_line", "Add Line"), ("remove_line", "Remove Line"), ("cancel", "Cancellation")]`
- `STATUS_CHOICES = [("draft", "Draft"), ("pending", "Pending Approval"), ("approved", "Approved"), ("rejected", "Rejected"), ("applied", "Applied"), ("withdrawn", "Withdrawn")]`

**Class constants:** `AMENDABLE_STATUSES = ("submitted", "on_hold", "allocated", "partially_fulfilled")` — mirrors
4.5's `ALLOCATABLE_STATUSES`; a `draft` needs no amendment and a `closed`/`cancelled` one is history ·
`OPEN_STATUSES = ("draft", "pending", "approved")`

**`Meta`:** `ordering = ["-created_at", "-id"]` · `constraints = [models.UniqueConstraint(fields=["tenant",
"number"], name="sales_amd_tenant_number_uniq")]` · `indexes = [models.Index(fields=["tenant", "status"],
name="sales_amd_tenant_status_idx"), models.Index(fields=["sales_order", "status"], name="sales_amd_order_status_idx"),
models.Index(fields=["tenant", "change_type"], name="sales_amd_tenant_type_idx")]`

**`@classmethod has_open_for(cls, order)`** — one open amendment per order, copied from `procurement.ContractAmendment`.
At most one open amendment, so two amendments cannot interleave and the second one's "original" values are not stale.

**Key method — `apply(decider, sales_order_locked, note="")`** — copies `procurement.ContractAmendment.apply()`
almost verbatim. It takes the order **already `select_for_update()`-ed inside the caller's `transaction.atomic()`**,
writes the line quantities / prices, calls `sales_order.recalc_totals()` (4.5's own Python-sum method — **never** an
`F()` expression, which integer-divides on SQLite and silently drops every per-line discount/tax), recomputes the
revenue schedule, and stamps the decision in the same transaction. **It re-checks its own guards inside the method** —
a button hidden in a template is not a guard (the 6.9 C1 lesson). For `change_type="cancel"` it **delegates to
4.5's cancellation rule** (refuse while `has_active_allocations()`) rather than writing `status` itself.

**`OrderAmendmentLine` — tenant-less child, NO `NUMBER_PREFIX`**, reached via `amendment.sales_order.tenant`:

- `amendment` — `ForeignKey("sales.OrderAmendment", on_delete=models.CASCADE, related_name="lines")`
- `sales_order_line` — `ForeignKey("scm.SalesOrderLine", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_amendment_lines")`
  — **SET_NULL, null**: an *added* line has no original
- `item` — `ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_amendment_lines")`
- `original_quantity` — `DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))`
- `proposed_quantity` — `DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))`
- `original_unit_price` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
- `proposed_unit_price` — `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
- `notes` — `CharField(max_length=255, blank=True)`

**`@property line_delta`** → `proposed_quantity - original_quantity` ·
**`@property value_delta`** → `(proposed_quantity * proposed_unit_price) - (original_quantity * original_unit_price)`
· **`@property is_addition`** → `self.sales_order_line_id is None`
**`Meta`:** `ordering = ["id"]` · `indexes = [models.Index(fields=["amendment"], name="sales_amdline_amendment_idx")]`

##### 2.4 `RevenueSchedule` + `PerformanceObligation` — `models/OrderManagement/RevenueSchedules.py`

The only representation of ASC 606 anywhere in the repo, keyed on the **order** (not the project), with every
balance derived and no journal posting. **`RevenueSchedule` fields, in order:**

- `tenant` / `created_at` / `updated_at` / `number` — inherited
- `sales_order` — `ForeignKey("scm.SalesOrder", on_delete=models.CASCADE, related_name="revenue_schedules")`
- `currency` — `ForeignKey("accounting.Currency", on_delete=models.PROTECT, related_name="sales_revenue_schedules")`
  — carried from the order, never typed free-hand
- `fiscal_period` — `ForeignKey("accounting.FiscalPeriod", on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_revenue_schedules")`
- `method` — `CharField(max_length=20, choices=METHOD_CHOICES, default="point_in_time")`
- `compliance_standard` — `CharField(max_length=8, choices=COMPLIANCE_STANDARD_CHOICES, default="asc606")`
- `status` — `CharField(max_length=12, choices=STATUS_CHOICES, default="draft", editable=False)`
- `contract_amount` — `DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"), editable=False)`
  — snapshot of the order's transaction price
- `recognized_amount` — `DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"), editable=False)`
- `deferred_amount` — `DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"), editable=False)`
- `approved_by` — `ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+", editable=False)`
- `approved_at` — `DateTimeField(null=True, blank=True, editable=False)`
- `notes` — `TextField(blank=True)`

**CHOICES, in full, in this exact order:**
- `METHOD_CHOICES = [("point_in_time", "Point In Time"), ("over_time", "Over Time"), ("milestone", "Milestone"), ("percent_complete", "Percent Complete"), ("ratable", "Ratable / Straight-Line")]`
- `COMPLIANCE_STANDARD_CHOICES = [("asc606", "ASC 606"), ("ifrs15", "IFRS 15")]`
- `STATUS_CHOICES = [("draft", "Draft"), ("active", "Active"), ("complete", "Complete"), ("void", "Void")]`

**`Meta`:** `ordering = ["-created_at", "-id"]` · `constraints = [models.UniqueConstraint(fields=["tenant",
"number"], name="sales_rvs_tenant_number_uniq")]` · `indexes = [models.Index(fields=["tenant", "status"],
name="sales_rvs_tenant_status_idx"), models.Index(fields=["sales_order"], name="sales_rvs_order_idx"),
models.Index(fields=["tenant", "fiscal_period"], name="sales_rvs_tenant_period_idx")]`

**Key method — `recompute()`** — rebuilds `recognized_amount` and `deferred_amount` from the obligations **in
Python**, never with `F()` / `aggregate` decimal arithmetic (SQLite integer-division trap, the same one 4.5's
`recalc_totals()` docstring documents). Called from `OrderAmendment.apply()` when the transaction price moves, and
from the schedule form's save. `point_in_time` recognises an obligation on `recognize_on`; `ratable` / `over_time`
spread `allocated_amount` evenly across the period; `milestone` recognises the whole allocation when
`recognize_on <= today`.

**`PerformanceObligation` — tenant-less child, NO `NUMBER_PREFIX`** (`MST` is taken by
`projects.ProjectMilestone`, a further reason milestones here are children and not a numbered master):

- `schedule` — `ForeignKey("sales.RevenueSchedule", on_delete=models.CASCADE, related_name="obligations")`
- `sales_order_line` — `ForeignKey("scm.SalesOrderLine", on_delete=models.PROTECT, related_name="performance_obligations")`
- `item` — `ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name="performance_obligations")`
- `obligation_type` — `CharField(max_length=20, choices=OBLIGATION_TYPE_CHOICES, default="goods_delivered")`
- `description` — `CharField(max_length=255, blank=True)`
- `allocation_pct` — `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(0), MaxValueValidator(100)])`
- `allocated_amount` — `DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"), editable=False)`
- `recognition_method` — `CharField(max_length=20, choices=METHOD_CHOICES, default="point_in_time")`
- `recognize_on` — `DateField(null=True, blank=True)` — the milestone / satisfaction date
- `status` — `CharField(max_length=12, choices=OBLIGATION_STATUS_CHOICES, default="planned", editable=False)`
- `fiscal_period` — `ForeignKey("accounting.FiscalPeriod", on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_performance_obligations")`
- `milestone_label` — `CharField(max_length=120, blank=True)`
- `recognized_amount` — `DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"), editable=False)`
- `journal_entry` — `ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_performance_obligations", editable=False)`
  — **a reference only. 8.6 posts NO journal entry** (L29), matching `scm.ReturnAuthorization`'s "SCM posts NO
  JournalEntry"

**CHOICES, in full:** `OBLIGATION_TYPE_CHOICES = [("goods_delivered", "Goods Delivered"), ("service_over_time",
"Service Over Time"), ("licence_right", "Right To Use / Licence"), ("installation", "Installation"),
("milestone", "Milestone")]` · `OBLIGATION_STATUS_CHOICES = [("planned", "Planned"), ("partial", "Partially
Recognized"), ("recognized", "Fully Recognized"), ("skipped", "Skipped"), ("void", "Void")]` ·
`METHOD_CHOICES` as above

**`Meta`:** `ordering = ["id"]` · `indexes = [models.Index(fields=["schedule"], name="sales_po_schedule_idx"),
models.Index(fields=["status"], name="sales_po_status_idx"), models.Index(fields=["fiscal_period"], name="sales_po_period_idx")]`

#### 3. Derived-not-stored rule — every one of these MUST be a `@property`, never a column

This is L37 applied to order management, and it is the single discipline that keeps 8.6 at four tables instead of
eleven. Each figure below would otherwise be a second source of truth beside the rows it summarises.

- [ ] **`OrderValidationRule`** — no derived columns. A rule's verdict is a function of the order *now*, so it is
  `evaluate()`'s return value, not a field. (A stored `last_fired_at` would be wrong the moment the order changes.)
- [ ] **`OrderHold`** — `is_checked_out` is a `@property` off `checked_out_by_id` + `status`; **not** a Boolean
  column, which would disagree with `status` the moment a hold is cleared without its checkout being released.
- [ ] **`OrderAmendmentLine`** — `line_delta` and `value_delta` are `@property` (see 2.3). Storing a delta
  duplicates the two operands and is wrong the instant either is edited.
- [ ] **`OrderAmendment`** — **`impact_snapshot` is a FROZEN STRING, not a set of live columns.** The live figures
  (allocated / shipped / invoiced / margin) are read on demand from `scm`; the snapshot answers "what did the
  approver see on the day", and a live column could not answer that after the fact.
- [ ] **`RevenueSchedule`** — these are the seven that must never become columns:
  - `remaining_deferred` → `deferred_amount` — a stored copy is a second truth beside `recognized_amount`, which is
    itself recomputed.
  - `contract_asset` → `recognized_amount - invoiced_amount` — a **signed** position, one property, not two models
    and not two columns (IFRS 15's contract asset).
  - `contract_liability` → `max(Decimal("0.00"), invoiced_amount - recognized_amount)` — the mirror of the same
    signed number.
  - `invoiced_amount` → `sales_order.invoice.total if sales_order.invoice else Decimal("0.00")` — the invoiced side
    is `accounting.Invoice`'s to own; 8.6 reads it.
  - `allocation_is_complete` → `abs(sum(obligation.allocated_amount) - contract_amount) < Decimal("0.01")` — a
    completeness *check* over the obligations, never a flag that can drift from them.
  - `recognition_progress_pct` → `(recognized_amount / contract_amount * 100)` in Python — an `F()` percentage
    integer-divides on SQLite.
  - `days_overdue` → derived from the obligations' `recognize_on` and `today` in Python; **`overdue`** →
    `days_overdue > 0`. **A stored `days_overdue` is wrong the moment the clock ticks past midnight** — the
    procurement 6.11 `Backorder` `RISK_CHOICES` docstring is the in-repo rule.
  - `is_editable` → `status in EDITABLE_STATUSES` (derived, not a column).
- [ ] **`PerformanceObligation`** — `remaining_amount` → `allocated_amount - recognized_amount`.
- [ ] **Not a column anywhere in 8.6, in the build's own words:** order quantities, backorder quantity, allocated
  quantity, deferred revenue, contract asset, contract liability, recognition progress, days overdue, expected order
  date, a `locked` flag, a `days_open` counter, a reorder cadence. Each is either 4.5's derived property
  (`quantity_allocated()`, `quantity_backordered()`, `is_backordered`, `is_unmapped`) or a `@property` here.
- [ ] **Every derived number computed in PYTHON over a fetched set, never with `F()` / `aggregate` decimal
  arithmetic.** The SQLite integer-division trap is documented in 4.5's own `recalc_totals()` docstring; it silently
  drops fractional cents rather than raising.
- [ ] **`RevenueSchedule.recompute()` and `OrderAmendment.apply()` are the only writers of `recognized_amount` /
  `deferred_amount` / `contract_amount` / `allocated_amount` / the obligation's `recognized_amount`.** All are
  `editable=False`, so no form can write them and no view writes them directly.

#### 4. Forms — exact `Meta.fields` and every exclusion, with the reason

All form classes inherit `TenantModelForm` from `apps/core/forms/_common.py` (which sets the `datetime-local` /
`date` / `form-select` / `form-textarea` / `form-check` widget classes), are constructed with
`tenant=request.tenant`, and set `instance.tenant` via the repo's `TenantUniqueMixin` pattern.

- [ ] **`OrderValidationRuleForm`** — `Meta.fields = ["name", "rule_type", "severity", "active_on", "parameters",
  "party", "priority", "is_active", "description"]`. **Excluded:** `tenant` (set by the view / `TenantUniqueMixin`) ·
  `number` (auto-numbered by `TenantNumbered.save()`) · `created_at` / `updated_at` (`auto_now*`).
  `party`'s queryset is narrowed to `core.Party.objects.filter(tenant=self.tenant)` — a rule may only point at the
  tenant's own customer. `parameters` renders as a textarea; a malformed JSON blob is a **form** error, never a 500
  from `JSONField` on save.
- [ ] **`OrderHoldForm`** — `Meta.fields = ["sales_order", "rule", "party", "hold_type", "reason", "clear_note"]`.
  **Excluded, with the reason for each:** `tenant` (tenant) · `number` (auto-number) · `status`
  (**workflow-governed** — written only by the raise / clear / supersede actions) · `severity`
  (**frozen at fire time**, `editable=False` — re-tuning a rule must never rewrite history) · `evaluation_snapshot`
  (**frozen evidence**, `editable=False`, server-generated from `rule.evaluate()`) · `raised_at` / `raised_by` /
  `checked_out_by` / `checked_out_at` / `cleared_by` / `cleared_at` (**action-stamped** — each written by exactly one
  named POST view) · `created_at` / `updated_at` (auto). Querysets: `sales_order` →
  `scm.SalesOrder.objects.filter(tenant=self.tenant)`, `rule` → `OrderValidationRule.objects.filter(tenant=
  self.tenant)`, `party` → `core.Party.objects.filter(tenant=self.tenant)`.
- [ ] **`OrderAmendmentForm`** — `Meta.fields = ["sales_order", "change_type", "reason", "document"]`.
  **Excluded:** `tenant` (tenant) · `number` (auto-number) · `status` (workflow — `pending` on create, then only the
  decide / apply / withdraw actions) · `impact_snapshot` (**frozen at propose time**, server-generated) · `requested_by`
  / `decided_by` / `decided_at` / `applied_at` (**action-stamped**) · `decision_note` (written by the decision form,
  not the create form) · `created_at` / `updated_at` (auto). Querysets: `sales_order` →
  `scm.SalesOrder.objects.filter(tenant=self.tenant, status__in=OrderAmendment.AMENDABLE_STATUSES)` — the dropdown
  itself refuses an unamendable order · `document` → `core.Document.objects.filter(tenant=self.tenant)`.
  **`clean()` re-checks `AMENDABLE_STATUSES` and `has_open_for()`**, raising on `NON_FIELD_ERRORS` and never
  `add_error(<field>)` for a field the form does not have — the 0.20 four-statuses-500 lesson.
- [ ] **`OrderAmendmentDecisionForm`** (`forms.Form`, not a ModelForm) — `fields = ["decision", "decision_note"]`,
  where `decision` is a `ChoiceField` over `[("approved", "Approve"), ("rejected", "Reject")]` and `decision_note` is
  a `CharField(max_length=255, blank=True)`. **One form for both outcomes**, so approve and reject cannot disagree
  about what they stamp.
- [ ] **`OrderAmendmentLineForm`** — `Meta.fields = ["sales_order_line", "item", "original_quantity",
  "proposed_quantity", "original_unit_price", "proposed_unit_price", "notes"]`. **Excluded:** `amendment` (**set by
  the parent view**, never by the user) · `line_delta` / `value_delta` (**derived**).
  `sales_order_line`'s queryset is `scm.SalesOrderLine.objects.filter(sales_order=instance.amendment.sales_order)`
  for edit, and `scm.SalesOrderLine.objects.filter(sales_order=amendment.sales_order)` for add — a line from
  another order is not selectable, which is also the IDOR guard.
- [ ] **`RevenueScheduleForm`** — `Meta.fields = ["sales_order", "method", "compliance_standard", "status",
  "fiscal_period", "notes"]`. **Excluded:** `tenant` (tenant) · `number` (auto-number) · `currency` (**taken from the
  order in `save()`, never typed**) · `contract_amount` / `recognized_amount` / `deferred_amount` (**recomputed**,
  `editable=False`) · `approved_by` / `approved_at` (action-stamped) · `created_at` / `updated_at` (auto).
  `fiscal_period`'s queryset → `accounting.FiscalPeriod.objects.filter(tenant=self.tenant)`. `status` **is** in
  `Meta.fields` (unlike every other `status` here) because a schedule is drafted and voided by a person, not by a
  workflow verb; its widget queryset is narrowed to `STATUS_CHOICES` so no other value is authorable.
- [ ] **`PerformanceObligationForm`** — `Meta.fields = ["sales_order_line", "item", "obligation_type", "description",
  "allocation_pct", "recognition_method", "recognize_on", "fiscal_period", "milestone_label",
  "evidence_reference"]`. **Excluded:** `schedule` (set by the parent view) · `allocated_amount` /
  `recognized_amount` (**recomputed**, `editable=False`) · `status` (recomputed) · `journal_entry`
  (**reference-only**, `editable=False`) · `created_at` / `updated_at`. `evidence_reference` is a
  `CharField(max_length=255, blank=True)` carrying a document / tracking-event reference as *the evidence that a
  milestone was met*; it is authorable, never overwritten, and rendered on the detail page as the obligation's proof.
- [ ] **Every form that takes a FK narrows its queryset to `tenant=self.tenant`,** and the repo's
  `_reject_foreign()` helper (`apps/sales/forms/_common.py`) is used where a cross-tenant FK must be rejected at
  validation time rather than at save time.

#### 5. Views & context-var contract — EVERY view, its URL name, and EVERY context key

**This is the highest-risk section in the plan (L7, L8).** A context key a template expects but the view does not
pass renders **blank at HTTP 200** — no traceback, no failure, just a silently empty region. Every key below is
pinned; a name left unpinned is either a `NoReverseMatch` (L7) or a blank page (L8).

**Conventions, fixed once for all 8.6 views:** every view is `@login_required` + `@tenant_admin_required` ·
every queryset is `Model.objects.filter(tenant=request.tenant)` (never `.all()`) · list views use
`Paginator(qs, 15)` and pass the **Page object itself** as the list var (the 8.5 shape) · every FK filter is a
`(param, orm_lookup, is_int)` tuple through `crud_list`'s `filters=` OR an explicit `request.GET` parse, and an
unparseable value is **ignored, not 500'd** (L11) · every list passes its `*_choices` explicitly and every FK
dropdown gets a **tenant-filtered queryset**, never a bare `.objects.all()`.

**5.1 `views/OrderManagement/OrderValidationRules.py` — 5 CRUD views**

| View function | URL name | Template | Context keys — **every one** |
|---|---|---|---|
| `order_validation_rule_list` | `order_validation_rule_list` | `sales/ordermanagement/ordervalidationrule/list.html` | `rules` (Page of 15) · `page_obj` (alias of `rules`, for the shared pagination partial) · `q` · `rule_type_choices` = `OrderValidationRule.RULE_TYPE_CHOICES` · `severity_choices` = `SEVERITY_CHOICES` · `active_on_choices` = `ACTIVE_ON_CHOICES` · `parties` = `core.Party.objects.filter(tenant=request.tenant).order_by("name")` · `stats` (dict: `total`, `active`, `blocking`, `by_type`) |
| `order_validation_rule_create` | `order_validation_rule_create` | `…/ordervalidationrule/form.html` | `form` · `obj` (`None` on create — **the detail/edit-mode object var is `obj` on every 8.6 form view**) · `is_edit` = `False` |
| `order_validation_rule_detail` | `order_validation_rule_detail` | `…/ordervalidationrule/detail.html` | `rule` (the object) · `raised_holds` (Page of 15) · `page_obj` · `recent_orders` (the 10 most recent `scm.SalesOrder` rows in `rule.party`'s tenant) |
| `order_validation_rule_edit` | `order_validation_rule_edit` | `…/ordervalidationrule/form.html` | `form` · `obj` (the rule) · `is_edit` = `True` |
| `order_validation_rule_delete` | `order_validation_rule_delete` | — (POST-only, redirects to `sales:order_validation_rule_list`) | — |

**Filters on the list (all read before pagination):** `?q=` → `Q(name__icontains) | Q(number__icontains) |
Q(description__icontains)` · `?rule_type=` → `.filter(rule_type=…)` · `?severity=` → `.filter(severity=…)` ·
`?active_on=` → `.filter(active_on=…)` · `?party=` → `.filter(party_id=as_db_int(val))` (**skip when 0** — L11) ·
`?is_active=true|false` → `.filter(is_active=True/False)`; any other value is ignored.

**5.2 `views/OrderManagement/OrderHolds.py` — 5 CRUD + 5 actions (the hold workbench)**

| View function | URL name | Template | Context keys — **every one** |
|---|---|---|---|
| `order_hold_list` | `order_hold_list` | `sales/ordermanagement/orderhold/list.html` | `holds` (Page) · `page_obj` · `q` · `hold_type_choices` · `status_choices` · `severity_choices` · `sales_orders` (tenant-filtered) · `parties` (tenant-filtered) · `checked_out_choices` = `[("", "All"), ("yes", "Checked Out"), ("no", "Not Checked Out")]` · `stats` (`total`, `open`, `checked_out`, `cleared`) |
| `order_hold_create` | `order_hold_create` | `…/orderhold/form.html` | `form` · `obj` = `None` · `is_edit` = `False` |
| `order_hold_detail` | `order_hold_detail` | `…/orderhold/detail.html` | `hold` (the object) · `evaluation` (the **parsed** `evaluation_snapshot` dict — `{}` when blank, **never the raw string rendered into the page**) · `order` (`hold.sales_order`) · `open_holds` (Page of the order's other open holds) · `page_obj` |
| `order_hold_edit` | `order_hold_edit` | `…/orderhold/form.html` | `form` · `obj` (the hold) · `is_edit` = `True` |
| `order_hold_delete` | `order_hold_delete` | — (POST-only → `sales:order_hold_list`) | — |
| `order_hold_raise` **(POST)** | `order_hold_raise` | — → `sales:order_hold_list` | — **Runs `rule.evaluate(order)` for every active rule, creates an `OrderHold` per non-`warn` finding, and writes back `SalesOrder.credit_hold = True` + `hold_reason` from the view.** `warn` findings are reported in a `messages.warning` and create no hold. |
| `order_hold_checkout` **(POST)** | `order_hold_checkout` | — → `sales:order_hold_detail` | — Sets `checked_out_by` / `checked_out_at`. **Refuses (message + redirect) if another user already holds the checkout**, and refuses if `status != "open"`. |
| `order_hold_release_checkout` **(POST)** | `order_hold_release_checkout` | — → `sales:order_hold_detail` | — Clears `checked_out_by` / `checked_out_at`; **refuses unless the caller is the checkout holder or a tenant admin** (the "override checkout" case, and it is recorded in `clear_note`). |
| `order_hold_clear` **(POST)** | `order_hold_clear` | — → `sales:order_hold_detail` | — Sets `status="cleared"`, `cleared_by`, `cleared_at`, `clear_note`; **if no open hold remains on the order, writes back `credit_hold = False` and `hold_reason = ""` from the view.** |
| `order_hold_clear_and_submit` **(POST)** | `order_hold_clear_and_submit` | — → `scm:salesorder_detail` | — Clears the hold, then **delegates the submit to 4.5's own `salesorder_submit` logic** (re-evaluated, never a blind status write). Refuses if any other open hold remains or if the order still has unmapped lines. |

**Filters on the list:** `?q=` → `Q(number__icontains) | Q(reason__icontains) | Q(sales_order__number__icontains)` ·
`?hold_type=` · `?status=` · `?severity=` · `?sales_order=` (int, skip 0) · `?party=` (int, skip 0) ·
`?checked_out=yes|no` → `.exclude(checked_out_by__isnull=True)` / `.filter(checked_out_by__isnull=True)` **scoped to
`status="open"`** so a cleared hold with a stale checkout is not counted as checked out.

**5.3 `views/OrderManagement/OrderAmendments.py` — 5 CRUD + 4 line actions + 4 amendment actions**

| View function | URL name | Template | Context keys — **every one** |
|---|---|---|---|
| `order_amendment_list` | `order_amendment_list` | `sales/ordermanagement/orderamendment/list.html` | `amendments` (Page) · `page_obj` · `q` · `change_type_choices` · `status_choices` · `sales_orders` (tenant-filtered) · `stats` (`total`, `open`, `approved`, `applied`) |
| `order_amendment_create` | `order_amendment_create` | `…/orderamendment/form.html` | `form` · `obj` = `None` · `is_edit` = `False` · `change_type_choices` · `sales_orders` (only `AMENDABLE_STATUSES`) |
| `order_amendment_detail` | `order_amendment_detail` | `…/orderamendment/detail.html` | `amendment` (the object) · `lines` (Page of 15 of `amendment.lines.all()`) · `page_obj` · `order` · `impact` (**parsed** `impact_snapshot` dict, `{}` when blank) · `decision_form` (an unbound `OrderAmendmentDecisionForm`) · `can_decide` (bool) · `can_apply` (bool) · `can_withdraw` (bool) · `line_form` (an unbound `OrderAmendmentLineForm`) |
| `order_amendment_edit` | `order_amendment_edit` | `…/orderamendment/form.html` | `form` · `obj` (the amendment) · `is_edit` = `True` · `change_type_choices` · `sales_orders` |
| `order_amendment_delete` | `order_amendment_delete` | — (POST-only → `sales:order_amendment_list`) | — |
| `order_amendment_line_add` **(POST)** | `order_amendment_line_add` | `…/orderamendment/line_form.html` on invalid | `form` · `amendment` · `line` = `None` · `order_lines` (the order's lines, tenant-scoped) |
| `order_amendment_line_edit` **(POST)** | `order_amendment_line_edit` | `…/orderamendment/line_form.html` on invalid | `form` · `amendment` · `line` (the child row) · `order_lines` |
| `order_amendment_line_delete` **(POST)** | `order_amendment_line_delete` | — → `sales:order_amendment_detail` | — |
| `order_amendment_decide` **(POST)** | `order_amendment_decide` | `…/orderamendment/detail.html` on invalid | `amendment` · `decision_form` · `lines` · `page_obj` · `order` · `impact` · `can_decide` · `can_apply` · `can_withdraw` · `line_form` — **the full detail context, so a validation error re-renders the page rather than a bare form** |
| `order_amendment_apply` **(POST)** | `order_amendment_apply` | — → `sales:order_amendment_detail` | — `transaction.atomic()` → `select_for_update()` on the order → `amendment.apply(user, locked_order, note)` |
| `order_amendment_withdraw` **(POST)** | `order_amendment_withdraw` | — → `sales:order_amendment_detail` | — Only while `status in ("draft", "pending")`, and only by `requested_by` or a tenant admin |
| `order_amendment_impact` | `order_amendment_impact` | `…/orderamendment/impact.html` | `amendment` · `impact` (parsed dict) · `lines` · `order` · `allocations` (the order's `SalesOrderAllocation` rows) · `shipments` (the order's `scm.Shipment` rows) · `schedule` (the order's `RevenueSchedule` or `None`) — **the pre-approval impact read-out, rendering the FROZEN snapshot beside the LIVE figures, and saying so** |

**Filters on the list:** `?q=` → `Q(number__icontains) | Q(reason__icontains) | Q(sales_order__number__icontains)` ·
`?change_type=` · `?status=` · `?sales_order=` (int, skip 0).

**Both children get their own CRUD triple, nested under the parent** (`orders/amendments/<int:pk>/lines/…`) — a
child row edited from the parent's detail page, with `?return_to=` never accepted from user input. `line_form.html`
is a *secondary action page inside the entity folder*, the shape the template rule prescribes.

**5.4 `views/OrderManagement/RevenueSchedules.py` — 5 CRUD + 3 obligation actions + 1 recognize action**

| View function | URL name | Template | Context keys — **every one** |
|---|---|---|---|
| `revenue_schedule_list` | `revenue_schedule_list` | `sales/ordermanagement/revenueschedule/list.html` | `schedules` (Page) · `page_obj` · `q` · `method_choices` · `status_choices` · `compliance_standard_choices` · `sales_orders` (tenant-filtered) · `fiscal_periods` (tenant-filtered) · `stats` (`total`, `active`, `overdue`, `contract_value`, `recognized`, `deferred`) — **every money figure in `stats` summed in PYTHON, never with `aggregate("Sum")` on a Decimal** |
| `revenue_schedule_create` | `revenue_schedule_create` | `…/revenueschedule/form.html` | `form` · `obj` = `None` · `is_edit` = `False` · `method_choices` · `fiscal_periods` |
| `revenue_schedule_detail` | `revenue_schedule_detail` | `…/revenueschedule/detail.html` | `schedule` (the object) · `order` · `obligations` (the child rows, `select_related("item")`) · `allocations` (the order's `SalesOrderAllocation` rows) · `fiscal_periods` (tenant-filtered) · `obligation_form` (an unbound `PerformanceObligationForm`) · `order_lines` (the order's `scm.SalesOrderLine` rows) · `can_recognize` (bool) |
| `revenue_schedule_edit` | `revenue_schedule_edit` | `…/revenueschedule/form.html` | `form` · `obj` · `is_edit` = `True` · `method_choices` · `fiscal_periods` |
| `revenue_schedule_delete` | `revenue_schedule_delete` | — (POST-only → `sales:revenue_schedule_list`) | — |
| `revenue_schedule_obligation_add` **(POST)** | `revenue_schedule_obligation_add` | `…/revenueschedule/obligation_form.html` on invalid | `form` · `schedule` · `obligation` = `None` · `order_lines` |
| `revenue_schedule_obligation_edit` **(POST)** | `revenue_schedule_obligation_edit` | `…/revenueschedule/obligation_form.html` on invalid | `form` · `schedule` · `obligation` (the child row) · `order_lines` |
| `revenue_schedule_obligation_delete` **(POST)** | `revenue_schedule_obligation_delete` | — → `sales:revenue_schedule_detail` | — |
| `revenue_schedule_recognize` **(POST)** | `revenue_schedule_recognize` | — → `sales:revenue_schedule_detail` | — `schedule.recompute()`; **refuses when `status != "active"`**, so a draft schedule can never recognise revenue |

**Filters on the list:** `?q=` → `Q(number__icontains) | Q(notes__icontains) | Q(sales_order__number__icontains)` ·
`?method=` · `?status=` · `?compliance_standard=` · `?fiscal_period=` (int, skip 0) · `?sales_order=` (int, skip 0).

**5.5 `views/OrderManagement/OrderBoards.py` — the seven read-only boards, one per researched P1/P2 view**

**These are views, not models** (the research's "views-only surfaces"). Each is a **projection over facts that
already exist** and each carries a visible "this is derived" note, so a reader never assumes the numbers are
stored. **No board writes anything** except the three explicit POST actions called out below.

| View function | URL name | Template | Context keys — **every one** |
|---|---|---|---|
| `order_capture_board` | `order_capture_board` | `sales/ordermanagement/boards/capture.html` | `orders` (Page of `scm.SalesOrder` in `ALLOCATABLE_STATUSES` + `on_hold`) · `page_obj` · `q` · `channel_choices` = `scm.SalesOrder.SOURCE_CHANNEL_CHOICES` · `status_choices` = `scm.SalesOrder.STATUS_CHOICES` · `open_hold_counts` (dict `{order_id: n}`) · `stats` (`total`, `on_hold`, `unmapped`, `by_channel`) |
| `order_fulfillment_board` | `order_fulfillment_board` | `…/boards/fulfillment.html` | `orders` (Page) · `page_obj` · `q` · `status_choices` · `risk_choices` = `[("", "All"), ("no_commitment", "No Commitment"), ("at_risk", "At Risk"), ("past_due", "Past Due"), ("on_track", "On Track")]` · `hold_counts` · `stats` (`total`, `backordered`, `past_due`, `awaiting_pod`) |
| `order_history_board` | `order_history_board` | `…/boards/history.html` | `orders` (Page) · `page_obj` · `q` · `status_choices` · `stats` (`total`, `open`, `closed`, `cancelled`) |
| `order_timeline` | `order_timeline` | `…/boards/timeline.html` | `order` · `events` (a list of dicts, newest first, each `{"at": <datetime>, "kind": <str>, "label": <str>, "detail": <str>}`) · `holds` · `amendments` · `shipments` · `tracking_events` · `invoice` — **assembled in the view from `scm` + `accounting` + 8.6's own tables. NO timeline table is created** — a sixth append-only log could disagree with the five it summarises |
| `reorder_customers_board` | `reorder_customers_board` | `…/boards/reorder.html` | `customers` (Page of dicts: `party`, `order_count`, `lifetime_value`, `avg_days_between`, `last_order_on`, `expected_order_on` (derived cadence), `on_time_pct`, `top_items`) · `page_obj` · `q` · `stats` (`customers`, `reorderable`, `lapsed`) |
| `renewals_due_board` | `renewals_due_board` | `…/boards/renewals.html` | `recurring_invoices` (Page of `accounting.RecurringInvoice` rows) · `page_obj` · `q` · `stats` (`due_30d`, `overdue`, `active_templates`) — **read-only over accounting's cadence engine. 8.6 builds NO renewal model and NO auto-renew order generation** (that is 8.15) |
| `revenue_recognition_board` | `revenue_recognition_board` | `…/boards/recognition.html` | `schedules` (Page) · `page_obj` · `q` · `method_choices` · `status_choices` · `fiscal_periods` · `stats` (`total`, `contract_value`, `recognized`, `deferred`, `contract_asset`, `contract_liability`, `overdue`) |
| `order_backorder_resolve` **(POST)** | `order_backorder_resolve` | — → `sales:order_fulfillment_board` | — The ONE genuinely new verb in bullet 2. Takes an `allocation` id and a `resolution` in `[("release", "Release"), ("cancel", "Cancel Shortfall"), ("keep", "Keep Promising")]` and **delegates to 4.5's own `salesorderallocation_release` / `salesorderallocation_cancel` logic.** `promised_date` stays `editable=False` — 8.6 never rewrites a promise already given to a customer. |
| `order_repeat` **(POST)** | `order_repeat` | — → `scm:salesorder_detail` | — Creates a NEW `scm.SalesOrder` + `SalesOrderLine` **through 4.5's own create path**, with `source_channel` preserved from the source order and the new order's `notes` recording the source order number. 8.6 writes no order fields itself. |
| `order_validate` **(POST)** | `order_validate` | `…/boards/validation.html` | `order` · `findings` (the list `rule.evaluate()` returned) · `raised_holds` · `evaluation_run_at` — the read-only "why is / is not this order held" screen, for a user who wants the analysis without raising a hold |

**Filters on each board:** `?q=` on the board's own search fields · `?status=` on the order status ·
`?channel=` on the capture board · `?risk=` on the fulfillment board (expressing the four buckets as **ORM date
arithmetic** over `promised_date` / `requested_date`, exactly as procurement 6.11's `Backorder.RISK_CHOICES` does) ·
`?fiscal_period=` on the recognition board. Junk values are ignored, never 500'd (L11).

#### 6. URLs — package layout, prefix, and the FULL `urlpatterns` list

- [ ] **Package: `apps/sales/urls/OrderManagement/`** with `__init__.py`, `OrderValidationRules.py`,
  `OrderHolds.py`, `OrderAmendments.py`, `RevenueSchedules.py`, `OrderBoards.py` — one file per entity, matching
  the models layer one-to-one. `urls/OrderManagement/__init__.py` concatenates them **in this order**:
  `board_patterns + rule_patterns + hold_patterns + amendment_patterns + revenue_patterns` (the board patterns come
  first precisely because they carry the literal routes, the 8.5 `QuoteOperations`-first precedent).
- [ ] **URL prefix segment: `orders/`.** Verified free — the prefixes already mounted under `sales:` are
  `account-classifications, account-plans, accounts, account-stakeholders, approval-rules, bundles,
  enrichment-events, forecast, leads, nurture-enrollments, opportunity, overview, qualifications, quotes,
  routing-rules, score-events`. **No collision.**
- [ ] **SHADOWING RISK, called out explicitly because 8.5 created it:** 8.5 already ships
  `sales:cpq_quote_list` at `quotes/` **plus eleven sub-routes under it**, including the greedy
  `quotes/portal/<str:token>/` and `quotes/portal/<str:token>/toggle/<int:line_id>/`. Those are inside
  `quotes/<int:pk>/`, so they cannot reach `orders/` — **but the check is mandatory anyway**: every new route is
  re-checked against the **whole concatenated `sales:urlpatterns` list**, not just its own module, and any route
  whose literal prefix could be captured by an existing `<int:pk>` or `<str:token>` route is rejected before it
  lands. **Literal routes always precede `<int:pk>` routes inside each module**, and `orders/holds/bulk/` /
  `orders/amendments/open/` style literals precede `orders/holds/<int:pk>/` within their own module.
- [ ] **`app_name = "sales"` is unchanged** in `apps/sales/urls/__init__.py`, and the new package is spliced in
  with a `# 8.6 Order Management.` comment.

**`urls/OrderManagement/OrderBoards.py` — the literal routes, FIRST (10 routes)**

```python
path("orders/", views.order_capture_board, name="order_capture_board"),
path("orders/fulfillment/", views.order_fulfillment_board, name="order_fulfillment_board"),
path("orders/history/", views.order_history_board, name="order_history_board"),
path("orders/timeline/<int:pk>/", views.order_timeline, name="order_timeline"),
path("orders/reorder/", views.reorder_customers_board, name="reorder_customers_board"),
path("orders/renewals/", views.renewals_due_board, name="renewals_due_board"),
path("orders/recognition-board/", views.revenue_recognition_board, name="revenue_recognition_board"),
path("orders/validate/<int:order_pk>/", views.order_validate, name="order_validate"),
path("orders/repeat/<int:pk>/", views.order_repeat, name="order_repeat"),
path("orders/backorders/<int:allocation_pk>/resolve/", views.order_backorder_resolve, name="order_backorder_resolve"),
```

**`urls/OrderManagement/OrderValidationRules.py` (5 routes)**

```python
path("orders/validation-rules/", views.order_validation_rule_list, name="order_validation_rule_list"),
path("orders/validation-rules/create/", views.order_validation_rule_create, name="order_validation_rule_create"),
path("orders/validation-rules/<int:pk>/", views.order_validation_rule_detail, name="order_validation_rule_detail"),
path("orders/validation-rules/<int:pk>/edit/", views.order_validation_rule_edit, name="order_validation_rule_edit"),
path("orders/validation-rules/<int:pk>/delete/", views.order_validation_rule_delete, name="order_validation_rule_delete"),
```

**`urls/OrderManagement/OrderHolds.py` (10 routes — literal `bulk/` first)**

```python
path("orders/holds/", views.order_hold_list, name="order_hold_list"),
path("orders/holds/create/", views.order_hold_create, name="order_hold_create"),
path("orders/holds/bulk-raise/", views.order_hold_bulk_raise, name="order_hold_bulk_raise"),
path("orders/holds/bulk-clear/", views.order_hold_bulk_clear, name="order_hold_bulk_clear"),
path("orders/holds/<int:pk>/", views.order_hold_detail, name="order_hold_detail"),
path("orders/holds/<int:pk>/edit/", views.order_hold_edit, name="order_hold_edit"),
path("orders/holds/<int:pk>/delete/", views.order_hold_delete, name="order_hold_delete"),
path("orders/holds/<int:pk>/checkout/", views.order_hold_checkout, name="order_hold_checkout"),
path("orders/holds/<int:pk>/release-checkout/", views.order_hold_release_checkout, name="order_hold_release_checkout"),
path("orders/holds/<int:pk>/clear/", views.order_hold_clear, name="order_hold_clear"),
```

plus `path("orders/holds/<int:pk>/clear-and-submit/", views.order_hold_clear_and_submit, name="order_hold_clear_and_submit")`
and `path("orders/holds/<int:order_pk>/raise/", views.order_hold_raise, name="order_hold_raise")` — **13 in total.**

**`urls/OrderManagement/OrderAmendments.py` (13 routes — literal `open/` first)**

```python
path("orders/amendments/", views.order_amendment_list, name="order_amendment_list"),
path("orders/amendments/create/", views.order_amendment_create, name="order_amendment_create"),
path("orders/amendments/open/", views.order_amendment_open_queue, name="order_amendment_open_queue"),
path("orders/amendments/<int:pk>/", views.order_amendment_detail, name="order_amendment_detail"),
path("orders/amendments/<int:pk>/edit/", views.order_amendment_edit, name="order_amendment_edit"),
path("orders/amendments/<int:pk>/delete/", views.order_amendment_delete, name="order_amendment_delete"),
path("orders/amendments/<int:pk>/impact/", views.order_amendment_impact, name="order_amendment_impact"),
path("orders/amendments/<int:pk>/decide/", views.order_amendment_decide, name="order_amendment_decide"),
path("orders/amendments/<int:pk>/apply/", views.order_amendment_apply, name="order_amendment_apply"),
path("orders/amendments/<int:pk>/withdraw/", views.order_amendment_withdraw, name="order_amendment_withdraw"),
path("orders/amendments/<int:pk>/lines/add/", views.order_amendment_line_add, name="order_amendment_line_add"),
path("orders/amendments/<int:pk>/lines/<int:line_pk>/edit/", views.order_amendment_line_edit, name="order_amendment_line_edit"),
path("orders/amendments/<int:pk>/lines/<int:line_pk>/delete/", views.order_amendment_line_delete, name="order_amendment_line_delete"),
```

**`urls/OrderManagement/RevenueSchedules.py` (9 routes)**

```python
path("orders/revenue-schedules/", views.revenue_schedule_list, name="revenue_schedule_list"),
path("orders/revenue-schedules/create/", views.revenue_schedule_create, name="revenue_schedule_create"),
path("orders/revenue-schedules/<int:pk>/", views.revenue_schedule_detail, name="revenue_schedule_detail"),
path("orders/revenue-schedules/<int:pk>/edit/", views.revenue_schedule_edit, name="revenue_schedule_edit"),
path("orders/revenue-schedules/<int:pk>/delete/", views.revenue_schedule_delete, name="revenue_schedule_delete"),
path("orders/revenue-schedules/<int:pk>/recognize/", views.revenue_schedule_recognize, name="revenue_schedule_recognize"),
path("orders/revenue-schedules/<int:pk>/obligations/add/", views.revenue_schedule_obligation_add, name="revenue_schedule_obligation_add"),
path("orders/revenue-schedules/<int:pk>/obligations/<int:obligation_pk>/edit/", views.revenue_schedule_obligation_edit, name="revenue_schedule_obligation_edit"),
path("orders/revenue-schedules/<int:pk>/obligations/<int:obligation_pk>/delete/", views.revenue_schedule_obligation_delete, name="revenue_schedule_obligation_delete"),
```

- [ ] **The three extra views the URL list implies, added to 5's contract so nothing is left unpinned:**
  `order_hold_bulk_raise` (`orders/holds/bulk-raise/`, **POST**) — no extra context; re-evaluates every active rule
  against every amendable order in the tenant and reports the count in a message.
  `order_hold_bulk_clear` (`orders/holds/bulk-clear/`, **POST**) — no extra context; clears every hold in the posted
  id set, and **writes the order write-back per order, never in bulk across orders.**
  `order_amendment_open_queue` (`orders/amendments/open/`, GET) — context: `amendments` (Page) · `page_obj` · `q` ·
  `change_type_choices` · `stats` (`open`, `awaiting_decision`, `ready_to_apply`) — the approval queue, which is a
  workflow over amendments rather than a CRUD view on one, so it lives beside the board routes (the 8.5
  `QuoteApprovalRules` / `QuoteOperations` split, exactly).
- [ ] **Total: 50 new url names under `sales:`, all unique, all reversing.** A throwaway script asserts `reverse()`
  succeeds for every one and that no two resolve to the same pattern.
- [ ] **No new namespace.** Every name is `sales:<name>`, reached through the existing `app_name = "sales"`.

#### 7. Templates — every file to be created, and the badge rule

`templates/sales/ordermanagement/` — sub-module folder `ordermanagement` (lowercase, matching
`templates/sales/quote_proposal_cpq/`'s sibling convention), then one folder per entity. **24 files:**

- [ ] `templates/sales/ordermanagement/ordervalidationrule/list.html` · `detail.html` · `form.html`
- [ ] `templates/sales/ordermanagement/orderhold/list.html` · `detail.html` · `form.html`
- [ ] `templates/sales/ordermanagement/orderamendment/list.html` · `detail.html` · `form.html` · `impact.html` ·
      `line_form.html`
- [ ] `templates/sales/ordermanagement/revenueschedule/list.html` · `detail.html` · `form.html` ·
      `obligation_form.html`
- [ ] `templates/sales/ordermanagement/boards/capture.html` · `fulfillment.html` · `history.html` · `timeline.html` ·
      `reorder.html` · `renewals.html` · `recognition.html` · `validation.html`

**`impact.html`, `line_form.html`, `obligation_form.html` and the eight board pages are secondary action / board
pages and live INSIDE the entity folder or the `boards/` folder** — never a flat `orderamendment_impact.html`.

- [ ] **Every template does `{% extends "base.html" %}`** and uses the repo's shared partials. `{% include %}` and
  `{% extends %}` paths are unaffected by the folder structure.
- [ ] **BADGE RULE (L33) — only these six classes exist, verified against `static/css/*.css`: `badge-green`,
  `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`. `badge-success`, `badge-warning` and
  `badge-danger` DO NOT EXIST and a template using one renders unstyled.** Every badge is keyed on the model's
  **exact choice value** and carries an `{% else %}` fallback to `{{ obj.get_<field>_display }}`. Worked examples
  that must appear verbatim:
  - `{% if obj.severity == "block" %}badge-red{% elif obj.severity == "hold" %}badge-amber{% else %}badge-muted{% endif %}`
  - `{% if obj.status == "open" %}badge-amber{% elif obj.status == "cleared" %}badge-green{% elif obj.status == "superseded" %}badge-muted{% else %}{{ obj.get_status_display }}{% endif %}`
  - `{% if obj.status == "applied" %}badge-green{% elif obj.status == "rejected" %}badge-red{% else %}{{ obj.get_status_display }}{% endif %}`
  - `{% if obj.status == "active" %}badge-green{% elif obj.status == "void" %}badge-muted{% else %}{{ obj.get_status_display }}{% endif %}`
- [ ] **Every list template carries the Actions column** — View (eye) → detail · Edit (pencil) → edit · Delete (bin)
  as a **POST form** with `{% csrf_token %}` and `onclick="return confirm('Delete {{ obj.number }}? This cannot be
  undone.')"` using the `\'` escape (L42). Edit / Delete are wrapped in a status guard where the action is
  status-dependent.
- [ ] **Every detail template has an Actions sidebar** — Edit (conditional on status) · Delete (POST + confirm,
  conditional) · Back to List.
- [ ] **FK filter dropdowns compare with `|stringformat:"d"`, NEVER `|slugify`:
  `{% if request.GET.party == party.pk|stringformat:"d" %}selected{% endif %}`.**
- [ ] **Every board page states, in visible prose, that its figures are derived** — e.g. *"Backorder quantities are
  derived from the order lines and their allocations; nothing here is stored."* A reader must never assume a number
  on a board is a column.
- [ ] **The fulfillment board shows the blocked-by-hold reason** on a live order (an open `OrderHold` is visible with
  its `reason`), because "while the order is on hold it can't be processed by the warehouse" is the whole point of
  the column.
- [ ] **The timeline page renders `events` as one ordered list** built in the view, from status, the three
  notification timestamps, allocation `allocated_at`, every `TrackingEvent`, the invoice `issue_date`, and 8.6's own
  hold and amendment events — **and labels its source records**, so a reader can tell an SCM fact from a Sales fact.
- [ ] **No template writes a `scm` field directly.** Every order mutation goes through a POST view.

#### 8. Wiring & integration — single writer, main session only

- [ ] `apps/sales/models/OrderManagement/__init__.py` — the **header docstring carrying the L36 ownership ruling**
  (see 1), then `from .OrderValidationRules import OrderValidationRule` ·
  `from .OrderHolds import OrderHold` · `from .OrderAmendments import OrderAmendment, OrderAmendmentLine` ·
  `from .RevenueSchedules import PerformanceObligation, RevenueSchedule`, and an `__all__` listing all six.
- [ ] `apps/sales/models/__init__.py` — add **six** imports (surgical `Edit`, never a rewrite — another session may be
  building in this checkout, L43) and add all six names to `__all__`. **Verify the file landed before wiring.**
- [ ] `apps/sales/forms/OrderManagement/__init__.py` — the seven form classes (six ModelForms + the decision `Form`).
- [ ] `apps/sales/forms/__init__.py` — add the seven imports and the seven `__all__` entries.
- [ ] `apps/sales/views/OrderManagement/__init__.py` — the five view modules re-exported.
- [ ] `apps/sales/views/__init__.py` — add every new view function by name, alphabetically within the 8.6 group.
- [ ] `apps/sales/urls/OrderManagement/__init__.py` — the concatenation shown in section 6.
- [ ] `apps/sales/urls/__init__.py` — add `from .OrderManagement import urlpatterns as _order_management` and splice
  `*_order_management` into `urlpatterns` under a `# 8.6 Order Management.` comment, **after** the 8.5 block.
  `app_name = "sales"` unchanged.
- [ ] `apps/sales/admin.py` — **four** `@admin.register` blocks: `OrderValidationRule`, `OrderHold`, `OrderAmendment`,
  `RevenueSchedule`, each with `list_display` / `list_filter` / `search_fields` and **`raw_id_fields` for every FK**.
  The two tenant-less children get inline `TabularInline`s on their parent admin, not registrations of their own
  (a child row is never edited from the admin list).
- [ ] `apps/sales/management/commands/seed_sales.py` — **extend `_seed_tenant` with a `_seed_order_management(tenant,
  owner)` call**, idempotent by construction:
  - `get_or_create(tenant=tenant, name=…)` for three `OrderValidationRule` rows (an unmapped-item rule, a
    missing-ship-to rule, a credit-limit rule with `parameters={"pct": 20}`), the first **inactive** so the demo shows
    both states.
  - `get_or_create(tenant=tenant, sales_order=<the seeded SO>, hold_type="credit")` for one `OrderHold` with a real
    `reason` and a **frozen `evaluation_snapshot` JSON string**, and `write_audit_log`-style `raised_by` set to `owner`.
  - `get_or_create(tenant=tenant, sales_order=…, change_type="quantity")` for one `OrderAmendment` in `pending` with
    one `OrderAmendmentLine` created through the child's `amendment` FK, and an `impact_snapshot` filled.
  - `get_or_create(tenant=tenant, sales_order=…)` for one `RevenueSchedule` (`active`, `asc606`) with two
    `PerformanceObligation` children summing to 100 % of `allocation_pct`, then `schedule.recompute()`.
  - The seeder's success string becomes `"Sales 8.1, 8.2, 8.3, 8.4, 8.5, and 8.6 seed complete."` and `help` mentions
    8.6. **Two runs must be byte-stable** — the same row counts and the same numbers, no `IntegrityError`.
  - If 8.6 has no `scm.SalesOrder` to hang holds on, the block **skips with a printed warning** rather than creating
    an order itself — 8.6 does not create the order spine.
- [ ] **`LIVE_LINKS["8.6"]` in `apps/core/navigation.py`, one entry, the five NavERP.md bullet strings VERBATIM as
  keys** (copied from `NavERP.md` lines 1350-1356, not retyped) mapping to **staff-reachable** pages (never a
  login-gated portal — L32):

  | NavERP.md 8.6 bullet (verbatim key) | url name |
  |---|---|
  | `Order Capture & Validation` | `sales:order_capture_board` |
  | `Order Fulfillment Tracking` | `sales:order_fulfillment_board` |
  | `Order Amendments & Cancellations` | `sales:order_amendment_list` |
  | `Revenue Recognition & Scheduling` | `sales:revenue_schedule_list` |
  | `Order History & Reorder` | `sales:order_history_board` |

  **Plus four extra live leaves**, each a real page: `Order Validation Rules` → `sales:order_validation_rule_list` ·
  `Order Holds` → `sales:order_hold_list` · `Amendment Approval Queue` → `sales:order_amendment_open_queue` ·
  `Revenue Recognition Board` → `sales:revenue_recognition_board`.
  **The entry carries the ownership comment from section 1** naming `scm.SalesOrder` as 4.5's and 8.6 as an extender.
- [ ] **NO `config/settings.py` EDIT.** `sales` is already in `INSTALLED_APPS`.
- [ ] **NO `config/urls.py` EDIT.** `apps.sales.urls` is already mounted under `sales/`.
- [ ] **Migration: `python manage.py makemigrations sales` → the file MUST be `0012_*.py`.** Read it before
  committing and confirm **no operation names an `scm` / `accounting` / `core` / `crm` / `projects` model.**
- [ ] `python manage.py migrate` → `python manage.py seed_sales` → **`python manage.py seed_sales` a second time** →
  `python manage.py check` → clean. Then `python manage.py makemigrations --check --dry-run` → **"No changes
  detected"** for every app.
- [ ] **Commit ONE FILE PER COMMIT, with explicit paths, PowerShell-safe (`;` separator, never `&&`):** every
  models/forms/views/urls `__init__.py`, every entity module, every `path()` module, every template, `admin.py`,
  `seed_sales.py`, `navigation.py`, the migration, and the two docs files. See section 12 for the snippet list.

#### 9. Security & tenant isolation gates

- [ ] **Cross-tenant → 404 on EVERY verb, including every action verb.** For each of the 50 routes, a tenant-A user
  handed a tenant-B pk gets **404, not 403 and not 302**. This is the defect the whole lane exists to catch, and it
  applies to `order_hold_checkout`, `order_hold_release_checkout`, `order_hold_clear`,
  `order_hold_clear_and_submit`, `order_hold_raise`, `order_hold_bulk_raise`, `order_hold_bulk_clear`,
  `order_amendment_decide`, `order_amendment_apply`, `order_amendment_withdraw`, `order_amendment_line_add`,
  `order_amendment_line_edit`, `order_amendment_line_delete`, `revenue_schedule_recognize`,
  `revenue_schedule_obligation_add`, `revenue_schedule_obligation_edit`, `revenue_schedule_obligation_delete`,
  `order_backorder_resolve` and `order_repeat` — **the action verbs are where an IDOR actually lands**, because a
  POST body can carry an id the path does not.
- [ ] **A posted id set is re-scoped, not trusted.** `order_hold_bulk_clear` and `order_amendment_line_delete` take
  ids in the POST body; each is re-fetched with `tenant=request.tenant` inside the loop, and a foreign id is
  **skipped and reported**, never acted on.
- [ ] **Every FK choice queryset is filtered to `tenant=request.tenant`** — in every form `__init__` and in every
  `*_choices` context key. A tenant-A user must never see tenant-B's order, party, item, document, fiscal period or
  rule in a dropdown.
- [ ] **A form that must reject a cross-tenant FK actually rejects it:** posting tenant-B's `sales_order_id` into
  `OrderHoldForm`, `OrderAmendmentForm` or `RevenueScheduleForm` produces a **form validation error, not a saved
  row**. The repo's `_reject_foreign()` helper is the mechanism.
- [ ] **`request.tenant is None` (the superuser) sees EMPTY lists on all 50 pages, and 200** — never a 500 from a
  null-tenant comparison, and never another tenant's data. Creating as a tenant-less user is refused with a
  message (the `crud_create` `set_tenant` behaviour), not a 500.
- [ ] **Every action verb is POST-only AND CSRF-protected.** All are `@require_POST` (a GET must redirect or 405,
  never execute) and are invoked from a `{% csrf_token %}`-carrying `<form method="post">` in the template. **No verb
  is reachable by a crafted link.**
- [ ] **No stored snapshot an attacker can supply.** `OrderHold.evaluation_snapshot` and
  `OrderAmendment.impact_snapshot` are **`editable=False`, excluded from every form, and built server-side only**
  (from `rule.evaluate()` and from the `scm` reads). Neither is ever echoed back from the request. A user who posts
  `evaluation_snapshot=<forged JSON>` has it ignored — which is exactly what makes the frozen-evidence property worth
  having.
- [ ] **`raised_by` / `checked_out_by` / `cleared_by` / `requested_by` / `decided_by` / `approved_by` all come from
  `request.user`, never from the POST body.** A user cannot clear a hold "as" someone else.
- [ ] **`OrderAmendment.apply()` re-checks its guards INSIDE the method** — amendable status, no second open
  amendment, quantity not below what is already allocated/shipped/invoiced. The template hides the button; the method
  refuses. **A hidden button is not a guard.**
- [ ] **The tenant-less children cannot be reached directly.** `OrderAmendmentLine` and `PerformanceObligation` have
  **no list URL and no standalone detail URL** — they are reachable only through their tenant-owned parent, whose
  `get_object_or_404(..., tenant=request.tenant)` is the guard. **No route takes a child pk alone.**
- [ ] **`order_validate` discloses nothing.** Its findings describe the acting tenant's own order only; a foreign
  order pk 404s before any rule is evaluated.
- [ ] **`core.AuditLog` is written on every 8.6 state transition** via `write_audit_log()` — hold raised, checked
  out, checkout released, cleared, amendment proposed, decided, applied, withdrawn, schedule recognised — and the
  entry **names the acting user**, never a posted one.
- [ ] **No `scm` field is written outside the two permitted write-backs** (`credit_hold`, `hold_reason`) and the
  `apply()` path. A grep of `apps/sales/views/OrderManagement/` for `.status = "cancelled"` must return nothing.
- [ ] **No journal entry is created.** A grep for `JournalEntry.objects.create` / `.save()` in
  `apps/sales/**/OrderManagement/` must return nothing. The only `journal_entry` reference is a SET_NULL FK on the
  obligation, and nothing in 8.6 assigns it.

#### 10. Smoke & verification — the throwaway `temp/` script

One script, `temp/smoke_sales_86.py`, run as `admin_acme`. **Asserted CONTENT, not just status** — a mismatched
context var returns 200 and renders blank (L8), which is the exact drift this pass exists to catch.

- [ ] **All 50 new url names reverse**, and each `reverse()` returns a path under `/sales/orders/`.
- [ ] **Every GET page returns 200 AND its asserted string is in the body** — a table of (url_name, expected
  substring) pairs, covering: each list page's own page title **and** at least one row's `number`; each detail
  page's object `number` **and** its FK's display value; each form page's `<form` **and** one field name from its
  `Meta.fields`; each board's heading **and** the string "derived"; the hold detail's parsed `reason`; the amendment
  detail's frozen `impact` figure; the schedule detail's `contract_amount` and `deferred_amount`.
- [ ] **Junk-parameter list:** every list and board URL fetched with `?q=` + `?status=bogus` + `?severity=nope` +
  `?party=abc` + `?party=0` + `?party=999999999999999999999` + `?page=notanumber` + `?is_active=maybe` → **200, no
  exception, and the page is not silently emptied by a pk filter** (L11: `0` is decimal and in range but is not a
  pk; `999…` overflows `int`).
- [ ] **Page 2** of every paginated list renders 200 (seed enough rows, or assert the empty-state message — **either
  outcome is a pass, a 500 is not**).
- [ ] **Cross-tenant IDOR:** as `admin_acme`, request every tenant-B detail / edit / delete **and every action
  verb** URL with a tenant-B pk → **404**.
- [ ] **The ownership guard, run as a hard gate:**
  `Select-String -Path 'apps\sales\**\*.py' -Pattern '^class SalesOrder'` → **zero hits.** If it returns a row, the
  order spine has been forked and the build stops.
- [ ] **`python manage.py check` → clean**, and **`python manage.py makemigrations --check --dry-run` → "No changes
  detected"** after the migration.
- [ ] **`seed_sales` run twice, byte-stable:** identical row counts per model on the second run, no
  `IntegrityError`.
- [ ] **Badge audit:**
  `Select-String -Path 'templates\sales\ordermanagement\**\*.html' -Pattern 'badge-(success|warning|danger)'` →
  **zero hits** (those classes do not exist in the stylesheet).
- [ ] **Template-path audit:** every `render(..., "sales/ordermanagement/...")` string resolves to a file on disk.
- [ ] **The script is never committed** (`temp/` is untracked); delete it after the pass.

#### 11. Tests — four lanes, the namespace, and the full unfiltered run

- [ ] **Four test files, written and run ONE AT A TIME, in this order:**
  `apps/sales/tests/test_ordermanagement_models.py` → `test_ordermanagement_forms.py` →
  `test_ordermanagement_views.py` → `test_ordermanagement_security.py`. Each is committed on its own as it lands.
- [ ] **Test namespace, so the next sub-module appending nearby cannot shadow anything:** every test function is
  `test_ordermanagement_*`; every module-level helper is `_ordermanagement_*`; every pytest fixture is
  `ordermanagement_*`. **The `_ordermanagement_*` record factories live in the models lane** — `_ordermanagement_tenant_a`,
  `_ordermanagement_tenant_b`, `_ordermanagement_admin_a`, `_ordermanagement_rep_a`, `_ordermanagement_admin_b`,
  `_ordermanagement_party`, `_ordermanagement_user`, `_ordermanagement_item`, `_ordermanagement_sales_order`,
  `_ordermanagement_order_line`, `_ordermanagement_rule`, `_ordermanagement_hold`, `_ordermanagement_amendment`,
  `_ordermanagement_amendment_line`, `_ordermanagement_schedule`, `_ordermanagement_obligation`,
  `_ordermanagement_fiscal_period`, `_ordermanagement_currency`, `_ordermanagement_document`.
- [ ] **conftest policy: NO EDITS to `apps/sales/tests/conftest.py`.** It exists and is 2707 lines, but it is 8.1 /
  8.2 / 8.4's contract; 8.5 added nothing to it and put its factories in the models lane, so 8.6 does the same. This
  is the decision, stated: **8.6 does not follow the 8.1/8.2/8.4 conftest pattern, it follows 8.5's.**
- [ ] **Models lane asserts the contract this plan froze**, because the contract is only worth writing down if
  something checks it: every `CHOICES` tuple **exactly and in order** · every field's `max_length` /
  `decimal_places` / `max_digits` · every FK's `(target, on_delete, related_name, null, blank, editable)` · every
  `Meta.indexes` name and field tuple · every `UniqueConstraint` name · the four `NUMBER_PREFIX` values and
  `number.max_length == 20` · **and `assert not hasattr(OrderAmendmentLine, "NUMBER_PREFIX")` and the same for
  `PerformanceObligation`** (the tenant-less children take no prefix) · `AMENDABLE_STATUSES`, `OPEN_STATUSES`,
  `EDITABLE_STATUSES` · every derived property exists and is a `property` object, **not a field**
  (`is_checked_out`, `line_delta`, `value_delta`, `is_addition`, `remaining_deferred`, `contract_asset`,
  `contract_liability`, `allocation_is_complete`, `recognition_progress_pct`, `days_overdue`, `overdue`,
  `remaining_amount`).
- [ ] **Models lane also asserts the ownership rule:** `evaluate()` returns findings and **writes nothing** (row
  count unchanged before/after) · `apply()` calls `recalc_totals()` and refuses an unamendable order ·
  `has_open_for()` · `recompute()` changes only the three recomputed columns · **and that no 8.6 migration
  operation names a non-`sales` model.**
- [ ] **Forms lane:** each `Meta.fields` list exactly as pinned in section 4 · each excluded field genuinely absent ·
  a cross-tenant FK is rejected · `parameters` with malformed JSON is a form error, not a 500 · the
  `OrderAmendmentForm.clean()` raises on `NON_FIELD_ERRORS` for an unamendable order **and for a second open
  amendment** · the `PerformanceObligationForm` cannot author `status` / `allocated_amount` / `journal_entry`.
- [ ] **Views lane:** every list page 200 with **asserted content** · every `*_choices` key present in the context ·
  the exact context-key set from section 5 for every view (asserted as a set, so a dropped key fails) · the junk
  GET params of section 10 · page 2 · a POST-only verb reached by GET does not execute · the seeder's rows render
  (the list pages are not empty against seeded data).
- [ ] **Security lane:** every one of the 20+ action verbs cross-tenant → **404** · every FK dropdown carries no
  foreign row · the three forms reject a foreign FK · `request.tenant=None` sees empty everywhere · every action
  verb is `@require_POST` and refuses a GET · a forged `evaluation_snapshot` / `impact_snapshot` in the POST body is
  **ignored** · `raised_by` / `cleared_by` / `decided_by` always equal the acting user · **`apply()` refuses an
  order whose status left `AMENDABLE_STATUSES`, proving the guard is in the method and not only in the template** ·
  no `JournalEntry` row is created by any 8.6 verb.
- [ ] **FINAL: the FULL, UNFILTERED `apps/sales` suite, green. NEVER a `-k` filter** (L47) — a filter excludes
  exactly the tests a shared-file change can break, and this run touches four `__init__.py` files every other lane
  imports. `python -m pytest apps/sales/tests -q` with **no** `-k`, and the whole app green, not just 8.6.

#### 12. Close-out

- [ ] **`.claude/skills/sales/SKILL.md` — UPDATE the EXISTING file. Do NOT create a new skill.** The sales skill
  already exists (verified). Add a **Sub-module 8.6** section to its Overview, and fill in the rows the skill's own
  shape calls for: the six new models with their prefixes / bases / key fields / which core-spine entities they
  **reuse vs. add**; the 50 url names grouped by module; the 24 template paths; the seeder's 8.6 rows; the
  conventions that are 8.6-specific (the `scm.SalesOrder` ownership ruling, the derived-not-stored rule, the
  `apply()`-is-the-single-writer rule, the context-var contract, the six legal badge classes); common tasks
  ("add a rule type", "add a recognition method", "add a board"); and the `LIVE_LINKS["8.6"]` entry.
  **One file, one commit.**
- [ ] **`README.md` — add the 8.6 sub-module row**, marked built, in the sales module's table, matching the wording
  the 8.5 row uses.
- [ ] **`NavERP-ERD.md` — reconcile BOTH rows** (see section 1). Row 4 (line 466) confirmed correct and **left
  alone**; row 8 (line 470) gains the 8.6 as-built Adds set and states the by-FK extension of `scm.SalesOrder`.
  **One file, one commit.**
- [ ] **`.claude/tasks/todo.md` — append a review section** at the END of this 8.6 block (never mass-tick the older
  backlog), recording: what the six reviewers found, what the fixer applied, and any finding **deliberately
  deferred** with its reason. The 8.5 close-out is the model.
- [ ] **`.claude/tasks/review-sales-8.6.md`** — created in Phase 4, one commit, findings deduplicated and sorted
  Critical → Important → Minor with IDs.
- [ ] **`.claude/tasks/lessons.md`** — append a line **only if** a user correction or a new lesson emerged during
  the build. Not a formality edit.
- [ ] **The one-file-per-commit PowerShell snippet list.** Every line uses `;` and **never** `&&`. This is the
  whole build, in order:

```powershell
git add 'apps/sales/models/OrderManagement/__init__.py'; git commit -m 'feat(sales): add OrderManagement models package re-exporting the 8.6 order-management classes'
git add 'apps/sales/models/OrderManagement/OrderValidationRules.py'; git commit -m 'feat(sales): add OrderValidationRule with typed JSON-parameterised rules replacing the hard-coded hold checks'
git add 'apps/sales/models/OrderManagement/OrderHolds.py'; git commit -m 'feat(sales): add OrderHold with checkout lifecycle and frozen evaluation snapshot'
git add 'apps/sales/models/OrderManagement/OrderAmendments.py'; git commit -m 'feat(sales): add OrderAmendment and tenant-less OrderAmendmentLine with impact analysis and a single-writer apply()'
git add 'apps/sales/models/OrderManagement/RevenueSchedules.py'; git commit -m 'feat(sales): add RevenueSchedule and tenant-less PerformanceObligation as the ASC 606 representation'
git add 'apps/sales/models/__init__.py'; git commit -m 'feat(sales): re-export the six 8.6 order-management models'
git add 'apps/sales/forms/OrderManagement/__init__.py'; git commit -m 'feat(sales): add OrderManagement forms package'
git add 'apps/sales/forms/OrderManagement/OrderValidationRules.py'; git commit -m 'feat(sales): add OrderValidationRuleForm excluding tenant, number and timestamps'
git add 'apps/sales/forms/OrderManagement/OrderHolds.py'; git commit -m 'feat(sales): add OrderHoldForm with tenant-scoped order, rule and party querysets'
git add 'apps/sales/forms/OrderManagement/OrderAmendments.py'; git commit -m 'feat(sales): add the amendment, decision and line forms with the amendability guard'
git add 'apps/sales/forms/OrderManagement/RevenueSchedules.py'; git commit -m 'feat(sales): add the revenue schedule and performance obligation forms'
git add 'apps/sales/forms/__init__.py'; git commit -m 'feat(sales): re-export the 8.6 order-management forms'
git add 'apps/sales/views/OrderManagement/__init__.py'; git commit -m 'feat(sales): add OrderManagement views package'
git add 'apps/sales/views/OrderManagement/OrderValidationRules.py'; git commit -m 'feat(sales): add the five order validation rule CRUD views with their context contract'
git add 'apps/sales/views/OrderManagement/OrderHolds.py'; git commit -m 'feat(sales): add the hold workbench views including checkout, clear and clear-and-submit'
git add 'apps/sales/views/OrderManagement/OrderAmendments.py'; git commit -m 'feat(sales): add the amendment CRUD, line and decision/apply/withdraw views'
git add 'apps/sales/views/OrderManagement/RevenueSchedules.py'; git commit -m 'feat(sales): add the revenue schedule CRUD, obligation and recognize views'
git add 'apps/sales/views/OrderManagement/OrderBoards.py'; git commit -m 'feat(sales): add the seven read-only order boards and the timeline over existing facts'
git add 'apps/sales/views/__init__.py'; git commit -m 'feat(sales): re-export the 8.6 order-management views'
git add 'apps/sales/urls/OrderManagement/__init__.py'; git commit -m 'feat(sales): add the OrderManagement URL package with boards-first ordering'
git add 'apps/sales/urls/OrderManagement/OrderValidationRules.py'; git commit -m 'feat(sales): add the order validation rule routes'
git add 'apps/sales/urls/OrderManagement/OrderHolds.py'; git commit -m 'feat(sales): add the order hold routes with literal bulk routes before the pk routes'
git add 'apps/sales/urls/OrderManagement/OrderAmendments.py'; git commit -m 'feat(sales): add the order amendment routes including nested line routes'
git add 'apps/sales/urls/OrderManagement/RevenueSchedules.py'; git commit -m 'feat(sales): add the revenue schedule and obligation routes'
git add 'apps/sales/urls/OrderManagement/OrderBoards.py'; git commit -m 'feat(sales): add the order board, timeline, repeat and backorder-resolution routes'
git add 'apps/sales/urls/__init__.py'; git commit -m 'feat(sales): mount the 8.6 OrderManagement urlpatterns under the sales namespace'
```

```powershell
git add 'templates/sales/ordermanagement/ordervalidationrule/list.html'; git commit -m 'feat(sales): order validation rule list template with search, filters and the Actions column'
git add 'templates/sales/ordermanagement/ordervalidationrule/detail.html'; git commit -m 'feat(sales): order validation rule detail template with the raises-holds trail and Actions sidebar'
git add 'templates/sales/ordermanagement/ordervalidationrule/form.html'; git commit -m 'feat(sales): order validation rule form template'
git add 'templates/sales/ordermanagement/orderhold/list.html'; git commit -m 'feat(sales): order hold workbench list template with the checkout and severity badges'
git add 'templates/sales/ordermanagement/orderhold/detail.html'; git commit -m 'feat(sales): order hold detail template rendering the frozen evaluation snapshot read-only'
git add 'templates/sales/ordermanagement/orderhold/form.html'; git commit -m 'feat(sales): order hold form template'
git add 'templates/sales/ordermanagement/orderamendment/list.html'; git commit -m 'feat(sales): order amendment list template with change-type and status filters'
git add 'templates/sales/ordermanagement/orderamendment/detail.html'; git commit -m 'feat(sales): order amendment detail template with the line diff, decision gate and Actions sidebar'
git add 'templates/sales/ordermanagement/orderamendment/form.html'; git commit -m 'feat(sales): order amendment form template limited to amendable orders'
git add 'templates/sales/ordermanagement/orderamendment/impact.html'; git commit -m 'feat(sales): order amendment impact template contrasting the frozen snapshot with the live figures'
git add 'templates/sales/ordermanagement/orderamendment/line_form.html'; git commit -m 'feat(sales): order amendment line form template capturing before and after values'
git add 'templates/sales/ordermanagement/revenueschedule/list.html'; git commit -m 'feat(sales): revenue schedule list template with derived deferred and asset positions'
git add 'templates/sales/ordermanagement/revenueschedule/detail.html'; git commit -m 'feat(sales): revenue schedule detail template with the obligation table and allocation completeness check'
git add 'templates/sales/ordermanagement/revenueschedule/form.html'; git commit -m 'feat(sales): revenue schedule form template'
git add 'templates/sales/ordermanagement/revenueschedule/obligation_form.html'; git commit -m 'feat(sales): performance obligation form template with the milestone evidence field'
git add 'templates/sales/ordermanagement/boards/capture.html'; git commit -m 'feat(sales): order capture board showing channel mix, open holds and rule failures'
git add 'templates/sales/ordermanagement/boards/fulfillment.html'; git commit -m 'feat(sales): order fulfillment board with derived allocation, shipment, POD and backorder columns'
git add 'templates/sales/ordermanagement/boards/history.html'; git commit -m 'feat(sales): order history board listing orders by lifecycle status'
git add 'templates/sales/ordermanagement/boards/timeline.html'; git commit -m 'feat(sales): order lifecycle timeline assembled from existing records with no new log table'
git add 'templates/sales/ordermanagement/boards/reorder.html'; git commit -m 'feat(sales): reorder customers board with derived cadence, lifetime value and on-time rate'
git add 'templates/sales/ordermanagement/boards/renewals.html'; git commit -m 'feat(sales): renewals-due board reading accounting recurring invoices without a second cadence engine'
git add 'templates/sales/ordermanagement/boards/recognition.html'; git commit -m 'feat(sales): revenue recognition board by fiscal period with derived deferred and contract positions'
git add 'templates/sales/ordermanagement/boards/validation.html'; git commit -m 'feat(sales): order validation read-out showing every rule finding without raising a hold'
git add 'apps/sales/admin.py'; git commit -m 'feat(sales): register the four 8.6 order-management admins with child inlines'
git add 'apps/sales/management/commands/seed_sales.py'; git commit -m 'feat(sales): seed 8.6 validation rules, a hold, an amendment and a revenue schedule idempotently'
git add 'apps/core/navigation.py'; git commit -m 'feat(sales): add LIVE_LINKS 8.6 with the five NavERP.md bullets verbatim and the scm ownership comment'
git add 'apps/sales/migrations/0012_ordervalidationrule_orderhold_and_more.py'; git commit -m 'feat(sales): add migration 0012 for the 8.6 order-management models'
```

- [ ] **NO `git push`, AT ANY STEP.** Stop at `git commit` every time; the user pushes manually.

---

#### Open questions / decisions taken

1. **The `TenantNumbered.save()` carry-forward bug is OUT OF SCOPE for 8.6, and this is stated so no later reader
   attributes it to this build.** `apps/sales/models/_base.py:31-40` (read and confirmed during planning) is:

   ```python
   def save(self, *args, **kwargs):
       if not self.number and self.tenant_id and self.NUMBER_PREFIX:
           for _ in range(5):
               self.number = next_number(type(self), self.tenant, self.NUMBER_PREFIX)
               try:
                   with transaction.atomic():
                       return super().save(*args, **kwargs)
               except IntegrityError:
                   self.number = ""
       return super().save(*args, **kwargs)   # <-- reached with self.number == ""
   ```

   On the **exhaustion path** (five consecutive `IntegrityError`s) the loop falls out of the `for` and the final
   `super().save()` writes an **empty** `number`, which then collides with the unique constraint on
   `(tenant, number)` for the *second* such row. **It is pre-existing, it is shared by every numbered `sales` model,
   and 8.6 adds four more numbered models onto that path — but 8.6 did not cause it and 8.6 does not fix it.** It is
   raised as a **separate one-file fix** against `apps/sales/models/_base.py`, in its own commit, on its own. **The
   todo agent must not widen this run's scope to do it, and a reviewer who finds it must file it as PRE-EXISTING,
   not as an 8.6 defect.**
2. **Deviation from the research, stated:** the research's P1 list also names `OrderIngestion` (P1.5) and
   `ReorderProfile` (the saved reorder basket, P2.4). **Neither is in the four-model scope this plan froze.** So 8.6's
   `order_capture_board` shows the channel mix, open holds and rule failures from the **existing**
   `scm.SalesOrder.source_channel` and adds **no** ingestion-ledger table, and `reorder_customers_board` is a
   read-only cadence / lifetime-value projection with **no** basket model. The research's own section 4.2 table names
   exactly the four models built here, and its section 5 already assigns the EDI/protocol work to 8.18 and the
   renewal contract to 8.15.
3. **Deviation from the research, stated:** the research listed seven "views-only surfaces" including
   `amendment_impact` and `order_timeline`. Both are built as **actions / pages inside the entity folders**
   (`…/orderamendment/impact.html`, `…/boards/timeline.html`) rather than as top-level boards, because each is about
   **one** amendment / **one** order and the template rule puts a single-entity page in that entity's own folder.
4. **Decision taken — `RevenueSchedule.status` is the ONE `status` in 8.6 a person may author.** Every other
   `status` is workflow-governed and excluded from its form; a schedule is drafted and voided by a person, so
   `status` is in `RevenueScheduleForm.Meta.fields` with its widget narrowed to `STATUS_CHOICES`.
5. **Decision taken — `OrderHold.severity` is COPIED, not referenced.** It duplicates
   `OrderValidationRule.severity` deliberately, so that re-tuning a rule next month cannot rewrite why an order was
   held last month. The models lane asserts the two agree **at raise time** and that they may legitimately diverge
   later.
6. **Decision taken — the two tenant-less children have NO standalone list or detail URL.**
   `OrderAmendmentLine` and `PerformanceObligation` are edited through their parent, which is simultaneously the
   CRUD-completeness answer and the tenant-isolation guard: **no route takes a child pk alone.**
7. **Decision taken — the `related_name="revenue_schedules"` collision is a NON-ISSUE, verified rather than
   assumed.** `projects.ProjectRevenueSchedule` already claims `revenue_schedules` on `projects.Project` and
   `projects.ProjectMilestone`; because `related_name` is scoped **per target model**, 8.6's identical
   `related_name` on `scm.SalesOrder` cannot clash. Checked with a grep over `apps\**\models\**\*.py` before the name
   was pinned.
8. **Open question for the build, answerable in one grep:** does `scm.SalesOrder` have a `notes` field? The
   research's repeat-order design has the new order's `notes` recording the source order number. **If `notes` does
   not exist on `scm.SalesOrder`, 8.6 does not add it** — that would be a column on a 4.5 model, which is how a spine
   forks. The repeat order instead records its provenance in `core.AuditLog` and preserves `source_channel`, and the
   link back to the source order is the operator's breadcrumb in the redirect message. **Resolve this in the build's
   first hour and write the answer back into this block.**
9. **Open question for the build:** does `accounting.RecurringInvoice` expose a `next_run_date`? The
   `renewals_due_board` is read-only over it, and if the field is named differently the board's `?due_before=` filter
   follows the real name. **The board must not add a field to an accounting model to make its filter convenient.**
---
