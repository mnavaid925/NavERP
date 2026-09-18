# Build Contract — Projects 7.15 Financial & Billing Management (`projects`)

> Frozen 2026-09-18 against the live tree at commit `f3791de3`.
> This contract is the single source of truth for the entity-by-entity build.
> Every variable name, field name, URL name, context key, and badge class is pinned here.

---

## 0. Scope & Capability Coverage

Five NavERP.md 7.15 capability bullets mapped to 4 primary entities + 4 computed financial boards:

| Bullet | What 7.15 Owns | Artifacts |
|---|---|---|
| **Project Accounting & Cost Centers** | ASC 606 / IFRS 15 revenue recognition schedules, cost center mapping, deferred vs unbilled tracking | `ProjectRevenueSchedule` [`PRS-`] (`RevenueSchedules.py`), `financial_pnl` |
| **Invoice Generation & Delivery** | Batch billing runs from timesheets/expenses, tax calculation, draft `accounting.Invoice` generation, email dispatch | `ProjectBillingRun` [`PBR-`] (`BillingRuns.py`) |
| **Payment Tracking & Reconciliation** | A/R collections workflow, dunning stages, promise-to-pay commitments, dispute logging, cash flow forecasting | `ProjectPaymentRecord` [`PPR-`] (`PaymentRecords.py`), `ar_aging`, `cash_flow_forecast` |
| **Budget vs. Actual Analysis** | Real-time cost & revenue variance, EVM metrics integration (`CPI`, `SPI`, `EAC` from 7.4 `CostControlAccount`) | `financial_variance` |
| **Multi-Currency & Tax Handling** | Role & project billing rate cards, expense markups, exchange rate snapshots, tax jurisdiction rules | `ProjectRateCard` [`RTC-`] (`RateCards.py`) |

### Non-Goals & Invariants
- **Accounting owns the financial ledger (L29/L36)**: `ProjectBillingRun` drafts canonical `accounting.Invoice` rows; payments reconcile through `accounting.PaymentAllocation`. 7.15 never declares a second GL/AR table.
- **7.4 Cost Management integration**: 7.15 consumes 7.4's `CostControlAccount` for EVM metrics and `ProjectExpense` for direct cost markup.
- **7.11 Time Tracking integration**: 7.15 consumes unbilled `ResourceTimeEntry` records as the source for billable hours.
- **Audit action strings <= 10 characters**: `create`, `update`, `delete`, `approve`, `generate`, `dispatch`, `recognize`, `lock`, `contact`, `promise`, `escalate`, `resolve`.
- **Badges strictly colour-named (L33)**: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.

---

## 1. Verified Ground Truth

- `Project` [`PRJ-`] (`apps/projects/models/ProjectInitiation/Projects.py`), url name `projects:prj_detail`.
- `ProjectMilestone` [`MST-`] (`apps/projects/models/ProjectPlanningScheduling/ProjectMilestones.py`), url name `projects:mst_detail`.
- `StatementOfWork` [`SOW-`] (`apps/projects/models/ClientExternalCollaboration/StatementOfWorks.py`), url name `projects:sow_detail`.
- `ResourceTimeEntry` [`RTE-`] (`apps/projects/models/ResourceManagement/ResourceTimeEntries.py`).
- `CostControlAccount` [`CCA-`] (`apps/projects/models/CostManagement/CostControlAccounts.py`).
- `ProjectExpense` [`PEX-`] (`apps/projects/models/CostManagement/ProjectExpenses.py`).
- `accounting.Currency` (Global, no tenant FK), `accounting.Invoice` (`apps/accounting/models/AccountsReceivable/Invoices.py`).
- `accounting.TaxCode` (`apps/accounting/models/Tax/TaxCodes.py`), `accounting.FiscalPeriod` (`apps/accounting/models/GeneralLedger/FiscalPeriods.py`).
- `accounting.GLAccount` (`apps/accounting/models/GeneralLedger/GLAccounts.py`), `accounting.JournalEntry` (`apps/accounting/models/GeneralLedger/JournalEntries.py`).
- `core.OrgUnit` (`apps/core/models/OrgUnit.py`), `core.Party` (`apps/core/models/Party.py`).
- `TenantNumbered`, `TenantOwned`, `q2`, `ZERO` (`apps/projects/models/_base.py`).
- `TenantModelForm`, `_reject_foreign` (`apps/projects/forms/_common.py`).
- `crud_list`, `crud_detail`, `crud_create`, `crud_edit`, `crud_delete` (`apps/core/crud.py`).
- `write_audit_log` (`apps/core/utils.py`).

---

## 2. Model & Form Specifications

### 2.1 Entity 1: `ProjectRateCard` [`RTC-`] (`apps/projects/models/FinancialBillingManagement/RateCards.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "RTC"`
- Fields:
  - `name`: `CharField(max_length=120)`
  - `project`: `ForeignKey("projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="rate_cards")`
  - `client`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="project_rate_cards")`
  - `role_name`: `CharField(max_length=100)`
  - `activity_code`: `CharField(max_length=40, blank=True)`
  - `hourly_rate`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `expense_markup_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=models.PROTECT, related_name="+")`
  - `effective_from`: `DateField(null=True, blank=True)`
  - `effective_to`: `DateField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `notes`: `TextField(blank=True)`
- Form (`forms/FinancialBillingManagement/RateCards.py`):
  - `ProjectRateCardForm(TenantModelForm)`:
    - `Meta.model = ProjectRateCard`
    - `Meta.fields = ["name", "project", "client", "role_name", "activity_code", "hourly_rate", "expense_markup_pct", "currency", "effective_from", "effective_to", "is_active", "notes"]`
    - `_reject_foreign` checks `project`, `client`.

### 2.2 Entity 2: `ProjectBillingRun` [`PBR-`] (`apps/projects/models/FinancialBillingManagement/BillingRuns.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "PBR"`
- Choices:
  - `BILLING_TYPE_CHOICES = [("time_and_materials", "Time & Materials"), ("fixed_fee", "Fixed Fee"), ("milestone", "Milestone-Based"), ("progress_percent", "Progress Percentage"), ("retainer", "Retainer")]`
  - `STATUS_CHOICES = [("draft", "Draft"), ("approved", "Approved"), ("invoiced", "Invoiced"), ("cancelled", "Cancelled")]`
  - `DELIVERY_CHANNEL_CHOICES = [("email", "Email Dispatch"), ("portal", "Client Portal"), ("download", "Manual Download")]`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="billing_runs")`
  - `client`: `ForeignKey("core.Party", on_delete=models.PROTECT, related_name="project_billing_runs")`
  - `sow`: `ForeignKey("projects.StatementOfWork", on_delete=models.SET_NULL, null=True, blank=True, related_name="billing_runs")`
  - `milestone`: `ForeignKey("projects.ProjectMilestone", on_delete=models.SET_NULL, null=True, blank=True, related_name="billing_runs")`
  - `billing_type`: `CharField(max_length=24, choices=BILLING_TYPE_CHOICES, default="time_and_materials")`
  - `run_date`: `DateField(default=timezone.localdate)`
  - `cutoff_date`: `DateField()`
  - `total_time_hours`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))`
  - `labor_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `expense_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `fee_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `subtotal`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `tax_code`: `ForeignKey("accounting.TaxCode", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `tax_rate_pct`: `DecimalField(max_digits=6, decimal_places=3, default=Decimal("0.000"))`
  - `tax_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `total_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=models.PROTECT, related_name="+")`
  - `exchange_rate`: `DecimalField(max_digits=18, decimal_places=8, default=Decimal("1.00000000"))`
  - `status`: `CharField(max_length=15, choices=STATUS_CHOICES, default="draft")`
  - `accounting_invoice`: `ForeignKey("accounting.Invoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="project_billing_runs")`
  - `delivery_channel`: `CharField(max_length=12, choices=DELIVERY_CHANNEL_CHOICES, default="email")`
  - `recipient_email`: `CharField(max_length=255, blank=True)`
  - `dispatched_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `dispatched_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="+")`
  - `notes`: `TextField(blank=True)`
- Forms (`forms/FinancialBillingManagement/BillingRuns.py`):
  - `ProjectBillingRunForm(TenantModelForm)`:
    - `Meta.model = ProjectBillingRun`
    - `Meta.fields = ["project", "client", "sow", "milestone", "billing_type", "run_date", "cutoff_date", "labor_amount", "expense_amount", "fee_amount", "tax_code", "currency", "exchange_rate", "delivery_channel", "recipient_email", "notes"]`
  - `BillingRunDispatchForm(forms.Form)`:
    - `recipient_email = forms.EmailField(required=True)`
    - `notes = forms.CharField(widget=forms.Textarea, required=False)`

### 2.3 Entity 3: `ProjectRevenueSchedule` [`PRS-`] (`apps/projects/models/FinancialBillingManagement/RevenueSchedules.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "PRS"`
- Choices:
  - `METHOD_CHOICES = [("percent_complete", "Percentage of Completion"), ("milestone", "Milestone-Based"), ("as_billed", "As Billed / Invoiced"), ("straight_line", "Straight-Line Amortization"), ("manual", "Manual Entry")]`
  - `STATUS_CHOICES = [("draft", "Draft"), ("approved", "Approved"), ("recognized", "Recognized"), ("locked", "Locked"), ("void", "Void")]`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="revenue_schedules")`
  - `milestone`: `ForeignKey("projects.ProjectMilestone", on_delete=models.SET_NULL, null=True, blank=True, related_name="revenue_schedules")`
  - `recognition_date`: `DateField(default=timezone.localdate)`
  - `fiscal_period`: `ForeignKey("accounting.FiscalPeriod", on_delete=models.SET_NULL, null=True, blank=True, related_name="project_revenue_schedules")`
  - `method`: `CharField(max_length=24, choices=METHOD_CHOICES, default="percent_complete")`
  - `contract_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `completion_percent`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))])`
  - `recognized_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `deferred_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `unbilled_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])`
  - `cost_center`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="project_revenue_schedules")`
  - `gl_account`: `ForeignKey("accounting.GLAccount", on_delete=models.PROTECT, null=True, blank=True, related_name="project_revenue_schedules")`
  - `journal_entry`: `ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="project_revenue_schedules")`
  - `status`: `CharField(max_length=12, choices=STATUS_CHOICES, default="draft")`
  - `recognized_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="+")`
  - `recognized_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `notes`: `TextField(blank=True)`
- Forms (`forms/FinancialBillingManagement/RevenueSchedules.py`):
  - `ProjectRevenueScheduleForm(TenantModelForm)`:
    - `Meta.model = ProjectRevenueSchedule`
    - `Meta.fields = ["project", "milestone", "recognition_date", "fiscal_period", "method", "contract_amount", "completion_percent", "recognized_amount", "deferred_amount", "unbilled_amount", "cost_center", "gl_account", "notes"]`
  - `RevenueScheduleRecognizeForm(forms.Form)`:
    - `recognition_date = forms.DateField(initial=timezone.localdate)`
    - `notes = forms.CharField(widget=forms.Textarea, required=False)`

### 2.4 Entity 4: `ProjectPaymentRecord` [`PPR-`] (`apps/projects/models/FinancialBillingManagement/PaymentRecords.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "PPR"`
- Choices:
  - `STAGE_CHOICES = [("current", "Current"), ("reminder_sent", "Reminder Sent"), ("overdue", "Overdue"), ("promise_to_pay", "Promise to Pay"), ("in_dispute", "In Dispute"), ("settled", "Settled"), ("written_off", "Written Off")]`
  - `DUNNING_LEVEL_CHOICES = [("friendly_reminder", "Friendly Reminder"), ("first_notice", "First Formal Notice"), ("second_notice", "Second Formal Notice"), ("final_demand", "Final Demand"), ("legal", "Legal Action")]`
  - `STATUS_CHOICES = [("open", "Open"), ("escalated", "Escalated"), ("resolved", "Resolved"), ("closed", "Closed")]`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="payment_records")`
  - `client`: `ForeignKey("core.Party", on_delete=models.PROTECT, related_name="project_payment_records")`
  - `billing_run`: `ForeignKey("projects.ProjectBillingRun", on_delete=models.SET_NULL, null=True, blank=True, related_name="payment_records")`
  - `accounting_invoice`: `ForeignKey("accounting.Invoice", on_delete=models.CASCADE, related_name="project_collections")`
  - `stage`: `CharField(max_length=20, choices=STAGE_CHOICES, default="current")`
  - `dunning_level`: `CharField(max_length=20, choices=DUNNING_LEVEL_CHOICES, default="friendly_reminder")`
  - `last_contact_date`: `DateField(null=True, blank=True)`
  - `next_follow_up_date`: `DateField(null=True, blank=True)`
  - `promised_payment_date`: `DateField(null=True, blank=True)`
  - `promised_amount`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.00"))])`
  - `dispute_reason`: `TextField(blank=True)`
  - `assigned_collector`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_project_collections")`
  - `status`: `CharField(max_length=12, choices=STATUS_CHOICES, default="open")`
  - `notes`: `TextField(blank=True)`
- Forms (`forms/FinancialBillingManagement/PaymentRecords.py`):
  - `ProjectPaymentRecordForm(TenantModelForm)`:
    - `Meta.model = ProjectPaymentRecord`
    - `Meta.fields = ["project", "client", "billing_run", "accounting_invoice", "dunning_level", "next_follow_up_date", "promised_payment_date", "promised_amount", "dispute_reason", "assigned_collector", "notes"]`
  - `PaymentPromiseForm(forms.Form)`:
    - `promised_payment_date = forms.DateField(required=True)`
    - `promised_amount = forms.DecimalField(max_digits=14, decimal_places=2, required=True)`
    - `notes = forms.CharField(widget=forms.Textarea, required=False)`
  - `ContactLogForm(forms.Form)`:
    - `contact_date = forms.DateField(initial=timezone.localdate)`
    - `notes = forms.CharField(widget=forms.Textarea, required=True)`
    - `next_follow_up_date = forms.DateField(required=False)`

---

## 3. URLs and View Context Variables Contract

| URL Name | Pattern | View Context Keys |
|---|---|---|
| `projects:rtc_list` | `financial/rate-cards/` | `rate_cards`, `projects`, `project_filter`, `is_active_filter` |
| `projects:rtc_create` | `financial/rate-cards/create/` | `form`, `is_edit=False` |
| `projects:rtc_detail` | `financial/rate-cards/<int:pk>/` | `rate_card` |
| `projects:rtc_edit` | `financial/rate-cards/<int:pk>/edit/` | `form`, `is_edit=True`, `rate_card` |
| `projects:rtc_delete` | `financial/rate-cards/<int:pk>/delete/` | POST only |
| `projects:pbr_list` | `financial/billing-runs/` | `billing_runs`, `projects`, `project_filter`, `status_choices`, `status_filter` |
| `projects:pbr_create` | `financial/billing-runs/create/` | `form`, `is_edit=False` |
| `projects:pbr_detail` | `financial/billing-runs/<int:pk>/` | `billing_run`, `dispatch_form` |
| `projects:pbr_edit` | `financial/billing-runs/<int:pk>/edit/` | `form`, `is_edit=True`, `billing_run` |
| `projects:pbr_delete` | `financial/billing-runs/<int:pk>/delete/` | POST only |
| `projects:pbr_approve` | `financial/billing-runs/<int:pk>/approve/` | POST only |
| `projects:pbr_generate_invoice` | `financial/billing-runs/<int:pk>/generate-invoice/` | POST only |
| `projects:pbr_dispatch` | `financial/billing-runs/<int:pk>/dispatch/` | POST only |
| `projects:pbr_preview_pdf` | `financial/billing-runs/<int:pk>/preview-pdf/` | `billing_run` |
| `projects:prs_list` | `financial/revenue-schedules/` | `revenue_schedules`, `projects`, `project_filter`, `status_choices`, `status_filter`, `method_choices`, `method_filter` |
| `projects:prs_create` | `financial/revenue-schedules/create/` | `form`, `is_edit=False` |
| `projects:prs_detail` | `financial/revenue-schedules/<int:pk>/` | `schedule` |
| `projects:prs_edit` | `financial/revenue-schedules/<int:pk>/edit/` | `form`, `is_edit=True`, `schedule` |
| `projects:prs_delete` | `financial/revenue-schedules/<int:pk>/delete/` | POST only |
| `projects:prs_approve` | `financial/revenue-schedules/<int:pk>/approve/` | POST only |
| `projects:prs_recognize` | `financial/revenue-schedules/<int:pk>/recognize/` | POST only |
| `projects:prs_lock` | `financial/revenue-schedules/<int:pk>/lock/` | POST only |
| `projects:ppr_list` | `financial/payment-records/` | `payment_records`, `projects`, `project_filter`, `stage_choices`, `stage_filter`, `dunning_choices`, `dunning_filter` |
| `projects:ppr_create` | `financial/payment-records/create/` | `form`, `is_edit=False` |
| `projects:ppr_detail` | `financial/payment-records/<int:pk>/` | `payment_record`, `promise_form`, `contact_form` |
| `projects:ppr_edit` | `financial/payment-records/<int:pk>/edit/` | `form`, `is_edit=True`, `payment_record` |
| `projects:ppr_delete` | `financial/payment-records/<int:pk>/delete/` | POST only |
| `projects:ppr_log_contact` | `financial/payment-records/<int:pk>/log-contact/` | POST only |
| `projects:ppr_record_promise` | `financial/payment-records/<int:pk>/record-promise/` | POST only |
| `projects:ppr_escalate` | `financial/payment-records/<int:pk>/escalate/` | POST only |
| `projects:ppr_resolve` | `financial/payment-records/<int:pk>/resolve/` | POST only |
| `projects:financial_pnl` | `financial/pnl/` | `pnl_rows`, `totals`, `projects`, `project_filter` |
| `projects:financial_variance` | `financial/variance/` | `variance_rows`, `totals`, `projects`, `project_filter` |
| `projects:ar_aging` | `financial/ar-aging/` | `aging_buckets`, `bucket_totals`, `projects`, `project_filter` |
| `projects:cash_flow_forecast` | `financial/cash-flow/` | `inflows`, `outflows`, `net_cash_periods`, `projects`, `project_filter` |

---

## 4. Navigation Wire-up Contract (`apps/core/navigation.py`)

```python
    # ----- 7.15 Financial & Billing Management -----
    "7.15": {
        "Project Accounting & Cost Centers": "projects:prs_list",
        "Invoice Generation & Delivery":     "projects:pbr_list",
        "Payment Tracking & Reconciliation": "projects:ppr_list",
        "Budget vs. Actual Analysis":        "projects:financial_variance",
        "Multi-Currency & Tax Handling":     "projects:rtc_list",
        # Extra live leaves:
        "Rate Card Register":                "projects:rtc_list",
        "Billing Runs":                      "projects:pbr_list",
        "Revenue Schedules":                 "projects:prs_list",
        "Collections & Payment Records":     "projects:ppr_list",
        "Project P&L":                       "projects:financial_pnl",
        "A/R Aging Dashboard":               "projects:ar_aging",
        "Cash Flow Forecast":                "projects:cash_flow_forecast",
    },
```
