# Contract — Sub-module 11.4: Depreciation & Financial Management (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.4 Depreciation & Financial Management • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-09 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending live `apps/assets/`. Incremental migration: `0006_...`.
- **Package Layout:** `AssetDepreciation/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/asset_depreciation/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AssetDepreciationSchedule` (`apps/assets/models/AssetDepreciation/AssetDepreciationSchedules.py`)
- **Table:** `assets_depreciation_schedule`
- **Number Prefix:** `ADEP` (format: `ADEP-00001`)
- **CHOICES:**
  - `METHOD_CHOICES = [('straight_line', 'Straight-Line (SL)'), ('declining_balance_150', 'Declining Balance (150%)'), ('declining_balance_200', 'Double Declining Balance (200%)'), ('sum_of_years', "Sum-of-the-Years'-Digits (SYD)"), ('units_of_production', 'Units-of-Production (UOP)')]`
  - `PERIOD_FREQUENCY_CHOICES = [('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('annual', 'Annual')]`
  - `STATUS_CHOICES = [('draft', 'Draft Schedule'), ('calculated', 'Calculated / Pending Post'), ('posted', 'Posted to General Ledger'), ('superseded', 'Superseded (Revaluation/Transfer)'), ('cancelled', 'Cancelled')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'calculated': 'badge-amber', 'posted': 'badge-green', 'superseded': 'badge-muted', 'cancelled': 'badge-red'}`
  - `METHOD_CSS = {'straight_line': 'badge-info', 'declining_balance_150': 'badge-amber', 'declining_balance_200': 'badge-purple', 'sum_of_years': 'badge-blue', 'units_of_production': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_depreciation_schedules')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=CASCADE, related_name='depreciation_schedules', help_text='Financial Fixed Asset in accounting subledger')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='depreciation_schedules', help_text='Operational asset register entry')`
  - `fiscal_period`: `ForeignKey('accounting.FiscalPeriod', on_delete=SET_NULL, null=True, blank=True, related_name='asset_depreciation_schedules')`
  - `fiscal_year`: `PositiveIntegerField(default=2026, help_text='Fiscal Year, e.g. 2026')`
  - `period_number`: `PositiveSmallIntegerField(default=1, help_text='Period number within fiscal year (1-12)')`
  - `period_frequency`: `CharField(max_length=20, choices=PERIOD_FREQUENCY_CHOICES, default='monthly')`
  - `schedule_date`: `DateField(default=timezone.now, help_text='Calculation / posting run date')`
  - `depreciation_method`: `CharField(max_length=30, choices=METHOD_CHOICES, default='straight_line')`
  - `starting_book_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Net book value before current period depreciation')`
  - `depreciation_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Depreciation charge calculated for this period')`
  - `accumulated_depreciation_after`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Cumulative depreciation after this period charge')`
  - `ending_book_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Carrying amount after this period charge')`
  - `total_units_expected`: `DecimalField(max_digits=16, decimal_places=2, null=True, blank=True, help_text='For UOP method: total lifetime expected units / hours')`
  - `units_produced_period`: `DecimalField(max_digits=16, decimal_places=2, null=True, blank=True, help_text='For UOP method: units consumed / produced in this period')`
  - `expense_account`: `ForeignKey('accounting.GLAccount', on_delete=SET_NULL, null=True, blank=True, related_name='asset_depreciation_expenses', help_text='Debit: Depreciation Expense GL Account')`
  - `accumulated_account`: `ForeignKey('accounting.GLAccount', on_delete=SET_NULL, null=True, blank=True, related_name='asset_accumulated_depreciations', help_text='Credit: Accumulated Depreciation GL Account')`
  - `cost_center`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='asset_depreciation_expenses', help_text='Cost center charged for depreciation')`
  - `journal_entry`: `ForeignKey('accounting.JournalEntry', on_delete=SET_NULL, null=True, blank=True, related_name='depreciation_schedules', help_text='Posted balanced GL Journal Entry')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `posted_at`: `DateTimeField(null=True, blank=True)`
  - `posted_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='posted_depreciations')`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_adep_ten_num_uniq')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_adep_ten_fa')`
  - `Index(fields=['tenant', 'status'], name='idx_adep_ten_stat')`
  - `Index(fields=['tenant', 'fiscal_year', 'period_number'], name='idx_adep_ten_fpyr')`
  - `Index(fields=['tenant', 'schedule_date'], name='idx_adep_ten_date')`
- **Actions:**
  - `calculate_depreciation()`: computes `depreciation_amount`, `accumulated_depreciation_after`, and `ending_book_value` based on chosen method.
  - `post_to_gl(user)`: generates balanced `accounting.JournalEntry` (Dr Expense / Cr Accum), sets `status='posted'`, updates `fixed_asset.accumulated_depreciation` and `fixed_asset.last_depreciation_date`.
- **Form exclusions:** `tenant`, `number`, `accumulated_depreciation_after`, `ending_book_value`, `journal_entry`, `status`, `posted_at`, `posted_by`, `created_at`, `updated_at`.

---

### 1.2 `AssetRevaluation` (`apps/assets/models/AssetDepreciation/AssetRevaluations.py`)
- **Table:** `assets_revaluation`
- **Number Prefix:** `AREV` (format: `AREV-00001`)
- **CHOICES:**
  - `EVENT_TYPE_CHOICES = [('impairment', 'Impairment Loss (ASC 360 / IAS 36)'), ('revaluation_up', 'Upward Fair Value Revaluation (IFRS 13)'), ('reversal_impairment', 'Reversal of Prior Impairment'), ('salvage_revision', 'Revision of Useful Life / Salvage Value')]`
  - `VALUATION_METHOD_CHOICES = [('market_approach', 'Market Comparable Sales Approach'), ('cost_approach', 'Depreciated Replacement Cost (DRC)'), ('income_approach', 'Discounted Cash Flow (DCF) / Value-in-Use'), ('independent_appraisal', 'Certified Third-Party Appraisal')]`
  - `STATUS_CHOICES = [('draft', 'Draft Assessment'), ('submitted', 'Submitted for Financial Approval'), ('approved', 'Approved / Ledger Updated'), ('rejected', 'Rejected')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'submitted': 'badge-info', 'approved': 'badge-green', 'rejected': 'badge-red'}`
  - `EVENT_TYPE_CSS = {'impairment': 'badge-red', 'revaluation_up': 'badge-green', 'reversal_impairment': 'badge-blue', 'salvage_revision': 'badge-amber'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_revaluations')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=200, help_text='Revaluation event title / reference')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=CASCADE, related_name='revaluation_events', help_text='Financial Fixed Asset being revalued')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='revaluation_events')`
  - `event_type`: `CharField(max_length=30, choices=EVENT_TYPE_CHOICES, default='impairment')`
  - `valuation_method`: `CharField(max_length=30, choices=VALUATION_METHOD_CHOICES, default='independent_appraisal')`
  - `valuation_date`: `DateField(default=timezone.now, help_text='Effective date of appraisal / impairment assessment')`
  - `appraiser`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='asset_revaluations', help_text='Valuation firm, certified appraiser, or internal auditor')`
  - `appraiser_name_fallback`: `CharField(max_length=120, blank=True, help_text='Fallback appraiser name / credentials if not in Party')`
  - `historical_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Asset original historical acquisition cost')`
  - `accumulated_depreciation_before`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Acc. depreciation immediately prior to revaluation')`
  - `carrying_value_before`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Net book value immediately prior to event')`
  - `new_fair_market_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Appraised fair value / recoverable amount')`
  - `revaluation_adjustment`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Net adjustment amount (new_fair_value - carrying_value_before)')`
  - `new_salvage_value`: `DecimalField(max_digits=16, decimal_places=2, null=True, blank=True, help_text='Updated residual value for forward depreciation')`
  - `remaining_useful_life_months`: `PositiveIntegerField(null=True, blank=True, help_text='Revised remaining useful life in months for future runs')`
  - `impairment_loss_account`: `ForeignKey('accounting.GLAccount', on_delete=SET_NULL, null=True, blank=True, related_name='asset_impairment_losses', help_text='P&L Impairment Loss Account')`
  - `revaluation_surplus_account`: `ForeignKey('accounting.GLAccount', on_delete=SET_NULL, null=True, blank=True, related_name='asset_revaluation_surpluses', help_text='Equity: Revaluation Surplus (OCI) Account')`
  - `journal_entry`: `ForeignKey('accounting.JournalEntry', on_delete=SET_NULL, null=True, blank=True, related_name='asset_revaluations')`
  - `reason_and_methodology`: `TextField(blank=True, help_text='Documented reason, market benchmarks, cash flow discount rates, or damage findings')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='approved_revaluations')`
  - `approved_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_arev_ten_num_uniq')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_arev_ten_fa')`
  - `Index(fields=['tenant', 'event_type'], name='idx_arev_ten_type')`
  - `Index(fields=['tenant', 'status'], name='idx_arev_ten_stat')`
  - `Index(fields=['tenant', 'valuation_date'], name='idx_arev_ten_date')`
- **Actions:**
  - `calculate_adjustment()`: `revaluation_adjustment = new_fair_market_value - carrying_value_before`.
  - `execute_revaluation(user)`: on approval, posts balanced journal entry, updates `fixed_asset.acquisition_cost` or carrying amount, and sets status `approved`.
- **Form exclusions:** `tenant`, `number`, `historical_cost`, `carrying_value_before`, `revaluation_adjustment`, `journal_entry`, `status`, `approved_by`, `approved_at`, `created_at`, `updated_at`.

---

### 1.3 `AssetTransfer` (`apps/assets/models/AssetDepreciation/AssetTransfers.py`)
- **Table:** `assets_transfer`
- **Number Prefix:** `AXFR` (format: `AXFR-00001`)
- **CHOICES:**
  - `TRANSFER_TYPE_CHOICES = [('cost_center', 'Cost Center Reallocation'), ('inter_department', 'Inter-Department Transfer'), ('inter_facility', 'Inter-Facility / Plant Relocation'), ('custodian_reassignment', 'Custodian / Employee Handover'), ('inter_company', 'Inter-Company Transfer (Affiliate)')]`
  - `STATUS_CHOICES = [('draft', 'Draft Transfer Order'), ('in_transit', 'In Transit / Dispatched'), ('completed', 'Completed & Accepted'), ('rejected', 'Rejected / Cancelled')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'in_transit': 'badge-amber', 'completed': 'badge-green', 'rejected': 'badge-red'}`
  - `TRANSFER_TYPE_CSS = {'cost_center': 'badge-info', 'inter_department': 'badge-blue', 'inter_facility': 'badge-purple', 'custodian_reassignment': 'badge-amber', 'inter_company': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_transfers')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=200, help_text='Transfer purpose or relocation order reference')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=CASCADE, related_name='transfers', help_text='Financial Fixed Asset being reallocated')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='transfers', help_text='Operational asset register entry')`
  - `transfer_type`: `CharField(max_length=30, choices=TRANSFER_TYPE_CHOICES, default='cost_center')`
  - `transfer_date`: `DateField(default=timezone.now, help_text='Effective transfer date')`
  - Source Allocation:
    - `source_department`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='asset_transfers_from_dept')`
    - `source_location`: `ForeignKey('scm.Location', on_delete=SET_NULL, null=True, blank=True, related_name='asset_transfers_from_loc')`
    - `source_custodian`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='asset_transfers_from_cust')`
    - `source_expense_account`: `ForeignKey('accounting.GLAccount', on_delete=SET_NULL, null=True, blank=True, related_name='asset_transfers_from_gl')`
  - Destination Allocation:
    - `destination_department`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='asset_transfers_to_dept')`
    - `destination_location`: `ForeignKey('scm.Location', on_delete=SET_NULL, null=True, blank=True, related_name='asset_transfers_to_loc')`
    - `destination_custodian`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='asset_transfers_to_cust')`
    - `destination_expense_account`: `ForeignKey('accounting.GLAccount', on_delete=SET_NULL, null=True, blank=True, related_name='asset_transfers_to_gl')`
  - Financial values:
    - `carrying_value_at_transfer`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Net book value at transfer date')`
    - `transportation_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Moving, freight, or decommissioning expenses')`
  - `journal_entry`: `ForeignKey('accounting.JournalEntry', on_delete=SET_NULL, null=True, blank=True, related_name='asset_transfers')`
  - `reason`: `TextField(blank=True, help_text='Operational justification for asset transfer')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `transferred_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='initiated_transfers')`
  - `received_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='received_transfers')`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_axfr_ten_num_uniq')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_axfr_ten_fa')`
  - `Index(fields=['tenant', 'status'], name='idx_axfr_ten_stat')`
  - `Index(fields=['tenant', 'transfer_type'], name='idx_axfr_ten_type')`
  - `Index(fields=['tenant', 'transfer_date'], name='idx_axfr_ten_date')`
- **Actions:**
  - `dispatch_transfer()`: sets status `in_transit`.
  - `complete_transfer(user)`: updates `fixed_asset.location` / `fixed_asset.custodian` / `fixed_asset.expense_account` and `scm.Asset.current_location` / `scm.Asset.assigned_to`, sets `status='completed'`.
- **Form exclusions:** `tenant`, `number`, `carrying_value_at_transfer`, `journal_entry`, `status`, `received_by`, `completed_at`, `created_at`, `updated_at`.

---

### 1.4 `CapitalizationPolicy` (`apps/assets/models/AssetDepreciation/CapitalizationPolicies.py`)
- **Table:** `assets_capitalization_policy`
- **Number Prefix:** `ACTH` (format: `ACTH-00001`)
- **CHOICES:**
  - `POLICY_SCOPE_CHOICES = [('global_default', 'Global Tenant Default'), ('category_override', 'Category-Specific Override'), ('tax_book_safe_harbor', 'Tax Book De Minimis Safe Harbor'), ('project_capex', 'Major Capital Project Threshold')]`
  - `CLASSIFICATION_CHOICES = [('capitalize', 'Capitalize into Fixed Assets Register (CapEx)'), ('expense_immediately', 'Immediate Period Expense (OpEx)'), ('manual_review', 'Flag for Controller Manual Review')]`
  - `STATUS_CSS = {'active': 'badge-green', 'draft': 'badge-slate', 'archived': 'badge-muted'}`
  - `SCOPE_CSS = {'global_default': 'badge-blue', 'category_override': 'badge-purple', 'tax_book_safe_harbor': 'badge-amber', 'project_capex': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_capitalization_policies')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `name`: `CharField(max_length=150, help_text='Policy title, e.g. IRS De Minimis Safe Harbor, Plant Machinery CapEx Rule')`
  - `policy_scope`: `CharField(max_length=30, choices=POLICY_SCOPE_CHOICES, default='global_default')`
  - `category`: `ForeignKey('assets.AssetCategory', on_delete=SET_NULL, null=True, blank=True, related_name='capitalization_policies', help_text='Category targeted if category override')`
  - `minimum_cost_threshold`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('2500.00'), help_text='Minimum cost amount required to capitalize (e.g. $2,500.00 or $5,000.00)')`
  - `minimum_useful_life_months`: `PositiveIntegerField(default=12, help_text='Minimum economic useful life required for capitalization (standard: >= 12 months)')`
  - `default_classification`: `CharField(max_length=24, choices=CLASSIFICATION_CHOICES, default='capitalize')`
  - `de_minimis_safe_harbor`: `BooleanField(default=True, help_text='Whether this complies with IRS Reg. 1.263(a)-1(f) de minimis safe harbor')`
  - `applicable_gaap_standard`: `CharField(max_length=60, default='US GAAP / IFRS IAS 16', help_text='Governing accounting framework reference')`
  - `default_cip_account`: `ForeignKey('accounting.GLAccount', on_delete=SET_NULL, null=True, blank=True, related_name='policy_cip_accounts')`
  - `default_expense_account`: `ForeignKey('accounting.GLAccount', on_delete=SET_NULL, null=True, blank=True, related_name='policy_expense_accounts')`
  - `policy_notes`: `TextField(blank=True, help_text='Detailed accounting policy memo, threshold justification, and audit notes')`
  - `effective_from`: `DateField(default=timezone.now)`
  - `effective_to`: `DateField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_acth_ten_num_uniq')`
  - `Index(fields=['tenant', 'policy_scope'], name='idx_acth_ten_scope')`
  - `Index(fields=['tenant', 'category'], name='idx_acth_ten_cat')`
  - `Index(fields=['tenant', 'is_active'], name='idx_acth_ten_active')`
- **Actions:**
  - `evaluate_asset(cost, useful_life_months)`: returns `(classification, reason_message)`.
- **Form exclusions:** `tenant`, `number`, `created_at`, `updated_at`.

---

## 2. Views, URL Names & Context Keys Contract

### 2.1 `AssetDepreciationSchedule`
- **URL Names:**
  - `assets:depreciation_schedule_list` -> `GET /assets/depreciation/`
  - `assets:depreciation_schedule_create` -> `GET/POST /assets/depreciation/create/`
  - `assets:depreciation_schedule_detail` -> `GET /assets/depreciation/<int:pk>/`
  - `assets:depreciation_schedule_edit` -> `GET/POST /assets/depreciation/<int:pk>/edit/`
  - `assets:depreciation_schedule_delete` -> `POST /assets/depreciation/<int:pk>/delete/`
  - `assets:depreciation_schedule_calculate` -> `POST /assets/depreciation/<int:pk>/calculate/`
  - `assets:depreciation_schedule_post` -> `POST /assets/depreciation/<int:pk>/post/`
- **Context Keys:**
  - List View:
    - `depreciation_schedules` (page queryset)
    - `page_obj`, `is_paginated`, `paginator`
    - `status_choices` (`AssetDepreciationSchedule.STATUS_CHOICES`)
    - `method_choices` (`AssetDepreciationSchedule.METHOD_CHOICES`)
    - `year_choices` (distinct fiscal years)
    - `total_depreciation_period` (sum of period depreciation)
    - `posted_count` (count of posted runs)
    - Filter keys: `q`, `selected_status`, `selected_method`, `selected_year`
  - Detail View:
    - `schedule`, `object`
  - Form View (Create/Edit):
    - `form`, `is_edit`, `schedule` / `object`

### 2.2 `AssetRevaluation`
- **URL Names:**
  - `assets:revaluation_list` -> `GET /assets/revaluations/`
  - `assets:revaluation_create` -> `GET/POST /assets/revaluations/create/`
  - `assets:revaluation_detail` -> `GET /assets/revaluations/<int:pk>/`
  - `assets:revaluation_edit` -> `GET/POST /assets/revaluations/<int:pk>/edit/`
  - `assets:revaluation_delete` -> `POST /assets/revaluations/<int:pk>/delete/`
  - `assets:revaluation_approve` -> `POST /assets/revaluations/<int:pk>/approve/`
- **Context Keys:**
  - List View:
    - `revaluations` (page queryset)
    - `page_obj`, `is_paginated`, `paginator`
    - `event_type_choices` (`AssetRevaluation.EVENT_TYPE_CHOICES`)
    - `status_choices` (`AssetRevaluation.STATUS_CHOICES`)
    - `total_adjustment_value` (net sum of adjustments)
    - Filter keys: `q`, `selected_event_type`, `selected_status`
  - Detail View:
    - `revaluation`, `object`
  - Form View (Create/Edit):
    - `form`, `is_edit`, `revaluation` / `object`

### 2.3 `AssetTransfer`
- **URL Names:**
  - `assets:transfer_list` -> `GET /assets/transfers/`
  - `assets:transfer_create` -> `GET/POST /assets/transfers/create/`
  - `assets:transfer_detail` -> `GET /assets/transfers/<int:pk>/`
  - `assets:transfer_edit` -> `GET/POST /assets/transfers/<int:pk>/edit/`
  - `assets:transfer_delete` -> `POST /assets/transfers/<int:pk>/delete/`
  - `assets:transfer_dispatch` -> `POST /assets/transfers/<int:pk>/dispatch/`
  - `assets:transfer_complete` -> `POST /assets/transfers/<int:pk>/complete/`
- **Context Keys:**
  - List View:
    - `transfers` (page queryset)
    - `page_obj`, `is_paginated`, `paginator`
    - `transfer_type_choices` (`AssetTransfer.TRANSFER_TYPE_CHOICES`)
    - `status_choices` (`AssetTransfer.STATUS_CHOICES`)
    - Filter keys: `q`, `selected_type`, `selected_status`
  - Detail View:
    - `transfer`, `object`
  - Form View (Create/Edit):
    - `form`, `is_edit`, `transfer` / `object`

### 2.4 `CapitalizationPolicy`
- **URL Names:**
  - `assets:capitalization_policy_list` -> `GET /assets/capitalization-policies/`
  - `assets:capitalization_policy_create` -> `GET/POST /assets/capitalization-policies/create/`
  - `assets:capitalization_policy_detail` -> `GET /assets/capitalization-policies/<int:pk>/`
  - `assets:capitalization_policy_edit` -> `GET/POST /assets/capitalization-policies/<int:pk>/edit/`
  - `assets:capitalization_policy_delete` -> `POST /assets/capitalization-policies/<int:pk>/delete/`
- **Context Keys:**
  - List View:
    - `policies` (page queryset)
    - `page_obj`, `is_paginated`, `paginator`
    - `scope_choices` (`CapitalizationPolicy.POLICY_SCOPE_CHOICES`)
    - `categories` (`AssetCategory.objects.filter(tenant=request.tenant)`)
    - Filter keys: `q`, `selected_scope`, `selected_category`
  - Detail View:
    - `policy`, `object`
  - Form View (Create/Edit):
    - `form`, `is_edit`, `policy` / `object`

---

## 3. Navigation `LIVE_LINKS["11.4"]` Wire-up Contract

Exact NavERP.md feature bullet text mapping:
```python
"11.4": {
    "Depreciation Schedule & Methods": "assets:depreciation_schedule_list",
    "Asset Valuation & Revaluation": "assets:revaluation_list",
    "Asset Transfer & Cost Allocation": "assets:transfer_list",
    "Capital vs. Expense Determination": "assets:capitalization_policy_list",
    "Fixed Asset Reporting & Compliance": "assets:depreciation_schedule_list",
    # Plural and convenience aliases
    "Depreciation Schedules": "assets:depreciation_schedule_list",
    "Asset Revaluations": "assets:revaluation_list",
    "Asset Transfers": "assets:transfer_list",
    "Capitalization Policies": "assets:capitalization_policy_list",
    "Cost Allocations": "assets:transfer_list",
    "Asset Financial Management Hub": "assets:overview",
},
```
