# Module 11.16 Pre-Build Contract — Document & Knowledge Management (`apps/assets/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, download hardening header, `AuditLog.action` verb (`<= 10` chars),
> and `LIVE_LINKS["11.16"]` entry below is authoritative across backend, templates, smoke tests,
> reviews, and unit/security tests.

- **Parent App**: `apps.assets` (existing app; NO scaffold; NO `config/settings.py` or `config/urls.py` edit)
- **Previous Migration**: `0021_assetexecutivescorecard_idx_akpi_ten_org_and_more`
- **Next Migration**: `0022_...` (verify via `makemigrations assets --dry-run` in Phase 3.4)
- **Package Directories**:
  - `apps/assets/models/AssetDocumentKnowledge/`
  - `apps/assets/forms/AssetDocumentKnowledge/`
  - `apps/assets/views/AssetDocumentKnowledge/`
  - `apps/assets/urls/AssetDocumentKnowledge/`
  - `templates/assets/assetdocumentknowledge/{asset_document,asset_operating_procedure,asset_operator_certification,asset_knowledge_article}/`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, changes=..., tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"review"`, `"approve"`, `"draft"`, `"checkout"`, `"checkin"`, `"revise"`, `"archive"`, `"activate"`, `"retire"`, `"verify"`, `"ack_sop"`, `"renew"`, `"revoke"`, `"helpful"`, `"publish"`, `"sync_exp"` (every verb `<= 8` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & Views Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Never expose raw `{{ obj.file.url }}`, `{{ obj.attachment.url }}`, or `{{ obj.certificate_file.url }}`. All file downloads route through authenticated tenant-scoped download views emitting `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`.

---

## 1. Models & Choices Contract (`apps/assets/models/AssetDocumentKnowledge/`)

All 4 models inherit `apps.assets.models._base.TenantNumbered` (provides `tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, and collision-retrying `save()`).

### 1.1 `AssetDocument` (`AssetDocuments.py`)
- **`NUMBER_PREFIX`**: `"ADOC"`
- **`Meta.ordering`**: `["-updated_at", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Asset Document"` / `"Asset Documents"`
- **Choices & Badge Maps**:
  - `DOCUMENT_CLASS_CHOICES` (`max_length=32`, max value len 18):
    - `("manual", "OEM Operation & Service Manual")`
    - `("schematic_pid", "P&ID / Process Schematic")`
    - `("electrical_diagram", "Electrical / Wiring Diagram")`
    - `("datasheet", "Technical Datasheet / Spec")`
    - `("warranty_cert", "Warranty Certificate")`
    - `("calibration_cert", "Calibration Certificate")`
    - `("compliance_cert", "Regulatory / Safety Certificate")`
    - `("inspection_dossier", "Inspection & NDT Dossier")`
    - `("vendor_transmittal", "Vendor Submittal / Transmittal")`
    - `("as_built_drawing", "As-Built Engineering Drawing")`
  - `ACCESS_CLASSIFICATION_CHOICES` (`max_length=24`, max value len 14):
    - `("public_floor", "Shop Floor / Public")`
    - `("internal_tech", "Internal Technical")`
    - `("restricted_eng", "Restricted Engineering")`
    - `("confidential", "Confidential / Vendor NDA")`
  - `CHANGE_TYPE_CHOICES` (`max_length=24`, max value len 18):
    - `("new_issue", "Initial Controlled Issue")`
    - `("drawing_redline", "Field Drawing Redline")`
    - `("spec_update", "Engineering Spec Update")`
    - `("vendor_bulletin", "OEM Service Bulletin")`
    - `("regulatory_update", "Regulatory Compliance Update")`
    - `("as_built_reconcile", "As-Built Reconciliation")`
  - `STATUS_CHOICES` (`max_length=20`, max value len 10):
    - `("draft", "Draft")`
    - `("in_review", "In Review")`
    - `("approved", "Approved / Released")`
    - `("superseded", "Superseded")`
    - `("archived", "Archived")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`, `"in_review": "badge-amber"`, `"approved": "badge-green"`, `"superseded": "badge-muted"`, `"archived": "badge-muted"`
  - `ACCESS_CLASSIFICATION_CSS`:
    - `"public_floor": "badge-green"`, `"internal_tech": "badge-info"`, `"restricted_eng": "badge-amber"`, `"confidential": "badge-red"`
  - `EDITABLE_STATUSES = {"draft", "in_review"}`
  - `LOCKED_STATUSES = {"approved", "superseded", "archived"}`
- **Fields**:
  - `title`: `CharField(max_length=200)`
  - `document_class`: `CharField(max_length=32, choices=DOCUMENT_CLASS_CHOICES, default="manual")`
  - `access_classification`: `CharField(max_length=24, choices=ACCESS_CLASSIFICATION_CHOICES, default="internal_tech")`
  - `tag_code`: `CharField(max_length=80, blank=True)`
  - `manufacturer_ref`: `CharField(max_length=120, blank=True)`
  - `document_language`: `CharField(max_length=32, default="en")`
  - `storage_location_ref`: `CharField(max_length=160, blank=True)`
  - `file`: `FileField(upload_to="assets/documents/%Y/%m/", blank=True, null=True)`
  - `original_filename`: `CharField(max_length=255, blank=True, editable=False)`
  - `file_size_bytes`: `PositiveBigIntegerField(default=0, editable=False)`
  - `file_checksum`: `CharField(max_length=64, blank=True, editable=False)`
  - `revision_label`: `CharField(max_length=24, default="Rev A")`
  - `revision_sequence`: `PositiveIntegerField(default=1, editable=False)`
  - `supersedes`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="superseded_by_revisions")`
  - `is_current_revision`: `BooleanField(default=True, editable=False)`
  - `change_request_ref`: `CharField(max_length=64, blank=True)`
  - `change_type`: `CharField(max_length=24, choices=CHANGE_TYPE_CHOICES, default="new_issue")`
  - `redline_summary`: `TextField(blank=True)`
  - `spec_delta_notes`: `TextField(blank=True)`
  - `checked_out_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="checked_out_asset_documents")`
  - `checked_out_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `effective_date`: `DateField(null=True, blank=True)`
  - `expiry_date`: `DateField(null=True, blank=True)`
  - `retention_years`: `PositiveSmallIntegerField(null=True, blank=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", editable=False)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="owned_asset_documents")`
  - `reviewer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_asset_documents")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="approved_asset_documents")`
  - `approved_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `review_notes`: `TextField(blank=True)`
  - `description`: `TextField(blank=True)`
  - **Tenant-Scoped Verified FKs**:
    - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_documents")`
    - `operational_asset`: `ForeignKey("scm.Asset", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_documents")`
    - `fixed_asset`: `ForeignKey("accounting.FixedAsset", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_documents")`
    - `asset_model`: `ForeignKey("assets.AssetModel", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_documents")`
    - `asset_category`: `ForeignKey("assets.AssetCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_documents")`
    - `specification_template`: `ForeignKey("assets.AssetSpecificationTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_documents")`
    - `warranty`: `ForeignKey("assets.AssetWarranty", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_documents")`
    - `compliance_framework`: `ForeignKey("assets.AssetComplianceFramework", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_documents")`
    - `vendor_party`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="vendor_asset_documents")`
    - `core_document`: `ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_document_records")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_adoc_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_adoc_ten_stat")`
  - `Index(fields=["tenant", "document_class"], name="idx_adoc_ten_cls")`
  - `Index(fields=["tenant", "operational_asset"], name="idx_adoc_ten_ast")`
  - `Index(fields=["tenant", "expiry_date"], name="idx_adoc_ten_exp")`
  - `Index(fields=["tenant", "is_current_revision"], name="idx_adoc_ten_cur")`
- **Properties & Methods**:
  - `status_badge_class`, `access_classification_badge_class`, `is_locked`, `is_expired`, `is_expiring_soon` (<= 30 days), `short_checksum` (`file_checksum[:12]` if set else `""`), `sync_file_metadata()` (computes `original_filename`, `file_size_bytes`, `file_checksum` if `file` present and unread/new).
  - `clean()`: validates `supersedes` not self & no cycle (max 25 hops), `expiry_date >= effective_date` when both set, `revision_sequence >= 1`, `validate_tenant_fks` on all 15 tenant/user FKs (`supersedes`, `checked_out_by`, `owner`, `reviewer`, `approved_by`, `org_unit`, `operational_asset`, `fixed_asset`, `asset_model`, `asset_category`, `specification_template`, `warranty`, `compliance_framework`, `vendor_party`, `core_document`).
  - `__str__`: `f"{self.number} · {self.title} ({self.revision_label})"` if `self.number` else `self.title`.

### 1.2 `AssetOperatingProcedure` (`AssetOperatingProcedures.py`)
- **`NUMBER_PREFIX`**: `"ASOP"`
- **`Meta.ordering`**: `["-updated_at", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Asset Operating Procedure"` / `"Asset Operating Procedures"`
- **Choices & Badge Maps**:
  - `PROCEDURE_TYPE_CHOICES` (`max_length=28`, max value len 20):
    - `("sop_operation", "Standard Operating Procedure")`
    - `("pm_protocol", "Preventive Maintenance Protocol")`
    - `("loto_isolation", "Lockout / Tagout (LOTO) Isolation")`
    - `("emergency_shutdown", "Emergency Shutdown & E-Stop")`
    - `("commissioning", "Commissioning & Startup")`
    - `("calibration_protocol", "Calibration Protocol")`
    - `("inspection_checklist", "Safety Inspection Checklist")`
  - `SAFETY_LEVEL_CHOICES` (`max_length=24`, max value len 16):
    - `("standard", "Standard Operations")`
    - `("caution", "Caution — PPE Required")`
    - `("high_hazard_loto", "High Hazard — LOTO Mandatory")`
    - `("permit_required", "Permit-to-Work Required")`
  - `STATUS_CHOICES` (`max_length=20`, max value len 12):
    - `("draft", "Draft")`
    - `("under_review", "Under Safety Review")`
    - `("active", "Active / Controlled")`
    - `("superseded", "Superseded")`
    - `("retired", "Retired")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`, `"under_review": "badge-amber"`, `"active": "badge-green"`, `"superseded": "badge-muted"`, `"retired": "badge-muted"`
  - `SAFETY_CSS`:
    - `"standard": "badge-slate"`, `"caution": "badge-info"`, `"high_hazard_loto": "badge-red"`, `"permit_required": "badge-amber"`
  - `EDITABLE_STATUSES = {"draft", "under_review"}`
  - `LOCKED_STATUSES = {"active", "superseded", "retired"}`
- **Fields**:
  - `title`: `CharField(max_length=200)`
  - `procedure_type`: `CharField(max_length=28, choices=PROCEDURE_TYPE_CHOICES, default="sop_operation")`
  - `safety_level`: `CharField(max_length=24, choices=SAFETY_LEVEL_CHOICES, default="standard")`
  - `revision_label`: `CharField(max_length=24, default="Rev 1.0")`
  - `supersedes`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="superseded_by_procedures")`
  - `purpose_scope`: `TextField(blank=True)`
  - `hazard_warnings`: `TextField(blank=True)`
  - `required_ppe`: `CharField(max_length=255, blank=True)`
  - `loto_required`: `BooleanField(default=False)`
  - `loto_isolation_points`: `JSONField(default=list, blank=True)` *(list of dicts with `energy_source`, `tag_id`, `isolation_point`, `lock_device`, `verification_step`)*
  - `procedure_steps`: `JSONField(default=list, blank=True)` *(list of dicts with `step_no`, `title`, `instruction`, `expected_reading`, `is_mandatory_signoff`)*
  - `required_qualification_code`: `CharField(max_length=64, blank=True)`
  - `estimated_duration_minutes`: `PositiveIntegerField(default=30)`
  - `attachment`: `FileField(upload_to="assets/procedures/%Y/%m/", blank=True, null=True)`
  - `original_filename`: `CharField(max_length=255, blank=True, editable=False)`
  - `file_checksum`: `CharField(max_length=64, blank=True, editable=False)`
  - `effective_date`: `DateField(null=True, blank=True)`
  - `review_cycle_months`: `PositiveSmallIntegerField(default=12)`
  - `next_review_date`: `DateField(null=True, blank=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", editable=False)`
  - `author`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="authored_asset_procedures")`
  - `safety_reviewer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="safety_reviewed_asset_procedures")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="approved_asset_procedures")`
  - `approved_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `review_notes`: `TextField(blank=True)`
  - **Tenant-Scoped Verified FKs**:
    - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operating_procedures")`
    - `operational_asset`: `ForeignKey("scm.Asset", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operating_procedures")`
    - `asset_category`: `ForeignKey("assets.AssetCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operating_procedures")`
    - `asset_model`: `ForeignKey("assets.AssetModel", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operating_procedures")`
    - `maintenance_schedule`: `ForeignKey("assets.AssetMaintenanceSchedule", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operating_procedures")`
    - `compliance_framework`: `ForeignKey("assets.AssetComplianceFramework", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operating_procedures")`
    - `primary_document`: `ForeignKey("assets.AssetDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="operating_procedures")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_asop_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_asop_ten_stat")`
  - `Index(fields=["tenant", "procedure_type"], name="idx_asop_ten_type")`
  - `Index(fields=["tenant", "safety_level"], name="idx_asop_ten_haz")`
  - `Index(fields=["tenant", "next_review_date"], name="idx_asop_ten_rev")`
- **Properties & Methods**:
  - `status_badge_class`, `safety_badge_class`, `is_locked`, `is_review_overdue` (`bool(self.next_review_date and self.next_review_date < timezone.localdate() and self.status == "active")`), `step_count` (`len(self.procedure_steps or [])`), `isolation_point_count` (`len(self.loto_isolation_points or [])`).
  - `clean()`: validates `supersedes` no self-reference & no cycle, `estimated_duration_minutes >= 1`, `review_cycle_months >= 1`, `next_review_date >= effective_date` when both set, `procedure_steps` (list of dicts <= 100 items), `loto_isolation_points` (list of dicts <= 50 items), `validate_tenant_fks` across all 11 tenant/user FKs.
  - `__str__`: `f"{self.number} · {self.title} ({self.revision_label})"` if `self.number` else `self.title`.

### 1.3 `AssetOperatorCertification` (`AssetOperatorCertifications.py`)
- **`NUMBER_PREFIX`**: `"AOCT"`
- **`Meta.ordering`**: `["expires_on", "-issued_date", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Asset Operator Certification"` / `"Asset Operator Certifications"`
- **Choices & Badge Maps**:
  - `QUALIFICATION_TYPE_CHOICES` (`max_length=28`, max value len 22):
    - `("equipment_operator", "Equipment Operator")`
    - `("maintenance_technician", "Maintenance Technician")`
    - `("loto_authorized", "LOTO Authorized Person")`
    - `("electrical_hv", "High-Voltage Electrical")`
    - `("confined_space", "Confined Space Entry")`
    - `("crane_rigging", "Crane & Rigging Operations")`
    - `("pressure_welding", "Pressure Vessel / Welding")`
    - `("calibration_specialist", "Calibration Specialist")`
    - `("oem_certified", "OEM Certified Specialist")`
  - `PROFICIENCY_LEVEL_CHOICES` (`max_length=24`, max value len 18):
    - `("trainee_supervised", "Trainee (Supervised)")`
    - `("qualified_operator", "Qualified Operator")`
    - `("senior_technician", "Senior Technician")`
    - `("lead_inspector", "Lead Inspector / SME")`
    - `("trainer_assessor", "Certified Trainer / Assessor")`
  - `STATUS_CHOICES` (`max_length=20`, max value len 13):
    - `("pending", "Pending Verification")`
    - `("active", "Active / Certified")`
    - `("expiring_soon", "Expiring Soon")`
    - `("expired", "Expired")`
    - `("revoked", "Revoked")`
  - `STATUS_CSS`:
    - `"pending": "badge-slate"`, `"active": "badge-green"`, `"expiring_soon": "badge-amber"`, `"expired": "badge-red"`, `"revoked": "badge-muted"`
  - `PROFICIENCY_CSS`:
    - `"trainee_supervised": "badge-slate"`, `"qualified_operator": "badge-info"`, `"senior_technician": "badge-green"`, `"lead_inspector": "badge-amber"`, `"trainer_assessor": "badge-green"`
- **Fields**:
  - `title`: `CharField(max_length=200)`
  - `qualification_code`: `CharField(max_length=64, blank=True)`
  - `qualification_type`: `CharField(max_length=28, choices=QUALIFICATION_TYPE_CHOICES, default="equipment_operator")`
  - `proficiency_level`: `CharField(max_length=24, choices=PROFICIENCY_LEVEL_CHOICES, default="qualified_operator")`
  - `issuing_authority`: `CharField(max_length=150, blank=True)`
  - `certificate_reference`: `CharField(max_length=80, blank=True)`
  - `certificate_file`: `FileField(upload_to="assets/certifications/%Y/%m/", blank=True, null=True)`
  - `original_filename`: `CharField(max_length=255, blank=True, editable=False)`
  - `file_checksum`: `CharField(max_length=64, blank=True, editable=False)`
  - `issued_date`: `DateField(default=timezone.localdate)`
  - `expires_on`: `DateField(null=True, blank=True)`
  - `renewal_lead_days`: `PositiveSmallIntegerField(default=30)`
  - `last_assessed_date`: `DateField(null=True, blank=True)`
  - `training_hours`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
  - `assessment_score`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`
  - `sop_acknowledged`: `BooleanField(default=False, editable=False)`
  - `sop_acknowledged_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `notes`: `TextField(blank=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="pending", editable=False)`
  - **Tenant-Scoped Verified FKs**:
    - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operator_certifications")`
    - `operator_party`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="operator_asset_certifications")`
    - `operator_user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operator_certifications")`
    - `employee_profile`: `ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operator_certifications")`
    - `hrm_certificate`: `ForeignKey("hrm.TrainingCertificate", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operator_certifications")`
    - `issuing_party`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_asset_certifications")`
    - `assessor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assessed_asset_certifications")`
    - `operational_asset`: `ForeignKey("scm.Asset", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operator_certifications")`
    - `asset_category`: `ForeignKey("assets.AssetCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operator_certifications")`
    - `asset_model`: `ForeignKey("assets.AssetModel", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operator_certifications")`
    - `operating_procedure`: `ForeignKey("assets.AssetOperatingProcedure", on_delete=models.SET_NULL, null=True, blank=True, related_name="operator_certifications")`
    - `compliance_framework`: `ForeignKey("assets.AssetComplianceFramework", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_operator_certifications")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_aoct_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_aoct_ten_stat")`
  - `Index(fields=["tenant", "qualification_type"], name="idx_aoct_ten_type")`
  - `Index(fields=["tenant", "expires_on"], name="idx_aoct_ten_exp")`
  - `Index(fields=["tenant", "operator_user"], name="idx_aoct_ten_usr")`
  - `Index(fields=["tenant", "operator_party"], name="idx_aoct_ten_pty")`
- **Properties, Methods & Helper**:
  - `days_until_expiry` (`(self.expires_on - timezone.localdate()).days` if `self.expires_on` else `None`)
  - `is_expired` (`bool(self.expires_on and self.expires_on < timezone.localdate())`)
  - `is_renewal_due` (`bool(self.expires_on and not self.is_expired and self.days_until_expiry <= self.renewal_lead_days)`)
  - `operator_display_name` (checks `operator_party`, `employee_profile`, `operator_user`, fallback `"—"`)
  - `status_badge_class`, `proficiency_badge_class`
  - `sync_expiry_status(save=True)`: for `status in ("active", "expiring_soon", "expired")`, flips to `"expired"` if `expires_on < today`, `"expiring_soon"` if `0 <= days <= renewal_lead_days`, `"active"` otherwise; returns `True` if changed.
  - Module-level helper `is_operator_certified(tenant, *, user=None, party=None, operational_asset=None, asset_category=None, qualification_code=None, as_of=None)`: returns `True` iff a tenant-scoped cert with `status in ("active", "expiring_soon")` and non-expired date (`expires_on is None or expires_on >= today`) matches the given operator & scope.
  - `clean()`: requires at least one of `operator_party`, `operator_user`, or `employee_profile`; `expires_on >= issued_date`; `training_hours >= 0`; `0 <= assessment_score <= 100`; `renewal_lead_days >= 1`; `validate_tenant_fks` across all 12 tenant/user FKs.

### 1.4 `AssetKnowledgeArticle` (`AssetKnowledgeArticles.py`)
- **`NUMBER_PREFIX`**: `"AKBA"`
- **`Meta.ordering`**: `["-published_at", "-updated_at", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Asset Knowledge Article"` / `"Asset Knowledge Articles"`
- **Choices & Badge Maps**:
  - `ARTICLE_TYPE_CHOICES` (`max_length=28`, max value len 21):
    - `("rca_post_incident", "Post-Incident RCA")`
    - `("lessons_learned", "Lessons Learned")`
    - `("troubleshooting_guide", "Troubleshooting Guide")`
    - `("failure_bulletin", "Failure Alert Bulletin")`
    - `("oem_service_advisory", "OEM Service Advisory")`
    - `("pm_optimization_note", "PM Optimization Note")`
  - `RCA_METHODOLOGY_CHOICES` (`max_length=28`, max value len 20):
    - `("five_whys", "5-Why Analysis")`
    - `("fishbone_ishikawa", "Fishbone / Ishikawa (6M)")`
    - `("problem_cause_remedy", "Problem-Cause-Remedy")`
    - `("fmea_feedback", "FMEA Feedback Loop")`
    - `("fault_tree", "Fault Tree Analysis")`
    - `("general_kb", "General Knowledge Base")`
  - `SEVERITY_CHOICES` (`max_length=16`, max value len 8):
    - `("low", "Low")`
    - `("medium", "Medium")`
    - `("high", "High")`
    - `("critical", "Critical")`
  - `STATUS_CHOICES` (`max_length=20`, max value len 11):
    - `("draft", "Draft")`
    - `("peer_review", "Peer Review")`
    - `("published", "Published")`
    - `("retired", "Retired")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`, `"peer_review": "badge-amber"`, `"published": "badge-green"`, `"retired": "badge-muted"`
  - `SEVERITY_CSS`:
    - `"low": "badge-slate"`, `"medium": "badge-info"`, `"high": "badge-amber"`, `"critical": "badge-red"`
  - `EDITABLE_STATUSES = {"draft", "peer_review"}`
  - `LOCKED_STATUSES = {"published", "retired"}`
- **Fields**:
  - `title`: `CharField(max_length=200)`
  - `article_type`: `CharField(max_length=28, choices=ARTICLE_TYPE_CHOICES, default="lessons_learned")`
  - `rca_methodology`: `CharField(max_length=28, choices=RCA_METHODOLOGY_CHOICES, default="five_whys")`
  - `severity`: `CharField(max_length=16, choices=SEVERITY_CHOICES, default="medium")`
  - `symptom_problem`: `TextField()`
  - `root_cause_summary`: `TextField(blank=True)`
  - `five_whys`: `JSONField(default=list, blank=True)` *(list of dicts with `why_level`, `question`, `answer`)*
  - `contributing_factors`: `JSONField(default=dict, blank=True)` *(Fishbone 6M dict with keys in `{"machine", "method", "material", "manpower", "measurement", "environment"}`)*
  - `remedy_corrective_action`: `TextField(blank=True)`
  - `preventive_lessons`: `TextField(blank=True)`
  - `downtime_hours_impacted`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))`
  - `recurrence_count`: `PositiveIntegerField(default=1)`
  - `tags`: `CharField(max_length=255, blank=True)`
  - `helpful_votes`: `PositiveIntegerField(default=0, editable=False)`
  - `view_count`: `PositiveIntegerField(default=0, editable=False)`
  - `attachment`: `FileField(upload_to="assets/knowledge/%Y/%m/", blank=True, null=True)`
  - `original_filename`: `CharField(max_length=255, blank=True, editable=False)`
  - `file_checksum`: `CharField(max_length=64, blank=True, editable=False)`
  - `incident_occurred_on`: `DateField(null=True, blank=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", editable=False)`
  - `author`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="authored_asset_kb_articles")`
  - `reviewed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="reviewed_asset_kb_articles")`
  - `published_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - **Tenant-Scoped Verified FKs**:
    - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_knowledge_articles")`
    - `operational_asset`: `ForeignKey("scm.Asset", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_knowledge_articles")`
    - `fixed_asset`: `ForeignKey("accounting.FixedAsset", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_knowledge_articles")`
    - `asset_category`: `ForeignKey("assets.AssetCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_knowledge_articles")`
    - `asset_model`: `ForeignKey("assets.AssetModel", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_knowledge_articles")`
    - `failure_mode`: `ForeignKey("assets.AssetFailureMode", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_knowledge_articles")`
    - `maintenance_request`: `ForeignKey("assets.AssetMaintenanceRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_knowledge_articles")`
    - `maintenance_log`: `ForeignKey("assets.AssetMaintenanceLog", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_knowledge_articles")`
    - `incident_report`: `ForeignKey("assets.AssetIncidentReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_knowledge_articles")`
    - `compliance_incident`: `ForeignKey("assets.AssetComplianceIncident", on_delete=models.SET_NULL, null=True, blank=True, related_name="asset_knowledge_articles")`
    - `related_document`: `ForeignKey("assets.AssetDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="knowledge_articles")`
    - `recommended_procedure`: `ForeignKey("assets.AssetOperatingProcedure", on_delete=models.SET_NULL, null=True, blank=True, related_name="knowledge_articles")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_akba_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_akba_ten_stat")`
  - `Index(fields=["tenant", "article_type"], name="idx_akba_ten_type")`
  - `Index(fields=["tenant", "severity"], name="idx_akba_ten_sev")`
  - `Index(fields=["tenant", "rca_methodology"], name="idx_akba_ten_rca")`
  - `Index(fields=["tenant", "operational_asset"], name="idx_akba_ten_ast")`
- **Properties & Methods**:
  - `status_badge_class`, `severity_badge_class`, `is_locked`, `tag_list` (`[t.strip() for t in (self.tags or "").split(",") if t.strip()]`).
  - `clean()`: validates `downtime_hours_impacted >= 0`, `recurrence_count >= 1`, `five_whys` bounded list, `contributing_factors` Fishbone 6M dict, and `validate_tenant_fks` across all 14 tenant/user FKs.

---

## 2. Forms Contract (`apps/assets/forms/AssetDocumentKnowledge/`)

All 4 forms inherit `(TenantUniqueMixin, TenantModelForm)`, explicitly scope every tenant/user `ModelChoiceField` queryset in `__init__` (`.none()` if `self.tenant is None`), call `reject_foreign(...)` in `clean()`, and validate uploads with `validate_safe_doc_upload` (`ALLOWED_DOC_EXTENSIONS` + `MAX_UPLOAD_BYTES` from `apps.core.forms._common`).

1. **`AssetDocumentForm`**:
   - `Meta.fields`: `["title", "document_class", "access_classification", "tag_code", "manufacturer_ref", "document_language", "storage_location_ref", "file", "revision_label", "supersedes", "change_request_ref", "change_type", "redline_summary", "spec_delta_notes", "effective_date", "expiry_date", "retention_years", "reviewer", "review_notes", "description", "org_unit", "operational_asset", "fixed_asset", "asset_model", "asset_category", "specification_template", "warranty", "compliance_framework", "vendor_party", "core_document"]`
   - Excluded: `tenant`, `number`, `status`, `revision_sequence`, `is_current_revision`, `original_filename`, `file_size_bytes`, `file_checksum`, `checked_out_by`, `checked_out_at`, `owner`, `approved_by`, `approved_at`, `created_at`, `updated_at`.
2. **`AssetOperatingProcedureForm`**:
   - `Meta.fields`: `["title", "procedure_type", "safety_level", "revision_label", "supersedes", "purpose_scope", "hazard_warnings", "required_ppe", "loto_required", "loto_isolation_points", "procedure_steps", "required_qualification_code", "estimated_duration_minutes", "attachment", "effective_date", "review_cycle_months", "next_review_date", "safety_reviewer", "review_notes", "org_unit", "operational_asset", "asset_category", "asset_model", "maintenance_schedule", "compliance_framework", "primary_document"]`
   - Excluded: `tenant`, `number`, `status`, `author`, `approved_by`, `approved_at`, `original_filename`, `file_checksum`, `created_at`, `updated_at`.
   - `clean_loto_isolation_points()` & `clean_procedure_steps()` normalize `None`/`""` to `[]`.
3. **`AssetOperatorCertificationForm`**:
   - `Meta.fields`: `["title", "qualification_code", "qualification_type", "proficiency_level", "org_unit", "operator_party", "operator_user", "employee_profile", "hrm_certificate", "issuing_authority", "issuing_party", "certificate_reference", "certificate_file", "operational_asset", "asset_category", "asset_model", "operating_procedure", "compliance_framework", "issued_date", "expires_on", "renewal_lead_days", "last_assessed_date", "assessor", "training_hours", "assessment_score", "notes"]`
   - Excluded: `tenant`, `number`, `status`, `sop_acknowledged`, `sop_acknowledged_at`, `original_filename`, `file_checksum`, `created_at`, `updated_at`.
4. **`AssetKnowledgeArticleForm`**:
   - `Meta.fields`: `["title", "article_type", "rca_methodology", "severity", "symptom_problem", "root_cause_summary", "five_whys", "contributing_factors", "remedy_corrective_action", "preventive_lessons", "downtime_hours_impacted", "recurrence_count", "tags", "attachment", "incident_occurred_on", "org_unit", "operational_asset", "fixed_asset", "asset_category", "asset_model", "failure_mode", "maintenance_request", "maintenance_log", "incident_report", "compliance_incident", "related_document", "recommended_procedure"]`
   - Excluded: `tenant`, `number`, `status`, `author`, `reviewed_by`, `published_at`, `helpful_votes`, `view_count`, `original_filename`, `file_checksum`, `created_at`, `updated_at`.
   - `clean_five_whys()` normalizes `None`/`""` to `[]`; `clean_contributing_factors()` normalizes `None`/`""` to `{}`.

---

## 3. URL Routes & Views Contract (`apps/assets/urls/AssetDocumentKnowledge/` & `views/`)

All literal routes precede `<int:pk>/` routes. No greedy `<str:...>` converters.

### 3.1 `AssetDocuments.py` (prefix `documents/`)
- `documents/` -> `asset_document_list`
- `documents/changes/` -> `asset_document_change_list`
- `documents/create/` -> `asset_document_create`
- `documents/export-csv/` -> `asset_document_export_csv`
- `documents/<int:pk>/` -> `asset_document_detail`
- `documents/<int:pk>/edit/` -> `asset_document_edit`
- `documents/<int:pk>/delete/` (`@require_POST`, `@tenant_admin_required`) -> `asset_document_delete`
- `documents/<int:pk>/download/` -> `asset_document_download`
- `documents/<int:pk>/submit-review/` (`@require_POST`) -> `asset_document_submit_review`
- `documents/<int:pk>/approve-release/` (`@require_POST`, `@tenant_admin_required`) -> `asset_document_approve_release`
- `documents/<int:pk>/return-draft/` (`@require_POST`, `@tenant_admin_required`) -> `asset_document_return_to_draft`
- `documents/<int:pk>/checkout/` (`@require_POST`) -> `asset_document_checkout`
- `documents/<int:pk>/checkin/` (`@require_POST`) -> `asset_document_checkin`
- `documents/<int:pk>/create-revision/` (`@require_POST`) -> `asset_document_create_revision`
- `documents/<int:pk>/archive/` (`@require_POST`, `@tenant_admin_required`) -> `asset_document_archive`

### 3.2 `AssetOperatingProcedures.py` (prefix `procedures/`)
- `procedures/` -> `asset_operating_procedure_list`
- `procedures/create/` -> `asset_operating_procedure_create`
- `procedures/export-csv/` -> `asset_operating_procedure_export_csv`
- `procedures/<int:pk>/` -> `asset_operating_procedure_detail`
- `procedures/<int:pk>/print/` -> `asset_operating_procedure_print`
- `procedures/<int:pk>/edit/` -> `asset_operating_procedure_edit`
- `procedures/<int:pk>/delete/` (`@require_POST`, `@tenant_admin_required`) -> `asset_operating_procedure_delete`
- `procedures/<int:pk>/download/` -> `asset_operating_procedure_download`
- `procedures/<int:pk>/submit-review/` (`@require_POST`) -> `asset_operating_procedure_submit_review`
- `procedures/<int:pk>/activate/` (`@require_POST`, `@tenant_admin_required`) -> `asset_operating_procedure_activate`
- `procedures/<int:pk>/clone-revision/` (`@require_POST`) -> `asset_operating_procedure_clone_revision`
- `procedures/<int:pk>/retire/` (`@require_POST`, `@tenant_admin_required`) -> `asset_operating_procedure_retire`

### 3.3 `AssetOperatorCertifications.py` (prefix `certifications/`)
- `certifications/` -> `asset_operator_certification_list`
- `certifications/create/` -> `asset_operator_certification_create`
- `certifications/refresh-alerts/` (`@require_POST`, `@tenant_admin_required`) -> `asset_operator_certification_refresh_alerts`
- `certifications/export-csv/` -> `asset_operator_certification_export_csv`
- `certifications/<int:pk>/` -> `asset_operator_certification_detail`
- `certifications/<int:pk>/edit/` -> `asset_operator_certification_edit`
- `certifications/<int:pk>/delete/` (`@require_POST`, `@tenant_admin_required`) -> `asset_operator_certification_delete`
- `certifications/<int:pk>/download/` -> `asset_operator_certification_download`
- `certifications/<int:pk>/verify-activate/` (`@require_POST`, `@tenant_admin_required`) -> `asset_operator_certification_verify_activate`
- `certifications/<int:pk>/acknowledge-sop/` (`@require_POST`) -> `asset_operator_certification_acknowledge_sop`
- `certifications/<int:pk>/renew/` (`@require_POST`, `@tenant_admin_required`) -> `asset_operator_certification_renew`
- `certifications/<int:pk>/revoke/` (`@require_POST`, `@tenant_admin_required`) -> `asset_operator_certification_revoke`

### 3.4 `AssetKnowledgeArticles.py` (prefix `knowledge-base/`)
- `knowledge-base/` -> `asset_knowledge_article_list`
- `knowledge-base/create/` -> `asset_knowledge_article_create`
- `knowledge-base/export-csv/` -> `asset_knowledge_article_export_csv`
- `knowledge-base/<int:pk>/` -> `asset_knowledge_article_detail`
- `knowledge-base/<int:pk>/edit/` -> `asset_knowledge_article_edit`
- `knowledge-base/<int:pk>/delete/` (`@require_POST`, `@tenant_admin_required`) -> `asset_knowledge_article_delete`
- `knowledge-base/<int:pk>/download/` -> `asset_knowledge_article_download`
- `knowledge-base/<int:pk>/submit-review/` (`@require_POST`) -> `asset_knowledge_article_submit_review`
- `knowledge-base/<int:pk>/publish/` (`@require_POST`, `@tenant_admin_required`) -> `asset_knowledge_article_publish`
- `knowledge-base/<int:pk>/mark-helpful/` (`@require_POST`) -> `asset_knowledge_article_mark_helpful`
- `knowledge-base/<int:pk>/retire/` (`@require_POST`, `@tenant_admin_required`) -> `asset_knowledge_article_retire`

---

## 4. Exact View Context Keys Contract (L7 / L8)

- **Document List (`assetdocumentknowledge/asset_document/list.html`) & Changes Queue (`.../changes.html`)**:
  - `documents` (`page_obj`), `paginator`, `page_obj`, `is_paginated`, `total_count`, `approved_count`, `in_review_count`, `expiring_soon_count`, `checked_out_count`, `draft_count`, `class_choices`, `classification_choices`, `change_type_choices`, `status_choices`, `assets_list`, `categories`, `org_units`, `search_query`
  - Filters parsed before pagination: `q`, `document_class`, `access_classification`, `change_type`, `status`, `operational_asset` (int), `asset_category` (int), `org_unit` (int)
- **Document Detail (`.../detail.html`)**:
  - `document`, `revision_history`, `linked_procedures`, `linked_articles`, `can_edit`, `can_approve`, `can_checkin`
- **Document Form (`.../form.html`)**:
  - `form`, `document` (instance on edit, `None` on create), `is_edit`, `title`
- **Procedure List (`assetdocumentknowledge/asset_operating_procedure/list.html`)**:
  - `procedures` (`page_obj`), `paginator`, `page_obj`, `is_paginated`, `total_count`, `active_count`, `loto_count`, `overdue_review_count`, `type_choices`, `safety_choices`, `status_choices`, `assets_list`, `categories`, `search_query`
  - Filters: `q`, `procedure_type`, `safety_level`, `status`, `operational_asset` (int), `asset_category` (int), `loto_only` (`"1"`)
- **Procedure Detail (`.../detail.html`) & Print Sheet (`.../print.html`)**:
  - `procedure`, `revision_history`, `certified_operators`, `linked_articles`, `can_edit`, `can_activate`
- **Procedure Form (`.../form.html`)**:
  - `form`, `procedure` (`None` on create), `is_edit`, `title`
- **Certification List (`assetdocumentknowledge/asset_operator_certification/list.html`)**:
  - `certifications` (`page_obj`), `paginator`, `page_obj`, `is_paginated`, `total_count`, `active_count`, `expiring_soon_count`, `expired_count`, `qualification_type_choices`, `proficiency_choices`, `status_choices`, `assets_list`, `procedures`, `search_query`
  - Filters: `q`, `qualification_type`, `proficiency_level`, `status`, `operational_asset` (int), `operating_procedure` (int)
- **Certification Detail (`.../detail.html`)**:
  - `certification`, `can_edit`, `can_verify`, `can_acknowledge_sop`, `can_renew`, `can_revoke`
- **Certification Form (`.../form.html`)**:
  - `form`, `certification` (`None` on create), `is_edit`, `title`
- **Knowledge Article List (`assetdocumentknowledge/asset_knowledge_article/list.html`)**:
  - `articles` (`page_obj`), `paginator`, `page_obj`, `is_paginated`, `total_count`, `published_count`, `critical_high_count`, `total_downtime_hours`, `article_type_choices`, `rca_choices`, `severity_choices`, `status_choices`, `assets_list`, `failure_modes`, `search_query`
  - Filters: `q`, `article_type`, `rca_methodology`, `severity`, `status`, `operational_asset` (int), `failure_mode` (int)
- **Knowledge Article Detail (`.../detail.html`)**:
  - `article`, `can_edit`, `can_publish`
- **Knowledge Article Form (`.../form.html`)**:
  - `form`, `article` (`None` on create), `is_edit`, `title`
- **Overview (`apps/assets/views/overview.py` -> `templates/assets/overview.html`)**:
  - Added `kpis` keys: `total_documents`, `approved_documents`, `total_procedures`, `active_procedures`, `total_certifications`, `expiring_certifications`, `total_kb_articles`, `published_kb_articles`

---

## 5. `LIVE_LINKS["11.16"]` Contract (`apps/core/navigation.py`)

```python
    "11.16": {
        "Asset Documentation Repository": "assets:asset_document_list",
        "Version Control & Change Management": "assets:asset_document_change_list",
        "SOP & Procedure Management": "assets:asset_operating_procedure_list",
        "Training & Certification Records": "assets:asset_operator_certification_list",
        "Lessons Learned & Failure Analysis": "assets:asset_knowledge_article_list",
    },
```
