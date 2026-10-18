# Build Contract — Sub-module 8.10: Incentive Compensation Management (Module 8: Sales Management System, `apps/sales`)

> Phase 3 Step 1. `BASE = bf3ecbf7017f0bec1590b4f5dc9f06585aa67cb7`.
> Research: `.claude/tasks/research-sales-8.10.md`. Plan: `.claude/tasks/todo.md`.
> Next migration: **`0019_incentivecompensation`** (claimed).

---

## 0. Ownership Rulings (L29 / L36 / L37)

8.10 adds 4 tenant-scoped models and 5 derived read-only boards. It declares **zero duplicate deal, quota, order, currency, or payroll ledger tables**.

| Entity / Domain | Read-Only Master Owner | Where It Lives | 8.10's Relationship |
|---|---|---|---|
| **Opportunities & Credit Splits** | **CRM 1.2** | `apps/crm/models/SalesForceAutomation/Opportunities.py` | `crm.Opportunity` (`OPP-`) and `crm.OpportunitySplit` are the transaction anchors (`CommissionEarning.opportunity`). Zero duplicate deal/split model. |
| **Sales Quotas** | **CRM 1.2** | `apps/crm/models/SalesForceAutomation/SalesQuotas.py` | `crm.SalesQuota` (`QTA-`) provides rep target figures for quota-attainment accelerator evaluation (`CommissionPlan.sales_quota` / `CommissionEarning.sales_quota`). Zero duplicate quota model. |
| **Quota Derivation & Periods** | **Sales 8.7 & 8.4** | `apps/sales/models/TerritoryQuotaManagement/QuotaPlans.py` & `SalesForecasting/ForecastPeriods.py` | `sales.QuotaPlan` (`QPA-`) and `sales.ForecastPeriod` (`FCP-`) provide calendar periods and quota planning envelope. |
| **Sales Orders & Order Changes** | **SCM 4.5 & Sales 8.6** | `apps/scm/models/OrderManagement/SalesOrders.py` & `apps/sales/models/OrderManagement/OrderAmendments.py` | `scm.SalesOrder` (`SO-`) provides order-level crediting; `sales.OrderAmendment` (`AMD-`) triggers cancellation clawbacks. |
| **Currencies & Exchange Rates** | **Accounting 2.2** | `apps/accounting/models/GeneralLedger/Currencies.py` & `ExchangeRates.py` | `accounting.Currency` (global ISO 4217) and `accounting.ExchangeRate` (tenant spot rate) provide multi-currency FX translation into functional currency. |
| **Payroll Runs & General Ledger** | **Accounting 2.8** | `apps/accounting/models/PayrollIntegration/PayrollRuns.py` | Locked statements integrate directly via FK into `accounting.PayrollRun` (`PRUN-`). Zero duplicate GL or payroll ledger. |
| **Payees, Managers & Approvers** | **accounts 0** | `apps/accounts/models/User.py` | `settings.AUTH_USER_MODEL` (`accounts.User`) represents plan participants, managers, and approvers. |

---

## 1. Models — Every Field, Every Choice, Every Constraint

All models reside in `apps/sales/models/IncentiveCompensation/`.
Base: `apps.sales.models._base.TenantNumbered` (includes `tenant` FK `core.Tenant`, `number = CharField(max_length=20, editable=False)`, `created_at`, `updated_at`).

### 1.1 `CommissionPlan` (`CommissionPlans.py`) — `NUMBER_PREFIX = "CMPL"`

```python
PLAN_TYPE_CHOICES = [
    ("flat_revenue", "Flat Revenue %"),
    ("gross_margin", "Gross Margin %"),
    ("tiered_quota", "Tiered Quota Attainment"),
    ("spif_only", "SPIF / Bonus Only"),
    ("hybrid", "Hybrid (Revenue + Tier + SPIF)"),
]

TIER_MODE_CHOICES = [
    ("incremental", "Incremental / Marginal Brackets"),
    ("retroactive", "Retroactive / All-In Payout"),
    ("not_applicable", "Not Applicable (Flat/No Tiers)"),
]

STATUS_CHOICES = [
    ("draft", "Draft"),
    ("active", "Active"),
    ("archived", "Archived"),
]

PAYOUT_FREQUENCY_CHOICES = [
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("semi_annual", "Semi-Annual"),
    ("annual", "Annual"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `name` | `CharField(200)` | Plan name, required |
| `code` | `SlugField(60)` | Unique per tenant |
| `description` | `TextField(blank=True)` | Summary / documentation |
| `plan_type` | `CharField(30, choices=PLAN_TYPE_CHOICES, default="flat_revenue")` | Indexed |
| `tier_mode` | `CharField(30, choices=TIER_MODE_CHOICES, default="not_applicable")` | Accelerator bracket logic |
| `status` | `CharField(20, choices=STATUS_CHOICES, default="draft")` | Indexed |
| `payout_frequency` | `CharField(20, choices=PAYOUT_FREQUENCY_CHOICES, default="monthly")` | Settlement cadence |
| `effective_start` | `DateField()` | Plan valid from |
| `effective_end` | `DateField(null=True, blank=True)` | Optional expiration |
| `currency` | `ForeignKey("accounting.Currency", PROTECT, related_name="sales_commission_plans")` | Plan denomination |
| `target_region` | `CharField(100, blank=True)` | E.g. "Americas", "EMEA", "APAC", "Global" |
| `base_rate_pct` | `DecimalField(5, 2, default=0.00, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Flat commission rate % |
| `tiers_config` | `JSONField(default=list, blank=True)` | List of dicts: `[{"min_pct": 0, "max_pct": 100, "rate_pct": 5.0}, {"min_pct": 100, "max_pct": 150, "rate_pct": 10.0}]` |
| `spif_config` | `JSONField(default=list, blank=True)` | List of dicts: `[{"name": "Q4 Booster", "bonus_amount": 500.0, "criteria": "new_logo"}]` |
| `draw_amount` | `DecimalField(12, 2, default=0.00, validators=[MinValueValidator(0)])` | Advance per period |
| `is_draw_recoverable` | `BooleanField(default=True)` | True = advance liability; False = guarantee |
| `clawback_window_days` | `PositiveIntegerField(default=90)` | Days post-close for clawback eligibility |
| `tax_withholding_pct` | `DecimalField(5, 2, default=0.00, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Estimated local tax withholding |
| `sales_quota` | `ForeignKey("crm.SalesQuota", SET_NULL, null=True, blank=True, related_name="commission_plans")` | Optional target reference |
| `owner` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="owned_commission_plans")` | Plan administrator |

- `Meta.ordering = ["-effective_start", "name"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_cmpl_tenant_number_uniq")`, `UniqueConstraint(fields=["tenant", "code"], name="sales_cmpl_tenant_code_uniq")`
- `Meta.indexes`: `Index(fields=["tenant", "status", "effective_start"], name="sales_cmpl_stat_start_idx")`, `Index(fields=["tenant", "plan_type"], name="sales_cmpl_type_idx")`
- `clean()`:
  - **G1**: If `effective_end` is provided, `effective_end >= effective_start`.
  - **G2**: If `plan_type in ("tiered_quota", "hybrid")`, `tiers_config` must be a valid non-empty list of tier dicts with monotonic ascending thresholds (`min_pct < max_pct`), non-overlapping brackets, and non-negative rates.
  - **G3**: If `sales_quota` is selected, verify same tenant (`sales_quota.tenant_id == self.tenant_id`).
  - **G4**: Verify `owner` belongs to the same tenant if assigned.

---

### 1.2 `CommissionEarning` (`CommissionEarnings.py`) — `NUMBER_PREFIX = "CER"`

```python
CREDIT_TYPE_CHOICES = [
    ("direct", "Direct Rep Credit"),
    ("split", "Team Deal Split"),
    ("overlay", "Overlay / Specialist Credit"),
    ("manager_override", "Manager Rollup / Override"),
    ("spif_bonus", "SPIF Campaign Bonus"),
]

STATUS_CHOICES = [
    ("pending", "Pending Calculation"),
    ("calculated", "Calculated / Verified"),
    ("approved", "Approved for Payout"),
    ("paid", "Paid out"),
    ("clawed_back", "Clawed Back"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `plan` | `ForeignKey("sales.CommissionPlan", CASCADE, related_name="earnings")` | Associated plan |
| `payee` | `ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name="sales_commission_earnings")` | Credited rep |
| `opportunity` | `ForeignKey("crm.Opportunity", SET_NULL, null=True, blank=True, related_name="commission_earnings")` | Deal master |
| `sales_order` | `ForeignKey("scm.SalesOrder", SET_NULL, null=True, blank=True, related_name="commission_earnings")` | Optional order execution link |
| `credit_type` | `CharField(30, choices=CREDIT_TYPE_CHOICES, default="direct")` | Credit channel |
| `split_percentage` | `DecimalField(5, 2, default=100.00, validators=[MinValueValidator(0), MaxValueValidator(100)])` | % of deal attributed |
| `deal_amount` | `DecimalField(14, 2, default=0.00, validators=[MinValueValidator(0)])` | Raw transaction value |
| `credited_volume` | `DecimalField(14, 2, default=0.00, validators=[MinValueValidator(0)])` | `deal_amount * split_percentage / 100` |
| `attainment_pct_at_close` | `DecimalField(6, 2, default=0.00, validators=[MinValueValidator(0)])` | Rep cumulative quota attainment % |
| `applied_rate_pct` | `DecimalField(5, 2, default=0.00, validators=[MinValueValidator(0), MaxValueValidator(100)])` | Base + accelerator rate |
| `base_commission_amount` | `DecimalField(14, 2, default=0.00, validators=[MinValueValidator(0)])` | `credited_volume * applied_rate_pct / 100` |
| `spif_amount` | `DecimalField(12, 2, default=0.00, validators=[MinValueValidator(0)])` | Tactical bonus addition |
| `gross_commission` | `DecimalField(14, 2, default=0.00, validators=[MinValueValidator(0)])` | `base_commission_amount + spif_amount` |
| `deal_currency` | `ForeignKey("accounting.Currency", PROTECT, related_name="sales_deal_earnings")` | Currency of the deal |
| `exchange_rate` | `DecimalField(12, 6, default=1.000000, validators=[MinValueValidator(0)])` | Spot FX rate to plan/tenant currency |
| `functional_amount` | `DecimalField(14, 2, default=0.00, validators=[MinValueValidator(0)])` | Gross commission converted to functional currency |
| `status` | `CharField(20, choices=STATUS_CHOICES, default="calculated")` | Lifecycle state |
| `earned_date` | `DateField()` | Close date / milestone date |
| `clawback_parent` | `ForeignKey("self", SET_NULL, null=True, blank=True, related_name="clawback_children")` | If this earning is a clawback, points to original |
| `statement` | `ForeignKey("sales.CommissionStatement", SET_NULL, null=True, blank=True, related_name="earnings")` | Rolled into pay statement |

- `Meta.ordering = ["-earned_date", "-created_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_cer_tenant_number_uniq")`
- `Meta.indexes`: `Index(fields=["tenant", "payee", "status"], name="sales_cer_payee_stat_idx")`, `Index(fields=["tenant", "earned_date"], name="sales_cer_date_idx")`, `Index(fields=["tenant", "opportunity"], name="sales_cer_opp_idx")`
- `clean()`:
  - **G5**: Tenant isolation: `plan.tenant_id == self.tenant_id`, `payee` belongs to tenant.
  - **G6**: If `opportunity` is set, `opportunity.tenant_id == self.tenant_id`.
  - **G7**: If `sales_order` is set, `sales_order.tenant_id == self.tenant_id`.
  - **G8**: `credited_volume` must equal `round(deal_amount * split_percentage / 100, 2)`.
  - **G9**: `gross_commission` must equal `round(base_commission_amount + spif_amount, 2)`.

---

### 1.3 `CommissionStatement` (`CommissionStatements.py`) — `NUMBER_PREFIX = "CST"`

```python
STATEMENT_STATUS_CHOICES = [
    ("draft", "Draft / Open"),
    ("under_review", "Under Manager Review"),
    ("approved", "Approved by Manager"),
    ("locked", "Locked / Finalized"),
    ("exported", "Exported / Sent to Payroll"),
    ("paid", "Paid"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `statement_number` | `CharField(40)` | Formatted code e.g. `STMT-2026-M10-REP` |
| `payee` | `ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name="commission_statements")` | Sales rep |
| `plan` | `ForeignKey("sales.CommissionPlan", PROTECT, related_name="statements")` | Applicable compensation plan |
| `period_start` | `DateField()` | Settlement period start |
| `period_end` | `DateField()` | Settlement period end |
| `status` | `CharField(20, choices=STATEMENT_STATUS_CHOICES, default="draft")` | Workflow state |
| `total_credited_volume` | `DecimalField(14, 2, default=0.00)` | Sum of credited volume |
| `total_base_commission` | `DecimalField(14, 2, default=0.00)` | Base earnings |
| `total_accelerator_amount` | `DecimalField(14, 2, default=0.00)` | Accelerator tier bonuses |
| `total_spif_amount` | `DecimalField(12, 2, default=0.00)` | Total SPIF bonuses |
| `gross_earnings` | `DecimalField(14, 2, default=0.00)` | Total earned before deductions |
| `draw_advance_paid` | `DecimalField(12, 2, default=0.00)` | Guaranteed draw given |
| `draw_recovered` | `DecimalField(12, 2, default=0.00)` | Draw recovered from gross |
| `adjustments_amount` | `DecimalField(12, 2, default=0.00)` | Net manual adjustments (+/-) |
| `clawbacks_deducted` | `DecimalField(12, 2, default=0.00)` | Cancellations/chargebacks deducted |
| `tax_withholding_amount` | `DecimalField(12, 2, default=0.00)` | Tax withholding |
| `net_payout` | `DecimalField(14, 2, default=0.00)` | Final net settlement amount |
| `approved_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="approved_commission_statements")` | Manager stamp |
| `approved_at` | `DateTimeField(null=True, blank=True)` | Approval timestamp |
| `locked_at` | `DateTimeField(null=True, blank=True)` | Lock timestamp |
| `payroll_run` | `ForeignKey("accounting.PayrollRun", SET_NULL, null=True, blank=True, related_name="commission_statements")` | Integration to Module 2 |
| `notes` | `TextField(blank=True)` | Audit & resolution remarks |

- `Meta.ordering = ["-period_end", "payee__email"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_cst_tenant_number_uniq")`, `UniqueConstraint(fields=["tenant", "payee", "period_start", "period_end"], name="sales_cst_payee_period_uniq")`
- `Meta.indexes`: `Index(fields=["tenant", "status", "period_end"], name="sales_cst_stat_end_idx")`, `Index(fields=["tenant", "payee"], name="sales_cst_payee_idx")`
- `clean()`:
  - **G10**: `period_end >= period_start`.
  - **G11**: Waterfall consistency: `net_payout` must equal `max(0, gross_earnings + adjustments_amount - draw_recovered - clawbacks_deducted - tax_withholding_amount)`.
  - **G12**: Once `status in ("locked", "exported", "paid")`, fields cannot be modified without being unlocked by an admin.
  - **G13**: Tenant isolation on `payee`, `plan`, `approved_by`, and `payroll_run`.

---

### 1.4 `CommissionAdjustment` (`CommissionAdjustments.py`) — `NUMBER_PREFIX = "CADJ"`

```python
ADJUSTMENT_TYPE_CHOICES = [
    ("cancellation_clawback", "Order Cancellation / Churn Clawback"),
    ("draw_true_up", "Draw True-Up / Reconciliation"),
    ("tier_true_up", "Retroactive Tier Rate True-Up"),
    ("manual_override", "Manager Discretionary Override"),
    ("dispute_resolution", "Rep Dispute Claim Settlement"),
    ("tax_adjustment", "Local Tax / FX Adjustment"),
]

STATUS_CHOICES = [
    ("draft", "Draft / Proposed"),
    ("disputed", "Under Rep Dispute"),
    ("approved", "Approved by Manager"),
    ("applied", "Applied to Statement"),
    ("rejected", "Rejected / Dismissed"),
]
```

| Field | Type | Attributes & Clean Guards |
|---|---|---|
| `statement` | `ForeignKey("sales.CommissionStatement", SET_NULL, null=True, blank=True, related_name="adjustments")` | Linked settlement statement |
| `earning` | `ForeignKey("sales.CommissionEarning", SET_NULL, null=True, blank=True, related_name="adjustments")` | Original earning record |
| `payee` | `ForeignKey(settings.AUTH_USER_MODEL, CASCADE, related_name="sales_commission_adjustments")` | Impacted sales rep |
| `adjustment_type` | `CharField(30, choices=ADJUSTMENT_TYPE_CHOICES)` | Reason categorization |
| `amount` | `DecimalField(12, 2)` | Positive (credit/bonus) or negative (clawback/deduction) |
| `status` | `CharField(20, choices=STATUS_CHOICES, default="draft")` | Lifecycle state |
| `reason` | `TextField()` | Justification, cancellation order reference, or dispute ticket notes |
| `dispute_comments` | `TextField(blank=True)` | In-app dispute ticket exchange |
| `requested_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="requested_commission_adjustments")` | Rep or manager author |
| `approved_by` | `ForeignKey(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="approved_commission_adjustments")` | Authorizing manager |
| `effective_date` | `DateField()` | Ledger posting date |

- `Meta.ordering = ["-effective_date", "-created_at"]`
- `Meta.constraints`: `UniqueConstraint(fields=["tenant", "number"], name="sales_cadj_tenant_number_uniq")`
- `Meta.indexes`: `Index(fields=["tenant", "payee", "status"], name="sales_cadj_payee_stat_idx")`, `Index(fields=["tenant", "adjustment_type"], name="sales_cadj_type_idx")`
- `clean()`:
  - **G14**: Tenant isolation: `payee`, `requested_by`, `approved_by`, `earning`, and `statement` must belong to `self.tenant`.
  - **G15**: If `adjustment_type == "cancellation_clawback"`, `amount` must be negative (`amount <= 0`).
  - **G16**: If `statement` is locked, adjustments cannot be attached to it directly; they must roll into a future draft statement.

---

## 2. Forms (`apps/sales/forms/IncentiveCompensation/`)

All forms inherit `(TenantUniqueMixin, TenantModelForm)` from `apps.sales.forms._common`.

1. **`CommissionPlanForm`** (`CommissionPlans.py`):
   - `Meta.fields = ["name", "code", "description", "plan_type", "tier_mode", "status", "payout_frequency", "effective_start", "effective_end", "currency", "target_region", "base_rate_pct", "draw_amount", "is_draw_recoverable", "clawback_window_days", "tax_withholding_pct", "sales_quota", "owner"]`
   - Excluded: `tenant`, `number`, `tiers_config`, `spif_config` (custom JSON text fields handled with clean validation).
   - Scopes: `currency` to all active currencies, `sales_quota` to same-tenant quotas, `owner` to same-tenant active users.

2. **`CommissionEarningForm`** (`CommissionEarnings.py`):
   - `Meta.fields = ["plan", "payee", "opportunity", "sales_order", "credit_type", "split_percentage", "deal_amount", "attainment_pct_at_close", "applied_rate_pct", "spif_amount", "deal_currency", "exchange_rate", "status", "earned_date", "clawback_parent"]`
   - Excluded: `tenant`, `number`, `credited_volume`, `base_commission_amount`, `gross_commission`, `functional_amount`, `statement`.
   - Scopes: `plan` to same-tenant active plans, `payee` to same-tenant active users, `opportunity` to same-tenant opportunities, `sales_order` to same-tenant orders.

3. **`CommissionStatementForm`** (`CommissionStatements.py`):
   - `Meta.fields = ["statement_number", "payee", "plan", "period_start", "period_end", "status", "draw_advance_paid", "notes"]`
   - Excluded: `tenant`, `number`, `total_credited_volume`, `total_base_commission`, `total_accelerator_amount`, `total_spif_amount`, `gross_earnings`, `draw_recovered`, `adjustments_amount`, `clawbacks_deducted`, `tax_withholding_amount`, `net_payout`, `approved_by`, `approved_at`, `locked_at`, `payroll_run`.
   - Scopes: `payee` and `plan` to same-tenant active records.

4. **`CommissionAdjustmentForm`** (`CommissionAdjustments.py`):
   - `Meta.fields = ["statement", "earning", "payee", "adjustment_type", "amount", "status", "reason", "effective_date"]`
   - Excluded: `tenant`, `number`, `dispute_comments`, `requested_by`, `approved_by`.
   - Scopes: `statement`, `earning`, and `payee` to same-tenant records.

5. **`CommissionDisputeTicketForm`** (`CommissionAdjustments.py`):
   - Form for sales reps to submit dispute tickets on specific earnings or statements.
   - `Meta.fields = ["earning", "amount", "reason"]`.

---

## 3. URLs & Routing (`apps/sales/urls/IncentiveCompensation/`)

App namespace: `sales:`. Literal routes before `<int:pk>`. Board routes concatenated first.

### 3.1 Boards (`CommissionBoards.py`):
- `compensation/plan-hub/` → `name="sales_commission_plan_hub"`
- `compensation/earnings-dashboard/` → `name="sales_commission_earnings_dashboard"`
- `compensation/adjustment-workbench/` → `name="sales_commission_adjustment_workbench"`
- `compensation/global-matrix/` → `name="sales_global_compensation_matrix"`
- `compensation/payout-processing/` → `name="sales_commission_payout_processing"`
- `compensation/what-if/` → `name="sales_commission_what_if_calc"` (HTMX JSON/HTML calculation endpoint)

### 3.2 Plans (`CommissionPlans.py`):
- `compensation/plans/` → `name="commission_plan_list"`
- `compensation/plans/add/` → `name="commission_plan_create"`
- `compensation/plans/<int:pk>/edit/` → `name="commission_plan_edit"`
- `compensation/plans/<int:pk>/delete/` → `name="commission_plan_delete"` (POST-only, `@tenant_admin_required`)
- `compensation/plans/<int:pk>/` → `name="commission_plan_detail"`

### 3.3 Earnings (`CommissionEarnings.py`):
- `compensation/earnings/` → `name="commission_earning_list"`
- `compensation/earnings/add/` → `name="commission_earning_create"`
- `compensation/earnings/<int:pk>/edit/` → `name="commission_earning_edit"`
- `compensation/earnings/<int:pk>/delete/` → `name="commission_earning_delete"` (POST-only, `@tenant_admin_required`)
- `compensation/earnings/<int:pk>/` → `name="commission_earning_detail"`

### 3.4 Statements (`CommissionStatements.py`):
- `compensation/statements/` → `name="commission_statement_list"`
- `compensation/statements/add/` → `name="commission_statement_create"`
- `compensation/statements/generate-batch/` → `name="commission_statement_generate_batch"` (POST-only)
- `compensation/statements/<int:pk>/edit/` → `name="commission_statement_edit"`
- `compensation/statements/<int:pk>/delete/` → `name="commission_statement_delete"` (POST-only, `@tenant_admin_required`)
- `compensation/statements/<int:pk>/approve/` → `name="commission_statement_approve"` (POST-only)
- `compensation/statements/<int:pk>/lock/` → `name="commission_statement_lock"` (POST-only)
- `compensation/statements/<int:pk>/` → `name="commission_statement_detail"`

### 3.5 Adjustments (`CommissionAdjustments.py`):
- `compensation/adjustments/` → `name="commission_adjustment_list"`
- `compensation/adjustments/add/` → `name="commission_adjustment_create"`
- `compensation/adjustments/<int:pk>/edit/` → `name="commission_adjustment_edit"`
- `compensation/adjustments/<int:pk>/delete/` → `name="commission_adjustment_delete"` (POST-only, `@tenant_admin_required`)
- `compensation/adjustments/<int:pk>/resolve-dispute/` → `name="commission_adjustment_resolve_dispute"` (POST-only)
- `compensation/adjustments/<int:pk>/` → `name="commission_adjustment_detail"`

---

## 4. Views & Context Variables

Every view is `@login_required`, tenant-isolated (`filter(tenant=request.tenant)`), and logs actions via `apps.core.utils.log_action`.

### 4.1 Plans (`CommissionPlans.py`)
- `commission_plan_list`:
  - Context: `object_list`, `page_obj`, `q`, `plan_type_choices`, `tier_mode_choices`, `status_choices`, `stats` (dict: `total`, `active`, `tiered`, `spif`).
- `commission_plan_detail`:
  - Context: `obj`, `plan_type_display`, `tier_mode_display`, `status_display`, `assigned_reps`, `recent_earnings`.
- `commission_plan_create` / `commission_plan_edit`:
  - Context: `form`, `obj`, `is_edit`, `plan_type_choices`, `tier_mode_choices`.

### 4.2 Earnings (`CommissionEarnings.py`)
- `commission_earning_list`:
  - Context: `object_list`, `page_obj`, `q`, `status_choices`, `credit_type_choices`, `payees`, `plans`, `stats` (dict: `total_gross`, `total_spif`, `calculated_count`, `paid_count`).
- `commission_earning_detail`:
  - Context: `obj`, `status_display`, `credit_type_display`, `deal_split_info`.
- `commission_earning_create` / `commission_earning_edit`:
  - Context: `form`, `obj`, `is_edit`, `credit_type_choices`, `status_choices`.

### 4.3 Statements (`CommissionStatements.py`)
- `commission_statement_list`:
  - Context: `object_list`, `page_obj`, `q`, `status_choices`, `payees`, `stats` (dict: `total_net_payout`, `locked_count`, `pending_approval`, `total_draws_recovered`).
- `commission_statement_detail`:
  - Context: `obj`, `status_display`, `earnings_list`, `adjustments_list`, `can_approve`, `can_lock`.
- `commission_statement_create` / `commission_statement_edit`:
  - Context: `form`, `obj`, `is_edit`, `status_choices`.

### 4.4 Adjustments (`CommissionAdjustments.py`)
- `commission_adjustment_list`:
  - Context: `object_list`, `page_obj`, `q`, `adjustment_type_choices`, `status_choices`, `payees`, `stats` (dict: `total_adjustments`, `clawbacks_total`, `disputes_count`, `approved_count`).
- `commission_adjustment_detail`:
  - Context: `obj`, `status_display`, `adjustment_type_display`.
- `commission_adjustment_create` / `commission_adjustment_edit`:
  - Context: `form`, `obj`, `is_edit`, `adjustment_type_choices`.

### 4.5 Boards (`CommissionBoards.py`)
1. **`sales_commission_plan_hub`**:
   - Context: `plans`, `active_spifs`, `tier_accelerator_benchmarks`, `stats` (dict: `active_plans_count`, `avg_base_rate`, `reps_enrolled`).
2. **`sales_commission_earnings_dashboard`**:
   - Context: `payee_summary`, `recent_earnings`, `attainment_gauge`, `spif_summary`, `plans` (for what-if simulator).
3. **`sales_commission_adjustment_workbench`**:
   - Context: `pending_clawbacks`, `active_disputes`, `draw_reconciliation_queue`, `stats` (dict: `pending_clawback_amount`, `open_disputes_count`).
4. **`sales_global_compensation_matrix`**:
   - Context: `regional_plans` (Americas, EMEA, APAC), `currencies`, `recent_exchange_rates`, `tax_withholding_summary`.
5. **`sales_commission_payout_processing`**:
   - Context: `ready_statements`, `pending_approvals`, `payroll_runs`, `stats` (dict: `total_payout_due`, `statements_ready`, `payroll_integrated`).
6. **`sales_commission_what_if_calc`**:
   - Context: `simulated_deal_amount`, `simulated_split`, `projected_attainment`, `projected_tier_rate`, `projected_earning`, `spif_eligible`.

---

## 5. Templates Layout (`templates/sales/incentivecompensation/`)

Lower-case folder names, bare file names, extending `templates/base.html`:
- `templates/sales/incentivecompensation/commissionplan/{list,detail,form}.html`
- `templates/sales/incentivecompensation/commissionearning/{list,detail,form}.html`
- `templates/sales/incentivecompensation/commissionstatement/{list,detail,form}.html`
- `templates/sales/incentivecompensation/commissionadjustment/{list,detail,form}.html`
- `templates/sales/incentivecompensation/boards/plan_hub.html`
- `templates/sales/incentivecompensation/boards/earnings_dashboard.html`
- `templates/sales/incentivecompensation/boards/adjustment_workbench.html`
- `templates/sales/incentivecompensation/boards/global_matrix.html`
- `templates/sales/incentivecompensation/boards/payout_processing.html`

All templates strictly adhere to design-system classes in `static/css/theme.css`:
- Badges: `.badge-green`, `.badge-amber`, `.badge-red`, `.badge-info`, `.badge-muted`, `.badge-slate` (**NO `-success/-danger`**).
- Stat cards: `.stat-card` with icon colors `blue`, `green`, `orange`, `purple`, `slate`.
- Filter forms: search input `name="q"`, select dropdowns preserving `request.GET`, pagination with `page_obj.has_previous` / `has_next`.
- Actions column: View / Edit / Delete (POST-only + confirm + csrf).

---

## 6. Seeder Extensions (`seed_sales.py`)

Extend `apps/sales/management/commands/seed_sales.py`:
- Add `_seed_incentive_compensation(tenant, owner)` called from `handle()`.
- Idempotent existence checks: `if CommissionPlan.objects.filter(tenant=tenant).exists(): return`.
- Creates:
  * 3 `CommissionPlan` records:
    1. "Enterprise Quota Accelerators" (`CMPL-00001`): tiered quota attainment with incremental rates (8% up to 100%, 15% 100-150%, 20% >150%).
    2. "Commercial Velocity Flat 10%" (`CMPL-00002`): flat 10% base rate, recoverable draw $2,000/mo.
    3. "Q4 Expansion SPIF & Margin Plan" (`CMPL-00003`): gross margin based + $1,000 tactical SPIF campaign.
  * 4 `CommissionEarning` records tied to existing closed-won opportunities and reps, demonstrating deal split, accelerator rate calculation, and SPIF bonuses.
  * 2 `CommissionStatement` records for past and current settlement cycles with waterfall deductions.
  * 3 `CommissionAdjustment` records demonstrating a cancellation clawback, a draw true-up, and an approved dispute resolution.

---

## 7. Navigation Wire-Up (`apps/core/navigation.py`)

Add `LIVE_LINKS["8.10"]` mapping all 5 NavERP.md 8.10 feature bullets verbatim:
```python
    "8.10": {
        # OWNERSHIP RULINGS (L29/L36/L37):
        # - Deals & splits: CRM 1.2 (`crm.Opportunity`, `crm.OpportunitySplit`).
        # - Quota targets: CRM 1.2 (`crm.SalesQuota`) & Sales 8.7 (`sales.QuotaPlan`).
        # - Sales orders: SCM 4.5 (`scm.SalesOrder`) & Sales 8.6 (`sales.OrderAmendment`).
        # - Multi-currency & FX: Accounting 2.2 (`accounting.Currency`, `accounting.ExchangeRate`).
        # - Payroll integration: Accounting 2.8 (`accounting.PayrollRun`).
        # Verbatim 5 feature bullets:
        "Commission Plan Design": "sales:sales_commission_plan_hub",
        "Real-Time Earnings Tracking": "sales:sales_commission_earnings_dashboard",
        "Clawbacks & Adjustments": "sales:sales_commission_adjustment_workbench",
        "Multi-Currency & Global Plans": "sales:sales_global_compensation_matrix",
        "Payout Processing & Integration": "sales:sales_commission_payout_processing",
        # Extra live leaves:
        "Commission Plans": "sales:commission_plan_list",
        "Commission Earnings": "sales:commission_earning_list",
        "Commission Statements": "sales:commission_statement_list",
        "Commission Adjustments": "sales:commission_adjustment_list",
    },
```

---

## 8. Verification & Smoke Gate

1. `venv\Scripts\python.exe manage.py makemigrations sales` → generates `0019_incentivecompensation.py`.
2. `venv\Scripts\python.exe manage.py migrate` → cleanly applies.
3. `venv\Scripts\python.exe manage.py seed_sales` × 2 → idempotent.
4. `venv\Scripts\python.exe manage.py check` → 0 errors.
5. Smoke test script (`temp/smoke_sales_8_10.py`):
   - Authenticates as `admin_acme` / `password`.
   - Asserts HTTP 200 on all list/detail/create/edit/board pages.
   - Asserts no unrendered `{#` or `{% comment` tags.
   - Asserts cross-tenant IDOR returns HTTP 404 when querying GlobeX records.
