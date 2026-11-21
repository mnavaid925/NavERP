# Module 12.17 Pre-Build Contract — Regulatory Compliance & Submissions (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.17"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0034_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/RegulatorySubmissions/`
  - `apps/quality/forms/RegulatorySubmissions/`
  - `apps/quality/views/RegulatorySubmissions/`
  - `apps/quality/urls/RegulatorySubmissions/`
  - `templates/quality/regulatory_submissions/{regulatory_submission,product_registration,regulatory_commitment,post_market_surveillance_report}/{list,detail,form}.html` + `templates/quality/regulatory_submissions/regulatory_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"submit"`, `"approve"`, `"export"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `HttpResponse(content_type="text/csv")` using CSV formula neutralization (`csv_safe` or leading quote stripping) + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `core.Party`, `quality.ControlledDocument`, `quality.RegulatoryInspectionHost`, `quality.RegulatorySubmission`, `quality.ProductRegistration`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering (`target_authority`, `regulatory_authority`, `regulatory_agency`, `product_registration`, `org_unit`).

---

## 1. Models & Choices Contract (`apps/quality/models/RegulatorySubmissions/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `RegulatorySubmission` (`RegulatorySubmissions.py`)
- **`NUMBER_PREFIX`**: `"QSUB"`
- **`Meta.ordering`**: `["-created_at", "number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Regulatory Submission"` / `"Regulatory Submissions"`
- **Choices & Badge Maps**:
  - `SUBMISSION_TYPE_CHOICES` (`max_length=30`):
    - `("510k", "510(k) Premarket Notification")`
    - `("pma", "Premarket Approval (PMA)")`
    - `("de_novo", "De Novo Classification")`
    - `("ce_tech_file", "CE Technical Documentation (MDR/IVDR)")`
    - `("hde", "Humanitarian Device Exemption (HDE)")`
    - `("ind", "Investigational New Drug (IND)")`
    - `("nda", "New Drug Application (NDA)")`
    - `("health_canada", "Health Canada Medical Device Licence (MDL)")`
    - `("pmda", "Japan PMDA Shonin / Ninsho")`
    - `("nmpa", "China NMPA Registration")`
    - `("other", "Other Health Authority Dossier")`
  - `DEVICE_CLASS_CHOICES` (`max_length=20`):
    - `("class_i", "Class I / Exempt")`
    - `("class_iia", "Class IIa")`
    - `("class_iib", "Class IIb")`
    - `("class_iii", "Class III / High Risk")`
    - `("unclassified", "Unclassified / Combo")`
  - `STATUS_CHOICES` (`max_length=30`):
    - `("draft", "Draft / Scoping")`
    - `("authoring", "Authoring & Compilation")`
    - `("internal_review", "Internal QA/RA Review")`
    - `("submitted", "Submitted to Authority")`
    - `("under_review", "Under Authority Review")`
    - `("deficiency_response", "Deficiency / AI Response")`
    - `("approved_cleared", "Approved / Cleared")`
    - `("rejected", "Rejected / Not Approvable")`
    - `("withdrawn", "Withdrawn")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"authoring": "badge-info"`
    - `"internal_review": "badge-amber"`
    - `"submitted": "badge-info"`
    - `"under_review": "badge-info"`
    - `"deficiency_response": "badge-amber"`
    - `"approved_cleared": "badge-green"`
    - `"rejected": "badge-red"`
    - `"withdrawn": "badge-muted"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `submission_type`: `CharField(max_length=30, choices=SUBMISSION_TYPE_CHOICES, default="510k", db_index=True)`
  - `target_authority`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="regulatory_submissions")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="regulatory_submissions")`
  - `product_name`: `CharField(max_length=255)`
  - `product_code`: `CharField(max_length=100, blank=True, db_index=True)`
  - `device_class`: `CharField(max_length=20, choices=DEVICE_CLASS_CHOICES, default="class_iib", db_index=True)`
  - `application_number`: `CharField(max_length=100, blank=True, db_index=True, help_text="e.g. K230123, P210045, MDR-TF-008")`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `planned_submission_date`: `DateField(null=True, blank=True)`
  - `actual_submission_date`: `DateField(null=True, blank=True, db_index=True)`
  - `decision_date`: `DateField(null=True, blank=True)`
  - `lead_author`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="authored_submissions")`
  - `qa_approver`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_submissions")`
  - `technical_dossier`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="regulatory_submissions")`
  - `technical_sections_summary`: `TextField(blank=True, help_text="Summary of technical modules, GSPR checklist, bench testing, biocompatibility")`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `@property is_submitted`: `status in ["submitted", "under_review", "deficiency_response", "approved_cleared"]`
  - `@property is_approved`: `status == "approved_cleared"`
  - `@property days_under_review`: computed days between `actual_submission_date` and `decision_date` or today
- **Form Exclusions**: `tenant`, `number`, `created_at`, `updated_at`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qsub_ten_num_uniq")` (26)
  - `Index(fields=["tenant", "status"], name="idx_qsub_ten_status")` (19)
  - `Index(fields=["tenant", "submission_type"], name="idx_qsub_ten_subtype")` (20)
  - `Index(fields=["tenant", "product_code"], name="idx_qsub_ten_prod")` (17)

---

### 1.2 `ProductRegistration` (`ProductRegistrations.py`)
- **`NUMBER_PREFIX`**: `"QREG"`
- **`Meta.ordering`**: `["product_name", "jurisdiction_country", "number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Product Registration"` / `"Product Registrations"`
- **Choices & Badge Maps**:
  - `REGISTRATION_TYPE_CHOICES` (`max_length=30`):
    - `("product_license", "Product License / Clearance")`
    - `("establishment_reg", "Establishment Registration")`
    - `("national_listing", "National Device Listing")`
    - `("ce_certificate", "CE Certificate (Notified Body)")`
    - `("import_permit", "Import / Export Permit")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("active", "Active / Authorized")`
    - `("pending_renewal", "Pending Renewal")`
    - `("in_application", "In Application")`
    - `("suspended", "Suspended")`
    - `("expired", "Expired")`
    - `("withdrawn", "Withdrawn")`
  - `STATUS_CSS`:
    - `"active": "badge-green"`
    - `"pending_renewal": "badge-amber"`
    - `"in_application": "badge-info"`
    - `"suspended": "badge-red"`
    - `"expired": "badge-red"`
    - `"withdrawn": "badge-slate"`
- **Fields (exact names & types)**:
  - `registration_title`: `CharField(max_length=255)`
  - `registration_type`: `CharField(max_length=30, choices=REGISTRATION_TYPE_CHOICES, default="product_license", db_index=True)`
  - `jurisdiction_country`: `CharField(max_length=100, db_index=True, help_text="Target Country / Economic Region e.g. USA, European Union, Canada, Japan")`
  - `regulatory_authority`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="authorized_registrations")`
  - `authorized_representative`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="represented_registrations", help_text="EU AR, UKRP, or local in-country sponsor")`
  - `product_name`: `CharField(max_length=255)`
  - `product_code`: `CharField(max_length=100, blank=True, db_index=True)`
  - `intended_purpose`: `TextField(blank=True)`
  - `license_certificate_number`: `CharField(max_length=100, blank=True, db_index=True)`
  - `establishment_id`: `CharField(max_length=100, blank=True, help_text="FEI, SRN, or National Establishment Identifier")`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="in_application", db_index=True)`
  - `initial_approval_date`: `DateField(null=True, blank=True)`
  - `effective_date`: `DateField(null=True, blank=True)`
  - `expiration_date`: `DateField(null=True, blank=True, db_index=True)`
  - `renewal_due_date`: `DateField(null=True, blank=True, db_index=True)`
  - `renewal_lead_days`: `PositiveIntegerField(default=90)`
  - `regulatory_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_registrations")`
  - `linked_submission`: `ForeignKey("quality.RegulatorySubmission", on_delete=models.SET_NULL, null=True, blank=True, related_name="product_registrations")`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `@property is_active`: `status == "active"`
  - `@property days_to_expiration`: days until `expiration_date`
  - `@property is_overdue_renewal`: boolean if `renewal_due_date` is past and status is not `active` or expired
  - `@property urgency_status`: `"expired"` (if past exp), `"urgent"` (<= 30d), `"warning"` (<= 90d), `"normal"`
- **Form Exclusions**: `tenant`, `number`, `created_at`, `updated_at`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qreg_ten_num_uniq")` (26)
  - `Index(fields=["tenant", "status"], name="idx_qreg_ten_status")` (19)
  - `Index(fields=["tenant", "jurisdiction_country"], name="idx_qreg_ten_juris")` (18)
  - `Index(fields=["tenant", "expiration_date"], name="idx_qreg_ten_exp")` (16)

---

### 1.3 `RegulatoryCommitment` (`RegulatoryCommitments.py`)
- **`NUMBER_PREFIX`**: `"QCOM"`
- **`Meta.ordering`**: `["due_date", "number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Regulatory Commitment"` / `"Regulatory Commitments"`
- **Choices & Badge Maps**:
  - `COMMITMENT_TYPE_CHOICES` (`max_length=30`):
    - `("agency_deficiency", "Deficiency / Additional Information Request")`
    - `("post_approval_study", "Post-Approval Clinical / Performance Study")`
    - `("annual_report", "Annual Status Report / Periodic Summary")`
    - `("labeling_update", "Mandated Labeling / IFU Revision")`
    - `("stability_monitoring", "Ongoing Stability / Shelf-Life Study")`
    - `("inspection_483_response", "Inspection Observation (483) Response")`
    - `("pmcf_commitment", "Post-Market Clinical Follow-up Commitment")`
    - `("other", "Other Regulatory Commitment")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("open", "Open / Assigned")`
    - `("in_progress", "In Progress / Authoring")`
    - `("submitted_to_agency", "Submitted to Agency")`
    - `("agency_accepted", "Agency Accepted / Fulfilled")`
    - `("overdue", "Overdue")`
    - `("waived", "Waived / Superseded")`
  - `STATUS_CSS`:
    - `"open": "badge-info"`
    - `"in_progress": "badge-amber"`
    - `"submitted_to_agency": "badge-info"`
    - `"agency_accepted": "badge-green"`
    - `"overdue": "badge-red"`
    - `"waived": "badge-slate"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `commitment_type`: `CharField(max_length=30, choices=COMMITMENT_TYPE_CHOICES, default="agency_deficiency", db_index=True)`
  - `regulatory_agency`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="regulatory_commitments")`
  - `linked_submission`: `ForeignKey("quality.RegulatorySubmission", on_delete=models.SET_NULL, null=True, blank=True, related_name="regulatory_commitments")`
  - `linked_registration`: `ForeignKey("quality.ProductRegistration", on_delete=models.SET_NULL, null=True, blank=True, related_name="regulatory_commitments")`
  - `linked_inspection`: `ForeignKey("quality.RegulatoryInspectionHost", on_delete=models.SET_NULL, null=True, blank=True, related_name="regulatory_commitments")`
  - `agency_reference_number`: `CharField(max_length=100, blank=True, help_text="Deficiency item number, 483 item number, or tracking ID")`
  - `correspondence_date`: `DateField(null=True, blank=True)`
  - `commitment_description`: `TextField()`
  - `responsible_owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_commitments")`
  - `due_date`: `DateField(db_index=True)`
  - `completion_date`: `DateField(null=True, blank=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="open", db_index=True)`
  - `verification_method`: `TextField(blank=True, help_text="Test data, protocol, labeling file, or formal response package")`
  - `agency_feedback`: `TextField(blank=True)`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `@property is_overdue`: `status in ["open", "in_progress"] and due_date < timezone.now().date()`
  - `@property days_remaining`: `(due_date - timezone.now().date()).days`
- **Form Exclusions**: `tenant`, `number`, `created_at`, `updated_at`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qcom_ten_num_uniq")` (26)
  - `Index(fields=["tenant", "status"], name="idx_qcom_ten_status")` (19)
  - `Index(fields=["tenant", "due_date"], name="idx_qcom_ten_due")` (16)
  - `Index(fields=["tenant", "commitment_type"], name="idx_qcom_ten_type")` (17)

---

### 1.4 `PostMarketSurveillanceReport` (`PostMarketSurveillanceReports.py`)
- **`NUMBER_PREFIX`**: `"QPMS"`
- **`Meta.ordering`**: `["-reporting_period_end", "number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Post-Market Surveillance Report"` / `"Post-Market Surveillance Reports"`
- **Choices & Badge Maps**:
  - `REPORT_TYPE_CHOICES` (`max_length=30`):
    - `("psur", "Periodic Safety Update Report (PSUR)")`
    - `("pms_report", "Post-Market Surveillance Report (PMS)")`
    - `("pmcf_evaluation", "Post-Market Clinical Follow-up (PMCF) Report")`
    - `("vigilance_trend", "Vigilance Trend Assessment")`
    - `("annual_safety", "Annual Safety Summary Report")`
  - `BENEFIT_RISK_CHOICES` (`max_length=30`):
    - `("favorable", "Favorable — Benefits Outweigh Risks")`
    - `("acceptable_monitoring", "Acceptable with Enhanced Monitoring")`
    - `("unfavorable_action", "Unfavorable — Corrective Action Required")`
  - `STATUS_CHOICES` (`max_length=25`):
    - `("draft", "Draft / In Preparation")`
    - `("in_review", "Under Clinical / QA Review")`
    - `("approved", "Approved Internally")`
    - `("submitted_to_authority", "Submitted to Notified Body / Authority")`
    - `("archived", "Archived / Historical")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"in_review": "badge-amber"`
    - `"approved": "badge-green"`
    - `"submitted_to_authority": "badge-info"`
    - `"archived": "badge-muted"`
  - `BENEFIT_RISK_CSS`:
    - `"favorable": "badge-green"`
    - `"acceptable_monitoring": "badge-amber"`
    - `"unfavorable_action": "badge-red"`
- **Fields (exact names & types)**:
  - `report_title`: `CharField(max_length=255)`
  - `report_type`: `CharField(max_length=30, choices=REPORT_TYPE_CHOICES, default="psur", db_index=True)`
  - `product_registration`: `ForeignKey("quality.ProductRegistration", on_delete=models.SET_NULL, null=True, blank=True, related_name="pms_reports")`
  - `device_model_family`: `CharField(max_length=255, help_text="Product line, device model, or UDI family")`
  - `reporting_period_start`: `DateField()`
  - `reporting_period_end`: `DateField(db_index=True)`
  - `units_distributed`: `PositiveIntegerField(default=0, help_text="Total units shipped or deployed in period")`
  - `total_complaints_count`: `PositiveIntegerField(default=0)`
  - `serious_incidents_count`: `PositiveIntegerField(default=0)`
  - `field_actions_count`: `PositiveIntegerField(default=0, help_text="Number of recalls or FSCAs executed")`
  - `benefit_risk_conclusion`: `CharField(max_length=30, choices=BENEFIT_RISK_CHOICES, default="favorable", db_index=True)`
  - `benefit_risk_rationale`: `TextField(blank=True)`
  - `pmcf_action_required`: `BooleanField(default=False)`
  - `pmcf_action_summary`: `TextField(blank=True)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `prepared_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="prepared_pms_reports")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_pms_reports")`
  - `approval_date`: `DateField(null=True, blank=True)`
  - `next_report_due_date`: `DateField(null=True, blank=True, db_index=True)`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `@property complaint_rate_pct`: `round((total_complaints_count / units_distributed * 100), 4) if units_distributed > 0 else 0.0`
  - `@property serious_incident_rate_pct`: `round((serious_incidents_count / units_distributed * 100), 4) if units_distributed > 0 else 0.0`
- **Form Exclusions**: `tenant`, `number`, `created_at`, `updated_at`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qpms_ten_num_uniq")` (26)
  - `Index(fields=["tenant", "status"], name="idx_qpms_ten_status")` (19)
  - `Index(fields=["tenant", "report_type"], name="idx_qpms_ten_type")` (17)
  - `Index(fields=["tenant", "reporting_period_end"], name="idx_qpms_ten_period")` (19)

---

## 2. Forms Contract (`apps/quality/forms/RegulatorySubmissions/`)

All ModelForms inherit `apps.quality.forms._common.TenantModelForm` (or standard `forms.ModelForm` with tenant kwargs popped in `__init__`, assigning `self.instance.tenant = tenant`).
Every form cleans tenant FKs via `apps.quality.forms._common.reject_foreign` or explicit tenant checks.

- `RegulatorySubmissionForm`:
  - `fields = ["title", "submission_type", "target_authority", "org_unit", "product_name", "product_code", "device_class", "application_number", "status", "planned_submission_date", "actual_submission_date", "decision_date", "lead_author", "qa_approver", "technical_dossier", "technical_sections_summary", "notes"]`
  - Date inputs use `type="date"` widget.
- `ProductRegistrationForm`:
  - `fields = ["registration_title", "registration_type", "jurisdiction_country", "regulatory_authority", "authorized_representative", "product_name", "product_code", "intended_purpose", "license_certificate_number", "establishment_id", "status", "initial_approval_date", "effective_date", "expiration_date", "renewal_due_date", "renewal_lead_days", "regulatory_lead", "linked_submission", "notes"]`
- `RegulatoryCommitmentForm`:
  - `fields = ["title", "commitment_type", "regulatory_agency", "linked_submission", "linked_registration", "linked_inspection", "agency_reference_number", "correspondence_date", "commitment_description", "responsible_owner", "due_date", "completion_date", "status", "verification_method", "agency_feedback", "notes"]`
- `PostMarketSurveillanceReportForm`:
  - `fields = ["report_title", "report_type", "product_registration", "device_model_family", "reporting_period_start", "reporting_period_end", "units_distributed", "total_complaints_count", "serious_incidents_count", "field_actions_count", "benefit_risk_conclusion", "benefit_risk_rationale", "pmcf_action_required", "pmcf_action_summary", "status", "prepared_by", "approved_by", "approval_date", "next_report_due_date", "notes"]`

---

## 3. Views & Context Contract (`apps/quality/views/RegulatorySubmissions/`)

### 3.1 `RegulatorySubmissions.py`
- `regulatory_submission_list(request)`:
  - Route: `submissions/`
  - Template: `quality/regulatory_submissions/regulatory_submission/list.html`
  - Context keys:
    - `page_obj`: paginated items
    - `regulatory_submissions`: page items list
    - `submission_type_choices`: `RegulatorySubmission.SUBMISSION_TYPE_CHOICES`
    - `device_class_choices`: `RegulatorySubmission.DEVICE_CLASS_CHOICES`
    - `status_choices`: `RegulatorySubmission.STATUS_CHOICES`
    - `target_authorities`: `Party.objects.filter(tenant=request.tenant)`
    - `total_submissions`: integer count
    - `pending_review_count`: integer count (status in `authoring`, `internal_review`, `under_review`, `deficiency_response`)
    - `approved_count`: integer count (status == `approved_cleared`)
    - `search_query`: `request.GET.get('q', '')`
- `regulatory_submission_detail(request, pk)`:
  - Route: `submissions/<int:pk>/`
  - Template: `quality/regulatory_submissions/regulatory_submission/detail.html`
  - Context keys:
    - `regulatory_submission`: model instance
    - `linked_commitments`: `RegulatoryCommitment` queryset
    - `linked_registrations`: `ProductRegistration` queryset
- `regulatory_submission_create(request)`:
  - Route: `submissions/create/`
  - Template: `quality/regulatory_submissions/regulatory_submission/form.html`
  - Context keys: `form`, `is_edit=False`
- `regulatory_submission_edit(request, pk)`:
  - Route: `submissions/<int:pk>/edit/`
  - Template: `quality/regulatory_submissions/regulatory_submission/form.html`
  - Context keys: `form`, `regulatory_submission`, `is_edit=True`
- `regulatory_submission_delete(request, pk)`:
  - Route: `submissions/<int:pk>/delete/` (POST only)
- `regulatory_submission_export(request)`:
  - Route: `submissions/export/` (CSV stream)

### 3.2 `ProductRegistrations.py`
- `product_registration_list(request)`:
  - Route: `registrations/`
  - Template: `quality/regulatory_submissions/product_registration/list.html`
  - Context keys:
    - `page_obj`: paginated items
    - `product_registrations`: page items list
    - `registration_type_choices`: `ProductRegistration.REGISTRATION_TYPE_CHOICES`
    - `status_choices`: `ProductRegistration.STATUS_CHOICES`
    - `authorities`: `Party.objects.filter(tenant=request.tenant)`
    - `total_registrations`: integer count
    - `active_count`: integer count
    - `expiring_soon_count`: integer count (expiring within 90 days)
    - `search_query`: `request.GET.get('q', '')`
- `product_registration_detail(request, pk)`:
  - Route: `registrations/<int:pk>/`
  - Template: `quality/regulatory_submissions/product_registration/detail.html`
  - Context keys:
    - `product_registration`: model instance
    - `linked_commitments`: `RegulatoryCommitment` queryset
    - `linked_pms_reports`: `PostMarketSurveillanceReport` queryset
- `product_registration_create(request)`:
  - Route: `registrations/create/`
  - Template: `quality/regulatory_submissions/product_registration/form.html`
  - Context keys: `form`, `is_edit=False`
- `product_registration_edit(request, pk)`:
  - Route: `registrations/<int:pk>/edit/`
  - Template: `quality/regulatory_submissions/product_registration/form.html`
  - Context keys: `form`, `product_registration`, `is_edit=True`
- `product_registration_delete(request, pk)`:
  - Route: `registrations/<int:pk>/delete/` (POST only)
- `product_registration_export(request)`:
  - Route: `registrations/export/` (CSV stream)

### 3.3 `RegulatoryCommitments.py`
- `regulatory_commitment_list(request)`:
  - Route: `commitments/`
  - Template: `quality/regulatory_submissions/regulatory_commitment/list.html`
  - Context keys:
    - `page_obj`: paginated items
    - `regulatory_commitments`: page items list
    - `commitment_type_choices`: `RegulatoryCommitment.COMMITMENT_TYPE_CHOICES`
    - `status_choices`: `RegulatoryCommitment.STATUS_CHOICES`
    - `agencies`: `Party.objects.filter(tenant=request.tenant)`
    - `total_commitments`: integer count
    - `open_count`: integer count (`open` + `in_progress`)
    - `overdue_count`: integer count
    - `search_query`: `request.GET.get('q', '')`
- `regulatory_commitment_detail(request, pk)`:
  - Route: `commitments/<int:pk>/`
  - Template: `quality/regulatory_submissions/regulatory_commitment/detail.html`
  - Context keys:
    - `regulatory_commitment`: model instance
- `regulatory_commitment_create(request)`:
  - Route: `commitments/create/`
  - Template: `quality/regulatory_submissions/regulatory_commitment/form.html`
  - Context keys: `form`, `is_edit=False`
- `regulatory_commitment_edit(request, pk)`:
  - Route: `commitments/<int:pk>/edit/`
  - Template: `quality/regulatory_submissions/regulatory_commitment/form.html`
  - Context keys: `form`, `regulatory_commitment`, `is_edit=True`
- `regulatory_commitment_delete(request, pk)`:
  - Route: `commitments/<int:pk>/delete/` (POST only)
- `regulatory_commitment_export(request)`:
  - Route: `commitments/export/` (CSV stream)

### 3.4 `PostMarketSurveillanceReports.py`
- `post_market_surveillance_report_list(request)`:
  - Route: `pms-reports/`
  - Template: `quality/regulatory_submissions/post_market_surveillance_report/list.html`
  - Context keys:
    - `page_obj`: paginated items
    - `post_market_surveillance_reports`: page items list
    - `report_type_choices`: `PostMarketSurveillanceReport.REPORT_TYPE_CHOICES`
    - `benefit_risk_choices`: `PostMarketSurveillanceReport.BENEFIT_RISK_CHOICES`
    - `status_choices`: `PostMarketSurveillanceReport.STATUS_CHOICES`
    - `registrations`: `ProductRegistration.objects.filter(tenant=request.tenant)`
    - `total_reports`: integer count
    - `approved_count`: integer count (`approved` + `submitted_to_authority`)
    - `search_query`: `request.GET.get('q', '')`
- `post_market_surveillance_report_detail(request, pk)`:
  - Route: `pms-reports/<int:pk>/`
  - Template: `quality/regulatory_submissions/post_market_surveillance_report/detail.html`
  - Context keys:
    - `post_market_surveillance_report`: model instance
- `post_market_surveillance_report_create(request)`:
  - Route: `pms-reports/create/`
  - Template: `quality/regulatory_submissions/post_market_surveillance_report/form.html`
  - Context keys: `form`, `is_edit=False`
- `post_market_surveillance_report_edit(request, pk)`:
  - Route: `pms-reports/<int:pk>/edit/`
  - Template: `quality/regulatory_submissions/post_market_surveillance_report/form.html`
  - Context keys: `form`, `post_market_surveillance_report`, `is_edit=True`
- `post_market_surveillance_report_delete(request, pk)`:
  - Route: `pms-reports/<int:pk>/delete/` (POST only)
- `post_market_surveillance_report_export(request)`:
  - Route: `pms-reports/export/` (CSV stream)

### 3.5 `RegulatoryDashboard.py`
- `regulatory_dashboard(request)`:
  - Route: `dashboard/`
  - Template: `quality/regulatory_submissions/regulatory_dashboard.html`
  - Context keys:
    - `total_submissions`: total count
    - `active_registrations`: total active registrations
    - `open_commitments`: open + in_progress count
    - `overdue_commitments`: count of overdue commitments
    - `pms_reports_count`: total PSUR/PMS reports
    - `recent_submissions`: 5 newest submissions
    - `expiring_registrations`: 5 registrations expiring soonest
    - `pending_commitments`: 5 commitments due soonest
    - `recent_pms_reports`: 5 newest PMS reports

---

## 4. URLs Contract (`apps/quality/urls/RegulatorySubmissions/`)

App namespace is `quality`. All routes concatenated into `apps/quality/urls/__init__.py`.

1. `RegulatorySubmissions.py`:
   - `path("submissions/", views.regulatory_submission_list, name="regulatory_submission_list")`
   - `path("submissions/create/", views.regulatory_submission_create, name="regulatory_submission_create")`
   - `path("submissions/export/", views.regulatory_submission_export, name="regulatory_submission_export")`
   - `path("submissions/<int:pk>/", views.regulatory_submission_detail, name="regulatory_submission_detail")`
   - `path("submissions/<int:pk>/edit/", views.regulatory_submission_edit, name="regulatory_submission_edit")`
   - `path("submissions/<int:pk>/delete/", views.regulatory_submission_delete, name="regulatory_submission_delete")`
2. `ProductRegistrations.py`:
   - `path("registrations/", views.product_registration_list, name="product_registration_list")`
   - `path("registrations/create/", views.product_registration_create, name="product_registration_create")`
   - `path("registrations/export/", views.product_registration_export, name="product_registration_export")`
   - `path("registrations/<int:pk>/", views.product_registration_detail, name="product_registration_detail")`
   - `path("registrations/<int:pk>/edit/", views.product_registration_edit, name="product_registration_edit")`
   - `path("registrations/<int:pk>/delete/", views.product_registration_delete, name="product_registration_delete")`
3. `RegulatoryCommitments.py`:
   - `path("commitments/", views.regulatory_commitment_list, name="regulatory_commitment_list")`
   - `path("commitments/create/", views.regulatory_commitment_create, name="regulatory_commitment_create")`
   - `path("commitments/export/", views.regulatory_commitment_export, name="regulatory_commitment_export")`
   - `path("commitments/<int:pk>/", views.regulatory_commitment_detail, name="regulatory_commitment_detail")`
   - `path("commitments/<int:pk>/edit/", views.regulatory_commitment_edit, name="regulatory_commitment_edit")`
   - `path("commitments/<int:pk>/delete/", views.regulatory_commitment_delete, name="regulatory_commitment_delete")`
4. `PostMarketSurveillanceReports.py`:
   - `path("pms-reports/", views.post_market_surveillance_report_list, name="post_market_surveillance_report_list")`
   - `path("pms-reports/create/", views.post_market_surveillance_report_create, name="post_market_surveillance_report_create")`
   - `path("pms-reports/export/", views.post_market_surveillance_report_export, name="post_market_surveillance_report_export")`
   - `path("pms-reports/<int:pk>/", views.post_market_surveillance_report_detail, name="post_market_surveillance_report_detail")`
   - `path("pms-reports/<int:pk>/edit/", views.post_market_surveillance_report_edit, name="post_market_surveillance_report_edit")`
   - `path("pms-reports/<int:pk>/delete/", views.post_market_surveillance_report_delete, name="post_market_surveillance_report_delete")`
5. `RegulatoryDashboard.py`:
   - `path("regulatory-compliance/dashboard/", views.regulatory_dashboard, name="regulatory_dashboard")`

---

## 5. Navigation Mapping (`apps/core/navigation.py`)

Exact `LIVE_LINKS["12.17"]` dictionary matching `NavERP.md`:
```python
    "12.17": {
        "Regulatory Intelligence & Tracking": "quality:regulatory_dashboard",
        "Submission Document Management": "quality:regulatory_submission_list",
        "Regulatory Correspondence & Commitments": "quality:regulatory_commitment_list",
        "Registration & Listing Management": "quality:product_registration_list",
        "Post-Market Surveillance (PMS)": "quality:post_market_surveillance_report_list",
    },
```
