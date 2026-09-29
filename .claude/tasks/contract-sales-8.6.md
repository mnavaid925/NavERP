# Contract — NavERP 8.6 Order Management

- App: `apps/sales` (**existing, live app** — no scaffold, **no `config/settings.py` edit, no `config/urls.py` edit**; `apps.sales` is already installed and the root URLconf already includes `apps/sales/urls/`).
- Sub-module: `8.6 Order Management` (NavERP.md lines **1350–1356**, five bullets).
- Research: `.claude/tasks/research-sales-8.6.md` · Plan: `.claude/tasks/todo.md` (8.6 block, lines 13–1047).
- Test namespace: `ordermanagement` (`test_ordermanagement_{models,forms,views,security}.py`).
- Migration: **`0012`** — leaf confirmed by listing `apps/sales/migrations/`: `0011_cpqquote_signer_ip_address.py`.
- `BASE` for the review range: **`020dd439434fc98ceffc71fe84dc5906a9968952`**.
- Read-only reference siblings: `apps/scm/models/OrderManagement/{SalesOrders,SalesOrderAllocations}.py`, `apps/sales/models/QuoteProposalCPQ/CPQQuotes.py`, `apps/sales/models/{SalesForecasting/ForecastSubmissions,OpportunityOutcomes/OpportunityOutcomes}.py`.

**This contract is FROZEN.** A name that appears here is the name in the code. A name that does not appear here is a defect. Every context key, url name, field, `related_name`, CHOICES value and template path is pinned below (L7 — an unpinned name is a `NoReverseMatch`; L8 — an unpinned context key is a blank page at HTTP 200).

---

## 0. Ownership & boundary — the L36/L37 ruling, and the ERD close-out

1. **`apps/scm` OWNS the sales order.** `scm.SalesOrder` (`SO-`), `scm.SalesOrderLine` and `scm.SalesOrderAllocation` are SCM 4.5's. `apps/scm/models/OrderManagement/SalesOrders.py:1-16` says so verbatim, and lines 44–47 say: *"There is deliberately NO amendment flow here — amend/cancel with impact analysis is Module 8.6's job."*
2. **8.6 EXTENDS that order by FK and declares NO second order master.** A `class SalesOrder` in `apps/sales` is a bug, not a variant. 8.6's genuine-new layer is the *commercial* one 4.5 declined to build.
3. **Other spine reuse (all by FK, all extend-only):**
   - `scm.Shipment` / `scm.TrackingEvent` (4.6 TMS) — fulfillment/POD facts are READ, never re-declared.
   - `scm.SalesOrderAllocation` (4.5) — the soft reservation; `order_backorder_resolve` DELEGATES to 4.5's own release/cancel logic.
   - `accounting.Currency` / `FiscalPeriod` / `TaxCode` / `Invoice`; `accounting.RecurringInvoice` (read-only on the renewals board).
   - `core.Party` / `core.Address`; `crm.Opportunity`; `sales.CPQQuote` (8.5, incl. its `converted_order` FK).
4. **No second cancellation path.** 4.5's `scm:views.salesorder_cancel` is the single mutator; it already refuses while `has_active_allocations()`. 8.6's cancellation goes through `OrderAmendment(change_type="cancel").apply()`, which re-derives and delegates.
5. **No `JournalEntry` posting** (L29), matching 4.10's explicit "SCM posts NO JournalEntry". `RevenueSchedule.journal_entry` is a **reference-only** FK, `editable=False`.
6. **No outbound `Backorder` table** — `SalesOrderLine.quantity_backordered()` is a derived `@property`; a table would be a second source of truth.
7. **No timeline table** — `order_timeline` assembles `events` in the view from the five logs it summarises.
8. **ERD close-out (L36 step 2, REQUIRED — both rows, same change).** `NavERP-ERD.md` **row 8 (line ~470) is STALE**: it stops at 8.3, never mentions 8.5 or 8.6, and lists `scm.SalesOrder` in its "Reuses" column in a way that reads as Sales owning it. Row 4 (line 466) is **already correct and is left untouched**. The build rewrites **row 8 only**, marking 8.6's adds as *as-built* and stating that 8.6 extends the SCM order by FK. Encode the ruling in **three durable places**: the `LIVE_LINKS["8.6"]` comment, the `apps/sales/models/OrderManagement/__init__.py` docstring, and `lessons.md` (append to L37, do not rewrite it).

---

## 1. Naming & package architecture

| Item | Name | Note |
|---|---|---|
| Backend package (all 4 layers) | `OrderManagement/` | PascalCase, matching `QuoteProposalCPQ/` |
| `models/OrderManagement/` | `OrderValidationRules.py` · `OrderHolds.py` · `OrderAmendments.py` · `RevenueSchedules.py` | |
| `forms/OrderManagement/` | same four files | |
| `views/OrderManagement/` | same four files + `OrderBoards.py` | 5 modules (the boards are views-only) |
| `urls/OrderManagement/` | same four files + `OrderBoards.py` + `__init__.py` | |
| Template root | `templates/sales/ordermanagement/` | lowercase, matching `templates/sales/quote_proposal_cpq/` |
| URL prefix segment | `orders/` | verified free against all 16 mounted `sales:` prefixes |
| Concatenation order | `board + rule + hold + amendment + revenue` | boards first — they carry the literal routes (the 8.5 `QuoteOperations`-first precedent) |
| Number prefixes | `OVR-` · `OHD-` · `AMD-` · `RVS-` | all four verified free; children get NO prefix |
| Base classes | `TenantNumbered` (4 headers) · children are tenant-less `models.Model` | matches `PurchaseOrderLine`/`RFQLine`/`GoodsReceiptLine` |
| New service module | **none** — the four compute paths live as methods on their own models | matches the 4.5 precedent; avoids a 4th shared surface |

**Absolute imports everywhere inside these packages** (`from apps.sales.models import X`, `from apps.sales.models._base import TenantNumbered`). A relative `from .models import` is wrong one level deep.


---

## 2. Models contract — exact fields, in this order

Four numbered headers (`TenantNumbered`) + two tenant-less children (`models.Model`), in `apps/sales/models/OrderManagement/`. The tenant-less children are reached via their parent's `tenant` — matching the scm sibling convention (`PurchaseOrderLine`, `RFQLine`, `GoodsReceiptLine`), not `crm.QuoteLine`'s outlier.

| # | Class | File | Base | `NUMBER_PREFIX` |
|---|---|---|---|---|
| 1 | `OrderValidationRule` | `OrderValidationRules.py` | `TenantNumbered` | `"OVR"` |
| 2 | `OrderHold` | `OrderHolds.py` | `TenantNumbered` | `"OHD"` |
| 3 | `OrderAmendment` | `OrderAmendments.py` | `TenantNumbered` | `"AMD"` |
| 3b | `OrderAmendmentLine` | `OrderAmendments.py` | plain `models.Model` (tenant-less) | none |
| 4 | `RevenueSchedule` | `RevenueSchedules.py` | `TenantNumbered` | `"RVS"` |
| 4b | `PerformanceObligation` | `RevenueSchedules.py` | plain `models.Model` (tenant-less) | none |

All four prefixes are ≤ 3 chars (`XXX-00001` = 9 of 20 chars). `MST` is **taken** by `projects.ProjectMilestone` — a second reason milestones here are child rows, not a numbered master.

### 2.1 `OrderValidationRule`

Replaces 4.5's two hard-coded hold checks with a tenant-configurable typed rule set.

- `name` — `CharField(max_length=255)`
- `rule_type` — `CharField(max_length=24, choices=RULE_TYPE_CHOICES, default="credit_limit")`
- `severity` — `CharField(max_length=12, choices=SEVERITY_CHOICES, default="hold")`
- `active_on` — `CharField(max_length=12, choices=ACTIVE_ON_CHOICES, default="submit")`
- `parameters` — `JSONField(default=dict, blank=True)` — per-rule-type thresholds (`{"amount": 5000}`). **A JSON blob, not a column per rule type**, so a new rule type is data, not a migration.
- `party` — `ForeignKey("core.Party", on_delete=models.CASCADE, null=True, blank=True, related_name="order_validation_rules")` — blank = every customer
- `priority` — `PositiveIntegerField(default=10)`
- `is_active` — `BooleanField(default=True)`
- `description` — `TextField(blank=True)`

**CHOICES, exact order:**
- `RULE_TYPE_CHOICES` = `[("credit_limit","Credit Limit Exceeded"), ("order_value","Order Value Ceiling"), ("margin_floor","Margin Floor"), ("discount_ceiling","Line Discount Ceiling"), ("unmapped_item","Unmapped Item Present"), ("missing_ship_to","Missing Ship-To Address"), ("expired_quote","Source Quote Expired"), ("inactive_item","Inactive Item On Order")]`
- `SEVERITY_CHOICES` = `[("block","Block Submission"), ("hold","Place On Hold"), ("warn","Warn Only")]`
- `ACTIVE_ON_CHOICES` = `[("submit","On Submit"), ("amendment","On Amendment"), ("both","On Submit And Amendment")]`

`Meta`: `ordering = ["priority", "number"]` · `unique_together = ("tenant", "number")` · indexes `(tenant, rule_type)` → `sales_ovr_tnt_type_idx`, `(tenant, is_active)` → `sales_ovr_tnt_active_idx`.

- `evaluate(order)` → `(findings, block)`; `findings` is a list of dicts `{"rule", "rule_type", "severity", "message", "observed", "threshold"}`. **Pure, side-effect-free** — it never writes. Returns a `list` (empty = clean); the caller decides what to persist.
- `@property is_blocking` → `self.is_active and self.severity in ("block", "hold")`.
- `clean()` — `parameters` must be a `dict`; unknown keys for a `rule_type` are ignored (forward-compatible), not fatal. A malformed blob is a **form** error, never a 500.
### 2.2 `OrderHold`

Makes 4.5's `credit_hold` / `hold_reason` a checkout-able, auditable record with a frozen evaluation snapshot.

- `sales_order` — `ForeignKey("scm.SalesOrder", on_delete=models.CASCADE, related_name="order_holds")`
- `rule` — `ForeignKey("OrderValidationRule", on_delete=models.SET_NULL, null=True, blank=True, related_name="raised_holds")` — **SET_NULL, never PROTECT**: deleting a rule must not delete the evidence of why an order was held.
- `party` — `ForeignKey("core.Party", on_delete=models.PROTECT, null=True, blank=True, related_name="order_holds")`
- `hold_type` — `CharField(max_length=24, choices=HOLD_TYPE_CHOICES, default="credit")`
- `reason` — `TextField()`
- `severity` — `CharField(max_length=12, choices=SEVERITY_CHOICES, default="hold", editable=False)` — **COPIED from the rule at fire time, deliberately**, so re-tuning a rule next month cannot rewrite why an order was held last month.
- `status` — `CharField(max_length=12, choices=STATUS_CHOICES, default="open", editable=False)`
- `evaluation_snapshot` — `JSONField(default=dict, blank=True, editable=False)` — frozen evidence, server-generated. **Never authorable (L22).**
- `raised_at` — `DateTimeField(default=timezone.now, editable=False)`
- `raised_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_holds_raised", editable=False)`
- `checked_out_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_holds_checked_out", editable=False)`
- `checked_out_at` — `DateTimeField(null=True, blank=True, editable=False)`
- `cleared_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_holds_cleared", editable=False)`
- `cleared_at` — `DateTimeField(null=True, blank=True, editable=False)`
- `clear_note` — `TextField(blank=True)` — **the only authorable lifecycle field**; a human writes the justification.
- `superseded_by` — `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="supersedes")`

**CHOICES:** `HOLD_TYPE_CHOICES` = `[("credit","Credit Hold"), ("fraud","Fraud Review"), ("validation","Validation Failure"), ("manual","Manual Hold")]` · `STATUS_CHOICES` = `[("open","Open"), ("cleared","Cleared"), ("superseded","Superseded")]` · `SEVERITY_CHOICES` as 2.1.

`Meta`: `ordering = ["-raised_at", "-id"]` · `unique_together = ("tenant", "number")` · indexes `(tenant, status)` → `sales_ohd_tnt_status_idx`, `(tenant, sales_order)` → `sales_ohd_tnt_order_idx`.
### 2.3 `OrderAmendment` + `OrderAmendmentLine`

The reserved change-order flow 4.5 deliberately omitted. Impact analysis is **frozen at propose time** into `impact_snapshot`; `apply()` is the single writer of order line quantities/prices.

`OrderAmendment`:
- `sales_order` — `ForeignKey("scm.SalesOrder", on_delete=models.CASCADE, related_name="order_amendments")`
- `change_type` — `CharField(max_length=16, choices=CHANGE_TYPE_CHOICES, default="quantity")`
- `status` — `CharField(max_length=12, choices=STATUS_CHOICES, default="draft", editable=False)`
- `reason` — `TextField()`
- `document` — `ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_amendments")`
- `impact_snapshot` — `JSONField(default=dict, blank=True, editable=False)` — frozen at propose time
- `requested_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_amendments_requested", editable=False)`
- `requested_at` — `DateTimeField(default=timezone.now, editable=False)`
- `decided_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_amendments_decided", editable=False)`
- `decided_at` — `DateTimeField(null=True, blank=True, editable=False)`
- `decision_note` — `TextField(blank=True)` — **written by the decision verb, never by a form** (L22: an authorable approval justification is a user-supplied evidentiary field). Present in the plan (`.claude/tasks/todo.md`) and in §3's exclusion prose; it was **missing from the first draft of this section** and is restored here. The `OrderAmendmentDecisionForm` field is named `decision_note` to match this column.
- `applied_at` — `DateTimeField(null=True, blank=True, editable=False)`
- `applied_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_amendments_applied", editable=False)`
- `notes` — `TextField(blank=True)`

**CHOICES:** `CHANGE_TYPE_CHOICES` = `[("quantity","Quantity Change"), ("price","Price Change"), ("add_line","Add Line"), ("remove_line","Remove Line"), ("cancel","Cancel Order")]` · `STATUS_CHOICES` = `[("draft","Draft"), ("pending","Pending Approval"), ("approved","Approved"), ("rejected","Rejected"), ("applied","Applied"), ("withdrawn","Withdrawn"), ("superseded","Superseded")]`.

> **CORRECTED 2026-09-29 — `("close","Close Order")` was REMOVED from these choices.** The original list carried it, and it was unreachable by construction: 4.5's `salesorder_close` accepts exactly one status (`invoiced`), and `invoiced` is deliberately *not* in `AMENDABLE_STATUSES`, so no Close amendment could ever satisfy both rules at once. A dropdown choice that always refuses is worse than no choice — it advertises a verb that cannot fire. **Closing stays 4.5's own action on the order page.** Do not re-add it without also revisiting `AMENDABLE_STATUSES`, and do not widen `AMENDABLE_STATUSES` to make it reachable: that would make every other amendment eligible against an invoiced order too, which is exactly what the tuple exists to prevent.

- `AMENDABLE_STATUSES = ("submitted", "on_hold", "allocated", "partially_fulfilled")` — an amendment changes a **live** commitment. `draft` orders are edited directly by 4.5; `fulfilled`/`invoiced`/`cancelled`/`closed` are terminal. **`recompute_impact()` and the create form's dropdown use this same tuple**, so eligibility cannot disagree.
- `Meta`: `ordering = ["-requested_at", "-id"]` · `unique_together = ("tenant", "number")` · indexes `(tenant, status)` → `sales_amd_tnt_status_idx`, `(tenant, sales_order)` → `sales_amd_tnt_order_idx`.
- `recompute_impact()` → `{"lines": [...], "allocations_affected": n, "shipments_affected": n, "delta_total": Decimal, "revenue_impact": Decimal}`, computed in **Python** over fetched sets. Does not save the snapshot.
- `apply(user, locked_order, note)` → `transaction.atomic()`; writes lines, calls 4.5's own `locked_order.recalc_totals()` then `locked_order.recompute_allocation_status()`; sets `status="applied"`, `applied_by`, `applied_at`. **Refuses unless `status == "approved"`.** For `change_type="cancel"` it **delegates to 4.5's own `scm` cancel logic** and refuses while `has_active_allocations()`.
- `@property is_open` → `self.status in ("draft", "pending", "approved")`.

`OrderAmendmentLine` (tenant-less, no prefix):
- `amendment` — `ForeignKey("OrderAmendment", on_delete=models.CASCADE, related_name="lines")`
- `sales_order_line` — `ForeignKey("scm.SalesOrderLine", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_amendment_lines")` — **SET_NULL and nullable: an `add_line` amendment has no original line.**
### 2.4 `RevenueSchedule` + `PerformanceObligation`

The repo's only ASC 606 representation. Order-keyed; **every balance derived, never stored**.

`RevenueSchedule`:
- `sales_order` — `ForeignKey("scm.SalesOrder", on_delete=models.CASCADE, related_name="revenue_schedules")`
- `status` — `CharField(max_length=12, choices=STATUS_CHOICES, default="draft")` — **the ONE authorable `status` in 8.6**: a schedule is drafted and voided by a person, not by a workflow verb. Its widget is narrowed to `STATUS_CHOICES`.
- `method` — `CharField(max_length=20, choices=METHOD_CHOICES, default="over_time")`
- `compliance_standard` — `CharField(max_length=10, choices=COMPLIANCE_STANDARD_CHOICES, default="asc606")`
- `fiscal_period` — `ForeignKey("accounting.FiscalPeriod", on_delete=models.SET_NULL, null=True, blank=True, related_name="revenue_schedules")`
- `journal_entry` — `ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True, related_name="revenue_schedules", editable=False)` — **reference-only**; 8.6 posts nothing (L29).
- `notes` — `TextField(blank=True)`
- `EDITABLE_STATUSES = ("draft", "active")` · `Meta`: `ordering = ["-created_at", "-id"]` · `unique_together = ("tenant", "number")` · indexes `(tenant, status)` → `sales_rvs_tnt_status_idx`, `(tenant, sales_order)` → `sales_rvs_tnt_order_idx`.

**CHOICES:** `STATUS_CHOICES` = `[("draft","Draft"), ("active","Active"), ("complete","Complete"), ("void","Void")]` · `METHOD_CHOICES` = `[("point_in_time","Point In Time"), ("over_time","Over Time"), ("milestone","Milestone")]` · `COMPLIANCE_STANDARD_CHOICES` = `[("asc606","ASC 606"), ("ifrs15","IFRS 15"), ("both","ASC 606 & IFRS 15")]`.

**Derived `@property` — NEVER columns:** `contract_amount` (the order's `total`) · `allocated_amount` (Σ obligations) · `recognized_amount` (Σ) · `deferred_amount` (`allocated − recognized`, floored at 0) · `contract_asset` (`recognized > allocated`) · `contract_liability` (`allocated > recognized`) · `recognition_progress_pct` (in **Python** — an `F()` percentage integer-divides on SQLite) · `is_unbalanced` (Σ ≠ 100 % within `Decimal("0.01")`) · `days_overdue` (obligations' `recognize_on` vs today, in Python — **a stored `days_overdue` is wrong the moment the clock ticks past midnight**) · `is_overdue` · `is_editable` · `is_locked` (`status == "complete"`).

- `recompute()` → the **only** writer of the obligations' `recognized_amount`. Walks obligations whose `recognize_on` has passed, in date order, allocating against `contract_amount` in Python, writes each back, then saves. **Refuses when `status != "active"`**, so a draft schedule can never recognise revenue.

`PerformanceObligation` (tenant-less, no prefix):
- `schedule` — `ForeignKey("RevenueSchedule", on_delete=models.CASCADE, related_name="obligations")`
- `sales_order_line` — `ForeignKey("scm.SalesOrderLine", on_delete=models.SET_NULL, null=True, blank=True, related_name="performance_obligations")`
- `item` — `ForeignKey("scm.Item", on_delete=models.PROTECT, null=True, blank=True, related_name="performance_obligations")`
- `obligation_type` — `CharField(max_length=20, choices=OBLIGATION_TYPE_CHOICES, default="goods")`
- `description` — `CharField(max_length=255)`
- `allocation_pct` — `DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100"))])`
- `recognition_method` — `CharField(max_length=20, choices=RECOGNITION_METHOD_CHOICES, default="over_time")`
- `recognize_on` — `DateField(null=True, blank=True)`
- `evidence_reference` — `CharField(max_length=255, blank=True)` — the document / tracking-event reference proving the milestone was met. Authorable, never overwritten, rendered as the obligation's proof.
- `allocated_amount` — `DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)`
- `recognized_amount` — `DecimalField(max_digits=18, decimal_places=2, default=0, editable=False)`
- `milestone_label` — `CharField(max_length=120, blank=True)`
- `Meta`: `ordering = ["id"]`
- **CHOICES:** `OBLIGATION_TYPE_CHOICES` = `[("goods","Goods"), ("services","Services"), ("subscription","Subscription"), ("milestone","Milestone"), ("warranty","Warranty")]` · `RECOGNITION_METHOD_CHOICES` = `[("point_in_time","Point In Time"), ("over_time","Over Time"), ("milestone","Milestone")]`
- `@property remaining_amount` → `allocated_amount - recognized_amount`. `clean()` → **`NON_FIELD_ERRORS`** only.

### 2.5 Derived-not-stored — the register

**Not a column anywhere in 8.6:** order quantities, backorder quantity, allocated quantity, deferred revenue, contract asset, contract liability, recognition progress, days overdue, expected order date, a `locked` flag, a `days_open` counter, a reorder cadence. Each is either 4.5's derived property (`quantity_allocated()`, `quantity_backordered()`, `is_backordered`, `is_unmapped`) or a `@property` here.

**Every derived number is computed in PYTHON over a fetched set, never with `F()` / `aggregate` decimal arithmetic** — the SQLite integer-division trap documented in 4.5's own `recalc_totals()` silently drops fractional cents rather than raising.

**Single-writer rules:** `RevenueSchedule.recompute()` and `OrderAmendment.apply()` are the ONLY writers of `recognized_amount` / `deferred_amount` / `contract_amount` / `allocated_amount` / an obligation's `recognized_amount`. All are `editable=False`, so no form and no view can write them. No view in `apps/sales` writes `SalesOrder.status` directly; `OrderHold` writes back only `SalesOrder.credit_hold` / `hold_reason`, and 4.5's `salesorder_release_hold` remains the release verb.


---

## 3. Forms — exact `Meta.fields`, with the reason for every exclusion

All form classes inherit `TenantModelForm` from `apps/core/forms/_common.py` (which supplies the widget classes), are constructed with `tenant=request.tenant`, and set `instance.tenant` via the repo's `TenantUniqueMixin` pattern. **Every FK queryset is narrowed to `tenant=self.tenant`**; the repo's `_reject_foreign()` helper is used where a cross-tenant FK must be rejected at validation time.

- **`OrderValidationRuleForm`** — `Meta.fields = ["name", "rule_type", "severity", "active_on", "parameters", "party", "priority", "is_active", "description"]`.
  **Excluded:** `tenant` (set by the view / mixin) · `number` (auto-numbered) · `created_at`/`updated_at` (`auto_now*`).
  `parameters` renders as a textarea; **a malformed JSON blob is a form error, never a 500 from `JSONField` on save.**
- **`OrderHoldForm`** — `Meta.fields = ["sales_order", "rule", "party", "hold_type", "reason", "clear_note"]`.
  **Excluded, with the reason for each:** `tenant` · `number` · `status` (**workflow-governed** — written only by the raise/clear/supersede verbs) · `severity` (**frozen at fire time**, `editable=False`) · `evaluation_snapshot` (**frozen evidence**, `editable=False`, server-generated) · `raised_at`/`raised_by`/`checked_out_by`/`checked_out_at`/`cleared_by`/`cleared_at` (**action-stamped** — each written by exactly one named POST view) · `superseded_by` (system) · `created_at`/`updated_at`.
  Querysets: `sales_order` → `scm.SalesOrder.objects.filter(tenant=self.tenant)` · `rule` → `OrderValidationRule.objects.filter(tenant=self.tenant)` · `party` → `core.Party.objects.filter(tenant=self.tenant)`.
- **`OrderAmendmentForm`** — `Meta.fields = ["sales_order", "change_type", "reason", "document", "notes"]`.
  **Excluded:** `tenant` · `number` · `status` (workflow) · `impact_snapshot` (**frozen evidence**, `editable=False`) · `requested_by`/`requested_at`/`decided_by`/`decided_at`/`applied_by`/`applied_at` (**action-stamped**) · `created_at`/`updated_at`.
  `sales_order`'s queryset is narrowed to `status__in=OrderAmendment.AMENDABLE_STATUSES` **and** `tenant=self.tenant`.
- **`OrderAmendmentLineForm`** — `Meta.fields = ["sales_order_line", "operation", "new_quantity", "new_unit_price", "note"]`.
  **Excluded:** `amendment` (**set by the parent view**, never from user input) · `created_at`/`updated_at`.
- **`OrderAmendmentDecisionForm`** — a plain `forms.Form` (NOT a ModelForm): `decision` (`ChoiceField`, choices `[("approved","Approve"), ("rejected","Reject")]`), `decision_note` (`CharField(widget=forms.Textarea, required=False)` — named for the `decision_note` column it writes). It is the only authorable path to the decision stamps, and those stamps plus `decision_note` are written by the **view**, never by the form.
- **`RevenueScheduleForm`** — `Meta.fields = ["sales_order", "status", "method", "compliance_standard", "fiscal_period", "notes"]`.
  **Excluded:** `tenant` · `number` · `journal_entry` (**reference-only**, `editable=False`) · `created_at`/`updated_at`.
  **`status` IS included** — the single authorable `status` in 8.6 — with its widget queryset narrowed to `STATUS_CHOICES`.
- **`PerformanceObligationForm`** — `Meta.fields = ["sales_order_line", "item", "obligation_type", "description", "allocation_pct", "recognition_method", "recognize_on", "milestone_label", "evidence_reference"]`.
  **Excluded:** `schedule` (set by the parent view) · `allocated_amount`/`recognized_amount` (**recomputed**, `editable=False`) · `created_at`/`updated_at`.

---

## 4. Views & context-var contract — EVERY view and EVERY key

**Highest-risk section (L7, L8).** A context key a template expects but the view does not pass renders **blank at HTTP 200** — no traceback, just a silently empty region.

### 4.1 `views/OrderManagement/OrderValidationRules.py` — 5 CRUD views

| View | URL name | Template | Context keys — **every one** |
|---|---|---|---|
| `order_validation_rule_list` | `order_validation_rule_list` | `…/ordervalidationrule/list.html` | `rules` (Page of 15) · `page_obj` (alias, for the shared pagination partial) · `q` · `rule_type_choices` · `severity_choices` · `active_on_choices` · `parties` (tenant-filtered, ordered by `name`) · `stats` (`total`, `active`, `blocking`, `by_type`) |
| `order_validation_rule_create` | `order_validation_rule_create` | `…/ordervalidationrule/form.html` | `form` · `obj` (`None`) · `is_edit`=`False` |
| `order_validation_rule_detail` | `order_validation_rule_detail` | `…/ordervalidationrule/detail.html` | `rule` · `raised_holds` (Page of 15) · `page_obj` · `recent_orders` (10 most recent `scm.SalesOrder` in the tenant) |
| `order_validation_rule_edit` | `order_validation_rule_edit` | `…/ordervalidationrule/form.html` | `form` · `obj` · `is_edit`=`True` |
| `order_validation_rule_delete` | `order_validation_rule_delete` | — (POST-only → `sales:order_validation_rule_list`) | — |

**Filters (read before pagination):** `?q=` → `Q(name__icontains) | Q(number__icontains) | Q(description__icontains)` · `?rule_type=` · `?severity=` · `?active_on=` · `?party=` (int, **skip 0** — L11) · `?is_active=true|false` (any other value ignored).

### 4.2 `views/OrderManagement/OrderHolds.py` — 5 CRUD + 7 actions (12 views)

| View | URL name | Template | Context keys |
|---|---|---|---|
| `order_hold_list` | `order_hold_list` | `…/orderhold/list.html` | `holds` (Page) · `page_obj` · `q` · `hold_type_choices` · `status_choices` · `severity_choices` · `sales_orders` (tenant-filtered) · `parties` (tenant-filtered) · `checked_out_choices` = `[("","All"), ("yes","Checked Out"), ("no","Not Checked Out")]` · `stats` (`total`, `open`, `checked_out`, `cleared`) |
| `order_hold_create` | `order_hold_create` | `…/orderhold/form.html` | `form` · `obj`=`None` · `is_edit`=`False` |
| `order_hold_detail` | `order_hold_detail` | `…/orderhold/detail.html` | `hold` · `evaluation` (**parsed** snapshot dict, `{}` when blank — never the raw string) · `order` · `open_holds` (Page of the order's other open holds) · `page_obj` |
### 4.3 `views/OrderManagement/OrderAmendments.py` — 5 CRUD + 4 line actions + 4 amendment actions

| View | URL name | Template | Context keys |
|---|---|---|---|
| `order_amendment_list` | `order_amendment_list` | `…/orderamendment/list.html` | `amendments` (Page) · `page_obj` · `q` · `change_type_choices` · `status_choices` · `sales_orders` (tenant-filtered) · `stats` (`total`, `open`, `approved`, `applied`) |
| `order_amendment_create` | `order_amendment_create` | `…/orderamendment/form.html` | `form` · `obj`=`None` · `is_edit`=`False` · `change_type_choices` · `sales_orders` (only `AMENDABLE_STATUSES`) |
| `order_amendment_detail` | `order_amendment_detail` | `…/orderamendment/detail.html` | `amendment` · `lines` (Page of 15) · `page_obj` · `order` · `impact` (**parsed** snapshot dict, `{}` when blank) · `decision_form` (unbound) · `can_decide` (bool) · `can_apply` (bool) · `can_withdraw` (bool) · `line_form` (unbound `OrderAmendmentLineForm`) |
| `order_amendment_edit` | `order_amendment_edit` | `…/orderamendment/form.html` | `form` · `obj` · `is_edit`=`True` · `change_type_choices` · `sales_orders` |
| `order_amendment_delete` | `order_amendment_delete` | — (POST → `sales:order_amendment_list`) | — |
| `order_amendment_line_add` (POST) | `order_amendment_line_add` | `…/orderamendment/line_form.html` on invalid | `form` · `amendment` · `line`=`None` · `order_lines` |
| `order_amendment_line_edit` (POST) | `order_amendment_line_edit` | `…/orderamendment/line_form.html` on invalid | `form` · `amendment` · `line` · `order_lines` |
| `order_amendment_line_delete` (POST) | `order_amendment_line_delete` | — → `sales:order_amendment_detail` | — |
| `order_amendment_decide` (POST) | `order_amendment_decide` | `…/orderamendment/detail.html` on invalid | `amendment` · `decision_form` · `lines` · `page_obj` · `order` · `impact` · `can_decide` · `can_apply` · `can_withdraw` · `line_form` — **the full detail context, so a validation error re-renders the page, not a bare form** |
| `order_amendment_apply` (POST) | `order_amendment_apply` | — → `sales:order_amendment_detail` | — `transaction.atomic()` → `select_for_update()` on the order → `amendment.apply(user, locked_order, note)` |
| `order_amendment_withdraw` (POST) | `order_amendment_withdraw` | — → `sales:order_amendment_detail` | — |
| `order_amendment_open_queue` | `order_amendment_open_queue` | `…/orderamendment/list.html` (filtered) | the same context as the list, **pre-filtered to `status__in=("draft","pending","approved")`** |
| `order_amendment_impact` | `order_amendment_impact` | `…/orderamendment/impact.html` | `amendment` · `impact` (parsed dict) · `lines` · `order` · `allocations` · `shipments` · `schedule` (the order's `RevenueSchedule` or `None`) — **the pre-approval impact read-out, rendering the FROZEN snapshot beside the LIVE figures, and saying so** |

**Filters:** `?q=` → `Q(number__icontains) | Q(reason__icontains) | Q(sales_order__number__icontains)` · `?change_type=` · `?status=` · `?sales_order=` (int, skip 0).

**No route takes a child pk alone** — both children are edited through the parent, which is simultaneously the CRUD-completeness answer and the tenant-isolation guard. `?return_to=` is **never** accepted from user input.

### 4.4 `views/OrderManagement/RevenueSchedules.py` — 5 CRUD + 3 obligation actions + 1 recognize action

### 4.5 `views/OrderManagement/OrderBoards.py` — seven read-only boards + 3 POST actions

Each board is a **projection over facts that already exist**, carries a visible "this is derived" note, and **writes nothing** except the three explicit POST actions below.

| View | URL name | Template | Context keys |
|---|---|---|---|
| `order_capture_board` | `order_capture_board` | `…/boards/capture.html` | `orders` (Page of `scm.SalesOrder` in `ALLOCATABLE_STATUSES` + `on_hold`) · `page_obj` · `q` · `channel_choices` = `scm.SalesOrder.SOURCE_CHANNEL_CHOICES` · `status_choices` = `scm.SalesOrder.STATUS_CHOICES` · `open_hold_counts` (dict `{order_id: n}`) · `stats` (`total`, `on_hold`, `unmapped`, `by_channel`) |
| `order_fulfillment_board` | `order_fulfillment_board` | `…/boards/fulfillment.html` | `orders` (Page) · `page_obj` · `q` · `status_choices` · `risk_choices` = `[("","All"), ("no_commitment","No Commitment"), ("at_risk","At Risk"), ("past_due","Past Due"), ("on_track","On Track")]` · `hold_counts` · `stats` (`total`, `backordered`, `past_due`, `awaiting_pod`) |
| `order_history_board` | `order_history_board` | `…/boards/history.html` | `orders` (Page) · `page_obj` · `q` · `status_choices` · `stats` (`total`, `open`, `closed`, `cancelled`) |
| `order_timeline` | `order_timeline` | `…/boards/timeline.html` | `order` · `events` (list of dicts, newest first, each `{"at": <datetime>, "kind": <str>, "label": <str>, "detail": <str>}`) · `holds` · `amendments` · `shipments` · `tracking_events` · `invoice` — **assembled in the view from scm + accounting + 8.6. NO timeline table** — a sixth append-only log could disagree with the five it summarises |
| `reorder_customers_board` | `reorder_customers_board` | `…/boards/reorder.html` | `customers` (Page of dicts: `party`, `order_count`, `lifetime_value`, `avg_days_between`, `last_order_on`, `expected_order_on`, `on_time_pct`, `top_items`) · `page_obj` · `q` · `stats` (`customers`, `reorderable`, `lapsed`) |
| `renewals_due_board` | `renewals_due_board` | `…/boards/renewals.html` | `recurring_invoices` (Page of `accounting.RecurringInvoice`) · `page_obj` · `q` · `stats` (`due_30d`, `overdue`, `active_templates`) — **read-only over accounting's cadence engine. 8.6 builds NO renewal model and NO auto-renew order generation** (that is 8.15) |
| `revenue_recognition_board` | `revenue_recognition_board` | `…/boards/recognition.html` | `schedules` (Page) · `page_obj` · `q` · `method_choices` · `status_choices` · `fiscal_periods` · `stats` (`total`, `contract_value`, `recognized`, `deferred`, `contract_asset`, `contract_liability`, `overdue`) |
| `order_backorder_resolve` (POST) | `order_backorder_resolve` | — → `sales:order_fulfillment_board` | — The one genuinely new verb in bullet 2. Takes an `allocation` id and a `resolution` in `[("release","Release"), ("cancel","Cancel Shortfall"), ("keep","Keep Promising")]` and **delegates to 4.5's own release/cancel logic**. `promised_date` stays `editable=False` — 8.6 never rewrites a promise already given. |
| `order_repeat` (POST) | `order_repeat` | — → `scm:salesorder_detail` | — Creates a NEW `scm.SalesOrder` + `SalesOrderLine` **through 4.5's own create path**, preserving `source_channel` and recording the source order number in the new order's `notes`. 8.6 writes no order fields itself. |
| `order_validate` (POST) | `order_validate` | `…/boards/validation.html` | `order` · `findings` · `raised_holds` · `evaluation_run_at` — the read-only "why is / is not this order held" screen |
---

## 5. URLs — the FULL `urlpatterns` list

Package `apps/sales/urls/OrderManagement/` with `__init__.py`, `OrderValidationRules.py`, `OrderHolds.py`, `OrderAmendments.py`, `RevenueSchedules.py`, `OrderBoards.py`. Concatenated in this order: **`board_patterns + rule_patterns + hold_patterns + amendment_patterns + revenue_patterns`** (boards first — they carry the literal routes, the 8.5 `QuoteOperations`-first precedent).

**Prefix segment `orders/`** — verified free against all 16 mounted `sales:` prefixes. **`app_name = "sales"` is unchanged.** Literal routes always precede `<int:pk>` routes inside each module.

**Shadowing check is MANDATORY** (8.5 created the risk): 8.5 ships `sales:cpq_quote_list` at `quotes/` plus eleven sub-routes including the greedy `quotes/portal/<str:token>/`. Those sit inside `quotes/<int:pk>/` so they cannot reach `orders/`, but **every new route is re-checked against the whole concatenated `sales:urlpatterns` list**, and any route whose literal prefix could be captured by an existing `<int:pk>` or `<str:token>` route is rejected before it lands. `orders/holds/bulk-*/` and `orders/amendments/open/` precede `orders/holds/<int:pk>/` and `orders/amendments/<int:pk>/`.

**`OrderBoards.py` (10 routes, literals FIRST):**
```
orders/                          -> order_capture_board
orders/fulfillment/              -> order_fulfillment_board
orders/history/                  -> order_history_board
orders/timeline/<int:pk>/        -> order_timeline
orders/reorder/                  -> reorder_customers_board
orders/renewals/                 -> renewals_due_board
orders/recognition-board/        -> revenue_recognition_board
orders/validate/<int:order_pk>/  -> order_validate
orders/repeat/<int:pk>/          -> order_repeat
orders/backorders/<int:allocation_pk>/resolve/ -> order_backorder_resolve
```

**`OrderValidationRules.py` (5):** `orders/validation-rules/` · `…/create/` · `…/<int:pk>/` · `…/<int:pk>/edit/` · `…/<int:pk>/delete/`

**`OrderHolds.py` (12):** `orders/holds/` · `…/create/` · `…/bulk-raise/` · `…/bulk-clear/` · `…/<int:pk>/` · `…/<int:pk>/edit/` · `…/<int:pk>/delete/` · `…/<int:pk>/checkout/` · `…/<int:pk>/release-checkout/` · `…/<int:pk>/clear/` · `…/<int:pk>/clear-and-submit/` · `orders/raise/<int:order_id>/`

> **AMENDED 2026-09-29 — `order_hold_raise` sits at `orders/raise/<int:order_id>/`, not `orders/holds/<int:order_pk>/raise/`.** It takes an ORDER id, not a hold id, so nesting it under the hold namespace would have implied it operates on a hold. It is also unambiguously safe from the sibling `<int:pk>` routes (a different literal prefix, listed first). The build used this path; the contract is amended to match.

**`OrderAmendments.py` (13):** `orders/amendments/` · `…/create/` · `…/open/` · `…/<int:pk>/` · `…/<int:pk>/edit/` · `…/<int:pk>/delete/` · `…/<int:pk>/impact/` · `…/<int:pk>/decide/` · `…/<int:pk>/apply/` · `…/<int:pk>/withdraw/` · `…/<int:pk>/lines/add/` · `…/<int:pk>/lines/<int:line_pk>/edit/` · `…/<int:pk>/lines/<int:line_pk>/delete/`

**`RevenueSchedules.py` (9):** `orders/revenue-schedules/` · `…/create/` · `…/<int:pk>/` · `…/<int:pk>/edit/` · `…/<int:pk>/delete/` · `…/<int:pk>/obligations/add/` · `…/<int:pk>/obligations/<int:obligation_pk>/edit/` · `…/<int:pk>/obligations/<int:obligation_pk>/delete/` · `…/<int:pk>/recognize/`
---

## 6. Templates — 24 files under `templates/sales/ordermanagement/`

- `ordervalidationrule/` — `list.html` · `detail.html` · `form.html`
- `orderhold/` — `list.html` · `detail.html` · `form.html`
- `orderamendment/` — `list.html` · `detail.html` · `form.html` · `impact.html` · `line_form.html`
- `revenueschedule/` — `list.html` · `detail.html` · `form.html` · `obligation_form.html`
- `boards/` — `capture.html` · `fulfillment.html` · `history.html` · `timeline.html` · `reorder.html` · `renewals.html` · `recognition.html` · `validation.html`

`impact.html`, `line_form.html`, `obligation_form.html` and the eight board pages are **secondary-action / board pages living inside the entity folder or `boards/`** — never a flat `orderamendment_impact.html`.

- Every template does `{% extends "base.html" %}` and uses the shared partials. Folder structure does not affect `{% extends %}` / `{% include %}` paths.
- **BADGE RULE (L33) — only these six classes exist:** `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`. **`badge-success`, `badge-warning`, `badge-danger` DO NOT EXIST** and render unstyled. Every badge keys on the model's **exact choice value** with an `{% else %}` fallback to `{{ obj.get_<field>_display }}`:
  - `{% if obj.severity == "block" %}badge-red{% elif obj.severity == "hold" %}badge-amber{% else %}badge-muted{% endif %}`
  - `{% if obj.status == "open" %}badge-amber{% elif obj.status == "cleared" %}badge-green{% elif obj.status == "superseded" %}badge-muted{% else %}{{ obj.get_status_display }}{% endif %}`
  - `{% if obj.status == "applied" %}badge-green{% elif obj.status == "rejected" %}badge-red{% else %}{{ obj.get_status_display }}{% endif %}`
  - `{% if obj.status == "active" %}badge-green{% elif obj.status == "void" %}badge-muted{% else %}{{ obj.get_status_display }}{% endif %}`
- **Every list template carries an Actions column** — View (eye) · Edit (pencil) · Delete (bin) as a **POST form** with `{% csrf_token %}` and `onclick="return confirm('Delete {{ obj.number }}? This cannot be undone.')"`, using the `\'` escape (L42). Edit/Delete wrapped in a status guard where status-dependent.
- **Every detail template has an Actions sidebar** — Edit (conditional on status) · Delete (POST + confirm, conditional) · Back to List.
- **FK filter dropdowns compare with `|stringformat:"d"`, NEVER `|slugify`:** `{% if request.GET.party == party.pk|stringformat:"d" %}selected{% endif %}`.
- **Every board states in visible prose that its figures are derived** — e.g. *"Backorder quantities are derived from the order lines and their allocations; nothing here is stored."*
- **The fulfillment board shows the blocked-by-hold reason** on a live order (an open `OrderHold` with its `reason`), because "while the order is on hold it can't be processed by the warehouse" is the point of the column.
- **The timeline renders `events` as one ordered list** and **labels each event's source record**, so a reader can tell an SCM fact from a Sales fact.
- **No template writes an `scm` field directly.** Every order mutation goes through a POST view.
---

## 7. Wiring & integration — single writer, main session only

- `apps/sales/models/OrderManagement/__init__.py` — **the header docstring carrying the L36 ownership ruling**, then the four entity imports and an `__all__` listing all six classes.
- `apps/sales/models/__init__.py` — add **six** imports and six `__all__` entries. **Surgical `Edit`, never a rewrite** (L43). **Verify the app files landed before wiring anything.**
- `apps/sales/forms/OrderManagement/__init__.py` + `apps/sales/forms/__init__.py` — seven form classes.
- `apps/sales/views/OrderManagement/__init__.py` — the five view modules. `apps/sales/views/__init__.py` — every new view function by name, alphabetically within the 8.6 group.
- `apps/sales/urls/OrderManagement/__init__.py` — the §5 concatenation. `apps/sales/urls/__init__.py` — add the import and splice `*_order_management` into `urlpatterns` under a `# 8.6 Order Management.` comment **after** the 8.5 block.
- `apps/sales/admin.py` — **four** `@admin.register` blocks with `list_display`/`list_filter`/`search_fields` and **`raw_id_fields` for every FK**. The two tenant-less children get inline `TabularInline`s on their parent admin, not registrations of their own.
- **Migration `0012`** — `makemigrations sales` → `migrate`. Then `seed_sales` **twice** and `check`. **No `config/settings.py` and no `config/urls.py` edit** (the app is already installed and mounted).
- **`apps/core/navigation.py`** — add the one `LIVE_LINKS["8.6"]` entry. The five NavERP.md bullet strings **verbatim** map to:
  - `"Order Capture & Validation"` → `sales:order_capture_board`
  - `"Order Fulfillment Tracking"` → `sales:order_fulfillment_board`
  - `"Order Amendments & Cancellations"` → `sales:order_amendment_list`
  - `"Revenue Recognition & Scheduling"` → `sales:revenue_schedule_list`
  - `"Order History & Reorder"` → `sales:order_history_board`

  Plus extra live leaves: `"Order Validation Rules"` → `sales:order_validation_rule_list` · `"Order Hold Workbench"` → `sales:order_hold_list` · `"Reorder & Renewal Watch"` → `sales:reorder_customers_board` · `"Revenue Recognition Board"` → `sales:revenue_recognition_board`.
  **The `LIVE_LINKS["8.6"]` comment must carry the L36 ownership ruling** — this is one of the three durable places the ruling is encoded.
- **`NavERP-ERD.md`** — rewrite **row 8 only** (line ~470) per §0.8. Row 4 (line 466) untouched.
- **`.claude/tasks/lessons.md`** — append to **L37** (do not rewrite it): the ships-first ruling held and the order was extended, not duplicated.

### 7.1 Seeder — `seed_sales.py`, idempotent by construction

Extend `_seed_tenant` with a `_seed_order_management(tenant, owner)` call, using `get_or_create` throughout (never bare `.create()` / `.save()`):
---

## 8. Security & tenant-isolation gates

- Cross-tenant **404** on every verb, including all action verbs — not just the detail pages.
- Every FK choice queryset filtered to `tenant=request.tenant`; a form must **reject** a cross-tenant FK (use `_reject_foreign`).
- `request.tenant=None` (the tenantless superuser) sees **empty** lists, by design.
- Every action verb is **POST-only with CSRF**. No GET may mutate.
- No stored snapshot an attacker can supply: `evaluation_snapshot` and `impact_snapshot` are server-generated and off the form (L22).
- The hold checkout is exclusive: a second user cannot steal an active checkout, and only the holder or a tenant admin may release it.
- The recognize verb refuses unless the schedule is `active`; apply refuses unless the amendment is `approved`.
- No `eval`, no dynamic import, no relation traversal, no network call on a user-supplied path.

---

## 9. Verification gates

- `manage.py check` clean; `makemigrations --check` says **"No changes detected"** after the migration lands.
- **All 49 url names reverse**, and no two resolve to the same pattern.
- Every new page renders **200 for `admin_acme` with ASSERTED CONTENT** (not just status) — a mismatched context var returns 200 and renders blank (L8).
- Junk-param list (`?status=not-a-status&party=abc`) → 200, no 500 (L11).
- Page 2 of every paginated list renders.
- Cross-tenant IDOR on every verb → **404**.
- `seed_sales` run **twice** → identical row counts.
- Every `LIVE_LINKS["8.6"]` target resolves.

## 10. Tests

Four lanes: `test_ordermanagement_{models,forms,views,security}.py` under `apps/sales/tests/`, namespace `ordermanagement`. Every test function is `test_ordermanagement_*` and every module-level helper `_ordermanagement_*`, so the next sub-module appending nearby cannot shadow them. **8.5 added nothing to `conftest.py`; 8.6 adds nothing either** — record factories live in the models lane. The final run is the **full unfiltered** `apps/sales/tests` suite, never `-k` filtered (L47).

## 11. Close-out

Update the **existing** `.claude/skills/sales/SKILL.md` (an existing module — update, do not create a new one), add the 8.6 row to `README.md`, record the review section in `todo.md`, and commit **one file per commit** in PowerShell-safe form (`git add 'f'; git commit -m 'msg'` — `;` never `&&`). **Never `git push`.**

## 12. Out of scope — pre-existing, do not fix in this run

`apps/sales/models/_base.py:31-40` — `TenantNumbered.save()` falls through to a final `super().save()` with `self.number == ""` after five consecutive `IntegrityError`s, which then collides with `unique_together` on the **second** such row. It is pre-existing, shared by every numbered `sales` model, and 8.6 did not cause it. **8.6 does not fix it and does not widen scope to do it.** A reviewer who finds it files it as **PRE-EXISTING**, not as an 8.6 defect. Raise it as a separate one-file fix against `_base.py`, on its own.

- three `OrderValidationRule` rows (an unmapped-item rule, a missing-ship-to rule, a credit rule with `parameters={"pct": 20}`), the first **inactive** so the demo shows both states;
- one `OrderHold` on the seeded SO with a real `reason` and a **frozen `evaluation_snapshot`**, `raised_by=owner`;
- one `OrderAmendment` in `pending` with one `OrderAmendmentLine` created through the child's `amendment` FK, and a filled `impact_snapshot`;
- one `RevenueSchedule` (`active`, `asc606`) with two `PerformanceObligation` children summing to 100 % of `allocation_pct`, then `schedule.recompute()`.

The success string becomes `"Sales 8.1, 8.2, 8.3, 8.4, 8.5, and 8.6 seed complete."` and `help` mentions 8.6. **Two runs must be byte-stable.** It must still print `admin_acme / password` and the tenantless-superuser warning.





**49 url names in total**, all `sales:<name>`, no new namespace. Every one must reverse in the smoke pass and no two may resolve to the same pattern.



**Board filters:** `?q=` on the board's own search fields · `?status=` on order status · `?channel=` on capture · `?risk=` on fulfillment (the four buckets as **ORM date arithmetic** over `promised_date`/`requested_date`, as procurement 6.11's `Backorder.RISK_CHOICES` does) · `?fiscal_period=` on recognition. **Junk values are ignored, never 500'd** (L11).


| View | URL name | Template | Context keys |
|---|---|---|---|
| `revenue_schedule_list` | `revenue_schedule_list` | `…/revenueschedule/list.html` | `schedules` (Page) · `page_obj` · `q` · `method_choices` · `status_choices` · `compliance_standard_choices` · `sales_orders` (tenant-filtered) · `fiscal_periods` (tenant-filtered) · `stats` (`total`, `active`, `overdue`, `contract_value`, `recognized`, `deferred`) — **every money figure summed in PYTHON, never `aggregate("Sum")` on a Decimal** |
| `revenue_schedule_create` | `revenue_schedule_create` | `…/revenueschedule/form.html` | `form` · `obj`=`None` · `is_edit`=`False` · `method_choices` · `fiscal_periods` |
| `revenue_schedule_detail` | `revenue_schedule_detail` | `…/revenueschedule/detail.html` | `schedule` · `order` · `obligations` (`select_related("item")`) · `allocations` · `fiscal_periods` (tenant-filtered) · `obligation_form` (unbound) · `order_lines` · `can_recognize` (bool) |
| `revenue_schedule_edit` | `revenue_schedule_edit` | `…/revenueschedule/form.html` | `form` · `obj` · `is_edit`=`True` · `method_choices` · `fiscal_periods` |
| `revenue_schedule_delete` | `revenue_schedule_delete` | — (POST → `sales:revenue_schedule_list`) | — |
| `revenue_schedule_obligation_add` (POST) | `revenue_schedule_obligation_add` | `…/revenueschedule/obligation_form.html` on invalid | `form` · `schedule` · `obligation`=`None` · `order_lines` |
| `revenue_schedule_obligation_edit` (POST) | `revenue_schedule_obligation_edit` | `…/revenueschedule/obligation_form.html` on invalid | `form` · `schedule` · `obligation` · `order_lines` |
| `revenue_schedule_obligation_delete` (POST) | `revenue_schedule_obligation_delete` | — → `sales:revenue_schedule_detail` | — |
| `revenue_schedule_recognize` (POST) | `revenue_schedule_recognize` | — → `sales:revenue_schedule_detail` | — `schedule.recompute()`; **refuses when `status != "active"`** |

**Filters:** `?q=` → `Q(number__icontains) | Q(notes__icontains) | Q(sales_order__number__icontains)` · `?method=` · `?status=` · `?compliance_standard=` · `?fiscal_period=` (int, skip 0) · `?sales_order=` (int, skip 0).


| `order_hold_edit` | `order_hold_edit` | `…/orderhold/form.html` | `form` · `obj` · `is_edit`=`True` |
| `order_hold_delete` | `order_hold_delete` | — (POST → `sales:order_hold_list`) | — |
| `order_hold_raise` (POST) | `order_hold_raise` | — → `sales:order_hold_list` | — Runs `rule.evaluate(order)` for every active rule, creates an `OrderHold` per non-`warn` finding, writes back `SalesOrder.credit_hold=True` + `hold_reason`. `warn` findings go to `messages.warning` and create no hold. |
| `order_hold_checkout` (POST) | `order_hold_checkout` | — → `sales:order_hold_detail` | — Sets `checked_out_by`/`checked_out_at`. **Refuses if another user already holds the checkout**, and if `status != "open"`. |
| `order_hold_release_checkout` (POST) | `order_hold_release_checkout` | — → `sales:order_hold_detail` | — Clears the checkout. **Refuses unless the caller is the holder or a tenant admin** (the override case, recorded in `clear_note`). |
| `order_hold_clear` (POST) | `order_hold_clear` | — → `sales:order_hold_detail` | — Sets `status="cleared"`, `cleared_by`, `cleared_at`, `clear_note`; **if no open hold remains, writes back `credit_hold=False` and `hold_reason=""`.** |
| `order_hold_clear_and_submit` (POST) | `order_hold_clear_and_submit` | — → `scm:salesorder_detail` | — Clears the hold, then **delegates the submit to 4.5's own `salesorder_submit` logic** (re-evaluated, never a blind status write). Refuses if any other open hold remains or the order still has unmapped lines. |
| `order_hold_bulk_raise` (POST) | `order_hold_bulk_raise` | — → `sales:order_hold_list` | — Raises across a set of order ids; per-order failures are reported individually, not swallowed. |
| `order_hold_bulk_clear` (POST) | `order_hold_bulk_clear` | — → `sales:order_hold_list` | — Clears across a set of hold ids; each is re-evaluated for checkout ownership. |

**Filters:** `?q=` → `Q(number__icontains) | Q(reason__icontains) | Q(sales_order__number__icontains)` · `?hold_type=` · `?status=` · `?severity=` · `?sales_order=` (int, skip 0) · `?party=` (int, skip 0) · `?checked_out=yes|no` → `.exclude(checked_out_by__isnull=True)` / `.filter(checked_out_by__isnull=True)`, **scoped to `status="open"`** so a cleared hold with a stale checkout is not counted as checked out.


**Conventions, fixed once for all 8.6 views:** every view is `@login_required` + `@tenant_admin_required` · every queryset is `Model.objects.filter(tenant=request.tenant)` (never `.all()`) · list views use `Paginator(qs, 15)` and pass the **Page object itself** as the list var (the 8.5 shape) · every FK filter is a `(param, orm_lookup, is_int)` tuple through `crud_list`'s `filters=` or an explicit `request.GET` parse, and an unparseable value is **ignored, never 500'd** (L11) · every list passes its `*_choices` explicitly and every FK dropdown gets a **tenant-filtered queryset**.


- `operation` — `CharField(max_length=8, choices=OPERATION_CHOICES, default="update")` — `[("add","Add"), ("update","Update"), ("remove","Remove")]`
- `new_quantity` — `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(Decimal("0.0001"))])`
- `new_unit_price` — `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(ZERO)])`
- `note` — `CharField(max_length=255, blank=True)`
- `Meta`: `ordering = ["id"]`
- `clean()` — **keyed on `NON_FIELD_ERRORS`, never on an excluded field** (the 0.20 lesson: a `ValidationError` keyed on a field absent from its form routes through `add_error(None, …)`, raising `ValueError` and 500-ing every create/edit). `add` requires no `sales_order_line`; `update`/`remove` require one; `remove` must carry neither a new quantity nor a new price.



- `@property is_open` → `self.status == "open"`.
- `@property is_checked_out` → `self.checked_out_by_id is not None`.
- `parsed_snapshot` → `json.loads` safety wrapper returning `{}` on any failure. **The detail view renders this dict, never the raw string.**



