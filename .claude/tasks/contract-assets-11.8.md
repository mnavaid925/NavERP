# Contract — Sub-module 11.8: Warranty & Insurance Management (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.8 Warranty & Insurance Management • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-10 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending live `apps/assets/`. Incremental migration: `0012_...`.
- **Package Layout:** `AssetWarrantyInsurance/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/assetwarrantyinsurance/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AssetWarranty` (`apps/assets/models/AssetWarrantyInsurance/AssetWarranties.py`)
- **Table:** `assets_assetwarranty`
- **Number Prefix:** `AWAR` (format: `AWAR-YYYYMM-XXXX`)
- **CHOICES:**
  - `WARRANTY_TYPE_CHOICES = [('oem_standard', 'OEM Factory Standard Warranty'), ('oem_extended', 'OEM Extended Warranty'), ('third_party_extended', 'Third-Party Service Contract / Warranty'), ('dealer_certified', 'Dealer Certified Pre-Owned Warranty'), ('refurbished_component', 'Rebuilt / Refurbished Component Warranty')]`
  - `COVERAGE_SCOPE_CHOICES = [('comprehensive', 'Comprehensive (Bumper-to-Bumper)'), ('parts_and_labor', 'Parts and Labor Included'), ('parts_only', 'Parts Only (Labor Excluded)'), ('powertrain_major_components', 'Powertrain & Major Subsystems'), ('corrosion_structural', 'Structural Integrity & Corrosion')]`
  - `METER_TYPE_CHOICES = [('hours', 'Operating Hours (Run Hours)'), ('kilometers', 'Odometer Distance (km)'), ('miles', 'Odometer Distance (mi)'), ('production_cycles', 'Machine Cycles / Impressions'), ('none_calendar_only', 'None (Calendar Time Only)')]`
  - `STATUS_CHOICES = [('draft', 'Draft (Pending Activation)'), ('active', 'Active (Under Warranty)'), ('expiring_soon', 'Expiring Soon (< 60 Days)'), ('expired', 'Expired'), ('voided', 'Voided (Condition Breach)'), ('claimed', 'Under Active Claim')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'active': 'badge-green', 'expiring_soon': 'badge-amber', 'expired': 'badge-muted', 'voided': 'badge-red', 'claimed': 'badge-info'}`
  - `WARRANTY_TYPE_CSS = {'oem_standard': 'badge-info', 'oem_extended': 'badge-green', 'third_party_extended': 'badge-amber', 'dealer_certified': 'badge-slate', 'refurbished_component': 'badge-muted'}`
  - `COVERAGE_SCOPE_CSS = {'comprehensive': 'badge-green', 'parts_and_labor': 'badge-info', 'parts_only': 'badge-amber', 'powertrain_major_components': 'badge-slate', 'corrosion_structural': 'badge-muted'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_warranties')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='Warranty policy title or contract agreement name')`
  - `warranty_certificate_number`: `CharField(max_length=100, blank=True, help_text='Manufacturer/vendor warranty contract or certificate registration ID')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='warranties', help_text='Financial Fixed Asset in accounting register')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='warranties', help_text='Operational plant equipment or machinery')`
  - `asset_category`: `ForeignKey('assets.AssetCategory', on_delete=SET_NULL, null=True, blank=True, related_name='warranties', help_text='Asset category taxonomy')`
  - `warrantor_party`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='provided_asset_warranties', help_text='OEM, authorized dealer, or warranty provider party')`
  - `currency`: `ForeignKey('accounting.Currency', on_delete=SET_NULL, null=True, blank=True, related_name='asset_warranties', help_text='Transaction currency')`
  - `warranty_type`: `CharField(max_length=32, choices=WARRANTY_TYPE_CHOICES, default='oem_standard')`
  - `coverage_scope`: `CharField(max_length=32, choices=COVERAGE_SCOPE_CHOICES, default='comprehensive')`
  - `start_date`: `DateField(help_text='Warranty coverage inception or commissioning date')`
  - `end_date`: `DateField(help_text='Calendar warranty expiration date')`
  - `meter_type`: `CharField(max_length=24, choices=METER_TYPE_CHOICES, default='none_calendar_only')`
  - `meter_limit`: `PositiveIntegerField(null=True, blank=True, help_text='Meter threshold limit (e.g. 5,000 hours or 100,000 km)')`
  - `parts_coverage_percent`: `PositiveIntegerField(default=100, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Covered replacement parts percentage (0-100%)')`
  - `labor_coverage_percent`: `PositiveIntegerField(default=100, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Covered technical labor percentage (0-100%)')`
  - `travel_dispatch_covered`: `BooleanField(default=True, help_text='Whether technician travel and on-site dispatch fees are covered')`
  - `deductible_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Per-incident warranty deductible payable by tenant')`
  - `contract_purchase_price`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Purchase cost paid for extended warranty or service protection')`
  - `terms_and_conditions`: `TextField(blank=True, help_text='Warranty coverage terms, exclusions, preventive maintenance mandates, and limits')`
  - `contract_document`: `ForeignKey('core.Document', on_delete=SET_NULL, null=True, blank=True, related_name='linked_asset_warranties', help_text='Scanned manufacturer warranty certificate or legal agreement')`
  - `service_contract`: `ForeignKey('assets.AssetServiceContract', on_delete=SET_NULL, null=True, blank=True, related_name='linked_warranties', help_text='Associated 11.5 maintenance service contract SLA if unified')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `registered_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='registered_asset_warranties')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_awar_ten_num_uniq')`
  - `Index(fields=['tenant', 'end_date'], name='idx_awar_ten_date')`
  - `Index(fields=['tenant', 'status'], name='idx_awar_ten_stat')`
  - `Index(fields=['tenant', 'warranty_type'], name='idx_awar_ten_type')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_awar_ten_fa')`
- **Actions / State Transitions:**
  - `asset_warranty_activate`: transitions `draft -> active`.
  - `asset_warranty_renew`: extends `end_date` and optionally adjusts `meter_limit`, resetting status to `active`.
  - `asset_warranty_void`: transitions `active -> voided` with rationale notes.
- **Form exclusions:** `tenant`, `number`, `status`, `registered_by`, `created_at`, `updated_at`.

---

### 1.2 `AssetWarrantyClaim` (`apps/assets/models/AssetWarrantyInsurance/AssetWarrantyClaims.py`)
- **Table:** `assets_assetwarrantyclaim`
- **Number Prefix:** `AWCL` (format: `AWCL-YYYYMM-XXXX`)
- **CHOICES:**
  - `CLAIM_STATUS_CHOICES = [('draft', 'Draft (Claim Preparation)'), ('submitted', 'Submitted to Warrantor / OEM'), ('under_review', 'Under Technical Review'), ('approved', 'Approved in Full'), ('partially_approved', 'Partially Approved (Adjusted)'), ('rejected', 'Rejected / Denied'), ('settled_closed', 'Settled & Closed')]`
  - `RESOLUTION_TYPE_CHOICES = [('pending_evaluation', 'Pending OEM Evaluation'), ('parts_replacement', 'OEM Direct Parts Replacement'), ('on_site_repair', 'On-Site Factory Authorized Repair'), ('depot_repair', 'Factory Depot Repair / Overhaul'), ('cash_reimbursement', 'Direct Cash Reimbursement'), ('credit_memo', 'Vendor Credit Memo on Account'), ('rejected_uncovered', 'Rejected / Excluded from Coverage')]`
  - `PART_RETURN_STATUS_CHOICES = [('not_required', 'Defective Part Scrap on Site (Return Not Required)'), ('return_required_pending', 'Defective Part Return Required (Pending Shipment)'), ('shipped_in_transit', 'Defective Part Shipped to OEM (In Transit)'), ('received_inspected_by_oem', 'Received & Authenticated by OEM Depot')]`
  - `CLAIM_STATUS_CSS = {'draft': 'badge-slate', 'submitted': 'badge-info', 'under_review': 'badge-amber', 'approved': 'badge-green', 'partially_approved': 'badge-amber', 'rejected': 'badge-red', 'settled_closed': 'badge-muted'}`
  - `RESOLUTION_TYPE_CSS = {'pending_evaluation': 'badge-slate', 'parts_replacement': 'badge-info', 'on_site_repair': 'badge-green', 'depot_repair': 'badge-amber', 'cash_reimbursement': 'badge-green', 'credit_memo': 'badge-info', 'rejected_uncovered': 'badge-red'}`
  - `PART_RETURN_STATUS_CSS = {'not_required': 'badge-slate', 'return_required_pending': 'badge-amber', 'shipped_in_transit': 'badge-info', 'received_inspected_by_oem': 'badge-green'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_warranty_claims')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='Warranty claim headline or defect summary')`
  - `warranty`: `ForeignKey('assets.AssetWarranty', on_delete=CASCADE, related_name='claims', help_text='Covering warranty policy')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='warranty_claims', help_text='Financial Fixed Asset in accounting register')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='warranty_claims', help_text='Operational equipment record')`
  - `maintenance_request`: `ForeignKey('assets.AssetMaintenanceRequest', on_delete=SET_NULL, null=True, blank=True, related_name='warranty_claims', help_text='Originating corrective maintenance work order or ticket')`
  - `incident_date`: `DateField(help_text='Date defect or component failure occurred')`
  - `operating_meter_at_failure`: `PositiveIntegerField(null=True, blank=True, help_text='Meter reading at time of failure (hours/km)')`
  - `defect_description`: `TextField(help_text='Detailed physical failure symptom, root cause analysis, or diagnostic code')`
  - `warrantor_claim_reference`: `CharField(max_length=100, blank=True, help_text='OEM / vendor RMA or ticket tracking number')`
  - `currency`: `ForeignKey('accounting.Currency', on_delete=SET_NULL, null=True, blank=True, related_name='asset_warranty_claims', help_text='Currency of claim valuation')`
  - `claimed_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Total cost claimed (parts + labor + dispatch)')`
  - `approved_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Amount accepted/authorized by warrantor')`
  - `deductible_applied`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Tenant warranty deductible deducted from settlement')`
  - `net_recovery_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Net payout/credit recovered (Approved - Deductible)')`
  - `resolution_type`: `CharField(max_length=28, choices=RESOLUTION_TYPE_CHOICES, default='pending_evaluation')`
  - `claim_status`: `CharField(max_length=24, choices=CLAIM_STATUS_CHOICES, default='draft')`
  - `part_return_status`: `CharField(max_length=32, choices=PART_RETURN_STATUS_CHOICES, default='not_required')`
  - `rma_tracking_number`: `CharField(max_length=100, blank=True, help_text='Courier shipping tracking for return of core/failed assembly')`
  - `submission_date`: `DateField(null=True, blank=True, help_text='Date formal claim submitted to warrantor')`
  - `settlement_date`: `DateField(null=True, blank=True, help_text='Date claim settled or credit/payment received')`
  - `settlement_notes`: `TextField(blank=True, help_text='Settlement reconciliation or rejection justification notes')`
  - `filed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='filed_asset_warranty_claims')`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='authorized_asset_warranty_claims')`
  - `supporting_document`: `ForeignKey('core.Document', on_delete=SET_NULL, null=True, blank=True, related_name='linked_warranty_claims', help_text='Diagnostic report, photos, or OEM settlement letter')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_awcl_ten_num_uniq')`
  - `Index(fields=['tenant', 'claim_status'], name='idx_awcl_ten_stat')`
  - `Index(fields=['tenant', 'incident_date'], name='idx_awcl_ten_date')`
  - `Index(fields=['tenant', 'warranty'], name='idx_awcl_ten_war')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_awcl_ten_fa')`
- **Actions / State Transitions:**
  - `asset_warranty_claim_submit`: transitions `draft -> submitted`, timestamps `submission_date`.
  - `asset_warranty_claim_review`: transitions `submitted -> under_review`.
  - `asset_warranty_claim_settle`: transitions `under_review -> approved / partially_approved -> settled_closed`, records `approved_amount`, calculates `net_recovery_amount`, sets `settlement_date`.
  - `asset_warranty_claim_reject`: transitions to `rejected`, records rejection rationale.
- **Form exclusions:** `tenant`, `number`, `claim_status`, `approved_amount`, `net_recovery_amount`, `submission_date`, `settlement_date`, `approved_by`, `created_at`, `updated_at`.

---

### 1.3 `AssetInsurancePolicy` (`apps/assets/models/AssetWarrantyInsurance/AssetInsurancePolicies.py`)
- **Table:** `assets_assetinsurancepolicy`
- **Number Prefix:** `AINS` (format: `AINS-YYYYMM-XXXX`)
- **CHOICES:**
  - `POLICY_TYPE_CHOICES = [('commercial_property', 'Commercial Property & Real Estate'), ('machinery_breakdown', 'Machinery Breakdown & Mechanical Extrusion'), ('boiler_pressure_vessel', 'Boiler, Pressure Vessel & Critical Plant'), ('inland_marine_transit', 'Inland Marine & Equipment in Transit'), ('business_interruption', 'Business Interruption & Loss of Profits'), ('commercial_auto_fleet', 'Commercial Motor Vehicle & Heavy Mobile Fleet'), ('comprehensive_all_risk', 'Comprehensive Industrial All-Risk (CAR/EAR)')]`
  - `VALUATION_BASIS_CHOICES = [('replacement_cost_value', 'Replacement Cost Value (RCV - As New)'), ('actual_cash_value', 'Actual Cash Value (ACV - Depreciated)'), ('agreed_stated_value', 'Agreed Stated Value (Appraised)'), ('functional_replacement', 'Functional Replacement Cost')]`
  - `PREMIUM_FREQUENCY_CHOICES = [('annual', 'Annual Lump Sum'), ('semi_annual', 'Semi-Annual (Bi-annual)'), ('quarterly', 'Quarterly Installments'), ('monthly', 'Monthly Direct Debit')]`
  - `STATUS_CHOICES = [('draft', 'Draft (Quotation / Binding)'), ('active', 'Active (In Force)'), ('pending_renewal', 'Pending Renewal (< 45 Days)'), ('expired', 'Expired'), ('cancelled', 'Cancelled / Surrendered')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'active': 'badge-green', 'pending_renewal': 'badge-amber', 'expired': 'badge-muted', 'cancelled': 'badge-red'}`
  - `POLICY_TYPE_CSS = {'commercial_property': 'badge-info', 'machinery_breakdown': 'badge-amber', 'boiler_pressure_vessel': 'badge-red', 'inland_marine_transit': 'badge-slate', 'business_interruption': 'badge-purple', 'commercial_auto_fleet': 'badge-info', 'comprehensive_all_risk': 'badge-green'}`
  - `VALUATION_BASIS_CSS = {'replacement_cost_value': 'badge-green', 'actual_cash_value': 'badge-amber', 'agreed_stated_value': 'badge-info', 'functional_replacement': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_insurance_policies')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `policy_number`: `CharField(max_length=100, help_text='Underwriter issued policy binder or certificate number')`
  - `title`: `CharField(max_length=255, help_text='Policy headline (e.g. FY26 Plant Machinery & Boiler Schedule)')`
  - `policy_type`: `CharField(max_length=32, choices=POLICY_TYPE_CHOICES, default='machinery_breakdown')`
  - `valuation_basis`: `CharField(max_length=28, choices=VALUATION_BASIS_CHOICES, default='replacement_cost_value')`
  - `underwriter_party`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='underwritten_asset_policies', help_text='Lead insurance underwriting carrier')`
  - `broker_party`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='brokered_asset_policies', help_text='Insurance brokerage intermediary firm')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='insurance_policies', help_text='Specific financial Fixed Asset (blank if blanket/fleet policy)')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='insurance_policies', help_text='Specific operational machinery (blank if schedule-wide)')`
  - `asset_category`: `ForeignKey('assets.AssetCategory', on_delete=SET_NULL, null=True, blank=True, related_name='insurance_policies', help_text='Target category for category-wide coverage')`
  - `currency`: `ForeignKey('accounting.Currency', on_delete=SET_NULL, null=True, blank=True, related_name='asset_insurance_policies', help_text='Policy valuation and premium currency')`
  - `effective_date`: `DateField(help_text='Policy inception / coverage start date')`
  - `expiration_date`: `DateField(help_text='Policy renewal / expiration cutoff date')`
  - `total_insured_value`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Statement of Values (SOV) / Sum insured limit')`
  - `deductible_retention`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Self-insured retention or per-claim deductible')`
  - `coinsurance_percentage`: `PositiveIntegerField(default=100, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Required coinsurance clause percentage (e.g. 80%, 90%, 100%)')`
  - `annual_premium`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Total annualized premium fee')`
  - `premium_frequency`: `CharField(max_length=16, choices=PREMIUM_FREQUENCY_CHOICES, default='annual')`
  - `coverage_terms`: `TextField(blank=True, help_text='Endorsements, named perils, territorial limits, and exclusion schedules')`
  - `policy_document`: `ForeignKey('core.Document', on_delete=SET_NULL, null=True, blank=True, related_name='linked_insurance_policies', help_text='Uploaded policy wording, endorsement schedule, or binder PDF')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `risk_manager`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='managed_asset_insurance_policies')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_ains_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_ains_ten_stat')`
  - `Index(fields=['tenant', 'expiration_date'], name='idx_ains_ten_exp')`
  - `Index(fields=['tenant', 'policy_type'], name='idx_ains_ten_type')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_ains_ten_fa')`
- **Actions / State Transitions:**
  - `asset_insurance_policy_activate`: transitions `draft -> active`.
  - `asset_insurance_policy_renew`: extends `expiration_date` by 1 year, updates `annual_premium` and resets status to `active`.
  - `asset_insurance_policy_cancel`: transitions `active -> cancelled` with recorded reason.
- **Form exclusions:** `tenant`, `number`, `status`, `created_at`, `updated_at`.

---

### 1.4 `AssetInsuranceClaim` (`apps/assets/models/AssetWarrantyInsurance/AssetInsuranceClaims.py`)
- **Table:** `assets_assetinsuranceclaim`
- **Number Prefix:** `AICL` (format: `AICL-YYYYMM-XXXX`)
- **CHOICES:**
  - `PERIL_TYPE_CHOICES = [('fire_lightning', 'Fire, Smoke & Lightning Strike'), ('flood_water_damage', 'Flood, Inundation & Pipe Burst Water Damage'), ('electrical_arcing_surge', 'Electrical Arcing, Short Circuit & Voltage Surge'), ('mechanical_breakdown', 'Sudden & Accidental Mechanical Breakdown'), ('operator_error_accidental', 'Operator Error, Dropping & Accidental Impact'), ('theft_burglary', 'Theft, Burglary & Vandalism'), ('windstorm_hail', 'Windstorm, Tornado & Hail Destruction'), ('collision_impact', 'Vehicle Collision & Heavy Mobile Plant Impact'), ('collapse_subsidence', 'Structural Collapse, Landslide & Subsidence')]`
  - `CLAIM_STATUS_CHOICES = [('incident_reported', 'Incident Reported (Intake)'), ('adjuster_assigned', 'Adjuster Assigned & Inspecting'), ('proof_of_loss_filed', 'Proof of Loss Filed & Sworn'), ('under_carrier_review', 'Under Carrier Claims Committee Review'), ('approved_pending_payout', 'Approved (Pending Payout Dispatch)'), ('settled_paid', 'Settled & Indemnity Dispatched'), ('denied_disputed', 'Denied / Under Formal Dispute'), ('closed', 'Claim File Closed')]`
  - `SETTLEMENT_METHOD_CHOICES = [('direct_indemnity_check', 'Direct Carrier Indemnity Payment (EFT/Check)'), ('vendor_direct_repair', 'Carrier Direct Payment to Authorized Repairer'), ('retained_salvage_offset', 'Settled Net of Retained Equipment Salvage'), ('none_denied', 'No Settlement (Claim Denied or Withdrawn)')]`
  - `CLAIM_STATUS_CSS = {'incident_reported': 'badge-slate', 'adjuster_assigned': 'badge-info', 'proof_of_loss_filed': 'badge-amber', 'under_carrier_review': 'badge-amber', 'approved_pending_payout': 'badge-info', 'settled_paid': 'badge-green', 'denied_disputed': 'badge-red', 'closed': 'badge-muted'}`
  - `PERIL_TYPE_CSS = {'fire_lightning': 'badge-red', 'flood_water_damage': 'badge-info', 'electrical_arcing_surge': 'badge-amber', 'mechanical_breakdown': 'badge-amber', 'operator_error_accidental': 'badge-slate', 'theft_burglary': 'badge-red', 'windstorm_hail': 'badge-info', 'collision_impact': 'badge-red', 'collapse_subsidence': 'badge-muted'}`
  - `SETTLEMENT_METHOD_CSS = {'direct_indemnity_check': 'badge-green', 'vendor_direct_repair': 'badge-info', 'retained_salvage_offset': 'badge-amber', 'none_denied': 'badge-red'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_insurance_claims')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='Insurance claim title or casualty incident summary')`
  - `policy`: `ForeignKey('assets.AssetInsurancePolicy', on_delete=CASCADE, related_name='claims', help_text='Covering insurance policy binder')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='insurance_claims', help_text='Financial Fixed Asset affected')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='insurance_claims', help_text='Operational equipment record')`
  - `incident_report`: `ForeignKey('assets.AssetIncidentReport', on_delete=SET_NULL, null=True, blank=True, related_name='insurance_claims', help_text='Linked 11.2 operational incident record')`
  - `incident_date`: `DateField(help_text='Date of peril occurrence or physical loss')`
  - `peril_type`: `CharField(max_length=32, choices=PERIL_TYPE_CHOICES, default='mechanical_breakdown')`
  - `incident_description`: `TextField(help_text='Detailed narrative of casualty event, damage scope, and operational interruption')`
  - `incident_location`: `CharField(max_length=255, help_text='Physical facility, plant floor, room, or geographical site of occurrence')`
  - `carrier_claim_number`: `CharField(max_length=100, blank=True, help_text='Insurance carrier assigned claim reference number')`
  - `adjuster_party`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='adjusted_asset_claims', help_text='Independent loss adjuster or forensic engineering agency')`
  - `adjuster_name`: `CharField(max_length=100, blank=True, help_text='Name of designated individual adjuster')`
  - `currency`: `ForeignKey('accounting.Currency', on_delete=SET_NULL, null=True, blank=True, related_name='asset_insurance_claims', help_text='Claim valuation currency')`
  - `claimed_loss_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Gross estimated direct physical loss claimed')`
  - `deductible_applied`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Policy deductible applied against gross settlement')`
  - `salvage_recovery_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Proceeds recovered from scrap / residual asset sale')`
  - `settlement_payout_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Actual net cash compensation paid by carrier')`
  - `claim_status`: `CharField(max_length=28, choices=CLAIM_STATUS_CHOICES, default='incident_reported')`
  - `settlement_method`: `CharField(max_length=32, choices=SET_METHOD_CHOICES, default='direct_indemnity_check')`
  - `date_reported_to_carrier`: `DateField(null=True, blank=True, help_text='Date insurer formally notified')`
  - `proof_of_loss_date`: `DateField(null=True, blank=True, help_text='Date formal sworn Proof of Loss submitted')`
  - `settlement_date`: `DateField(null=True, blank=True, help_text='Date final payout received or release agreement executed')`
  - `settlement_notes`: `TextField(blank=True, help_text='Settlement calculation notes, subrogation details, or denial justification')`
  - `claims_officer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='managed_asset_insurance_claims')`
  - `proof_of_loss_document`: `ForeignKey('core.Document', on_delete=SET_NULL, null=True, blank=True, related_name='linked_insurance_claims', help_text='Sworn proof of loss, adjuster report, police report, or engineering forensic certificate')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_aicl_ten_num_uniq')`
  - `Index(fields=['tenant', 'claim_status'], name='idx_aicl_ten_stat')`
  - `Index(fields=['tenant', 'incident_date'], name='idx_aicl_ten_date')`
  - `Index(fields=['tenant', 'policy'], name='idx_aicl_ten_pol')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_aicl_ten_fa')`
- **Actions / State Transitions:**
  - `asset_insurance_claim_assign_adjuster`: transitions `incident_reported -> adjuster_assigned`.
  - `asset_insurance_claim_file_proof`: transitions `adjuster_assigned -> proof_of_loss_filed`, timestamps `proof_of_loss_date`.
  - `asset_insurance_claim_settle`: transitions to `settled_paid`, records `settlement_payout_amount`, `salvage_recovery_amount`, sets `settlement_date`.
  - `asset_insurance_claim_deny`: transitions to `denied_disputed` with denial notes.
- **Form exclusions:** `tenant`, `number`, `claim_status`, `settlement_payout_amount`, `date_reported_to_carrier`, `proof_of_loss_date`, `settlement_date`, `created_at`, `updated_at`.

---

## 2. Forms Contract

Located in `apps/assets/forms/AssetWarrantyInsurance/`:
- `AssetWarrantyForm` (`AssetWarranties.py`) -> excludes `tenant`, `number`, `status`, `registered_by`, `created_at`, `updated_at`.
- `AssetWarrantyClaimForm` (`AssetWarrantyClaims.py`) -> excludes `tenant`, `number`, `claim_status`, `approved_amount`, `net_recovery_amount`, `submission_date`, `settlement_date`, `approved_by`, `created_at`, `updated_at`.
- `AssetInsurancePolicyForm` (`AssetInsurancePolicies.py`) -> excludes `tenant`, `number`, `status`, `created_at`, `updated_at`.
- `AssetInsuranceClaimForm` (`AssetInsuranceClaims.py`) -> excludes `tenant`, `number`, `claim_status`, `settlement_payout_amount`, `date_reported_to_carrier`, `proof_of_loss_date`, `settlement_date`, `created_at`, `updated_at`.

All forms inherit from `apps.core.forms.TenantModelForm` (which scopes FK choices to `tenant`).

---

## 3. URLs Contract

App name is `assets`. Concatenated in `apps/assets/urls/__init__.py`.

```python
# apps/assets/urls/AssetWarrantyInsurance/AssetWarranties.py
urlpatterns = [
    path('warranty-insurance/warranties/', views.asset_warranty_list, name='asset_warranty_list'),
    path('warranty-insurance/warranties/create/', views.asset_warranty_create, name='asset_warranty_create'),
    path('warranty-insurance/warranties/<int:pk>/', views.asset_warranty_detail, name='asset_warranty_detail'),
    path('warranty-insurance/warranties/<int:pk>/edit/', views.asset_warranty_edit, name='asset_warranty_edit'),
    path('warranty-insurance/warranties/<int:pk>/delete/', views.asset_warranty_delete, name='asset_warranty_delete'),
    path('warranty-insurance/warranties/<int:pk>/activate/', views.asset_warranty_activate, name='asset_warranty_activate'),
    path('warranty-insurance/warranties/<int:pk>/renew/', views.asset_warranty_renew, name='asset_warranty_renew'),
    path('warranty-insurance/warranties/<int:pk>/void/', views.asset_warranty_void, name='asset_warranty_void'),
]

# apps/assets/urls/AssetWarrantyInsurance/AssetWarrantyClaims.py
urlpatterns = [
    path('warranty-insurance/warranty-claims/', views.asset_warranty_claim_list, name='asset_warranty_claim_list'),
    path('warranty-insurance/warranty-claims/create/', views.asset_warranty_claim_create, name='asset_warranty_claim_create'),
    path('warranty-insurance/warranty-claims/<int:pk>/', views.asset_warranty_claim_detail, name='asset_warranty_claim_detail'),
    path('warranty-insurance/warranty-claims/<int:pk>/edit/', views.asset_warranty_claim_edit, name='asset_warranty_claim_edit'),
    path('warranty-insurance/warranty-claims/<int:pk>/delete/', views.asset_warranty_claim_delete, name='asset_warranty_claim_delete'),
    path('warranty-insurance/warranty-claims/<int:pk>/submit/', views.asset_warranty_claim_submit, name='asset_warranty_claim_submit'),
    path('warranty-insurance/warranty-claims/<int:pk>/review/', views.asset_warranty_claim_review, name='asset_warranty_claim_review'),
    path('warranty-insurance/warranty-claims/<int:pk>/settle/', views.asset_warranty_claim_settle, name='asset_warranty_claim_settle'),
    path('warranty-insurance/warranty-claims/<int:pk>/reject/', views.asset_warranty_claim_reject, name='asset_warranty_claim_reject'),
]

# apps/assets/urls/AssetWarrantyInsurance/AssetInsurancePolicies.py
urlpatterns = [
    path('warranty-insurance/policies/', views.asset_insurance_policy_list, name='asset_insurance_policy_list'),
    path('warranty-insurance/policies/create/', views.asset_insurance_policy_create, name='asset_insurance_policy_create'),
    path('warranty-insurance/policies/<int:pk>/', views.asset_insurance_policy_detail, name='asset_insurance_policy_detail'),
    path('warranty-insurance/policies/<int:pk>/edit/', views.asset_insurance_policy_edit, name='asset_insurance_policy_edit'),
    path('warranty-insurance/policies/<int:pk>/delete/', views.asset_insurance_policy_delete, name='asset_insurance_policy_delete'),
    path('warranty-insurance/policies/<int:pk>/activate/', views.asset_insurance_policy_activate, name='asset_insurance_policy_activate'),
    path('warranty-insurance/policies/<int:pk>/renew/', views.asset_insurance_policy_renew, name='asset_insurance_policy_renew'),
    path('warranty-insurance/policies/<int:pk>/cancel/', views.asset_insurance_policy_cancel, name='asset_insurance_policy_cancel'),
]

# apps/assets/urls/AssetWarrantyInsurance/AssetInsuranceClaims.py
urlpatterns = [
    path('warranty-insurance/insurance-claims/', views.asset_insurance_claim_list, name='asset_insurance_claim_list'),
    path('warranty-insurance/insurance-claims/create/', views.asset_insurance_claim_create, name='asset_insurance_claim_create'),
    path('warranty-insurance/insurance-claims/<int:pk>/', views.asset_insurance_claim_detail, name='asset_insurance_claim_detail'),
    path('warranty-insurance/insurance-claims/<int:pk>/edit/', views.asset_insurance_claim_edit, name='asset_insurance_claim_edit'),
    path('warranty-insurance/insurance-claims/<int:pk>/delete/', views.asset_insurance_claim_delete, name='asset_insurance_claim_delete'),
    path('warranty-insurance/insurance-claims/<int:pk>/assign-adjuster/', views.asset_insurance_claim_assign_adjuster, name='asset_insurance_claim_assign_adjuster'),
    path('warranty-insurance/insurance-claims/<int:pk>/file-proof/', views.asset_insurance_claim_file_proof, name='asset_insurance_claim_file_proof'),
    path('warranty-insurance/insurance-claims/<int:pk>/settle/', views.asset_insurance_claim_settle, name='asset_insurance_claim_settle'),
    path('warranty-insurance/insurance-claims/<int:pk>/deny/', views.asset_insurance_claim_deny, name='asset_insurance_claim_deny'),
]
```

---

## 4. Views & Context Contract

All views require `@login_required` (actions and deletes `@tenant_admin_required`). Tenant isolation: `tenant=request.tenant`.

### 4.1 `AssetWarranty` Views
- **List View (`asset_warranty_list`):**
  - **Context Keys:**
    - `warranties`: Page object / queryset
    - `page_obj`: Django pagination object
    - `paginator`: Paginator instance
    - `is_paginated`: Boolean
    - `status_choices`: `AssetWarranty.STATUS_CHOICES`
    - `warranty_type_choices`: `AssetWarranty.WARRANTY_TYPE_CHOICES`
    - `coverage_scope_choices`: `AssetWarranty.COVERAGE_SCOPE_CHOICES`
    - `category_list`: `AssetCategory.objects.filter(tenant=request.tenant)`
    - `total_warranties`: Total count for tenant
    - `active_warranties`: Count with `status='active'`
    - `expiring_soon_count`: Count with `status='expiring_soon'` or `(end_date <= now + 60 days and status='active')`
    - `claimed_count`: Count with `status='claimed'`
- **Detail View (`asset_warranty_detail`):**
  - **Context Keys:**
    - `warranty`: `AssetWarranty` instance
    - `claims`: Related `AssetWarrantyClaim` queryset
- **Form View (`asset_warranty_create` / `asset_warranty_edit`):**
  - **Context Keys:**
    - `form`: `AssetWarrantyForm`
    - `warranty`: Instance when editing, None when creating
    - `is_edit`: Boolean

### 4.2 `AssetWarrantyClaim` Views
- **List View (`asset_warranty_claim_list`):**
  - **Context Keys:**
    - `warranty_claims`: Page object / queryset
    - `page_obj`: Django pagination object
    - `paginator`: Paginator instance
    - `is_paginated`: Boolean
    - `claim_status_choices`: `AssetWarrantyClaim.CLAIM_STATUS_CHOICES`
    - `resolution_type_choices`: `AssetWarrantyClaim.RESOLUTION_TYPE_CHOICES`
    - `part_return_status_choices`: `AssetWarrantyClaim.PART_RETURN_STATUS_CHOICES`
    - `total_claims`: Total count for tenant
    - `pending_claims`: Count with `claim_status__in=['draft', 'submitted', 'under_review']`
    - `settled_claims`: Count with `claim_status='settled_closed'`
    - `total_net_recovered`: Sum of `net_recovery_amount` for settled claims
- **Detail View (`asset_warranty_claim_detail`):**
  - **Context Keys:**
    - `claim`: `AssetWarrantyClaim` instance
- **Form View (`asset_warranty_claim_create` / `asset_warranty_claim_edit`):**
  - **Context Keys:**
    - `form`: `AssetWarrantyClaimForm`
    - `claim`: Instance when editing, None when creating
    - `is_edit`: Boolean

### 4.3 `AssetInsurancePolicy` Views
- **List View (`asset_insurance_policy_list`):**
  - **Context Keys:**
    - `policies`: Page object / queryset
    - `page_obj`: Django pagination object
    - `paginator`: Paginator instance
    - `is_paginated`: Boolean
    - `status_choices`: `AssetInsurancePolicy.STATUS_CHOICES`
    - `policy_type_choices`: `AssetInsurancePolicy.POLICY_TYPE_CHOICES`
    - `valuation_basis_choices`: `AssetInsurancePolicy.VALUATION_BASIS_CHOICES`
    - `category_list`: `AssetCategory.objects.filter(tenant=request.tenant)`
    - `total_policies`: Total count for tenant
    - `active_policies`: Count with `status='active'`
    - `pending_renewal_count`: Count with `status='pending_renewal'` or `(expiration_date <= now + 45 days and status='active')`
    - `total_insured_value`: Sum of `total_insured_value` for active policies
- **Detail View (`asset_insurance_policy_detail`):**
  - **Context Keys:**
    - `policy`: `AssetInsurancePolicy` instance
    - `claims`: Related `AssetInsuranceClaim` queryset
- **Form View (`asset_insurance_policy_create` / `asset_insurance_policy_edit`):**
  - **Context Keys:**
    - `form`: `AssetInsurancePolicyForm`
    - `policy`: Instance when editing, None when creating
    - `is_edit`: Boolean

### 4.4 `AssetInsuranceClaim` Views
- **List View (`asset_insurance_claim_list`):**
  - **Context Keys:**
    - `insurance_claims`: Page object / queryset
    - `page_obj`: Django pagination object
    - `paginator`: Paginator instance
    - `is_paginated`: Boolean
    - `claim_status_choices`: `AssetInsuranceClaim.CLAIM_STATUS_CHOICES`
    - `peril_type_choices`: `AssetInsuranceClaim.PERIL_TYPE_CHOICES`
    - `settlement_method_choices`: `AssetInsuranceClaim.SETTLEMENT_METHOD_CHOICES`
    - `total_claims`: Total count for tenant
    - `active_claims`: Count with `claim_status__in=['incident_reported', 'adjuster_assigned', 'proof_of_loss_filed', 'under_carrier_review']`
    - `settled_claims`: Count with `claim_status='settled_paid'`
    - `total_payout_recovered`: Sum of `settlement_payout_amount` for settled claims
- **Detail View (`asset_insurance_claim_detail`):**
  - **Context Keys:**
    - `claim`: `AssetInsuranceClaim` instance
- **Form View (`asset_insurance_claim_create` / `asset_insurance_claim_edit`):**
  - **Context Keys:**
    - `form`: `AssetInsuranceClaimForm`
    - `claim`: Instance when editing, None when creating
    - `is_edit`: Boolean

---

## 5. Templates Contract

Paths follow `templates/assets/assetwarrantyinsurance/<entity>/<page>.html`:
1. `templates/assets/assetwarrantyinsurance/assetwarranty/list.html`
2. `templates/assets/assetwarrantyinsurance/assetwarranty/detail.html`
3. `templates/assets/assetwarrantyinsurance/assetwarranty/form.html`
4. `templates/assets/assetwarrantyinsurance/assetwarrantyclaim/list.html`
5. `templates/assets/assetwarrantyinsurance/assetwarrantyclaim/detail.html`
6. `templates/assets/assetwarrantyinsurance/assetwarrantyclaim/form.html`
7. `templates/assets/assetwarrantyinsurance/assetinsurancepolicy/list.html`
8. `templates/assets/assetwarrantyinsurance/assetinsurancepolicy/detail.html`
9. `templates/assets/assetwarrantyinsurance/assetinsurancepolicy/form.html`
10. `templates/assets/assetwarrantyinsurance/assetinsuranceclaim/list.html`
11. `templates/assets/assetwarrantyinsurance/assetinsuranceclaim/detail.html`
12. `templates/assets/assetwarrantyinsurance/assetinsuranceclaim/form.html`

Badges strictly use `theme.css` color names: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`, `badge-muted`.

---

## 6. Navigation Wire-up (`LIVE_LINKS["11.8"]`)

In `apps/core/navigation.py`:
```python
"11.8": {
    "Warranty Registration & Tracking": "assets:asset_warranty_list",
    "Warranty Claim Processing": "assets:asset_warranty_claim_list",
    "Insurance Policy Management": "assets:asset_insurance_policy_list",
    "Claim Filing & Settlement": "assets:asset_insurance_claim_list",
    "Extended Warranty & Service Contracts": "assets:asset_warranty_list",
},
```

---

## 7. Seeder Rows

In `apps/assets/management/commands/seed_assets.py`:
- Acme Corporation:
  - 3 `AssetWarranty` records (CNC Milling OEM warranty, CAT Generator extended warranty, Forklift fleet warranty).
  - 2 `AssetWarrantyClaim` records (Spindle bearing defect claim - settled; Alternator voltage regulator claim - submitted).
  - 2 `AssetInsurancePolicy` records (All-Risk Property & Plant Policy, Machinery Breakdown Special Peril Policy).
  - 2 `AssetInsuranceClaim` records (Transformer electrical surge loss claim - settled; Hydraulic press catastrophic seal failure - adjuster reviewing).
- Globex Corporation:
  - 2 `AssetWarranty` records, 1 `AssetWarrantyClaim`, 1 `AssetInsurancePolicy`, 1 `AssetInsuranceClaim`.
- Total: 5 Warranties, 3 Warranty Claims, 3 Insurance Policies, 3 Insurance Claims.
- Idempotency guard: checks existing records per tenant before creating.
