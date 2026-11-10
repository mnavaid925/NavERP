# Contract — Sub-module 11.10: Lease & Rental Management (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.10 Lease & Rental Management • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-10 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending live `apps/assets/`. Incremental migration: `0013_...`.
- **Package Layout:** `AssetLeaseRental/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/assetleaserental/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AssetLeaseContract` (`apps/assets/models/AssetLeaseRental/AssetLeaseContracts.py`)
- **Table:** `assets_assetleasecontract`
- **Number Prefix:** `ALC` (format: `ALC-YYYYMM-XXXX`)
- **CHOICES:**
  - `CLASSIFICATION_CHOICES = [('operating', 'Operating Lease'), ('finance', 'Finance / Capital Lease')]`
  - `PAYMENT_FREQUENCY_CHOICES = [('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('semi_annual', 'Semi-Annual'), ('annual', 'Annual')]`
  - `PAYMENT_TIMING_CHOICES = [('advance', 'Payment in Advance (Beginning of Period)'), ('arrears', 'Payment in Arrears (End of Period)')]`
  - `STATUS_CHOICES = [('draft', 'Draft (Pending Inception)'), ('pending_approval', 'Pending Authorization'), ('active', 'Active (Capitalized)'), ('modified', 'Modified / Remeasured'), ('expired', 'Expired (Completed)'), ('terminated', 'Early Terminated'), ('buyout', 'Asset Purchased / Buyout')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'pending_approval': 'badge-amber', 'active': 'badge-green', 'modified': 'badge-info', 'expired': 'badge-muted', 'terminated': 'badge-red', 'buyout': 'badge-purple'}`
  - `CLASSIFICATION_CSS = {'operating': 'badge-info', 'finance': 'badge-purple'}`
  - `PAYMENT_FREQUENCY_CSS = {'monthly': 'badge-info', 'quarterly': 'badge-slate', 'semi_annual': 'badge-slate', 'annual': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_lease_contracts')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='Lease agreement title or descriptive identification')`
  - `master_lease_agreement_ref`: `CharField(max_length=100, blank=True, help_text='Master Lease Agreement (MLA) or master facility reference')`
  - `lessor`: `ForeignKey('core.Party', on_delete=PROTECT, related_name='leased_asset_contracts', help_text='Lessor, financial institution, or equipment rental vendor')`
  - `asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='lease_contracts', help_text='Operational plant machinery or equipment leased')`
  - `category`: `ForeignKey('assets.AssetCategory', on_delete=SET_NULL, null=True, blank=True, related_name='lease_contracts', help_text='Asset category classification')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='lease_contracts', help_text='Capitalized Right-of-Use (ROU) Fixed Asset record')`
  - `inception_date`: `DateField(default=timezone.now, help_text='Agreement execution / contract signature date')`
  - `commencement_date`: `DateField(default=timezone.now, help_text='Date asset is placed in service and lease term starts')`
  - `expiration_date`: `DateField(help_text='Stipulated base lease term expiration date')`
  - `first_payment_date`: `DateField(default=timezone.now, help_text='Date of initial lease payment installment')`
  - `early_termination_notice_date`: `DateField(null=True, blank=True, help_text='Cutoff deadline for exercising early termination or return')`
  - `lease_term_months`: `PositiveIntegerField(default=36, help_text='Base non-cancellable lease duration in months')`
  - `economic_life_months`: `PositiveIntegerField(default=60, help_text='Estimated economic useful life of the leased asset')`
  - `payment_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Periodic base rental installment payment amount')`
  - `payment_frequency`: `CharField(max_length=20, choices=PAYMENT_FREQUENCY_CHOICES, default='monthly')`
  - `payment_timing`: `CharField(max_length=20, choices=PAYMENT_TIMING_CHOICES, default='arrears')`
  - `discount_rate_pct`: `DecimalField(max_digits=6, decimal_places=4, default=Decimal('5.0000'), help_text='Annual Incremental Borrowing Rate (IBR) or rate implicit in lease')`
  - `fair_market_value`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Estimated fair market value of leased asset at commencement')`
  - `initial_direct_costs`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Ancillary origination fees, commissions, or legal setup costs capitalized into ROU asset')`
  - `lease_incentives`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Incentive rebates received from lessor offsetting ROU asset value')`
  - `residual_value_guarantee`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Lessee guaranteed residual amount payable at lease expiration')`
  - `purchase_option_price`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, help_text='Fixed bargain purchase option price if applicable')`
  - `transfer_of_ownership`: `BooleanField(default=False, help_text='Criterion 1: Ownership transfers to lessee by end of term')`
  - `has_purchase_option`: `BooleanField(default=False, help_text='Criterion 2: Option to purchase reasonably certain to be exercised')`
  - `is_specialized_asset`: `BooleanField(default=False, help_text='Criterion 5: Asset has no alternative use to lessor at end of term')`
  - `classification`: `CharField(max_length=20, choices=CLASSIFICATION_CHOICES, default='operating')`
  - `classification_overridden`: `BooleanField(default=False, help_text='Flag indicating manual override of automated statutory classification')`
  - `classification_notes`: `TextField(blank=True, help_text='Technical accounting justification for lease classification')`
  - `initial_lease_liability`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Calculated Present Value of lease payments at commencement')`
  - `initial_rou_asset_value`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Capitalized initial Right-of-Use asset carrying value')`
  - `current_lease_liability`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Current remaining lease liability principal')`
  - `current_rou_asset_carrying_value`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Current net book value of ROU asset after amortization')`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default='draft')`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='approved_asset_leases', help_text='Authorizing corporate controller or finance executive')`
  - `notes`: `TextField(blank=True, help_text='Administrative remarks, terms, or operational stipulations')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_alc_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_alc_ten_stat')`
  - `Index(fields=['tenant', 'classification'], name='idx_alc_ten_class')`
  - `Index(fields=['tenant', 'lessor'], name='idx_alc_ten_lessor')`
  - `Index(fields=['tenant', 'commencement_date'], name='idx_alc_ten_cdate')`
  - `Index(fields=['tenant', 'expiration_date'], name='idx_alc_ten_edate')`
- **Actions / State Machine:**
  - `asset_lease_contract_activate`: calculates present values, sets initial liability & ROU asset, generates payment schedule, transitions `draft/pending_approval -> active`.
  - `asset_lease_contract_calculate`: evaluates 5-criteria statutory test, computes PV and sets initial balances without changing status.
  - `asset_lease_contract_terminate`: records buyout or early return, transitions to `terminated` or `buyout`.
- **Form exclusions:** `tenant`, `number`, `initial_lease_liability`, `initial_rou_asset_value`, `current_lease_liability`, `current_rou_asset_carrying_value`, `approved_by`, `created_at`, `updated_at`.

---

### 1.2 `AssetLeaseSchedule` (`apps/assets/models/AssetLeaseRental/AssetLeaseSchedules.py`)
- **Table:** `assets_assetleaseschedule`
- **Number Prefix:** `ALSP` (format: `ALSP-YYYYMM-XXXX`)
- **CHOICES:**
  - `STATUS_CHOICES = [('scheduled', 'Scheduled (Pending Due Date)'), ('accrued', 'Accrued (Interest/Amortization Booked)'), ('paid', 'Paid & Settled'), ('cancelled', 'Cancelled / Derecognized')]`
  - `STATUS_CSS = {'scheduled': 'badge-slate', 'accrued': 'badge-info', 'paid': 'badge-green', 'cancelled': 'badge-muted'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_lease_schedules')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `lease_contract`: `ForeignKey('assets.AssetLeaseContract', on_delete=CASCADE, related_name='payment_schedules', help_text='Parent lease agreement')`
  - `period_number`: `PositiveIntegerField(help_text='Sequential period index (1 to N)')`
  - `due_date`: `DateField(help_text='Payment due date for this installment')`
  - `payment_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Gross installment cash payment due')`
  - `beginning_liability`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Liability balance at start of period')`
  - `interest_expense`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Accreted interest expense component')`
  - `principal_reduction`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Reduction in lease liability principal')`
  - `ending_liability`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Remaining liability balance at period end')`
  - `rou_depreciation`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Straight-line or asset-specific ROU depreciation')`
  - `ending_rou_asset_value`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Carrying value of ROU asset at period end')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')`
  - `payment_reference`: `CharField(max_length=100, blank=True, help_text='Disbursement voucher, check, or wire transaction reference')`
  - `paid_date`: `DateField(null=True, blank=True, help_text='Actual date payment was settled')`
  - `notes`: `TextField(blank=True, help_text='Accrual or settlement remarks')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_alsp_ten_num_uniq')`
  - `Index(fields=['tenant', 'lease_contract', 'period_number'], name='idx_alsp_ten_ctr_prd')`
  - `Index(fields=['tenant', 'status'], name='idx_alsp_ten_stat')`
  - `Index(fields=['tenant', 'due_date'], name='idx_alsp_ten_due')`
- **Actions / State Machine:**
  - `asset_lease_schedule_mark_paid`: records `payment_reference` and `paid_date`, updates `status = 'paid'`, syncs contract's `current_lease_liability = ending_liability` and `current_rou_asset_carrying_value = ending_rou_asset_value`.
  - `asset_lease_schedule_accrue`: transitions `status = 'accrued'`.
- **Form exclusions:** `tenant`, `number`, `created_at`, `updated_at`.

---

### 1.3 `AssetLeaseModification` (`apps/assets/models/AssetLeaseRental/AssetLeaseModifications.py`)
- **Table:** `assets_assetleasemodification`
- **Number Prefix:** `ALMD` (format: `ALMD-YYYYMM-XXXX`)
- **CHOICES:**
  - `MODIFICATION_TYPE_CHOICES = [('term_extension', 'Lease Term Extension'), ('payment_change', 'Payment Amount Adjustment'), ('partial_termination', 'Partial Scope / Asset Reduction'), ('full_termination', 'Full Early Termination'), ('impairment', 'ROU Asset Impairment Write-down'), ('discount_rate_change', 'Discount Rate / IBR Remeasurement')]`
  - `STATUS_CHOICES = [('draft', 'Draft Amendment'), ('submitted', 'Submitted for Review'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('executed', 'Executed & Remeasured')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'submitted': 'badge-amber', 'approved': 'badge-info', 'rejected': 'badge-red', 'executed': 'badge-green'}`
  - `MODIFICATION_TYPE_CSS = {'term_extension': 'badge-info', 'payment_change': 'badge-slate', 'partial_termination': 'badge-amber', 'full_termination': 'badge-red', 'impairment': 'badge-red', 'discount_rate_change': 'badge-purple'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_lease_modifications')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `lease_contract`: `ForeignKey('assets.AssetLeaseContract', on_delete=CASCADE, related_name='modifications', help_text='Lease agreement modified')`
  - `modification_type`: `CharField(max_length=30, choices=MODIFICATION_TYPE_CHOICES, default='term_extension')`
  - `request_date`: `DateField(default=timezone.now, help_text='Date modification was requested')`
  - `effective_date`: `DateField(default=timezone.now, help_text='Effective accounting date of modification')`
  - `prior_lease_liability`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Carrying lease liability before remeasurement')`
  - `revised_lease_liability`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Remeasured present value of remaining lease payments')`
  - `liability_adjustment`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Net change in lease liability (+/-)')`
  - `prior_rou_asset_value`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Carrying ROU asset value before remeasurement')`
  - `revised_rou_asset_value`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Remeasured ROU asset carrying value')`
  - `rou_asset_adjustment`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Net adjustment to ROU asset basis (+/-)')`
  - `gain_loss_on_modification`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Gain (+) or loss (-) recognized on partial/full termination')`
  - `impairment_loss_recognized`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Impairment loss recognized against ROU asset')`
  - `revised_term_months`: `PositiveIntegerField(null=True, blank=True, help_text='New total lease duration if term is amended')`
  - `revised_payment_amount`: `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, help_text='New periodic payment amount if rent is amended')`
  - `revised_discount_rate_pct`: `DecimalField(max_digits=6, decimal_places=4, null=True, blank=True, help_text='Updated IBR discount rate at modification date')`
  - `requested_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='requested_lease_modifications', help_text='Contract administrator requesting amendment')`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='approved_lease_modifications', help_text='Corporate controller approving remeasurement')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `justification`: `TextField(blank=True, help_text='Commercial and operational justification for lease modification')`
  - `notes`: `TextField(blank=True, help_text='Audit remarks and accounting documentation notes')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_almd_ten_num_uniq')`
  - `Index(fields=['tenant', 'lease_contract'], name='idx_almd_ten_ctr')`
  - `Index(fields=['tenant', 'status'], name='idx_almd_ten_stat')`
  - `Index(fields=['tenant', 'effective_date'], name='idx_almd_ten_eff')`
  - `Index(fields=['tenant', 'modification_type'], name='idx_almd_ten_type')`
- **Actions / State Machine:**
  - `asset_lease_modification_approve`: calculates adjustments (`liability_adjustment = revised_lease_liability - prior_lease_liability`, updates `lease_contract.current_lease_liability = revised_lease_liability`, `lease_contract.current_rou_asset_carrying_value = revised_rou_asset_value`, updates contract status to `modified` or `terminated`), sets status to `executed`.
- **Form exclusions:** `tenant`, `number`, `liability_adjustment`, `rou_asset_adjustment`, `approved_by`, `created_at`, `updated_at`.

---

### 1.4 `AssetLeaseBuyAnalysis` (`apps/assets/models/AssetLeaseRental/AssetLeaseBuyAnalyses.py`)
- **Table:** `assets_assetleasebuyanalysis`
- **Number Prefix:** `ALBA` (format: `ALBA-YYYYMM-XXXX`)
- **CHOICES:**
  - `RECOMMENDATION_CHOICES = [('buy', 'Acquire via Outright Purchase / Loan'), ('lease', 'Acquire via Lease Financing'), ('neutral', 'Financial Parity / Neutral Indifference')]`
  - `STATUS_CHOICES = [('draft', 'Draft Scenario'), ('evaluated', 'Evaluated (Metrics Computed)'), ('approved', 'Approved Recommendation'), ('rejected', 'Rejected')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'evaluated': 'badge-info', 'approved': 'badge-green', 'rejected': 'badge-red'}`
  - `RECOMMENDATION_CSS = {'buy': 'badge-green', 'lease': 'badge-purple', 'neutral': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_lease_buy_analyses')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='Capital acquisition analysis title or project name')`
  - `description`: `TextField(blank=True, help_text='Project description and asset requirement background')`
  - `target_asset_name`: `CharField(max_length=255, help_text='Name, make, model or description of target asset')`
  - `category`: `ForeignKey('assets.AssetCategory', on_delete=SET_NULL, null=True, blank=True, related_name='lease_buy_analyses', help_text='Asset category classification')`
  - `expected_useful_life_years`: `DecimalField(max_digits=4, decimal_places=1, default=Decimal('5.0'), help_text='Expected operational life of target equipment in years')`
  - `purchase_price`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Outright purchase price / capitalized equipment quote')`
  - `down_payment_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'), help_text='Down payment required for debt purchase financing (%)')`
  - `loan_interest_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('6.00'), help_text='Annual loan financing interest rate (%)')`
  - `loan_term_years`: `DecimalField(max_digits=4, decimal_places=1, default=Decimal('5.0'), help_text='Commercial loan term in years')`
  - `estimated_salvage_value`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Estimated residual salvage proceeds at end of life')`
  - `annual_maintenance_cost_buy`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Annual owner-incurred preventive maintenance expense')`
  - `annual_insurance_tax_buy`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Annual property tax and insurance premium incurred under ownership')`
  - `lease_term_months`: `PositiveIntegerField(default=36, help_text='Proposed lease agreement duration in months')`
  - `monthly_lease_payment`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Monthly lease installment payment quote')`
  - `upfront_lease_fees`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Upfront documentation, delivery, or origination fees')`
  - `end_of_lease_purchase_option`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Stipulated buyout option price at lease conclusion')`
  - `lessor_covers_maintenance`: `BooleanField(default=True, help_text='Flag indicating whether maintenance is included in lease fee')`
  - `annual_maintenance_cost_lease`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Any supplemental lessee-incurred maintenance under lease')`
  - `discount_rate_wacc_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('8.00'), help_text='Corporate Weighted Average Cost of Capital (WACC) hurdle rate (%)')`
  - `corporate_tax_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('21.00'), help_text='Effective marginal corporate income tax rate (%)')`
  - `npv_purchase_option`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Net Present Value of cash outflows for purchase/borrow scenario')`
  - `npv_lease_option`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Net Present Value of cash outflows for lease scenario')`
  - `tco_purchase_option`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Undiscounted nominal Total Cost of Ownership under purchase')`
  - `tco_lease_option`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Undiscounted nominal Total Cost of Ownership under lease')`
  - `net_advantage_to_leasing`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Net Present Value Advantage to Leasing: NPV(Buy) - NPV(Lease)')`
  - `recommendation`: `CharField(max_length=20, choices=RECOMMENDATION_CHOICES, default='neutral')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `evaluated_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='evaluated_lease_buy_analyses', help_text='Financial analyst performing evaluation')`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='approved_lease_buy_analyses', help_text='CFO or Treasurer approving acquisition method')`
  - `evaluation_notes`: `TextField(blank=True, help_text='Executive summary and qualitative evaluation narrative')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_alba_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_alba_ten_stat')`
  - `Index(fields=['tenant', 'recommendation'], name='idx_alba_ten_recom')`
  - `Index(fields=['tenant', 'category'], name='idx_alba_ten_cat')`
- **Actions / State Machine:**
  - `asset_lease_buy_analysis_evaluate`: computes discounted after-tax NPV for purchase and lease, computes nominal TCOs, determines `net_advantage_to_leasing`, assigns `recommendation = 'lease' if NAL > 0 else 'buy'`, and transitions status `draft -> evaluated`.
- **Form exclusions:** `tenant`, `number`, `npv_purchase_option`, `npv_lease_option`, `tco_purchase_option`, `tco_lease_option`, `net_advantage_to_leasing`, `recommendation`, `approved_by`, `created_at`, `updated_at`.

---

## 2. URLs & View Route Names Contract

Namespace: `assets` (in `apps/assets/urls/AssetLeaseRental/`)

### 2.1 `AssetLeaseContract`
- List: `assets:asset_lease_contract_list` -> `leases/`
- Detail: `assets:asset_lease_contract_detail` -> `leases/<int:pk>/`
- Create: `assets:asset_lease_contract_create` -> `leases/create/`
- Edit: `assets:asset_lease_contract_edit` -> `leases/<int:pk>/edit/`
- Delete: `assets:asset_lease_contract_delete` -> `leases/<int:pk>/delete/` (POST-only)
- Calculate: `assets:asset_lease_contract_calculate` -> `leases/<int:pk>/calculate/` (POST-only)
- Activate: `assets:asset_lease_contract_activate` -> `leases/<int:pk>/activate/` (POST-only)
- Terminate: `assets:asset_lease_contract_terminate` -> `leases/<int:pk>/terminate/` (POST-only)

### 2.2 `AssetLeaseSchedule`
- List: `assets:asset_lease_schedule_list` -> `lease-schedules/`
- Detail: `assets:asset_lease_schedule_detail` -> `lease-schedules/<int:pk>/`
- Create: `assets:asset_lease_schedule_create` -> `lease-schedules/create/`
- Edit: `assets:asset_lease_schedule_edit` -> `lease-schedules/<int:pk>/edit/`
- Delete: `assets:asset_lease_schedule_delete` -> `lease-schedules/<int:pk>/delete/` (POST-only)
- Mark Paid: `assets:asset_lease_schedule_mark_paid` -> `lease-schedules/<int:pk>/mark-paid/` (POST-only)
- Accrue: `assets:asset_lease_schedule_accrue` -> `lease-schedules/<int:pk>/accrue/` (POST-only)

### 2.3 `AssetLeaseModification`
- List: `assets:asset_lease_modification_list` -> `modifications/`
- Detail: `assets:asset_lease_modification_detail` -> `modifications/<int:pk>/`
- Create: `assets:asset_lease_modification_create` -> `modifications/create/`
- Edit: `assets:asset_lease_modification_edit` -> `modifications/<int:pk>/edit/`
- Delete: `assets:asset_lease_modification_delete` -> `modifications/<int:pk>/delete/` (POST-only)
- Approve: `assets:asset_lease_modification_approve` -> `modifications/<int:pk>/approve/` (POST-only)

### 2.4 `AssetLeaseBuyAnalysis`
- List: `assets:asset_lease_buy_analysis_list` -> `lease-buy-analyses/`
- Detail: `assets:asset_lease_buy_analysis_detail` -> `lease-buy-analyses/<int:pk>/`
- Create: `assets:asset_lease_buy_analysis_create` -> `lease-buy-analyses/create/`
- Edit: `assets:asset_lease_buy_analysis_edit` -> `lease-buy-analyses/<int:pk>/edit/`
- Delete: `assets:asset_lease_buy_analysis_delete` -> `lease-buy-analyses/<int:pk>/delete/` (POST-only)
- Evaluate: `assets:asset_lease_buy_analysis_evaluate` -> `lease-buy-analyses/<int:pk>/evaluate/` (POST-only)

---

## 3. View Context Variables Contract (MANDATORY PINNING)

### 3.1 `AssetLeaseContract`
- **List (`asset_lease_contract_list`):**
  - Queryset: `leases`
  - Pagination: `page_obj`, `paginator`, `is_paginated`
  - Filter choices: `status_choices` (`AssetLeaseContract.STATUS_CHOICES`), `classification_choices` (`AssetLeaseContract.CLASSIFICATION_CHOICES`), `lessor_list` (`Party.objects.filter(tenant=request.tenant)`)
  - Filter params: `q`, `status`, `classification`, `lessor`
  - Stat cards: `total_leases`, `active_count`, `total_liability`, `total_rou_value`
- **Detail (`asset_lease_contract_detail`):**
  - Primary object: `lease`
  - Sub-collections: `schedules` (`lease.payment_schedules.all()`), `modifications` (`lease.modifications.all()`)
- **Form (`asset_lease_contract_form`):**
  - Primary form: `form`
  - Page title: `title`
  - Mode flag: `is_edit`
  - Object ref: `lease` (when editing)

### 3.2 `AssetLeaseSchedule`
- **List (`asset_lease_schedule_list`):**
  - Queryset: `schedules`
  - Pagination: `page_obj`, `paginator`, `is_paginated`
  - Filter choices: `status_choices` (`AssetLeaseSchedule.STATUS_CHOICES`), `lease_list` (`AssetLeaseContract.objects.filter(tenant=request.tenant)`)
  - Filter params: `q`, `status`, `lease`
  - Stat cards: `total_schedules`, `scheduled_count`, `paid_count`, `total_paid_amount`
- **Detail (`asset_lease_schedule_detail`):**
  - Primary object: `schedule`
- **Form (`asset_lease_schedule_form`):**
  - Primary form: `form`
  - Page title: `title`
  - Mode flag: `is_edit`
  - Object ref: `schedule` (when editing)

### 3.3 `AssetLeaseModification`
- **List (`asset_lease_modification_list`):**
  - Queryset: `modifications`
  - Pagination: `page_obj`, `paginator`, `is_paginated`
  - Filter choices: `status_choices` (`AssetLeaseModification.STATUS_CHOICES`), `type_choices` (`AssetLeaseModification.MODIFICATION_TYPE_CHOICES`), `lease_list` (`AssetLeaseContract.objects.filter(tenant=request.tenant)`)
  - Filter params: `q`, `status`, `type`, `lease`
  - Stat cards: `total_modifications`, `executed_count`, `total_adjustments`
- **Detail (`asset_lease_modification_detail`):**
  - Primary object: `modification`
- **Form (`asset_lease_modification_form`):**
  - Primary form: `form`
  - Page title: `title`
  - Mode flag: `is_edit`
  - Object ref: `modification` (when editing)

### 3.4 `AssetLeaseBuyAnalysis`
- **List (`asset_lease_buy_analysis_list`):**
  - Queryset: `analyses`
  - Pagination: `page_obj`, `paginator`, `is_paginated`
  - Filter choices: `status_choices` (`AssetLeaseBuyAnalysis.STATUS_CHOICES`), `recommendation_choices` (`AssetLeaseBuyAnalysis.RECOMMENDATION_CHOICES`), `category_list` (`AssetCategory.objects.filter(tenant=request.tenant)`)
  - Filter params: `q`, `status`, `recommendation`, `category`
  - Stat cards: `total_analyses`, `buy_recommended_count`, `lease_recommended_count`
- **Detail (`asset_lease_buy_analysis_detail`):**
  - Primary object: `analysis`
- **Form (`asset_lease_buy_analysis_form`):**
  - Primary form: `form`
  - Page title: `title`
  - Mode flag: `is_edit`
  - Object ref: `analysis` (when editing)

---

## 4. Navigation Wiring (`apps/core/navigation.py`)

Sub-module 11.10 adds `LIVE_LINKS["11.10"]`:
```python
    "11.10": {
        "Lease Contract Administration": "assets:asset_lease_contract_list",
        "Operating vs. Finance Lease Classification": "assets:asset_lease_contract_list",
        "Lease Payment & Amortization": "assets:asset_lease_schedule_list",
        "Lease Modification & Termination": "assets:asset_lease_modification_list",
        "Lease vs. Buy Analysis": "assets:asset_lease_buy_analysis_list",
    },
```
All 5 NavERP.md feature bullets point directly to staff-facing management views.
