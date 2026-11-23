# Module 13.7 Pre-Build Contract — Document Security & Access Control (`apps/documents/`)

> Frozen in Phase 3.1 before any entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["13.7"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.documents` (Extends existing app; claims incremental migration `0014_...`)
- **Package Directories**:
  - `apps/documents/models/SecurityAccessControl/`
  - `apps/documents/forms/SecurityAccessControl/`
  - `apps/documents/views/SecurityAccessControl/`
  - `apps/documents/urls/SecurityAccessControl/`
  - `templates/documents/security_access_control/{document_access_permission,watermark_policy,document_drm_policy,dlp_policy,dlp_incident}/{list,detail,form}.html` + `secure_viewer.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"revoke"`, `"resolve"`, `"simulate"`, `"view"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `documents.Document`, `documents.DocumentVersion`, `documents.DocumentFolder`, `documents.DlpPolicy`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/documents/models/SecurityAccessControl/`)

All 5 models inherit `apps.documents.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `DocumentAccessPermission` (`DocumentAccessPermissions.py`)
- **`NUMBER_PREFIX`**: `"DPRM"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Access Permission"` / `"Document Access Permissions"`
- **Choices & Badge Maps**:
  - `GRANTEE_TYPE_CHOICES` (`max_length=20`):
    - `("user", "Specific User")`
    - `("org_unit", "Organizational Unit (Department)")`
    - `("role", "Standardized Role")`
    - `("tenant_wide", "Tenant-Wide (All Employees)")`
  - `PERMISSION_LEVEL_CHOICES` (`max_length=20`):
    - `("viewer", "Viewer (Read & Preview Only)")`
    - `("commenter", "Commenter (Read & Annotate)")`
    - `("editor", "Editor (Read, Edit, & Version)")`
    - `("manager", "Manager (Read, Edit, & Share)")`
    - `("owner", "Owner (Full Control & Admin)")`
    - `("custom", "Custom Capabilities Matrix")`
  - `GRANTEE_TYPE_CSS`:
    - `"user": "badge-info"`
    - `"org_unit": "badge-purple"`
    - `"role": "badge-amber"`
    - `"tenant_wide": "badge-slate"`
  - `PERMISSION_LEVEL_CSS`:
    - `"viewer": "badge-slate"`
    - `"commenter": "badge-info"`
    - `"editor": "badge-amber"`
    - `"manager": "badge-purple"`
    - `"owner": "badge-green"`
    - `"custom": "badge-muted"`
- **Fields (exact names & types)**:
  - `number`: `CharField(max_length=32, editable=False)`
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)`
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, null=True, blank=True, related_name="access_permissions")`
  - `folder`: `ForeignKey("documents.DocumentFolder", on_delete=models.CASCADE, null=True, blank=True, related_name="access_permissions")`
  - `grantee_type`: `CharField(max_length=20, choices=GRANTEE_TYPE_CHOICES, default="user", db_index=True)`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="document_permissions")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.CASCADE, null=True, blank=True, related_name="document_permissions")`
  - `role_name`: `CharField(max_length=50, blank=True)`
  - `permission_level`: `CharField(max_length=20, choices=PERMISSION_LEVEL_CHOICES, default="viewer")`
  - `can_read`: `BooleanField(default=True)`
  - `can_write`: `BooleanField(default=False)`
  - `can_delete`: `BooleanField(default=False)`
  - `can_download`: `BooleanField(default=True)`
  - `can_print`: `BooleanField(default=True)`
  - `can_share`: `BooleanField(default=False)`
  - `is_inherited`: `BooleanField(default=False)`
  - `inherited_from_folder`: `ForeignKey("documents.DocumentFolder", on_delete=models.SET_NULL, null=True, blank=True, related_name="inherited_permissions")`
  - `valid_from`: `DateTimeField(null=True, blank=True)`
  - `valid_until`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `access_count`: `PositiveIntegerField(default=0)`
  - `last_accessed_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `CharField(max_length=255, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="granted_document_permissions")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dprm_ten_num_uniq")` (21 chars)
  - `models.Index(fields=["tenant", "document", "is_active"], name="doc_dprm_tnt_doc_act_idx")` (24 chars)
  - `models.Index(fields=["tenant", "user", "is_active"], name="doc_dprm_tnt_usr_act_idx")` (24 chars)
  - `models.Index(fields=["tenant", "folder", "is_active"], name="doc_dprm_tnt_fld_act_idx")` (24 chars)

---

### 1.2 `WatermarkPolicy` (`WatermarkPolicies.py`)
- **`NUMBER_PREFIX`**: `"DWTR"`
- **`Meta.ordering`**: `["priority", "name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Watermark Policy"` / `"Watermark Policies"`
- **Choices & Badge Maps**:
  - `CLASSIFICATION_CHOICES` (`max_length=20`):
    - `("all", "All Classifications")`
    - `("public", "Public")`
    - `("internal", "Internal Use Only")`
    - `("confidential", "Confidential")`
    - `("restricted", "Strictly Restricted")`
  - `POSITION_CHOICES` (`max_length=20`):
    - `("diagonal_center", "Diagonal Center (-45°)")`
    - `("center", "Horizontal Center")`
    - `("header_banner", "Top Header Banner")`
    - `("footer_banner", "Bottom Footer Banner")`
    - `("tiled_grid", "Tiled Watermark Grid")`
  - `BANNER_POSITION_CHOICES` (`max_length=20`):
    - `("top", "Top Only")`
    - `("bottom", "Bottom Only")`
    - `("both", "Top and Bottom")`
  - `CLASSIFICATION_CSS`:
    - `"all": "badge-slate"`
    - `"public": "badge-green"`
    - `"internal": "badge-info"`
    - `"confidential": "badge-amber"`
    - `"restricted": "badge-red"`
- **Fields (exact names & types)**:
  - `number`: `CharField(max_length=32, editable=False)`
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)`
  - `name`: `CharField(max_length=150)`
  - `slug`: `SlugField(max_length=160, blank=True)`
  - `description`: `TextField(blank=True)`
  - `classification`: `CharField(max_length=20, choices=CLASSIFICATION_CHOICES, default="all")`
  - `document_type`: `CharField(max_length=40, default="all")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="watermark_policies")`
  - `apply_to_all`: `BooleanField(default=False)`
  - `watermark_text`: `CharField(max_length=255, default="{{classification}} | {{user_name}} | {{timestamp}}")`
  - `secondary_text`: `CharField(max_length=255, blank=True)`
  - `position`: `CharField(max_length=20, choices=POSITION_CHOICES, default="diagonal_center")`
  - `opacity_percent`: `PositiveIntegerField(default=25)`
  - `font_size`: `PositiveIntegerField(default=32)`
  - `font_color`: `CharField(max_length=20, default="#94a3b8")`
  - `rotation_angle`: `IntegerField(default=-45)`
  - `show_classification_banner`: `BooleanField(default=True)`
  - `banner_position`: `CharField(max_length=20, choices=BANNER_POSITION_CHOICES, default="top")`
  - `enforce_on_view`: `BooleanField(default=True)`
  - `enforce_on_download`: `BooleanField(default=True)`
  - `enforce_on_print`: `BooleanField(default=True)`
  - `priority`: `PositiveIntegerField(default=100)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_watermark_policies")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dwtr_ten_num_uniq")` (21 chars)
  - `UniqueConstraint(fields=["tenant", "slug"], name="doc_dwtr_tnt_slug_uniq")` (22 chars)
  - `models.Index(fields=["tenant", "is_active", "priority"], name="doc_dwtr_tnt_act_prio_idx")` (25 chars)
  - `models.Index(fields=["tenant", "classification", "is_active"], name="doc_dwtr_tnt_cls_act_idx")` (24 chars)

---

### 1.3 `DocumentDrmPolicy` (`DocumentDrmPolicies.py`)
- **`NUMBER_PREFIX`**: `"DDRM"`
- **`Meta.ordering`**: `["name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document DRM Policy"` / `"Document DRM Policies"`
- **Choices & Badge Maps**:
  - `CLASSIFICATION_CHOICES` (`max_length=20`):
    - `("all", "All Classifications")`
    - `("public", "Public")`
    - `("internal", "Internal Use Only")`
    - `("confidential", "Confidential")`
    - `("restricted", "Strictly Restricted")`
  - `ENCRYPTION_CHOICES` (`max_length=30`):
    - `("AES_256_GCM", "AES-256-GCM (Authenticated)")`
    - `("AES_256_CBC", "AES-256-CBC (Standard)")`
    - `("CHACHA20_POLY1305", "ChaCha20-Poly1305 (Stream)")`
  - `STATUS_CSS`:
    - `True: "badge-green"`
    - `False: "badge-slate"`
  - `REVOCATION_CSS`:
    - `True: "badge-red"`
    - `False: "badge-green"`
- **Fields (exact names & types)**:
  - `number`: `CharField(max_length=32, editable=False)`
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)`
  - `name`: `CharField(max_length=150)`
  - `slug`: `SlugField(max_length=160, blank=True)`
  - `description`: `TextField(blank=True)`
  - `classification`: `CharField(max_length=20, choices=CLASSIFICATION_CHOICES, default="confidential")`
  - `document_type`: `CharField(max_length=40, default="all")`
  - `target_document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, null=True, blank=True, related_name="drm_policies")`
  - `target_folder`: `ForeignKey("documents.DocumentFolder", on_delete=models.CASCADE, null=True, blank=True, related_name="drm_policies")`
  - `allow_download`: `BooleanField(default=False)`
  - `allow_print`: `BooleanField(default=False)`
  - `allow_copy_paste`: `BooleanField(default=False)`
  - `screen_shield_enabled`: `BooleanField(default=True)`
  - `secure_viewer_required`: `BooleanField(default=True)`
  - `require_watermark`: `BooleanField(default=True)`
  - `max_offline_hours`: `PositiveIntegerField(default=0)`
  - `expiry_days`: `PositiveIntegerField(default=30)`
  - `ip_allowlist`: `TextField(blank=True)`
  - `geo_fencing_countries`: `CharField(max_length=255, blank=True)`
  - `is_revoked`: `BooleanField(default=False, db_index=True)`
  - `revoked_at`: `DateTimeField(null=True, blank=True)`
  - `revocation_reason`: `TextField(blank=True)`
  - `encryption_standard`: `CharField(max_length=30, choices=ENCRYPTION_CHOICES, default="AES_256_GCM")`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_drm_policies")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_ddrm_ten_num_uniq")` (21 chars)
  - `UniqueConstraint(fields=["tenant", "slug"], name="doc_ddrm_tnt_slug_uniq")` (22 chars)
  - `models.Index(fields=["tenant", "is_active", "is_revoked"], name="doc_ddrm_tnt_act_rvk_idx")` (24 chars)
  - `models.Index(fields=["tenant", "classification", "is_active"], name="doc_ddrm_tnt_cls_act_idx")` (24 chars)

---

### 1.4 `DlpPolicy` (`DlpPolicies.py`)
- **`NUMBER_PREFIX`**: `"DDLP"`
- **`Meta.ordering`**: `["severity", "name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"DLP Policy"` / `"DLP Policies"`
- **Choices & Badge Maps**:
  - `RULE_TYPE_CHOICES` (`max_length=30`):
    - `("built_in_pattern", "Built-in SIT Pattern")`
    - `("sensitive_keywords", "Sensitive Keyword List")`
    - `("custom_regex", "Custom Regular Expression")`
    - `("classification_anomaly", "Classification Level Anomaly")`
  - `BUILT_IN_PATTERN_CHOICES` (`max_length=30`):
    - `("none", "None / Custom Only")`
    - `("credit_card_pci", "Payment Card Industry (PCI-DSS Credit Cards)")`
    - `("us_ssn", "US Social Security Number (SSN)")`
    - `("iban_banking", "International Bank Account Number (IBAN)")`
    - `("national_id_pii", "National ID & Government Identifiers")`
    - `("email_list", "Bulk Email Addresses Extraction")`
    - `("api_keys_secrets", "API Keys, Tokens & Private Keys")`
  - `ACTION_CHOICES` (`max_length=20`):
    - `("log_only", "Audit Log Only (Silent Monitor)")`
    - `("warn_author", "Warn Author on Save")`
    - `("block_save", "Block Document Save / Upload")`
    - `("quarantine", "Quarantine Document for Review")`
    - `("force_watermark", "Force Strict Watermarking")`
  - `SEVERITY_CHOICES` (`max_length=20`):
    - `("low", "Low")`
    - `("medium", "Medium")`
    - `("high", "High")`
    - `("critical", "Critical")`
  - `SEVERITY_CSS`:
    - `"low": "badge-slate"`
    - `"medium": "badge-info"`
    - `"high": "badge-amber"`
    - `"critical": "badge-red"`
  - `ACTION_CSS`:
    - `"log_only": "badge-slate"`
    - `"warn_author": "badge-info"`
    - `"block_save": "badge-red"`
    - `"quarantine": "badge-amber"`
    - `"force_watermark": "badge-purple"`
- **Fields (exact names & types)**:
  - `number`: `CharField(max_length=32, editable=False)`
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)`
  - `name`: `CharField(max_length=150)`
  - `slug`: `SlugField(max_length=160, blank=True)`
  - `description`: `TextField(blank=True)`
  - `rule_type`: `CharField(max_length=30, choices=RULE_TYPE_CHOICES, default="built_in_pattern")`
  - `built_in_pattern`: `CharField(max_length=30, choices=BUILT_IN_PATTERN_CHOICES, default="none")`
  - `custom_regex`: `TextField(blank=True)`
  - `sensitive_keywords`: `JSONField(default=list, blank=True)`
  - `match_threshold`: `PositiveIntegerField(default=1)`
  - `action`: `CharField(max_length=20, choices=ACTION_CHOICES, default="warn_author")`
  - `severity`: `CharField(max_length=20, choices=SEVERITY_CHOICES, default="high")`
  - `notify_security_officer`: `BooleanField(default=True)`
  - `notification_email`: `CharField(max_length=255, blank=True)`
  - `apply_to_all_types`: `BooleanField(default=True)`
  - `target_document_types`: `JSONField(default=list, blank=True)`
  - `target_classifications`: `JSONField(default=list, blank=True)`
  - `incident_count`: `PositiveIntegerField(default=0)`
  - `last_triggered_at`: `DateTimeField(null=True, blank=True)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_dlp_policies")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_ddlp_ten_num_uniq")` (21 chars)
  - `UniqueConstraint(fields=["tenant", "slug"], name="doc_ddlp_tnt_slug_uniq")` (22 chars)
  - `models.Index(fields=["tenant", "is_active", "severity"], name="doc_ddlp_tnt_act_sev_idx")` (24 chars)
  - `models.Index(fields=["tenant", "rule_type", "is_active"], name="doc_ddlp_tnt_rule_act_idx")` (25 chars)

---

### 1.5 `DlpIncident` (`DlpIncidents.py`)
- **`NUMBER_PREFIX`**: `"DINC"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"DLP Incident"` / `"DLP Incidents"`
- **Choices & Badge Maps**:
  - `SEVERITY_CHOICES` (`max_length=20`): `low`, `medium`, `high`, `critical`
  - `ACTION_TAKEN_CHOICES` (`max_length=20`):
    - `("logged", "Logged Only")`
    - `("warned", "Author Warned")`
    - `("blocked", "Save Blocked")`
    - `("quarantined", "Document Quarantined")`
    - `("watermarked", "Watermark Enforced")`
  - `RESOLUTION_CHOICES` (`max_length=25`):
    - `("open", "Open / Pending Review")`
    - `("under_investigation", "Under Investigation")`
    - `("resolved_justified", "Resolved (Legitimate Business Need)")`
    - `("false_positive", "False Positive")`
    - `("dismissed", "Dismissed")`
  - `RESOLUTION_CSS`:
    - `"open": "badge-red"`
    - `"under_investigation": "badge-amber"`
    - `"resolved_justified": "badge-green"`
    - `"false_positive": "badge-slate"`
    - `"dismissed": "badge-muted"`
- **Fields (exact names & types)**:
  - `number`: `CharField(max_length=32, editable=False)`
  - `tenant`: `ForeignKey("core.Tenant", on_delete=models.CASCADE, db_index=True)`
  - `policy`: `ForeignKey("documents.DlpPolicy", on_delete=models.CASCADE, related_name="incidents")`
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="dlp_incidents")`
  - `document_version`: `ForeignKey("documents.DocumentVersion", on_delete=models.SET_NULL, null=True, blank=True, related_name="dlp_incidents")`
  - `triggered_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="triggered_dlp_incidents")`
  - `severity`: `CharField(max_length=20, choices=SEVERITY_CHOICES, default="high")`
  - `action_taken`: `CharField(max_length=20, choices=ACTION_TAKEN_CHOICES, default="logged")`
  - `matches_detected_count`: `PositiveIntegerField(default=1)`
  - `snippet_redacted`: `TextField(blank=True)`
  - `resolution_status`: `CharField(max_length=25, choices=RESOLUTION_CHOICES, default="open", db_index=True)`
  - `resolved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_dlp_incidents")`
  - `resolution_notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dinc_ten_num_uniq")` (21 chars)
  - `models.Index(fields=["tenant", "policy", "resolution_status"], name="doc_dinc_tnt_pol_res_idx")` (24 chars)
  - `models.Index(fields=["tenant", "document", "created_at"], name="doc_dinc_tnt_doc_crt_idx")` (24 chars)
  - `models.Index(fields=["tenant", "severity", "resolution_status"], name="doc_dinc_tnt_sev_res_idx")` (24 chars)

---

## 2. Forms Contract (`apps/documents/forms/SecurityAccessControl/`)

Each form accepts `tenant=request.tenant` in `__init__`, filters all FK querysets to `tenant`, and enforces tenant isolation in `clean()`.

### 2.1 `DocumentAccessPermissionForm`
- **Model**: `DocumentAccessPermission`
- **Fields**: `document`, `folder`, `grantee_type`, `user`, `org_unit`, `role_name`, `permission_level`, `can_read`, `can_write`, `can_delete`, `can_download`, `can_print`, `can_share`, `valid_from`, `valid_until`, `is_active`, `notes`
- **Exclusions**: `tenant`, `number`, `is_inherited`, `inherited_from_folder`, `access_count`, `last_accessed_at`, `created_by`, `created_at`, `updated_at`

### 2.2 `WatermarkPolicyForm`
- **Model**: `WatermarkPolicy`
- **Fields**: `name`, `slug`, `description`, `classification`, `document_type`, `department`, `apply_to_all`, `watermark_text`, `secondary_text`, `position`, `opacity_percent`, `font_size`, `font_color`, `rotation_angle`, `show_classification_banner`, `banner_position`, `enforce_on_view`, `enforce_on_download`, `enforce_on_print`, `priority`, `is_active`
- **Exclusions**: `tenant`, `number`, `created_by`, `created_at`, `updated_at`

### 2.3 `DocumentDrmPolicyForm`
- **Model**: `DocumentDrmPolicy`
- **Fields**: `name`, `slug`, `description`, `classification`, `document_type`, `target_document`, `target_folder`, `allow_download`, `allow_print`, `allow_copy_paste`, `screen_shield_enabled`, `secure_viewer_required`, `require_watermark`, `max_offline_hours`, `expiry_days`, `ip_allowlist`, `geo_fencing_countries`, `encryption_standard`, `is_active`
- **Exclusions**: `tenant`, `number`, `is_revoked`, `revoked_at`, `revocation_reason`, `created_by`, `created_at`, `updated_at`

### 2.4 `DlpPolicyForm`
- **Model**: `DlpPolicy`
- **Fields**: `name`, `slug`, `description`, `rule_type`, `built_in_pattern`, `custom_regex`, `sensitive_keywords`, `match_threshold`, `action`, `severity`, `notify_security_officer`, `notification_email`, `apply_to_all_types`, `target_document_types`, `target_classifications`, `is_active`
- **Exclusions**: `tenant`, `number`, `incident_count`, `last_triggered_at`, `created_by`, `created_at`, `updated_at`

### 2.5 `DlpIncidentResolveForm`
- **Model**: `DlpIncident`
- **Fields**: `resolution_status`, `resolution_notes`

---

## 3. URLs & Routes Contract (`apps/documents/urls/SecurityAccessControl/`)

Literal routes are declared BEFORE parameterized `<int:pk>/` routes!

### 3.1 Permissions Routes (`DocumentAccessPermissions.py`)
- `access-permissions/`: `documents:permission_list`
- `access-permissions/create/`: `documents:permission_create`
- `access-permissions/simulate/`: `documents:permission_simulate`
- `access-permissions/<int:pk>/`: `documents:permission_detail`
- `access-permissions/<int:pk>/edit/`: `documents:permission_edit`
- `access-permissions/<int:pk>/delete/`: `documents:permission_delete`

### 3.2 Watermark Routes (`WatermarkPolicies.py`)
- `watermark-policies/`: `documents:watermark_list`
- `watermark-policies/create/`: `documents:watermark_create`
- `watermark-policies/preview/`: `documents:watermark_preview`
- `watermark-policies/<int:pk>/`: `documents:watermark_detail`
- `watermark-policies/<int:pk>/edit/`: `documents:watermark_edit`
- `watermark-policies/<int:pk>/delete/`: `documents:watermark_delete`

### 3.3 DRM Policy Routes (`DocumentDrmPolicies.py`)
- `drm-policies/`: `documents:drm_policy_list`
- `drm-policies/create/`: `documents:drm_policy_create`
- `drm-policies/<int:pk>/`: `documents:drm_policy_detail`
- `drm-policies/<int:pk>/edit/`: `documents:drm_policy_edit`
- `drm-policies/<int:pk>/delete/`: `documents:drm_policy_delete`
- `drm-policies/<int:pk>/kill-switch/`: `documents:drm_kill_switch`

### 3.4 DLP Policy & Incident Routes (`DlpPolicies.py` & `DlpIncidents.py`)
- `dlp-policies/`: `documents:dlp_policy_list`
- `dlp-policies/create/`: `documents:dlp_policy_create`
- `dlp-policies/<int:pk>/`: `documents:dlp_policy_detail`
- `dlp-policies/<int:pk>/edit/`: `documents:dlp_policy_edit`
- `dlp-policies/<int:pk>/delete/`: `documents:dlp_policy_delete`
- `dlp-incidents/`: `documents:dlp_incident_list`
- `dlp-incidents/<int:pk>/`: `documents:dlp_incident_detail`
- `dlp-incidents/<int:pk>/resolve/`: `documents:dlp_incident_resolve`

### 3.5 Secure Viewer Routes (`SecureViewer.py`)
- `secure-viewer/`: `documents:secure_viewer`
- `secure-viewer/<int:pk>/`: `documents:secure_viewer_doc`

---

## 4. Views & Context Contract (`apps/documents/views/SecurityAccessControl/`)

### 4.1 `permission_list`
- Context keys: `permissions`, `page_obj`, `is_paginated`, `paginator`, `search_query`, `grantee_type`, `permission_level`, `is_active`, `grantee_choices`, `level_choices`, `documents`, `folders`

### 4.2 `permission_detail`
- Context keys: `permission`, `document`, `folder`, `grantee`

### 4.3 `permission_create` / `permission_edit`
- Context keys: `form`, `is_edit`, `permission` (if edit)

### 4.4 `permission_simulate`
- Context keys: `documents`, `users`, `simulated`, `target_document`, `target_user`, `effective_capabilities`

### 4.5 `watermark_list`
- Context keys: `policies`, `page_obj`, `is_paginated`, `paginator`, `search_query`, `classification`, `is_active`, `classification_choices`

### 4.6 `watermark_detail`
- Context keys: `policy`, `sample_watermark_text`

### 4.7 `watermark_create` / `watermark_edit`
- Context keys: `form`, `is_edit`, `policy` (if edit)

### 4.8 `watermark_preview`
- Context keys: `preview_text`, `opacity`, `angle`, `position`, `classification`

### 4.9 `drm_policy_list`
- Context keys: `policies`, `page_obj`, `is_paginated`, `paginator`, `search_query`, `classification`, `is_revoked`, `classification_choices`

### 4.10 `drm_policy_detail`
- Context keys: `policy`

### 4.11 `drm_policy_create` / `drm_policy_edit`
- Context keys: `form`, `is_edit`, `policy` (if edit)

### 4.12 `drm_kill_switch`
- Context keys: `policy`

### 4.13 `dlp_policy_list`
- Context keys: `policies`, `page_obj`, `is_paginated`, `paginator`, `search_query`, `rule_type`, `severity`, `is_active`, `rule_choices`, `severity_choices`

### 4.14 `dlp_policy_detail`
- Context keys: `policy`, `incidents`

### 4.15 `dlp_policy_create` / `dlp_policy_edit`
- Context keys: `form`, `is_edit`, `policy` (if edit)

### 4.16 `dlp_incident_list`
- Context keys: `incidents`, `page_obj`, `is_paginated`, `paginator`, `search_query`, `severity`, `resolution_status`, `severity_choices`, `resolution_choices`

### 4.17 `dlp_incident_detail`
- Context keys: `incident`, `resolve_form`

### 4.18 `dlp_incident_resolve`
- Context keys: `incident`, `form`

### 4.19 `secure_viewer` / `secure_viewer_doc`
- Context keys: `document`, `version`, `watermark_policy`, `drm_policy`, `watermark_text`, `screen_shield`, `allow_copy`, `allow_print`, `allow_download`, `available_documents`

---

## 5. Navigation LIVE_LINKS Contract (`apps/core/navigation.py`)

```python
    # 13.7 Document Security & Access Control
    "13.7": {
        "Document-Level Permissions": "documents:permission_list",
        "Dynamic Watermarking": "documents:watermark_list",
        "DRM & Document Protection": "documents:drm_policy_list",
        "Data Loss Prevention (DLP)": "documents:dlp_policy_list",
        # Extra live leaves:
        "DLP Incidents": "documents:dlp_incident_list",
        "Secure Web Viewer": "documents:secure_viewer",
    },
```
