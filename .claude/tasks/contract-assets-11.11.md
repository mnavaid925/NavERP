# Contract — Sub-module 11.11: Compliance & Regulatory Management (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.11 Compliance & Regulatory Management • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-10 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending live `apps/assets/`. Incremental migration: `0013_...`.
- **Package Layout:** `AssetCompliance/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/assetcompliance/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AssetComplianceFramework` (`apps/assets/models/AssetCompliance/AssetComplianceFrameworks.py`)
- **Table:** `assets_assetcomplianceframework`
- **Number Prefix:** `ACF` (format: `ACF-YYYYMM-XXXX`)
- **CHOICES:**
  - `FRAMEWORK_TYPE_CHOICES = [('regulatory', 'Government Regulatory Mandate'), ('statutory', 'Statutory / Legal Code'), ('voluntary_standard', 'Voluntary Industry Standard (ISO/IEC)'), ('industry_code', 'Industry Engineering Code (ASME/NFPA)'), ('corporate_policy', 'Corporate Internal EHS Policy')]`
  - `STATUS_CHOICES = [('draft', 'Draft (Proposed)'), ('active', 'Active & Enforced'), ('under_review', 'Under Revision / Review'), ('deprecated', 'Deprecated / Superseded')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'active': 'badge-green', 'under_review': 'badge-amber', 'deprecated': 'badge-muted'}`
  - `FRAMEWORK_TYPE_CSS = {'regulatory': 'badge-red', 'statutory': 'badge-amber', 'voluntary_standard': 'badge-info', 'industry_code': 'badge-slate', 'corporate_policy': 'badge-muted'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='compliance_frameworks')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `name`: `CharField(max_length=255, help_text='Official standard or framework name')`
  - `code`: `CharField(max_length=50, help_text='Short standard code, e.g. OSHA-1910-PSM, ISO-55001')`
  - `framework_type`: `CharField(max_length=24, choices=FRAMEWORK_TYPE_CHOICES, default='regulatory')`
  - `regulatory_agency`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='compliance_frameworks', help_text='Enforcing agency or standard body')`
  - `applicable_category`: `ForeignKey('assets.AssetCategory', on_delete=SET_NULL, null=True, blank=True, related_name='compliance_frameworks', help_text='Asset category governed by this framework')`
  - `effective_date`: `DateField(default=timezone.now)`
  - `revision`: `CharField(max_length=50, default='Current', help_text='Standard edition or revision identifier')`
  - `mandatory_audit_cycle_months`: `PositiveIntegerField(default=12, help_text='Mandatory compliance review frequency in months')`
  - `readiness_score`: `PositiveIntegerField(default=100, help_text='Compliance readiness rating percentage (0-100)')`
  - `description`: `TextField(blank=True, help_text='Detailed scope, mandate requirements, and compliance objectives')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_acf_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_acf_ten_stat')`
  - `Index(fields=['tenant', 'framework_type'], name='idx_acf_ten_type')`
  - `Index(fields=['tenant', 'code'], name='idx_acf_ten_code')`
- **Helper Properties:**
  - `is_active`: returns `status == 'active'`
  - `is_audit_due`: returns whether next scheduled review is within 30 days

---

### 1.2 `AssetComplianceAudit` (`apps/assets/models/AssetCompliance/AssetComplianceAudits.py`)
- **Table:** `assets_assetcomplianceaudit`
- **Number Prefix:** `ACA` (format: `ACA-YYYYMM-XXXX`)
- **CHOICES:**
  - `AUDIT_TYPE_CHOICES = [('internal', 'Internal Periodic Compliance Audit'), ('external_regulatory', 'External Statutory / Agency Inspection'), ('third_party_certification', 'Third-Party ISO / Registrar Audit'), ('customer_qualification', 'Customer / Supplier EHS Qualification')]`
  - `COMPLIANCE_RATING_CHOICES = [('fully_compliant', 'Fully Compliant (No Findings)'), ('minor_deficiencies', 'Substantially Compliant (Minor Deficiencies)'), ('major_non_conformance', 'Major Non-Conformance (Action Required)'), ('critical_breach', 'Critical Breach / Imminent Danger'), ('not_rated', 'Not Rated / In Progress')]`
  - `STATUS_CHOICES = [('scheduled', 'Audit Scheduled'), ('in_progress', 'Audit Fieldwork In Progress'), ('under_review', 'Audit Findings Under Review'), ('completed', 'Audit Completed & Signed Off'), ('cancelled', 'Audit Cancelled')]`
  - `STATUS_CSS = {'scheduled': 'badge-slate', 'in_progress': 'badge-info', 'under_review': 'badge-amber', 'completed': 'badge-green', 'cancelled': 'badge-muted'}`
  - `COMPLIANCE_RATING_CSS = {'fully_compliant': 'badge-green', 'minor_deficiencies': 'badge-amber', 'major_non_conformance': 'badge-red', 'critical_breach': 'badge-red', 'not_rated': 'badge-slate'}`
  - `AUDIT_TYPE_CSS = {'internal': 'badge-info', 'external_regulatory': 'badge-red', 'third_party_certification': 'badge-green', 'customer_qualification': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='compliance_audits')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='Descriptive title of audit or statutory inspection')`
  - `framework`: `ForeignKey('assets.AssetComplianceFramework', on_delete=PROTECT, related_name='audits', help_text='Governing compliance standard evaluated')`
  - `asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='compliance_audits', help_text='Subject operational plant equipment or facility')`
  - `audit_type`: `CharField(max_length=30, choices=AUDIT_TYPE_CHOICES, default='internal')`
  - `lead_auditor_user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='led_compliance_audits', help_text='Internal lead auditor or EHS compliance officer')`
  - `auditor_party`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='conducted_asset_audits', help_text='External registrar, certified audit firm, or agency inspector')`
  - `audit_date`: `DateField(default=timezone.now)`
  - `scope_description`: `TextField(blank=True, help_text='Boundaries of audit, operating units, and evaluated physical assets')`
  - `total_checkpoints`: `PositiveIntegerField(default=0, help_text='Total evaluated checkpoints in compliance checklist')`
  - `passed_checkpoints`: `PositiveIntegerField(default=0, help_text='Checkpoints found fully conforming')`
  - `minor_findings_count`: `PositiveIntegerField(default=0, help_text='Minor deficiencies identified')`
  - `major_findings_count`: `PositiveIntegerField(default=0, help_text='Major non-conformances identified')`
  - `critical_findings_count`: `PositiveIntegerField(default=0, help_text='Critical safety breaches or imminent hazards identified')`
  - `compliance_rating`: `CharField(max_length=24, choices=COMPLIANCE_RATING_CHOICES, default='not_rated')`
  - `summary_findings`: `TextField(blank=True, help_text='Executive summary of findings, observations, and required remedial actions')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_aca_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_aca_ten_stat')`
  - `Index(fields=['tenant', 'audit_type'], name='idx_aca_ten_type')`
  - `Index(fields=['tenant', 'compliance_rating'], name='idx_aca_ten_rate')`
  - `Index(fields=['tenant', 'audit_date'], name='idx_aca_ten_adate')`
- **Actions / State Machine:**
  - `asset_compliance_audit_start`: transitions `scheduled -> in_progress`
  - `asset_compliance_audit_complete`: evaluates findings count, sets `completed_at = timezone.now()`, transitions `in_progress/under_review -> completed`

---

### 1.3 `AssetPermitLicense` (`apps/assets/models/AssetCompliance/AssetPermitLicenses.py`)
- **Table:** `assets_assetpermitlicense`
- **Number Prefix:** `APL` (format: `APL-YYYYMM-XXXX`)
- **CHOICES:**
  - `PERMIT_TYPE_CHOICES = [('environmental_emissions', 'Air Quality / Emissions Permit'), ('safety_operating', 'Plant Equipment Operating Certificate'), ('hazardous_material', 'Hazardous Materials Storage Permit'), ('water_discharge', 'NPDES / Industrial Wastewater Discharge'), ('pressure_vessel', 'Boiler & Pressure Vessel Certificate'), ('radiation_device', 'Radiation / X-Ray Source License'), ('municipal_zoning', 'Municipal Special Operations Permit'), ('transportation', 'DOT Hazmat Transport Certificate')]`
  - `STATUS_CHOICES = [('active', 'Active & Valid'), ('pending_renewal', 'Renewal Pending Approval'), ('under_review', 'Under Agency Review'), ('expired', 'Expired (Non-Compliant)'), ('suspended', 'Suspended by Regulator'), ('revoked', 'Revoked / Injunction')]`
  - `STATUS_CSS = {'active': 'badge-green', 'pending_renewal': 'badge-amber', 'under_review': 'badge-info', 'expired': 'badge-red', 'suspended': 'badge-red', 'revoked': 'badge-muted'}`
  - `PERMIT_TYPE_CSS = {'environmental_emissions': 'badge-amber', 'safety_operating': 'badge-green', 'hazardous_material': 'badge-red', 'water_discharge': 'badge-info', 'pressure_vessel': 'badge-slate', 'radiation_device': 'badge-red', 'municipal_zoning': 'badge-slate', 'transportation': 'badge-info'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='permits_licenses')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `permit_name`: `CharField(max_length=255, help_text='Official statutory permit or license title')`
  - `permit_number`: `CharField(max_length=100, help_text='Regulatory permit or license number issued by agency')`
  - `permit_type`: `CharField(max_length=30, choices=PERMIT_TYPE_CHOICES, default='safety_operating')`
  - `asset`: `ForeignKey('scm.Asset', on_delete=CASCADE, related_name='permits_licenses', help_text='Permitted plant machinery or physical asset')`
  - `issuing_authority`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='issued_asset_permits', help_text='Permitting authority or government agency')`
  - `issue_date`: `DateField(default=timezone.now)`
  - `effective_date`: `DateField(default=timezone.now)`
  - `expiration_date`: `DateField(help_text='Statutory license expiration date')`
  - `renewal_lead_days`: `PositiveIntegerField(default=60, help_text='Advance notice lead window for renewal alert in days')`
  - `renewal_fee`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Statutory renewal filing fee')`
  - `operating_conditions`: `TextField(blank=True, help_text='Mandated operating conditions, capacity thresholds, and monitoring limits')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_apl_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_apl_ten_stat')`
  - `Index(fields=['tenant', 'permit_type'], name='idx_apl_ten_type')`
  - `Index(fields=['tenant', 'expiration_date'], name='idx_apl_ten_exp')`
  - `Index(fields=['tenant', 'asset'], name='idx_apl_ten_ast')`
- **Actions / State Machine:**
  - `asset_permit_license_renew`: records renewal submission and updates status

---

### 1.4 `AssetComplianceIncident` (`apps/assets/models/AssetCompliance/AssetComplianceIncidents.py`)
- **Table:** `assets_assetcomplianceincident`
- **Number Prefix:** `ACI` (format: `ACI-YYYYMM-XXXX`)
- **CHOICES:**
  - `INCIDENT_TYPE_CHOICES = [('notice_of_violation', 'Formal Notice of Violation (NOV)'), ('regulatory_citation', 'Statutory Agency Citation'), ('emissions_exceedance', 'Air / Water Discharge Exceedance'), ('unpermitted_discharge', 'Unpermitted Chemical / Fluid Spill'), ('safety_infraction', 'OSHA Safety Violation / Guarding Issue'), ('failed_inspection', 'Failed Regulatory Inspection'), ('internal_audit_breach', 'Internal Compliance Audit Failure')]`
  - `SEVERITY_CHOICES = [('de_minimis', 'De Minimis (Administrative / Advisory)'), ('other_than_serious', 'Other-Than-Serious (Low Direct Impact)'), ('serious', 'Serious (Substantial Probability of Harm)'), ('repeat', 'Repeat Infraction'), ('willful', 'Willful / Intentional Non-Compliance'), ('imminent_danger', 'Imminent Danger / Stop-Work Order')]`
  - `ROOT_CAUSE_CHOICES = [('mechanical_failure', 'Equipment / Mechanical Component Failure'), ('human_error', 'Operator Error / Procedural Drift'), ('inadequate_procedure', 'Inadequate SOP / Training Deficiency'), ('lack_of_maintenance', 'Deferred Maintenance / Missed Inspection'), ('measurement_error', 'Instrumentation / Sensor Calibration Error'), ('external_factor', 'Extreme Weather / External Contractor Factor')]`
  - `STATUS_CHOICES = [('open', 'Open (Reported)'), ('under_investigation', 'Under Root Cause Investigation'), ('capa_in_progress', 'CAPA Remediation In Progress'), ('under_agency_review', 'CAPA Submitted for Agency Review'), ('appealed', 'Formal Administrative Appeal Filed'), ('resolved', 'Resolved (CAPA Verified)'), ('closed', 'Closed & Settled')]`
  - `STATUS_CSS = {'open': 'badge-red', 'under_investigation': 'badge-amber', 'capa_in_progress': 'badge-info', 'under_agency_review': 'badge-amber', 'appealed': 'badge-slate', 'resolved': 'badge-green', 'closed': 'badge-muted'}`
  - `SEVERITY_CSS = {'de_minimis': 'badge-slate', 'other_than_serious': 'badge-info', 'serious': 'badge-amber', 'repeat': 'badge-red', 'willful': 'badge-red', 'imminent_danger': 'badge-red'}`
  - `INCIDENT_TYPE_CSS = {'notice_of_violation': 'badge-red', 'regulatory_citation': 'badge-red', 'emissions_exceedance': 'badge-amber', 'unpermitted_discharge': 'badge-red', 'safety_infraction': 'badge-amber', 'failed_inspection': 'badge-info', 'internal_audit_breach': 'badge-slate'}`
  - `ROOT_CAUSE_CSS = {'mechanical_failure': 'badge-amber', 'human_error': 'badge-slate', 'inadequate_procedure': 'badge-info', 'lack_of_maintenance': 'badge-red', 'measurement_error': 'badge-slate', 'external_factor': 'badge-muted'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='compliance_incidents')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='Brief summary of violation or non-compliance event')`
  - `incident_date`: `DateTimeField(default=timezone.now, help_text='Date and time violation occurred')`
  - `discovery_date`: `DateField(default=timezone.now, help_text='Date cited or internally discovered')`
  - `incident_type`: `CharField(max_length=30, choices=INCIDENT_TYPE_CHOICES, default='safety_infraction')`
  - `severity`: `CharField(max_length=24, choices=SEVERITY_CHOICES, default='serious')`
  - `asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='compliance_incidents', help_text='Cited operational equipment or plant asset')`
  - `permit`: `ForeignKey('assets.AssetPermitLicense', on_delete=SET_NULL, null=True, blank=True, related_name='incidents', help_text='Violated permit or operating certificate')`
  - `audit`: `ForeignKey('assets.AssetComplianceAudit', on_delete=SET_NULL, null=True, blank=True, related_name='incidents', help_text='Source audit that identified non-compliance')`
  - `enforcement_agency`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='cited_compliance_incidents', help_text='Issuing regulatory enforcement authority')`
  - `citation_reference`: `CharField(max_length=100, blank=True, help_text='Statutory docket, citation, or ticket number')`
  - `fine_assessed`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Monetary fine or penalty assessed by regulator')`
  - `fine_paid`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Penalty amount paid to date')`
  - `fine_payment_date`: `DateField(null=True, blank=True, help_text='Settlement payment confirmation date')`
  - `root_cause`: `CharField(max_length=30, choices=ROOT_CAUSE_CHOICES, default='mechanical_failure')`
  - `root_cause_analysis`: `TextField(blank=True, help_text='Detailed root cause investigation analysis')`
  - `corrective_action_plan`: `TextField(blank=True, help_text='Mandated CAPA remediation and prevention plan')`
  - `assigned_investigator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='investigated_compliance_incidents', help_text='Lead investigator or remediation manager')`
  - `target_resolution_date`: `DateField(null=True, blank=True)`
  - `actual_resolution_date`: `DateField(null=True, blank=True)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default='open')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_aci_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_aci_ten_stat')`
  - `Index(fields=['tenant', 'severity'], name='idx_aci_ten_sev')`
  - `Index(fields=['tenant', 'incident_type'], name='idx_aci_ten_type')`
  - `Index(fields=['tenant', 'incident_date'], name='idx_aci_ten_idate')`
  - `Index(fields=['tenant', 'asset'], name='idx_aci_ten_ast')`
- **Actions / State Machine:**
  - `asset_compliance_incident_resolve`: verifies CAPA, sets `actual_resolution_date = timezone.now().date()`, transitions to `resolved`
  - `asset_compliance_incident_close`: marks incident formally closed

---

## 2. Forms Contract & Exclusions

All forms live under `apps/assets/forms/AssetCompliance/<Entity>.py`. Forms exclude tenant, auto-number, auto-timestamps, and internal workflow timestamps.

| Entity | Form Class | Excluded Fields | Required Fields & Widgets |
|---|---|---|---|
| `AssetComplianceFramework` | `AssetComplianceFrameworkForm` | `tenant`, `number`, `created_at`, `updated_at` | `name`, `code`, `framework_type`, `status`. DateInput for `effective_date`. Textarea for `description`. |
| `AssetComplianceAudit` | `AssetComplianceAuditForm` | `tenant`, `number`, `completed_at`, `created_at`, `updated_at` | `title`, `framework`, `audit_type`, `audit_date`, `status`. DateInput for `audit_date`. Textarea for `scope_description`, `summary_findings`. |
| `AssetPermitLicense` | `AssetPermitLicenseForm` | `tenant`, `number`, `created_at`, `updated_at` | `permit_name`, `permit_number`, `permit_type`, `asset`, `expiration_date`, `status`. DateInput for `issue_date`, `effective_date`, `expiration_date`. |
| `AssetComplianceIncident` | `AssetComplianceIncidentForm` | `tenant`, `number`, `actual_resolution_date`, `created_at`, `updated_at` | `title`, `incident_type`, `severity`, `incident_date`, `status`. DateTimeInput for `incident_date`, DateInput for `discovery_date`, `fine_payment_date`, `target_resolution_date`. |

---

## 3. URLs Contract

App name is `assets`. All routes registered in `apps/assets/urls/AssetCompliance/<Entity>.py` and re-exported in `apps/assets/urls/__init__.py`.

### 3.1 `AssetComplianceFramework`
- `assets:asset_compliance_framework_list` -> `/assets/compliance/frameworks/`
- `assets:asset_compliance_framework_create` -> `/assets/compliance/frameworks/create/`
- `assets:asset_compliance_framework_detail` -> `/assets/compliance/frameworks/<int:pk>/`
- `assets:asset_compliance_framework_edit` -> `/assets/compliance/frameworks/<int:pk>/edit/`
- `assets:asset_compliance_framework_delete` -> `/assets/compliance/frameworks/<int:pk>/delete/`

### 3.2 `AssetComplianceAudit`
- `assets:asset_compliance_audit_list` -> `/assets/compliance/audits/`
- `assets:asset_compliance_audit_create` -> `/assets/compliance/audits/create/`
- `assets:asset_compliance_audit_detail` -> `/assets/compliance/audits/<int:pk>/`
- `assets:asset_compliance_audit_edit` -> `/assets/compliance/audits/<int:pk>/edit/`
- `assets:asset_compliance_audit_delete` -> `/assets/compliance/audits/<int:pk>/delete/`
- `assets:asset_compliance_audit_start` -> `/assets/compliance/audits/<int:pk>/start/` (POST)
- `assets:asset_compliance_audit_complete` -> `/assets/compliance/audits/<int:pk>/complete/` (POST)

### 3.3 `AssetPermitLicense`
- `assets:asset_permit_license_list` -> `/assets/compliance/permits/`
- `assets:asset_permit_license_create` -> `/assets/compliance/permits/create/`
- `assets:asset_permit_license_detail` -> `/assets/compliance/permits/<int:pk>/`
- `assets:asset_permit_license_edit` -> `/assets/compliance/permits/<int:pk>/edit/`
- `assets:asset_permit_license_delete` -> `/assets/compliance/permits/<int:pk>/delete/`
- `assets:asset_permit_license_renew` -> `/assets/compliance/permits/<int:pk>/renew/` (POST)

### 3.4 `AssetComplianceIncident`
- `assets:asset_compliance_incident_list` -> `/assets/compliance/incidents/`
- `assets:asset_compliance_incident_create` -> `/assets/compliance/incidents/create/`
- `assets:asset_compliance_incident_detail` -> `/assets/compliance/incidents/<int:pk>/`
- `assets:asset_compliance_incident_edit` -> `/assets/compliance/incidents/<int:pk>/edit/`
- `assets:asset_compliance_incident_delete` -> `/assets/compliance/incidents/<int:pk>/delete/`
- `assets:asset_compliance_incident_resolve` -> `/assets/compliance/incidents/<int:pk>/resolve/` (POST)
- `assets:asset_compliance_incident_close` -> `/assets/compliance/incidents/<int:pk>/close/` (POST)

---

## 4. View Context Keys Contract (L7 Pinned)

### 4.1 `AssetComplianceFramework`
- **List View (`asset_compliance_framework_list`):**
  - `frameworks`: Page object / queryset of `AssetComplianceFramework` records
  - `page_obj`: Django Paginator Page
  - `paginator`: Paginator instance
  - `is_paginated`: Boolean flag
  - `status_choices`: `AssetComplianceFramework.STATUS_CHOICES`
  - `type_choices`: `AssetComplianceFramework.FRAMEWORK_TYPE_CHOICES`
  - `category_list`: Tenant-scoped `AssetCategory.objects.filter(tenant=request.tenant)`
  - `total_frameworks`: Integer total count
  - `active_count`: Integer count where `status='active'`
  - `avg_readiness_score`: Float/Int average readiness score
- **Detail View (`asset_compliance_framework_detail`):**
  - `framework`: Subject `AssetComplianceFramework` instance
  - `audits`: Related audits queryset
  - `incidents`: Related incidents queryset
- **Form Views (Create/Edit):**
  - `form`: `AssetComplianceFrameworkForm`
  - `framework`: Subject instance (or `None` in create)
  - `is_edit`: Boolean

### 4.2 `AssetComplianceAudit`
- **List View (`asset_compliance_audit_list`):**
  - `audits`: Page object / queryset of `AssetComplianceAudit` records
  - `page_obj`: Django Paginator Page
  - `paginator`: Paginator instance
  - `is_paginated`: Boolean flag
  - `status_choices`: `AssetComplianceAudit.STATUS_CHOICES`
  - `type_choices`: `AssetComplianceAudit.AUDIT_TYPE_CHOICES`
  - `rating_choices`: `AssetComplianceAudit.COMPLIANCE_RATING_CHOICES`
  - `framework_list`: Tenant-scoped `AssetComplianceFramework.objects.filter(tenant=request.tenant)`
  - `total_audits`: Integer total count
  - `in_progress_count`: Integer count where `status='in_progress'`
  - `completed_count`: Integer count where `status='completed'`
  - `breaches_count`: Integer count where `compliance_rating in ['major_non_conformance', 'critical_breach']`
- **Detail View (`asset_compliance_audit_detail`):**
  - `audit`: Subject `AssetComplianceAudit` instance
  - `incidents`: Related incidents queryset
- **Form Views (Create/Edit):**
  - `form`: `AssetComplianceAuditForm`
  - `audit`: Subject instance (or `None` in create)
  - `is_edit`: Boolean

### 4.3 `AssetPermitLicense`
- **List View (`asset_permit_license_list`):**
  - `permits`: Page object / queryset of `AssetPermitLicense` records
  - `page_obj`: Django Paginator Page
  - `paginator`: Paginator instance
  - `is_paginated`: Boolean flag
  - `status_choices`: `AssetPermitLicense.STATUS_CHOICES`
  - `type_choices`: `AssetPermitLicense.PERMIT_TYPE_CHOICES`
  - `authority_list`: Tenant-scoped `Party.objects.filter(tenant=request.tenant)`
  - `total_permits`: Integer total count
  - `active_count`: Integer count where `status='active'`
  - `expiring_soon_count`: Integer count expiring within 60 days
  - `expired_count`: Integer count where `status='expired'`
- **Detail View (`asset_permit_license_detail`):**
  - `permit`: Subject `AssetPermitLicense` instance
  - `incidents`: Related incidents queryset
- **Form Views (Create/Edit):**
  - `form`: `AssetPermitLicenseForm`
  - `permit`: Subject instance (or `None` in create)
  - `is_edit`: Boolean

### 4.4 `AssetComplianceIncident`
- **List View (`asset_compliance_incident_list`):**
  - `incidents`: Page object / queryset of `AssetComplianceIncident` records
  - `page_obj`: Django Paginator Page
  - `paginator`: Paginator instance
  - `is_paginated`: Boolean flag
  - `status_choices`: `AssetComplianceIncident.STATUS_CHOICES`
  - `severity_choices`: `AssetComplianceIncident.SEVERITY_CHOICES`
  - `type_choices`: `AssetComplianceIncident.INCIDENT_TYPE_CHOICES`
  - `agency_list`: Tenant-scoped `Party.objects.filter(tenant=request.tenant)`
  - `total_incidents`: Integer total count
  - `open_count`: Integer count where `status in ['open', 'under_investigation', 'capa_in_progress']`
  - `critical_severity_count`: Integer count where `severity in ['serious', 'repeat', 'willful', 'imminent_danger']`
  - `total_fines_assessed`: Decimal sum of `fine_assessed`
  - `total_fines_paid`: Decimal sum of `fine_paid`
- **Detail View (`asset_compliance_incident_detail`):**
  - `incident`: Subject `AssetComplianceIncident` instance
- **Form Views (Create/Edit):**
  - `form`: `AssetComplianceIncidentForm`
  - `incident`: Subject instance (or `None` in create)
  - `is_edit`: Boolean

---

## 5. Navigation & Sidebar Wiring Contract

`apps/core/navigation.py` will receive `LIVE_LINKS["11.11"]`:

```python
    "11.11": {
        "Regulatory Standards Mapping": "assets:asset_compliance_framework_list",
        "Audit Preparation & Documentation": "assets:asset_compliance_audit_list",
        "Environmental & Safety Compliance": "assets:asset_compliance_incident_list",
        "License & Permit Tracking": "assets:asset_permit_license_list",
        "Penalty & Violation Management": "assets:asset_compliance_incident_list",
        # Plural and convenience aliases
        "Compliance Frameworks": "assets:asset_compliance_framework_list",
        "Regulatory Standards": "assets:asset_compliance_framework_list",
        "Compliance Audits": "assets:asset_compliance_audit_list",
        "Audit Preparation": "assets:asset_compliance_audit_list",
        "Operating Permits": "assets:asset_permit_license_list",
        "Permits & Licenses": "assets:asset_permit_license_list",
        "Compliance Incidents": "assets:asset_compliance_incident_list",
        "Notices of Violation": "assets:asset_compliance_incident_list",
        "Penalties & Violations": "assets:asset_compliance_incident_list",
    },
```

---

## 6. Seed Data Specifications

The command `apps/assets/management/commands/seed_assets.py` will be extended with:
- 3 `AssetComplianceFramework` records (OSHA 1910 PSM, ISO 55001 Asset Mgmt, EPA Title V Air Quality)
- 3 `AssetComplianceAudit` records (Internal ISO surveillance, Annual OSHA mechanical safety, EPA compliance inspection)
- 4 `AssetPermitLicense` records (Boiler Operating Certificate, Stationary Air Emissions Permit, Hazmat Storage Permit, Industrial Wastewater Discharge Permit)
- 3 `AssetComplianceIncident` records (Emissions exceedance warning, OSHA machine guarding deficiency, unpermitted solvent spill incident)
- Reuses existing `admin_acme` tenant, `admin_globex` tenant, existing `scm.Asset` rows, and `core.Party` regulatory authorities.
- Idempotent: checks `.exists()` per tenant before creating.
