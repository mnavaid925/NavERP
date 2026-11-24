# Module 13.10 Pre-Build Contract — Audit Trail & Reporting (`apps/documents/`)

> Frozen in Phase 3.1 before any entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["13.10"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.documents` (Extends existing app; claims incremental migration `0018_...`)
- **Package Directories**:
  - `apps/documents/models/AuditReporting/`
  - `apps/documents/forms/AuditReporting/`
  - `apps/documents/views/AuditReporting/`
  - `apps/documents/urls/AuditReporting/`
  - `apps/documents/services/`
  - `templates/documents/audit_reporting/{audit_trail,report_definition,security_alert,chain_of_custody}/{list,detail,form}.html` + `audit_dashboard.html` + `lifecycle_dashboard.html` + `chain_of_custody/certificate.html` + `chain_of_custody/auditor_portal.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"verify"`, `"scan"`, `"triage"`, `"export"`, `"seal"`, `"revoke"`, `"access"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `documents.Document`, `documents.DocumentVersion`, `documents.DocumentFolder`, `documents.DocumentApprovalRequest`, `documents.DlpIncident`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/documents/models/AuditReporting/`)

All 4 models inherit `apps.documents.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `DocumentAuditTrail` (`DocumentAuditTrails.py`)
- **`NUMBER_PREFIX`**: `"DAUD"`
- **`Meta.ordering`**: `["-event_timestamp", "-id"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Audit Trail"` / `"Document Audit Trails"`
- **Choices & Badge Maps**:
  - `ACTION_TYPE_CHOICES` (`max_length=40`):
    - `("created", "Document Created")`
    - `("viewed", "Document Viewed")`
    - `("previewed", "Document Previewed")`
    - `("edited", "Document Edited")`
    - `("version_uploaded", "New Version Uploaded")`
    - `("downloaded", "Document Downloaded")`
    - `("printed", "Document Printed")`
    - `("checked_out", "Checked Out")`
    - `("checked_in", "Checked In")`
    - `("permission_changed", "Permission Modified")`
    - `("watermark_applied", "Watermark Applied")`
    - `("shared_externally", "Shared Externally")`
    - `("share_revoked", "Share Revoked")`
    - `("workflow_approved", "Workflow Approved")`
    - `("workflow_rejected", "Workflow Rejected")`
    - `("signed", "Document Signed")`
    - `("moved", "Document Moved")`
    - `("deleted", "Document Deleted")`
    - `("restored", "Document Restored")`
    - `("purged", "Document Purged")`
    - `("dlp_violation", "DLP Violation Blocked")`
    - `("auditor_portal_accessed", "Auditor Portal Inspection")`
  - `ACTION_TYPE_CSS`:
    - `"created": "badge-info"`
    - `"viewed": "badge-slate"`
    - `"previewed": "badge-slate"`
    - `"edited": "badge-info"`
    - `"version_uploaded": "badge-info"`
    - `"downloaded": "badge-green"`
    - `"printed": "badge-slate"`
    - `"checked_out": "badge-amber"`
    - `"checked_in": "badge-green"`
    - `"permission_changed": "badge-amber"`
    - `"watermark_applied": "badge-slate"`
    - `"shared_externally": "badge-amber"`
    - `"share_revoked": "badge-red"`
    - `"workflow_approved": "badge-green"`
    - `"workflow_rejected": "badge-red"`
    - `"signed": "badge-green"`
    - `"moved": "badge-slate"`
    - `"deleted": "badge-red"`
    - `"restored": "badge-green"`
    - `"purged": "badge-red"`
    - `"dlp_violation": "badge-red"`
    - `"auditor_portal_accessed": "badge-info"`
  - `RESULT_CSS`:
    - `True: "badge-green"` (Success)
    - `False: "badge-red"` (Failed / Blocked)
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_entries", db_index=True)`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_entries")`
  - `document_number_snapshot`: `CharField(max_length=64, blank=True)`
  - `document_title_snapshot`: `CharField(max_length=255, blank=True)`
  - `actor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_audit_entries", db_index=True)`
  - `actor_email_snapshot`: `EmailField(blank=True)`
  - `action_type`: `CharField(max_length=40, choices=ACTION_TYPE_CHOICES, db_index=True)`
  - `event_timestamp`: `DateTimeField(default=timezone.now, editable=False, db_index=True)`
  - `is_success`: `BooleanField(default=True, db_index=True)`
  - `failure_reason`: `CharField(max_length=100, blank=True)`
  - `ip_address`: `GenericIPAddressField(null=True, blank=True)`
  - `user_agent`: `CharField(max_length=255, blank=True)`
  - `session_id`: `CharField(max_length=64, blank=True)`
  - `details_json`: `JSONField(default=dict, blank=True)`
  - `prev_hash`: `CharField(max_length=64, blank=True)`
  - `chain_hash`: `CharField(max_length=64, editable=False, db_index=True)`
- **Indexes & Constraints (`<= 30` chars)**:
  - `models.UniqueConstraint(fields=["tenant", "number"], name="doc_daud_ten_num_uniq")`
  - `models.Index(fields=["tenant", "event_timestamp"], name="doc_daud_tnt_evt_idx")`
  - `models.Index(fields=["tenant", "action_type"], name="doc_daud_tnt_act_idx")`
  - `models.Index(fields=["tenant", "document"], name="doc_daud_tnt_doc_idx")`
  - `models.Index(fields=["tenant", "actor"], name="doc_daud_tnt_usr_idx")`
  - `models.Index(fields=["tenant", "is_success"], name="doc_daud_tnt_suc_idx")`
  - `models.Index(fields=["tenant", "chain_hash"], name="doc_daud_chn_hsh_idx")`
- **Properties & Helper Methods**:
  - `compute_chain_hash(prev_hash)`: Returns `hashlib.sha256(f"{prev_hash}|{tenant_id}|{action_type}|{event_timestamp.isoformat()}|{actor_email_snapshot}|{document_number_snapshot}|{json.dumps(details_json, sort_keys=True)}".encode()).hexdigest()`
  - `verify_hash()`: Validates that `self.chain_hash == self.compute_chain_hash(self.prev_hash)`
  - `save(*args, **kwargs)`: Immutability enforcement (`if self.pk: raise ValidationError("Audit records are strictly immutable.")`), computes `prev_hash` from last tenant record if not set, and sets `chain_hash`.
  - `delete(*args, **kwargs)`: Raises `ValidationError("Audit records cannot be deleted.")`.
  - `get_action_type_badge()`: Returns matching CSS class.

---

### 1.2 `AuditReportDefinition` (`AuditReportDefinitions.py`)
- **`NUMBER_PREFIX`**: `"DRPT"`
- **`Meta.ordering`**: `["name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Audit Report Definition"` / `"Audit Report Definitions"`
- **Choices & Badge Maps**:
  - `REPORT_TYPE_CHOICES` (`max_length=40`):
    - `("document_history", "Complete Document Lifecycle History")`
    - `("user_activity", "User Access & Activity Summary")`
    - `("confidential_access", "Confidential / Restricted Document Access")`
    - `("permission_audit", "Permission & Access Control Changes")`
    - `("security_exceptions", "Security Exceptions & DLP Blocks")`
    - `("external_sharing", "External Sharing & Public Links")`
    - `("deletion_purge", "Document Deletions & Purges")`
    - `("lifecycle_bottlenecks", "Approval Cycle Time & Bottlenecks")`
    - `("version_churn", "Version Volatility & High Churn")`
    - `("custom_query", "Custom Filtered Audit Query")`
  - `DATE_RANGE_CHOICES` (`max_length=30`):
    - `("today", "Today")`
    - `("last_7_days", "Last 7 Days")`
    - `("last_30_days", "Last 30 Days")`
    - `("last_90_days", "Last 90 Days")`
    - `("last_year", "Last 365 Days")`
    - `("custom", "Custom Date Range")`
  - `OUTPUT_FORMAT_CHOICES` (`max_length=20`):
    - `("table_view", "Interactive Web Table")`
    - `("csv", "Downloadable CSV")`
    - `("json", "Downloadable JSON")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("active", "Active")`
    - `("archived", "Archived")`
  - `REPORT_TYPE_CSS`:
    - `"document_history": "badge-info"`
    - `"user_activity": "badge-slate"`
    - `"confidential_access": "badge-amber"`
    - `"permission_audit": "badge-info"`
    - `"security_exceptions": "badge-red"`
    - `"external_sharing": "badge-amber"`
    - `"deletion_purge": "badge-red"`
    - `"lifecycle_bottlenecks": "badge-amber"`
    - `"version_churn": "badge-slate"`
    - `"custom_query": "badge-green"`
  - `STATUS_CSS`:
    - `"active": "badge-green"`
    - `"archived": "badge-muted"`
- **Fields (exact names & types)**:
  - `name`: `CharField(max_length=150)`
  - `description`: `TextField(blank=True)`
  - `report_type`: `CharField(max_length=40, choices=REPORT_TYPE_CHOICES, default="custom_query", db_index=True)`
  - `is_system_preset`: `BooleanField(default=False, db_index=True)`
  - `date_range_preset`: `CharField(max_length=30, choices=DATE_RANGE_CHOICES, default="last_30_days")`
  - `custom_start_date`: `DateField(null=True, blank=True)`
  - `custom_end_date`: `DateField(null=True, blank=True)`
  - `filter_criteria_json`: `JSONField(default=dict, blank=True)`
  - `output_format`: `CharField(max_length=20, choices=OUTPUT_FORMAT_CHOICES, default="table_view")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_created_audit_reports")`
  - `last_run_at`: `DateTimeField(null=True, blank=True)`
  - `last_run_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_executed_audit_reports")`
  - `total_runs`: `PositiveIntegerField(default=0)`
- **Indexes & Constraints (`<= 30` chars)**:
  - `models.UniqueConstraint(fields=["tenant", "number"], name="doc_drpt_ten_num_uniq")`
  - `models.Index(fields=["tenant", "report_type"], name="doc_drpt_tnt_typ_idx")`
  - `models.Index(fields=["tenant", "status"], name="doc_drpt_tnt_sts_idx")`
  - `models.Index(fields=["tenant", "is_system_preset"], name="doc_drpt_tnt_sys_idx")`
- **Properties & Helper Methods**:
  - `get_report_type_badge()`: Returns badge CSS class.
  - `get_status_badge()`: Returns badge CSS class.
  - `get_effective_date_range()`: Computes `(start_datetime, end_datetime)` tuple based on preset or custom range.

---

### 1.3 `DocumentSecurityAlert` (`DocumentSecurityAlerts.py`)
- **`NUMBER_PREFIX`**: `"DANM"`
- **`Meta.ordering`**: `["-detected_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Security Alert"` / `"Document Security Alerts"`
- **Choices & Badge Maps**:
  - `ALERT_TYPE_CHOICES` (`max_length=40`):
    - `("mass_download", "Mass Document Download / Exfiltration")`
    - `("off_hours_access", "Unusual Off-Hours Bulk Access")`
    - `("rapid_deletion", "Rapid Document Deletion / Purge")`
    - `("excessive_denials", "Excessive Permission Denials (Probing)")`
    - `("unusual_location", "Anomalous Geolocation / IP Subnet")`
    - `("dormant_file_access", "Sudden Access to Dormant Sensitive File")`
    - `("permission_escalation", "Suspicious Permission Escalation")`
  - `SEVERITY_CHOICES` (`max_length=20`):
    - `("low", "Low Severity (Risk 1-39)")`
    - `("medium", "Medium Severity (Risk 40-69)")`
    - `("high", "High Severity (Risk 70-89)")`
    - `("critical", "Critical Threat (Risk 90-100)")`
  - `STATUS_CHOICES` (`max_length=30`):
    - `("new", "New / Unassigned")`
    - `("investigating", "Under Investigation")`
    - `("confirmed_threat", "Confirmed Threat")`
    - `("false_positive", "False Positive")`
    - `("resolved", "Resolved & Mitigated")`
    - `("dismissed", "Dismissed")`
  - `ACTION_TAKEN_CHOICES` (`max_length=40`):
    - `("logged_only", "Logged / Monitoring Only")`
    - `("user_warned", "User Warned via Notification")`
    - `("downloads_blocked", "Document Downloads Blocked")`
    - `("sharing_revoked", "External Shares Revoked")`
    - `("session_terminated", "User Session Terminated")`
  - `ALERT_TYPE_CSS`:
    - `"mass_download": "badge-red"`
    - `"off_hours_access": "badge-amber"`
    - `"rapid_deletion": "badge-red"`
    - `"excessive_denials": "badge-amber"`
    - `"unusual_location": "badge-info"`
    - `"dormant_file_access": "badge-slate"`
    - `"permission_escalation": "badge-red"`
  - `SEVERITY_CSS`:
    - `"low": "badge-slate"`
    - `"medium": "badge-info"`
    - `"high": "badge-amber"`
    - `"critical": "badge-red"`
  - `STATUS_CSS`:
    - `"new": "badge-red"`
    - `"investigating": "badge-amber"`
    - `"confirmed_threat": "badge-red"`
    - `"false_positive": "badge-slate"`
    - `"resolved": "badge-green"`
    - `"dismissed": "badge-muted"`
- **Fields (exact names & types)**:
  - `alert_type`: `CharField(max_length=40, choices=ALERT_TYPE_CHOICES, db_index=True)`
  - `severity`: `CharField(max_length=20, choices=SEVERITY_CHOICES, default="medium", db_index=True)`
  - `risk_score`: `PositiveIntegerField(default=50, db_index=True)`
  - `title`: `CharField(max_length=200)`
  - `description`: `TextField()`
  - `detected_at`: `DateTimeField(default=timezone.now, db_index=True)`
  - `target_user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_security_alerts", db_index=True)`
  - `target_document`: `ForeignKey("documents.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="security_alerts")`
  - `source_ip`: `GenericIPAddressField(null=True, blank=True)`
  - `event_count`: `PositiveIntegerField(default=1)`
  - `evidence_json`: `JSONField(default=dict, blank=True)`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="new", db_index=True)`
  - `action_taken`: `CharField(max_length=40, choices=ACTION_TAKEN_CHOICES, default="logged_only", db_index=True)`
  - `assigned_to`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_assigned_security_alerts")`
  - `triage_notes`: `TextField(blank=True)`
  - `resolved_at`: `DateTimeField(null=True, blank=True)`
  - `resolved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_resolved_security_alerts")`
- **Indexes & Constraints (`<= 30` chars)**:
  - `models.UniqueConstraint(fields=["tenant", "number"], name="doc_danm_ten_num_uniq")`
  - `models.Index(fields=["tenant", "status"], name="doc_danm_tnt_sts_idx")`
  - `models.Index(fields=["tenant", "severity"], name="doc_danm_tnt_sev_idx")`
  - `models.Index(fields=["tenant", "alert_type"], name="doc_danm_tnt_typ_idx")`
  - `models.Index(fields=["tenant", "risk_score"], name="doc_danm_tnt_rsk_idx")`
  - `models.Index(fields=["tenant", "action_taken"], name="doc_danm_tnt_act_idx")`
- **Properties & Helper Methods**:
  - `get_severity_badge()`: Returns badge CSS class.
  - `get_status_badge()`: Returns badge CSS class.
  - `get_alert_type_badge()`: Returns badge CSS class.

---

### 1.4 `ChainOfCustodyExport` (`ChainOfCustodyExports.py`)
- **`NUMBER_PREFIX`**: `"DCOC"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Chain of Custody Export"` / `"Chain of Custody Exports"`
- **Choices & Badge Maps**:
  - `REGULATORY_FRAMEWORK_CHOICES` (`max_length=50`):
    - `("general_compliance", "General Corporate Compliance / Audit")`
    - `("iso_27001", "ISO/IEC 27001 Information Security")`
    - `("soc2_type2", "SOC 2 Type II Security & Confidentiality")`
    - `("fda_21cfr11", "FDA 21 CFR Part 11 Electronic Records")`
    - `("hipaa", "HIPAA Security Rule")`
    - `("gdpr_article30", "GDPR Article 30 Records of Processing")`
    - `("legal_hold", "Civil Litigation / Legal Hold Evidence")`
  - `SCOPE_CHOICES` (`max_length=30`):
    - `("single_document", "Single Document Comprehensive Package")`
    - `("folder_tree", "Entire Folder Repository Branch")`
    - `("date_range", "All Tenant Activity in Date Range")`
    - `("regulatory_filing", "Specific Regulatory Inspection Pack")`
  - `REGULATORY_FRAMEWORK_CSS`:
    - `"general_compliance": "badge-slate"`
    - `"iso_27001": "badge-info"`
    - `"soc2_type2": "badge-green"`
    - `"fda_21cfr11": "badge-amber"`
    - `"hipaa": "badge-info"`
    - `"gdpr_article30": "badge-slate"`
    - `"legal_hold": "badge-red"`
  - `STATUS_CSS`:
    - `"active": "badge-green"`
    - `"expired": "badge-amber"`
    - `"revoked": "badge-red"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=200)`
  - `regulatory_framework`: `CharField(max_length=50, choices=REGULATORY_FRAMEWORK_CHOICES, default="general_compliance")`
  - `scope`: `CharField(max_length=30, choices=SCOPE_CHOICES, default="single_document")`
  - `document`: `ForeignKey("documents.Document", on_delete=models.SET_NULL, null=True, blank=True, related_name="custody_exports", db_index=True)`
  - `folder`: `ForeignKey("documents.DocumentFolder", on_delete=models.SET_NULL, null=True, blank=True, related_name="custody_exports")`
  - `start_date`: `DateField(null=True, blank=True)`
  - `end_date`: `DateField(null=True, blank=True)`
  - `package_hash`: `CharField(max_length=64, blank=True)`
  - `manifest_json`: `JSONField(default=dict, blank=True)`
  - `is_sealed`: `BooleanField(default=True)`
  - `sealed_at`: `DateTimeField(default=timezone.now)`
  - `auditor_name`: `CharField(max_length=150)`
  - `auditor_email`: `EmailField()`
  - `auditor_organization`: `CharField(max_length=200, blank=True)`
  - `access_token`: `CharField(max_length=64, unique=True, db_index=True)`
  - `passcode_hash`: `CharField(max_length=128, blank=True)`
  - `is_portal_active`: `BooleanField(default=True, db_index=True)`
  - `expires_at`: `DateTimeField(db_index=True)`
  - `access_count`: `PositiveIntegerField(default=0)`
  - `last_accessed_at`: `DateTimeField(null=True, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="dms_created_custody_exports")`
  - `revoked_at`: `DateTimeField(null=True, blank=True)`
  - `revoked_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dms_revoked_custody_exports")`
- **Indexes & Constraints (`<= 30` chars)**:
  - `models.UniqueConstraint(fields=["tenant", "number"], name="doc_dcoc_ten_num_uniq")`
  - `models.Index(fields=["tenant", "document"], name="doc_dcoc_tnt_doc_idx")`
  - `models.Index(fields=["tenant", "access_token"], name="doc_dcoc_tnt_tok_idx")`
  - `models.Index(fields=["tenant", "is_portal_active"], name="doc_dcoc_tnt_act_idx")`
  - `models.Index(fields=["tenant", "expires_at"], name="doc_dcoc_tnt_exp_idx")`
- **Properties & Helper Methods**:
  - `is_expired` (@property): `timezone.now() > self.expires_at`
  - `is_valid` (@property): `self.is_portal_active and not self.is_expired`
  - `set_passcode(raw_passcode)`: `self.passcode_hash = make_password(raw_passcode)`
  - `check_passcode(raw_passcode)`: `check_password(raw_passcode, self.passcode_hash)` if `self.passcode_hash` else `True`
  - `generate_manifest()`: Compiles document metadata, version history, file SHA-256 hashes, and chronological audit entries; computes `package_hash`.
  - `revoke(user)`: Sets `is_portal_active=False`, `revoked_at=timezone.now()`, `revoked_by=user`.

---

## 2. Forms Contract (`apps/documents/forms/AuditReporting/`)

### 2.1 `DocumentAuditTrailFilterForm` (`DocumentAuditTrails.py`)
- Standard Django `Form` (not ModelForm)
- Fields:
  - `q`: `CharField(required=False, widget=TextInput(attrs={'placeholder': 'Search action, actor, doc, details...', 'class': 'form-input'}))`
  - `action_type`: `ChoiceField(required=False, choices=[('', 'All Actions')] + DocumentAuditTrail.ACTION_TYPE_CHOICES, widget=Select(attrs={'class': 'form-select'}))`
  - `is_success`: `ChoiceField(required=False, choices=[('', 'All Results'), ('1', 'Success'), ('0', 'Failed/Blocked')], widget=Select(attrs={'class': 'form-select'}))`
  - `date_from`: `DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-input'}))`
  - `date_to`: `DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-input'}))`

### 2.2 `AuditReportDefinitionForm` (`AuditReportDefinitions.py`)
- Subclasses `ModelForm`
- `Meta.model`: `AuditReportDefinition`
- `Meta.fields`: `["name", "description", "report_type", "date_range_preset", "custom_start_date", "custom_end_date", "output_format", "status"]`
- Excluded fields: `tenant`, `number`, `is_system_preset`, `created_by`, `last_run_at`, `last_run_by`, `total_runs`, `filter_criteria_json`, `created_at`, `updated_at`.
- Validation: When `date_range_preset == "custom"`, `custom_start_date` and `custom_end_date` are required and start must be `<= end`.

### 2.3 `DocumentSecurityAlertTriageForm` (`DocumentSecurityAlerts.py`)
- Subclasses `ModelForm`
- `Meta.model`: `DocumentSecurityAlert`
- `Meta.fields`: `["status", "severity", "action_taken", "assigned_to", "triage_notes"]`
- Excluded fields: `tenant`, `number`, `alert_type`, `risk_score`, `title`, `description`, `detected_at`, `target_user`, `target_document`, `source_ip`, `event_count`, `evidence_json`, `resolved_at`, `resolved_by`, `created_at`, `updated_at`.
- `__init__(tenant, *args, **kwargs)`: Filters `assigned_to` queryset by `tenant`.

### 2.4 `DocumentSecurityAlertFilterForm` (`DocumentSecurityAlerts.py`)
- Standard Django `Form`
- Fields: `q`, `severity`, `status`, `alert_type`

### 2.5 `ChainOfCustodyExportForm` (`ChainOfCustodyExports.py`)
- Subclasses `ModelForm`
- `Meta.model`: `ChainOfCustodyExport`
- `Meta.fields`: `["title", "regulatory_framework", "scope", "document", "folder", "start_date", "end_date", "auditor_name", "auditor_email", "auditor_organization", "expires_at"]`
- Extra field: `portal_passcode = CharField(required=False, widget=PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Optional guest passcode'}))`
- Excluded fields: `tenant`, `number`, `package_hash`, `manifest_json`, `is_sealed`, `sealed_at`, `access_token`, `passcode_hash`, `is_portal_active`, `access_count`, `last_accessed_at`, `created_by`, `revoked_at`, `revoked_by`, `created_at`, `updated_at`.
- `__init__(tenant, *args, **kwargs)`: Filters `document` and `folder` querysets by `tenant`.

### 2.6 `AuditorPortalPasscodeForm` (`ChainOfCustodyExports.py`)
- Standard Django `Form`
- Field: `passcode = CharField(required=True, widget=PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Enter Portal Passcode'}))`

---

## 3. Views & URLs Contract (`apps/documents/views/AuditReporting/`)

### 3.1 DocumentAuditTrails
- Module: `apps/documents/views/AuditReporting/DocumentAuditTrails.py`
- URL Module: `apps/documents/urls/AuditReporting/DocumentAuditTrails.py`
- Routes:
  - `path("audit-trails/", audit_trail_list, name="audit_trail_list")`
  - `path("audit-trails/verify-chain/", audit_trail_verify_chain, name="audit_trail_verify_chain")`
  - `path("audit-trails/export-csv/", audit_trail_export_csv, name="audit_trail_export_csv")`
  - `path("audit-trails/<int:pk>/", audit_trail_detail, name="audit_trail_detail")`
- Context Keys:
  - `audit_trail_list`: `audit_trails`, `page_obj`, `filter_form`, `total_count`, `chain_status`, `action_type_choices`, `result_choices`, `search_query`
  - `audit_trail_detail`: `audit_entry`, `chain_valid`, `prev_entry`, `next_entry`
  - `audit_trail_verify_chain`: `is_valid`, `verified_count`, `tampered_id`, `latest_hash`

### 3.2 AuditReportDefinitions
- Module: `apps/documents/views/AuditReporting/AuditReportDefinitions.py`
- URL Module: `apps/documents/urls/AuditReporting/AuditReportDefinitions.py`
- Routes:
  - `path("audit-reports/", audit_report_list, name="audit_report_list")`
  - `path("audit-reports/create/", audit_report_create, name="audit_report_create")`
  - `path("audit-reports/<int:pk>/", audit_report_detail, name="audit_report_detail")`
  - `path("audit-reports/<int:pk>/edit/", audit_report_edit, name="audit_report_edit")`
  - `path("audit-reports/<int:pk>/delete/", audit_report_delete, name="audit_report_delete")`
  - `path("audit-reports/<int:pk>/run/", audit_report_run, name="audit_report_run")`
- Context Keys:
  - `audit_report_list`: `system_reports`, `custom_reports`, `total_reports`, `report_type_choices`, `status_choices`
  - `audit_report_detail`: `report_def`, `report_data`, `summary_kpis`, `date_start`, `date_end`, `total_events`
  - `audit_report_create` & `audit_report_edit`: `form`, `report_def`, `is_edit`

### 3.3 DocumentSecurityAlerts
- Module: `apps/documents/views/AuditReporting/DocumentSecurityAlerts.py`
- URL Module: `apps/documents/urls/AuditReporting/DocumentSecurityAlerts.py`
- Routes:
  - `path("security-alerts/", security_alert_list, name="security_alert_list")`
  - `path("security-alerts/scan/", security_alert_scan, name="security_alert_scan")`
  - `path("security-alerts/<int:pk>/", security_alert_detail, name="security_alert_detail")`
  - `path("security-alerts/<int:pk>/triage/", security_alert_triage, name="security_alert_triage")`
- Context Keys:
  - `security_alert_list`: `alerts`, `page_obj`, `filter_form`, `open_count`, `critical_count`, `severity_choices`, `status_choices`, `alert_type_choices`
  - `security_alert_detail`: `alert`, `triage_form`, `correlated_audit_logs`, `target_user_stats`

### 3.4 ChainOfCustodyExports
- Module: `apps/documents/views/AuditReporting/ChainOfCustodyExports.py`
- URL Module: `apps/documents/urls/AuditReporting/ChainOfCustodyExports.py`
- Routes:
  - `path("custody-exports/", custody_export_list, name="custody_export_list")`
  - `path("custody-exports/create/", custody_export_create, name="custody_export_create")`
  - `path("custody-exports/<int:pk>/", custody_export_detail, name="custody_export_detail")`
  - `path("custody-exports/<int:pk>/certificate/", custody_export_certificate, name="custody_export_certificate")`
  - `path("custody-exports/<int:pk>/revoke/", custody_export_revoke, name="custody_export_revoke")`
  - `path("auditor-portal/<str:token>/", auditor_portal_view, name="auditor_portal_view")`
  - `path("auditor-portal/<str:token>/verify/", auditor_portal_verify, name="auditor_portal_verify")`
- Context Keys:
  - `custody_export_list`: `exports`, `page_obj`, `active_passes_count`, `framework_choices`
  - `custody_export_create`: `form`
  - `custody_export_detail`: `export_pkg`, `portal_url`, `manifest_data`, `is_hash_valid`
  - `custody_export_certificate`: `export_pkg`, `manifest_data`, `tenant`
  - `auditor_portal_view`: `export_pkg`, `manifest_data`, `passcode_required`, `passcode_form`, `document`, `versions`, `audit_trail`

### 3.5 AuditReportingDashboard
- Module: `apps/documents/views/AuditReporting/AuditReportingDashboard.py`
- URL Module: `apps/documents/urls/AuditReporting/AuditReportingDashboard.py`
- Routes:
  - `path("audit-dashboard/", audit_dashboard, name="audit_dashboard")`
  - `path("lifecycle-dashboard/", document_lifecycle_dashboard, name="document_lifecycle_dashboard")`
- Context Keys:
  - `audit_dashboard`: `stats` (total_events_24h, downloads_24h, security_threats, chain_status), `recent_audit_logs`, `recent_alerts`, `active_custody_passes`
  - `document_lifecycle_dashboard`: `lifecycle_kpis` (avg_approval_hours, bottleneck_stages, high_churn_docs, status_distribution)

---

## 4. Navigation & LIVE_LINKS Mapping (`apps/core/navigation.py`)

All 5 NavERP.md `### 13.10` section bullets are mapped directly in `LIVE_LINKS["13.10"]`:
```python
LIVE_LINKS["13.10"] = {
    "Immutable Activity Logs": "documents:audit_trail_list",
    "Audit Report Generation": "documents:audit_report_list",
    "User Behavior Analytics": "documents:security_alert_list",
    "Document Lifecycle Reporting": "documents:document_lifecycle_dashboard",
    "Regulatory Audit Support": "documents:custody_export_list",
    "Chain of Custody Packages": "documents:custody_export_list",
    "Audit Command Center": "documents:audit_dashboard",
}
```

---

## 5. Security & Isolation Rules
- Every query has `tenant=request.tenant`.
- Forms validate tenant matches for all foreign keys.
- Write actions require `@require_POST` and `@login_required` (except external auditor portal which uses unguessable token + session passcode).
- Streaming CSV uses CSV injection sanitization (prefixing `'='`, `'+'`, `'-'`, `'@'` with single quote).
- External auditor portal interaction logs back to `DocumentAuditTrail` with `action_type="auditor_portal_accessed"`.
