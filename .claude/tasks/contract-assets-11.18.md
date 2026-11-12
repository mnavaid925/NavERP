# Module 11.18 Pre-Build Contract — IT Asset Management (ITAM) (`apps/assets/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["11.18"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.assets` (existing app; NO scaffold; NO `config/settings.py` or `config/urls.py` edit)
- **Migration**: Incremental (run `makemigrations assets --dry-run` in Phase 3.4 Integrate; claim next arrival-order number after current leaf)
- **Package Directories**:
  - `apps/assets/models/ItAssetManagement/`
  - `apps/assets/forms/ItAssetManagement/`
  - `apps/assets/views/ItAssetManagement/`
  - `apps/assets/urls/ItAssetManagement/`
  - `templates/assets/itassetmanagement/{it_hardware_asset,software_license,cloud_asset_subscription,cmdb_relationship}/{list,detail,form}.html` + `templates/assets/itassetmanagement/{it_refresh_board,cmdb_impact_analysis}.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, changes=..., tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"deploy"`, `"stock"`, `"repair"`, `"loaner"`, `"refresh"`, `"sanitize"`, `"retire"`, `"sync_elp"`, `"reclaim"`, `"true_up"`, `"renew"`, `"hold"`, `"sanction"`, `"shadow"`, `"finops"`, `"suspend"`, `"decomm"`, `"verify"`, `"deprec"`, `"sever"` (every verb `<= 8` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `csv_export_response` using `csv_safe(...)` formula neutralization + `X-Content-Type-Options: nosniff`.
- **Global `accounting.Currency` Rule (L39)**:
  - `accounting.Currency` is global (NO `tenant` FK). Filter ONLY `Currency.objects.filter(is_active=True)` in form `__init__`, and NEVER pass `"currency"` to `reject_foreign(...)` or `_TENANT_FK_FIELDS`.

---

## 1. Models & Choices Contract (`apps/assets/models/ItAssetManagement/`)

All 4 models inherit `apps.assets.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `ItHardwareAsset` (`ItHardwareAssets.py`)
- **`NUMBER_PREFIX`**: `"ITHW"`
- **`Meta.ordering`**: `["hostname", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"IT Hardware Asset"` / `"IT Hardware Assets"`
- **Choices & Badge Maps**:
  - `DEVICE_CLASS_CHOICES` (`max_length=24`, max value len 15):
    - `("laptop", "Laptop / Notebook")`
    - `("desktop", "Desktop PC")`
    - `("workstation", "Engineering Workstation")`
    - `("physical_server", "Physical Server")`
    - `("virtual_host", "Virtualization Host")`
    - `("network_switch", "Network Switch")`
    - `("router_firewall", "Router / Firewall")`
    - `("wireless_ap", "Wireless Access Point")`
    - `("storage_array", "SAN / NAS Storage Array")`
    - `("mobile_tablet", "Mobile / Tablet")`
    - `("printer_mfp", "Printer / MFP")`
    - `("peripheral", "Dock / Monitor / Peripheral")`
  - `ENVIRONMENT_CHOICES` (`max_length=24`, max value len 17):
    - `("corporate_enduser", "Corporate End-User")`
    - `("production", "Production")`
    - `("staging", "Staging")`
    - `("development", "Development")`
    - `("dr_standby", "DR / Standby")`
  - `CRITICALITY_CHOICES` (`max_length=16`, max value len 8):
    - `("critical", "Critical")`
    - `("high", "High")`
    - `("medium", "Medium")`
    - `("low", "Low")`
  - `DISK_ENCRYPTION_CHOICES` (`max_length=24`, max value len 19):
    - `("bitlocker_filevault", "BitLocker / FileVault")`
    - `("luks_encrypted", "LUKS / dm-crypt")`
    - `("unencrypted", "Unencrypted")`
    - `("exempt", "Exempt / N/A")`
  - `STATUS_CHOICES` (`max_length=24`, max value len 17):
    - `("procured", "Procured")`
    - `("staged_in_stock", "Staged in Stock")`
    - `("deployed", "Deployed / In Use")`
    - `("in_repair", "In Repair / RMA")`
    - `("loaner_pool", "Loaner Pool")`
    - `("pending_refresh", "Pending Refresh")`
    - `("sanitized_retired", "Sanitized & Retired")`
    - `("disposed", "Disposed")`
  - `SANITIZATION_METHOD_CHOICES` (`max_length=24`, max value len 18):
    - `("none", "None")`
    - `("nist_clear", "NIST SP 800-88 Clear")`
    - `("nist_purge", "NIST SP 800-88 Purge")`
    - `("crypto_erase", "Cryptographic Erase")`
    - `("physical_shredding", "Physical Shredding / Degauss")`
  - `SANITIZATION_STATUS_CHOICES` (`max_length=24`, max value len 19):
    - `("not_required", "Not Required")`
    - `("pending_wipe", "Pending Sanitization")`
    - `("wiped_verified", "Wiped & Verified")`
    - `("certificate_on_file", "Certificate on File")`
  - `STATUS_CSS`:
    - `"procured": "badge-slate"`, `"staged_in_stock": "badge-info"`, `"deployed": "badge-green"`, `"in_repair": "badge-amber"`, `"loaner_pool": "badge-info"`, `"pending_refresh": "badge-amber"`, `"sanitized_retired": "badge-slate"`, `"disposed": "badge-muted"`
  - `CRITICALITY_CSS`:
    - `"critical": "badge-red"`, `"high": "badge-amber"`, `"medium": "badge-info"`, `"low": "badge-slate"`
  - `SANITIZATION_CSS`:
    - `"not_required": "badge-slate"`, `"pending_wipe": "badge-amber"`, `"wiped_verified": "badge-green"`, `"certificate_on_file": "badge-green"`
  - `LOCKED_STATUSES = {"sanitized_retired", "disposed"}`
- **Fields**:
  - `hostname`: `CharField(max_length=120)`
  - `fqdn`: `CharField(max_length=200, blank=True)`
  - `device_class`: `CharField(max_length=24, choices=DEVICE_CLASS_CHOICES, default="laptop")`
  - `serial_number`: `CharField(max_length=80, blank=True)`
  - `asset_tag_code`: `CharField(max_length=64, blank=True)`
  - `manufacturer`: `CharField(max_length=120, blank=True)`
  - `model_name`: `CharField(max_length=120, blank=True)`
  - `mac_address`: `CharField(max_length=48, blank=True)`
  - `ip_address`: `GenericIPAddressField(null=True, blank=True)`
  - `operating_system`: `CharField(max_length=100, blank=True)`
  - `os_version`: `CharField(max_length=64, blank=True)`
  - `cpu_spec`: `CharField(max_length=120, blank=True)`
  - `ram_gb`: `PositiveIntegerField(null=True, blank=True)`
  - `storage_gb`: `PositiveIntegerField(null=True, blank=True)`
  - `bios_firmware_version`: `CharField(max_length=64, blank=True)`
  - `rack_unit_ref`: `CharField(max_length=64, blank=True)`
  - `environment`: `CharField(max_length=24, choices=ENVIRONMENT_CHOICES, default="corporate_enduser")`
  - `criticality`: `CharField(max_length=16, choices=CRITICALITY_CHOICES, default="medium")`
  - `mdm_enrolled`: `BooleanField(default=False)`
  - `mdm_platform`: `CharField(max_length=60, blank=True)`
  - `mdm_device_id`: `CharField(max_length=80, blank=True)`
  - `disk_encryption_status`: `CharField(max_length=24, choices=DISK_ENCRYPTION_CHOICES, default="unencrypted")`
  - `last_seen_checkin`: `DateTimeField(null=True, blank=True, editable=False)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="procured", editable=False)`
  - `commissioned_date`: `DateField(null=True, blank=True)`
  - `assigned_date`: `DateField(null=True, blank=True)`
  - `vendor_eos_date`: `DateField(null=True, blank=True)`
  - `vendor_eol_date`: `DateField(null=True, blank=True)`
  - `refresh_cycle_months`: `PositiveSmallIntegerField(default=48)`
  - `refresh_due_date`: `DateField(null=True, blank=True)`
  - `estimated_refresh_cost`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")` (GLOBAL)
  - `sanitization_required`: `BooleanField(default=True)`
  - `sanitization_method`: `CharField(max_length=24, choices=SANITIZATION_METHOD_CHOICES, default="none")`
  - `sanitization_status`: `CharField(max_length=24, choices=SANITIZATION_STATUS_CHOICES, default="pending_wipe")`
  - `sanitization_date`: `DateField(null=True, blank=True)`
  - `sanitization_certificate_ref`: `CharField(max_length=100, blank=True)`
  - `sanitization_verified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, editable=False, related_name="verified_it_sanitizations")`
  - `sanitized_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `retired_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `operational_asset`: `ForeignKey("scm.Asset", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")`
  - `fixed_asset`: `ForeignKey("accounting.FixedAsset", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")`
  - `asset_model`: `ForeignKey("assets.AssetModel", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")`
  - `asset_category`: `ForeignKey("assets.AssetCategory", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")`
  - `warranty`: `ForeignKey("assets.AssetWarranty", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")`
  - `requisition`: `ForeignKey("assets.AssetRequisition", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")`
  - `replacement_plan`: `ForeignKey("assets.AssetReplacementPlan", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")`
  - `disposal_request`: `ForeignKey("assets.AssetDisposalRequest", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")`
  - `scrap_salvage`: `ForeignKey("assets.AssetScrapSalvage", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")`
  - `location`: `ForeignKey("scm.Location", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")`
  - `custodian_party`: `ForeignKey("core.Party", on_delete=SET_NULL, null=True, blank=True, related_name="custodian_it_hardware_assets")`
  - `vendor_party`: `ForeignKey("core.Party", on_delete=SET_NULL, null=True, blank=True, related_name="vendor_it_hardware_assets")`
  - `employee_profile`: `ForeignKey("hrm.EmployeeProfile", on_delete=SET_NULL, null=True, blank=True, related_name="it_hardware_assets")`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="owned_it_hardware_assets")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_ithw_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_ithw_ten_stat")`
  - `Index(fields=["tenant", "device_class"], name="idx_ithw_ten_dcls")`
  - `Index(fields=["tenant", "vendor_eol_date"], name="idx_ithw_ten_eol")`
  - `Index(fields=["tenant", "refresh_due_date"], name="idx_ithw_ten_rfsh")`
- **Derived Properties**:
  - `is_eol_expired` (bool: `vendor_eol_date` < today)
  - `is_eos_approaching` (bool: `vendor_eos_date` <= today + 90d and >= today)
  - `refresh_priority` (`"overdue_critical"`, `"due_within_90d"`, `"planned_fy"`, `"healthy"`)
  - `refresh_priority_badge_class` (`badge-red` / `badge-amber` / `badge-info` / `badge-green`)
  - `status_badge_class`, `criticality_badge_class`, `sanitization_badge_class`
  - `is_locked` (`status in LOCKED_STATUSES`)
- **`save()` auto-derivation**:
  - If `refresh_due_date` is None: derive from `commissioned_date + refresh_cycle_months` (using calendar month helper `_add_months`) or fallback to `vendor_eol_date`.

---

### 1.2 `SoftwareLicense` (`SoftwareLicenses.py`)
- **`NUMBER_PREFIX`**: `"ITSW"`
- **`Meta.ordering`**: `["software_name", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Software License"` / `"Software Licenses"`
- **Choices & Badge Maps**:
  - `SOFTWARE_CATEGORY_CHOICES` (`max_length=24`, max value len 18):
    - `("os_platform", "OS & Platform")`
    - `("productivity_suite", "Productivity & Collaboration")`
    - `("erp_finance", "ERP & Finance")`
    - `("devops_ide", "DevOps & Developer Tools")`
    - `("database_engine", "Database Engine")`
    - `("security_edr", "Security & EDR")`
    - `("design_cad", "Engineering / CAD / Creative")`
    - `("virtualization", "Virtualization & Hypervisor")`
    - `("middleware", "Middleware & Integration")`
    - `("other", "Other Software")`
  - `LICENSE_TYPE_CHOICES` (`max_length=32`, max value len 22):
    - `("subscription_term", "Term Subscription")`
    - `("perpetual", "Perpetual")`
    - `("enterprise_ela", "Enterprise Agreement (ELA)")`
    - `("oem_bundled", "OEM / Hardware Bundled")`
    - `("open_source_commercial", "Commercial Open Source")`
  - `LICENSE_METRIC_CHOICES` (`max_length=24`, max value len 19):
    - `("per_user", "Per Named User")`
    - `("per_device", "Per Device / Endpoint")`
    - `("per_core", "Per Processor Core")`
    - `("per_cpu_socket", "Per CPU Socket")`
    - `("concurrent_floating", "Concurrent / Floating")`
    - `("site_unlimited", "Site / Enterprise Unlimited")`
    - `("cal_client_access", "Client Access License (CAL)")`
  - `STATUS_CHOICES` (`max_length=24`, max value len 19):
    - `("draft", "Draft")`
    - `("active_compliant", "Active / Compliant")`
    - `("surplus_reclaimable", "Surplus / Reclaimable")`
    - `("true_up_required", "True-Up Required")`
    - `("audit_hold", "Audit Hold")`
    - `("expired", "Expired")`
    - `("retired", "Retired")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`, `"active_compliant": "badge-green"`, `"surplus_reclaimable": "badge-info"`, `"true_up_required": "badge-red"`, `"audit_hold": "badge-amber"`, `"expired": "badge-red"`, `"retired": "badge-muted"`
  - `LOCKED_STATUSES = {"retired"}`
- **Fields**:
  - `software_name`: `CharField(max_length=200)`
  - `publisher_name`: `CharField(max_length=150)`
  - `product_sku`: `CharField(max_length=80, blank=True)`
  - `version_edition`: `CharField(max_length=80, blank=True)`
  - `software_category`: `CharField(max_length=24, choices=SOFTWARE_CATEGORY_CHOICES, default="productivity_suite")`
  - `license_type`: `CharField(max_length=32, choices=LICENSE_TYPE_CHOICES, default="subscription_term")`
  - `license_metric`: `CharField(max_length=24, choices=LICENSE_METRIC_CHOICES, default="per_user")`
  - `agreement_number`: `CharField(max_length=80, blank=True)`
  - `license_key_ref`: `CharField(max_length=120, blank=True)` (masked reference only — e.g. `MS365-****-9X2K`)
  - `entitled_quantity`: `PositiveIntegerField(default=1)`
  - `allocated_quantity`: `PositiveIntegerField(default=0)`
  - `active_used_quantity`: `PositiveIntegerField(default=0)`
  - `reclaimable_inactive_count`: `PositiveIntegerField(default=0)`
  - `unit_license_cost`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `total_annual_spend`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=SET_NULL, null=True, blank=True, related_name="software_licenses")` (GLOBAL)
  - `effective_date`: `DateField(null=True, blank=True)`
  - `renewal_date`: `DateField(null=True, blank=True)`
  - `vendor_eol_date`: `DateField(null=True, blank=True)`
  - `auto_renew`: `BooleanField(default=False)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="draft", editable=False)`
  - `last_reconciled_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `retired_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `publisher_party`: `ForeignKey("core.Party", on_delete=SET_NULL, null=True, blank=True, related_name="publisher_software_licenses")`
  - `reseller_party`: `ForeignKey("core.Party", on_delete=SET_NULL, null=True, blank=True, related_name="reseller_software_licenses")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True, related_name="software_licenses")`
  - `gl_expense_account`: `ForeignKey("accounting.GLAccount", on_delete=SET_NULL, null=True, blank=True, related_name="software_licenses")`
  - `purchase_order`: `ForeignKey("scm.PurchaseOrder", on_delete=SET_NULL, null=True, blank=True, related_name="software_licenses")`
  - `service_contract`: `ForeignKey("assets.AssetServiceContract", on_delete=SET_NULL, null=True, blank=True, related_name="software_licenses")`
  - `license_owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="owned_software_licenses")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_itsw_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_itsw_ten_stat")`
  - `Index(fields=["tenant", "software_category"], name="idx_itsw_ten_cat")`
  - `Index(fields=["tenant", "renewal_date"], name="idx_itsw_ten_ren")`
  - `Index(fields=["tenant", "vendor_eol_date"], name="idx_itsw_ten_eol")`
- **Derived Properties**:
  - `compliance_delta` (`entitled_quantity - allocated_quantity`)
  - `is_under_licensed` (`compliance_delta < 0`)
  - `utilization_pct` (`round(active_used_quantity * 100 / entitled_quantity, 1)` when `entitled_quantity > 0` else `0.0`)
  - `estimated_true_up_cost` (`abs(compliance_delta) * unit_license_cost` when `compliance_delta < 0` else `Decimal("0.00")`)
  - `reclaim_savings_potential` (`reclaimable_inactive_count * unit_license_cost`)
  - `is_eol_expired` (`vendor_eol_date < today`)
  - `status_badge_class`, `is_locked`
- **Helper method `compute_compliance_status(today=None)`**:
  - If `status in ("audit_hold", "retired")`: preserve status.
  - Else if `renewal_date` and `renewal_date < today`: `"expired"`.
  - Else if `allocated_quantity > entitled_quantity`: `"true_up_required"`.
  - Else if `reclaimable_inactive_count > 0` or (`entitled_quantity > allocated_quantity` and `entitled_quantity - allocated_quantity >= max(1, int(entitled_quantity * 0.15))`): `"surplus_reclaimable"`.
  - Else: `"active_compliant"`.

---

### 1.3 `CloudAssetSubscription` (`CloudAssetSubscriptions.py`)
- **`NUMBER_PREFIX`**: `"ITCL"`
- **`Meta.ordering`**: `["name", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Cloud Asset & Subscription"` / `"Cloud Assets & Subscriptions"`
- **Choices & Badge Maps**:
  - `ASSET_KIND_CHOICES` (`max_length=24`, max value len 17):
    - `("saas_application", "SaaS Application")`
    - `("iaas_compute", "IaaS Compute / VM / Cluster")`
    - `("paas_database", "PaaS Database / Managed Service")`
    - `("reserved_instance", "Reserved Instance (RI)")`
    - `("savings_plan", "Cloud Savings Plan")`
    - `("cloud_storage", "Object / Block Storage")`
    - `("cloud_network_cdn", "Cloud Network / CDN / WAF")`
    - `("ai_api_platform", "AI / API Platform")`
  - `PROVIDER_CHOICES` (`max_length=24`, max value len 16):
    - `("aws", "Amazon Web Services (AWS)")`
    - `("azure", "Microsoft Azure")`
    - `("gcp", "Google Cloud (GCP)")`
    - `("oracle_cloud", "Oracle Cloud (OCI)")`
    - `("microsoft_365", "Microsoft 365")`
    - `("google_workspace", "Google Workspace")`
    - `("salesforce", "Salesforce")`
    - `("atlassian", "Atlassian Cloud")`
    - `("github", "GitHub Enterprise")`
    - `("slack", "Slack")`
    - `("datadog", "Datadog")`
    - `("other_saas", "Other Cloud / SaaS")`
  - `ENVIRONMENT_CHOICES` (`max_length=24`, max value len 14):
    - `("production", "Production")`
    - `("staging", "Staging")`
    - `("development", "Development")`
    - `("corporate_saas", "Corporate SaaS")`
    - `("sandbox", "Sandbox")`
  - `BILLING_CADENCE_CHOICES` (`max_length=16`, max value len 10):
    - `("monthly", "Monthly")`
    - `("quarterly", "Quarterly")`
    - `("annual", "Annual")`
    - `("multi_year", "Multi-Year")`
    - `("usage_payg", "Pay-As-You-Go")`
  - `COMMITMENT_TERM_CHOICES` (`max_length=24`, max value len 15):
    - `("on_demand", "On-Demand")`
    - `("1yr_reserved", "1-Year Reserved")`
    - `("3yr_reserved", "3-Year Reserved")`
    - `("annual_contract", "Annual Contract")`
    - `("monthly_flex", "Monthly Flex")`
  - `SSO_STATUS_CHOICES` (`max_length=28`, max value len 20):
    - `("sso_enforced", "SSO / SAML Enforced")`
    - `("sso_optional", "SSO Optional")`
    - `("local_auth_only", "Local Auth Only")`
    - `("shadow_it_unapproved", "Shadow IT / Unmanaged")`
  - `APPROVAL_STATUS_CHOICES` (`max_length=28`, max value len 20):
    - `("sanctioned", "IT Sanctioned")`
    - `("under_review", "Under Security Review")`
    - `("shadow_it_flagged", "Shadow IT Flagged")`
    - `("consolidation_target", "Consolidation Target")`
    - `("decommissioned", "Decommissioned")`
  - `STATUS_CHOICES` (`max_length=24`, max value len 14):
    - `("active", "Active")`
    - `("expiring_soon", "Expiring Soon")`
    - `("underutilized", "Underutilized")`
    - `("shadow_flagged", "Shadow IT Flagged")`
    - `("suspended", "Suspended")`
    - `("cancelled", "Cancelled")`
  - `STATUS_CSS`:
    - `"active": "badge-green"`, `"expiring_soon": "badge-amber"`, `"underutilized": "badge-info"`, `"shadow_flagged": "badge-red"`, `"suspended": "badge-amber"`, `"cancelled": "badge-muted"`
  - `APPROVAL_CSS`:
    - `"sanctioned": "badge-green"`, `"under_review": "badge-info"`, `"shadow_it_flagged": "badge-red"`, `"consolidation_target": "badge-amber"`, `"decommissioned": "badge-muted"`
  - `SSO_CSS`:
    - `"sso_enforced": "badge-green"`, `"sso_optional": "badge-info"`, `"local_auth_only": "badge-amber"`, `"shadow_it_unapproved": "badge-red"`
  - `LOCKED_STATUSES = {"cancelled"}`
- **Fields**:
  - `name`: `CharField(max_length=200)`
  - `asset_kind`: `CharField(max_length=24, choices=ASSET_KIND_CHOICES, default="saas_application")`
  - `provider`: `CharField(max_length=24, choices=PROVIDER_CHOICES, default="aws")`
  - `external_account_id`: `CharField(max_length=120, blank=True)`
  - `cloud_resource_id`: `CharField(max_length=200, blank=True)`
  - `cloud_region`: `CharField(max_length=64, blank=True)`
  - `environment`: `CharField(max_length=24, choices=ENVIRONMENT_CHOICES, default="corporate_saas")`
  - `resource_tags`: `JSONField(default=dict, blank=True)`
  - `billing_cadence`: `CharField(max_length=16, choices=BILLING_CADENCE_CHOICES, default="monthly")`
  - `commitment_term`: `CharField(max_length=24, choices=COMMITMENT_TERM_CHOICES, default="annual_contract")`
  - `monthly_recurring_cost`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `annual_contract_value`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=SET_NULL, null=True, blank=True, related_name="cloud_asset_subscriptions")` (GLOBAL)
  - `provisioned_seats`: `PositiveIntegerField(default=0)`
  - `active_seats_30d`: `PositiveIntegerField(default=0)`
  - `sso_status`: `CharField(max_length=28, choices=SSO_STATUS_CHOICES, default="sso_optional")`
  - `approval_status`: `CharField(max_length=28, choices=APPROVAL_STATUS_CHOICES, default="sanctioned")`
  - `renewal_date`: `DateField(null=True, blank=True)`
  - `cancellation_notice_days`: `PositiveSmallIntegerField(default=30)`
  - `auto_renew`: `BooleanField(default=True)`
  - `vendor_eol_date`: `DateField(null=True, blank=True)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="active", editable=False)`
  - `last_finops_sync_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `decommissioned_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True, related_name="cloud_asset_subscriptions")`
  - `vendor_party`: `ForeignKey("core.Party", on_delete=SET_NULL, null=True, blank=True, related_name="cloud_asset_subscriptions")`
  - `gl_expense_account`: `ForeignKey("accounting.GLAccount", on_delete=SET_NULL, null=True, blank=True, related_name="cloud_asset_subscriptions")`
  - `business_owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="business_owned_cloud_assets")`
  - `technical_owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="technical_owned_cloud_assets")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_itcl_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_itcl_ten_stat")`
  - `Index(fields=["tenant", "provider"], name="idx_itcl_ten_prov")`
  - `Index(fields=["tenant", "approval_status"], name="idx_itcl_ten_aprv")`
  - `Index(fields=["tenant", "renewal_date"], name="idx_itcl_ten_ren")`
- **Derived Properties**:
  - `seat_utilization_pct` (`round(active_seats_30d * 100 / provisioned_seats, 1)` when `provisioned_seats > 0` else `None`)
  - `wasted_monthly_spend` (`((provisioned_seats - active_seats_30d) / provisioned_seats) * monthly_recurring_cost` rounded to 2dp when `provisioned_seats > 0` and `active_seats_30d < provisioned_seats` else `Decimal("0.00")`)
  - `has_required_tags` (bool: `"env"`, `"cost_center"`, `"owner"` all non-empty in `resource_tags` dict)
  - `is_eol_expired` (`vendor_eol_date < today`)
  - `status_badge_class`, `approval_badge_class`, `sso_badge_class`, `is_locked`

---

### 1.4 `CmdbRelationship` (`CmdbRelationships.py`)
- **`NUMBER_PREFIX`**: `"CMDB"`
- **`Meta.ordering`**: `["-updated_at", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"CMDB Relationship"` / `"CMDB Relationships"`
- **Choices & Badge Maps**:
  - `CI_TYPE_CHOICES` (`max_length=24`, max value len 17):
    - `("it_hardware", "IT Hardware Asset")`
    - `("software_license", "Software License")`
    - `("cloud_asset", "Cloud Asset / SaaS")`
    - `("service_component", "Core Service Component")`
    - `("operational_asset", "Operational Asset (SCM)")`
  - `RELATIONSHIP_TYPE_CHOICES` (`max_length=24`, max value len 15):
    - `("runs_on", "Runs On")`
    - `("depends_on", "Depends On")`
    - `("hosted_in", "Hosted In")`
    - `("connects_to", "Connects To")`
    - `("backed_up_by", "Backed Up By")`
    - `("licensed_by", "Licensed By")`
    - `("integrates_with", "Integrates With")`
    - `("replicates_to", "Replicates To")`
  - `ENVIRONMENT_CHOICES` (`max_length=20`, max value len 12):
    - `("production", "Production")`
    - `("staging", "Staging")`
    - `("development", "Development")`
    - `("dr_failover", "DR / Failover")`
    - `("shared_infra", "Shared Infrastructure")`
  - `CRITICALITY_CHOICES` (`max_length=32`, max value len 23):
    - `("tier_1_mission_critical", "Tier 1 — Mission Critical")`
    - `("tier_2_business_important", "Tier 2 — Business Important")`
    - `("tier_3_operational", "Tier 3 — Operational")`
    - `("tier_4_low", "Tier 4 — Low")`
  - `IMPACT_SEVERITY_CHOICES` (`max_length=28`, max value len 20):
    - `("hard_outage", "Hard Outage")`
    - `("degraded_performance", "Degraded Performance")`
    - `("failover_available", "Failover Available")`
    - `("informational", "Informational")`
  - `STATUS_CHOICES` (`max_length=16`, max value len 10):
    - `("active", "Active")`
    - `("planned", "Planned")`
    - `("deprecated", "Deprecated")`
    - `("severed", "Severed")`
  - `STATUS_CSS`:
    - `"active": "badge-green"`, `"planned": "badge-info"`, `"deprecated": "badge-amber"`, `"severed": "badge-muted"`
  - `CRITICALITY_CSS`:
    - `"tier_1_mission_critical": "badge-red"`, `"tier_2_business_important": "badge-amber"`, `"tier_3_operational": "badge-info"`, `"tier_4_low": "badge-slate"`
  - `LOCKED_STATUSES = {"severed"}`
  - `CI_FIELD_BY_TYPE`:
    - `"it_hardware": "hardware"`, `"software_license": "software"`, `"cloud_asset": "cloud"`, `"service_component": "service"`, `"operational_asset": "asset"`
- **Fields**:
  - `source_ci_type`: `CharField(max_length=24, choices=CI_TYPE_CHOICES, default="service_component")`
  - `source_hardware`: `ForeignKey("assets.ItHardwareAsset", on_delete=CASCADE, null=True, blank=True, related_name="outbound_cmdb_edges")`
  - `source_software`: `ForeignKey("assets.SoftwareLicense", on_delete=CASCADE, null=True, blank=True, related_name="outbound_cmdb_edges")`
  - `source_cloud`: `ForeignKey("assets.CloudAssetSubscription", on_delete=CASCADE, null=True, blank=True, related_name="outbound_cmdb_edges")`
  - `source_service`: `ForeignKey("core.ServiceComponent", on_delete=CASCADE, null=True, blank=True, related_name="outbound_cmdb_edges")`
  - `source_asset`: `ForeignKey("scm.Asset", on_delete=CASCADE, null=True, blank=True, related_name="outbound_cmdb_edges")`
  - `relationship_type`: `CharField(max_length=24, choices=RELATIONSHIP_TYPE_CHOICES, default="depends_on")`
  - `target_ci_type`: `CharField(max_length=24, choices=CI_TYPE_CHOICES, default="it_hardware")`
  - `target_hardware`: `ForeignKey("assets.ItHardwareAsset", on_delete=CASCADE, null=True, blank=True, related_name="inbound_cmdb_edges")`
  - `target_software`: `ForeignKey("assets.SoftwareLicense", on_delete=CASCADE, null=True, blank=True, related_name="inbound_cmdb_edges")`
  - `target_cloud`: `ForeignKey("assets.CloudAssetSubscription", on_delete=CASCADE, null=True, blank=True, related_name="inbound_cmdb_edges")`
  - `target_service`: `ForeignKey("core.ServiceComponent", on_delete=CASCADE, null=True, blank=True, related_name="inbound_cmdb_edges")`
  - `target_asset`: `ForeignKey("scm.Asset", on_delete=CASCADE, null=True, blank=True, related_name="inbound_cmdb_edges")`
  - `environment`: `CharField(max_length=20, choices=ENVIRONMENT_CHOICES, default="production")`
  - `criticality`: `CharField(max_length=32, choices=CRITICALITY_CHOICES, default="tier_2_business_important")`
  - `impact_severity`: `CharField(max_length=28, choices=IMPACT_SEVERITY_CHOICES, default="degraded_performance")`
  - `is_single_point_of_failure`: `BooleanField(default=False)`
  - `verified_on`: `DateField(null=True, blank=True, editable=False)`
  - `verified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, editable=False, related_name="verified_cmdb_edges")`
  - `severed_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default="active", editable=False)`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="owned_cmdb_relationships")`
  - `blast_radius_notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_cmdb_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_cmdb_ten_stat")`
  - `Index(fields=["tenant", "relationship_type"], name="idx_cmdb_ten_rel")`
  - `Index(fields=["tenant", "source_ci_type"], name="idx_cmdb_ten_src")`
  - `Index(fields=["tenant", "target_ci_type"], name="idx_cmdb_ten_tgt")`
- **Derived Properties**:
  - `source_ci`, `target_ci`, `source_ci_key` (`(ci_type, pk)`), `target_ci_key`, `source_label`, `target_label`, `status_badge_class`, `criticality_badge_class`, `is_locked`

---

## 2. Forms Contract (`apps/assets/forms/ItAssetManagement/`)

All 4 forms inherit `(TenantUniqueMixin, TenantModelForm)` and scope tenant FKs via `_helpers.scope_tenant_querysets(self, self._TENANT_FIELDS)` with `select_related` optimizations on `EmployeeProfile` (`select_related("party")`) and `PurchaseOrder` (`select_related("vendor")`).

1. **`ItHardwareAssetForm`** (`ItHardwareAssets.py`):
   - `Meta.fields`: `hostname`, `fqdn`, `device_class`, `serial_number`, `asset_tag_code`, `manufacturer`, `model_name`, `mac_address`, `ip_address`, `operating_system`, `os_version`, `cpu_spec`, `ram_gb`, `storage_gb`, `bios_firmware_version`, `rack_unit_ref`, `environment`, `criticality`, `mdm_enrolled`, `mdm_platform`, `mdm_device_id`, `disk_encryption_status`, `commissioned_date`, `assigned_date`, `vendor_eos_date`, `vendor_eol_date`, `refresh_cycle_months`, `refresh_due_date`, `estimated_refresh_cost`, `currency`, `sanitization_required`, `sanitization_method`, `sanitization_status`, `sanitization_date`, `sanitization_certificate_ref`, `operational_asset`, `fixed_asset`, `asset_model`, `asset_category`, `warranty`, `requisition`, `replacement_plan`, `disposal_request`, `scrap_salvage`, `org_unit`, `location`, `custodian_party`, `vendor_party`, `employee_profile`, `owner`, `notes`
   - Excluded: `tenant`, `number`, `status`, `last_seen_checkin`, `sanitization_verified_by`, `sanitized_at`, `retired_at`, `created_at`, `updated_at`
   - Global `currency` queryset: `Currency.objects.filter(is_active=True).order_by("code")` (NOT in `_TENANT_FIELDS` / `reject_foreign`).

2. **`SoftwareLicenseForm`** (`SoftwareLicenses.py`):
   - `Meta.fields`: `software_name`, `publisher_name`, `product_sku`, `version_edition`, `software_category`, `license_type`, `license_metric`, `agreement_number`, `license_key_ref`, `entitled_quantity`, `allocated_quantity`, `active_used_quantity`, `reclaimable_inactive_count`, `unit_license_cost`, `total_annual_spend`, `currency`, `effective_date`, `renewal_date`, `vendor_eol_date`, `auto_renew`, `publisher_party`, `reseller_party`, `org_unit`, `gl_expense_account`, `purchase_order`, `service_contract`, `license_owner`, `notes`
   - Excluded: `tenant`, `number`, `status`, `last_reconciled_at`, `retired_at`, `created_at`, `updated_at`
   - Global `currency` queryset: `Currency.objects.filter(is_active=True).order_by("code")` (NOT in `reject_foreign`).

3. **`CloudAssetSubscriptionForm`** (`CloudAssetSubscriptions.py`):
   - `Meta.fields`: `name`, `asset_kind`, `provider`, `external_account_id`, `cloud_resource_id`, `cloud_region`, `environment`, `resource_tags`, `billing_cadence`, `commitment_term`, `monthly_recurring_cost`, `annual_contract_value`, `currency`, `provisioned_seats`, `active_seats_30d`, `sso_status`, `approval_status`, `renewal_date`, `cancellation_notice_days`, `auto_renew`, `vendor_eol_date`, `org_unit`, `vendor_party`, `gl_expense_account`, `business_owner`, `technical_owner`, `notes`
   - Excluded: `tenant`, `number`, `status`, `last_finops_sync_at`, `decommissioned_at`, `created_at`, `updated_at`
   - Global `currency` queryset: `Currency.objects.filter(is_active=True).order_by("code")` (NOT in `reject_foreign`).

4. **`CmdbRelationshipForm`** (`CmdbRelationships.py`):
   - `Meta.fields`: `source_ci_type`, `source_hardware`, `source_software`, `source_cloud`, `source_service`, `source_asset`, `relationship_type`, `target_ci_type`, `target_hardware`, `target_software`, `target_cloud`, `target_service`, `target_asset`, `environment`, `criticality`, `impact_severity`, `is_single_point_of_failure`, `owner`, `blast_radius_notes`
   - Excluded: `tenant`, `number`, `status`, `verified_on`, `verified_by`, `severed_at`, `created_at`, `updated_at`
   - `clean()`: zeroes out the 4 inactive CI FK fields per side based on `source_ci_type` / `target_ci_type`, validates the selected FK is non-null, validates `reject_foreign`, and relies on `Model.clean()` for self-loop & duplicate active edge guards.

---

## 3. URL Routes & Views Context Contract (`apps/assets/{urls,views}/ItAssetManagement/`)

All literal routes (`create/`, `export-csv/`, `refresh-board/`, `cmdb/impact-analysis/`) appear BEFORE `<int:pk>/`.

### 3.1 `ItHardwareAssets.py`
- URLs (`it-hardware/`):
  - `it-hardware/` -> `it_hardware_asset_list`
  - `it-hardware/create/` -> `it_hardware_asset_create`
  - `it-hardware/export-csv/` -> `it_hardware_asset_export_csv`
  - `it-hardware/<int:pk>/` -> `it_hardware_asset_detail`
  - `it-hardware/<int:pk>/edit/` -> `it_hardware_asset_edit`
  - `it-hardware/<int:pk>/delete/` -> `it_hardware_asset_delete` (`@tenant_admin_required`, `@require_POST`)
  - `it-hardware/<int:pk>/deploy/` -> `it_hardware_asset_deploy` (`@require_POST`)
  - `it-hardware/<int:pk>/stock/` -> `it_hardware_asset_move_to_stock` (`@require_POST`)
  - `it-hardware/<int:pk>/repair/` -> `it_hardware_asset_send_to_repair` (`@require_POST`)
  - `it-hardware/<int:pk>/loaner/` -> `it_hardware_asset_move_to_loaner` (`@require_POST`)
  - `it-hardware/<int:pk>/flag-refresh/` -> `it_hardware_asset_flag_for_refresh` (`@require_POST`)
  - `it-hardware/<int:pk>/sanitize/` -> `it_hardware_asset_mark_sanitized` (`@tenant_admin_required`, `@require_POST`)
  - `it-hardware/<int:pk>/retire/` -> `it_hardware_asset_retire` (`@tenant_admin_required`, `@require_POST`)
- Context keys:
  - List (`templates/assets/itassetmanagement/it_hardware_asset/list.html`):
    `hardware_assets` (`page_obj`), `page_obj`, `paginator`, `total_count`, `deployed_count`, `eol_due_count`, `pending_wipe_count`, `status_choices`, `device_class_choices`, `environment_choices`, `encryption_choices`, `org_units`, `search_query`
  - Detail (`templates/assets/itassetmanagement/it_hardware_asset/detail.html`):
    `hardware`, `outbound_edges`, `inbound_edges`
  - Form (`templates/assets/itassetmanagement/it_hardware_asset/form.html`):
    `form`, `hardware` (`obj` or `None`), `is_edit`, `title`

### 3.2 `SoftwareLicenses.py`
- URLs (`software-licenses/`):
  - `software-licenses/` -> `software_license_list`
  - `software-licenses/create/` -> `software_license_create`
  - `software-licenses/export-csv/` -> `software_license_export_csv`
  - `software-licenses/<int:pk>/` -> `software_license_detail`
  - `software-licenses/<int:pk>/edit/` -> `software_license_edit`
  - `software-licenses/<int:pk>/delete/` -> `software_license_delete` (`@tenant_admin_required`, `@require_POST`)
  - `software-licenses/<int:pk>/sync-compliance/` -> `software_license_sync_compliance` (`@require_POST`)
  - `software-licenses/<int:pk>/reclaim/` -> `software_license_reclaim_inactive` (`@require_POST`)
  - `software-licenses/<int:pk>/true-up/` -> `software_license_record_true_up` (`@tenant_admin_required`, `@require_POST`)
  - `software-licenses/<int:pk>/renew/` -> `software_license_renew_term` (`@require_POST`)
  - `software-licenses/<int:pk>/audit-hold/` -> `software_license_place_audit_hold` (`@tenant_admin_required`, `@require_POST`)
  - `software-licenses/<int:pk>/retire/` -> `software_license_retire` (`@tenant_admin_required`, `@require_POST`)
- Context keys:
  - List (`templates/assets/itassetmanagement/software_license/list.html`):
    `licenses` (`page_obj`), `page_obj`, `paginator`, `total_count`, `compliant_count`, `true_up_count`, `reclaimable_seats_total`, `status_choices`, `category_choices`, `license_type_choices`, `metric_choices`, `org_units`, `search_query`
  - Detail (`templates/assets/itassetmanagement/software_license/detail.html`):
    `license_obj`, `outbound_edges`, `inbound_edges`
  - Form (`templates/assets/itassetmanagement/software_license/form.html`):
    `form`, `license_obj` (`obj` or `None`), `is_edit`, `title`

### 3.3 `CloudAssetSubscriptions.py`
- URLs (`cloud-assets/`):
  - `cloud-assets/` -> `cloud_asset_subscription_list`
  - `cloud-assets/create/` -> `cloud_asset_subscription_create`
  - `cloud-assets/export-csv/` -> `cloud_asset_subscription_export_csv`
  - `cloud-assets/<int:pk>/` -> `cloud_asset_subscription_detail`
  - `cloud-assets/<int:pk>/edit/` -> `cloud_asset_subscription_edit`
  - `cloud-assets/<int:pk>/delete/` -> `cloud_asset_subscription_delete` (`@tenant_admin_required`, `@require_POST`)
  - `cloud-assets/<int:pk>/sanction/` -> `cloud_asset_subscription_sanction` (`@require_POST`)
  - `cloud-assets/<int:pk>/flag-shadow/` -> `cloud_asset_subscription_flag_shadow` (`@require_POST`)
  - `cloud-assets/<int:pk>/sync-finops/` -> `cloud_asset_subscription_sync_finops` (`@require_POST`)
  - `cloud-assets/<int:pk>/renew/` -> `cloud_asset_subscription_renew` (`@require_POST`)
  - `cloud-assets/<int:pk>/suspend/` -> `cloud_asset_subscription_suspend` (`@tenant_admin_required`, `@require_POST`)
  - `cloud-assets/<int:pk>/decommission/` -> `cloud_asset_subscription_decommission` (`@tenant_admin_required`, `@require_POST`)
- Context keys:
  - List (`templates/assets/itassetmanagement/cloud_asset_subscription/list.html`):
    `cloud_assets` (`page_obj`), `page_obj`, `paginator`, `total_count`, `monthly_spend_total`, `shadow_flagged_count`, `underutilized_count`, `status_choices`, `asset_kind_choices`, `provider_choices`, `approval_choices`, `sso_choices`, `org_units`, `search_query`
  - Detail (`templates/assets/itassetmanagement/cloud_asset_subscription/detail.html`):
    `cloud_asset`, `outbound_edges`, `inbound_edges`
  - Form (`templates/assets/itassetmanagement/cloud_asset_subscription/form.html`):
    `form`, `cloud_asset` (`obj` or `None`), `is_edit`, `title`

### 3.4 `CmdbRelationships.py`
- URLs (`cmdb/`):
  - `cmdb/` -> `cmdb_relationship_list`
  - `cmdb/create/` -> `cmdb_relationship_create`
  - `cmdb/export-csv/` -> `cmdb_relationship_export_csv`
  - `cmdb/<int:pk>/` -> `cmdb_relationship_detail`
  - `cmdb/<int:pk>/edit/` -> `cmdb_relationship_edit`
  - `cmdb/<int:pk>/delete/` -> `cmdb_relationship_delete` (`@tenant_admin_required`, `@require_POST`)
  - `cmdb/<int:pk>/verify/` -> `cmdb_relationship_verify` (`@require_POST`)
  - `cmdb/<int:pk>/deprecate/` -> `cmdb_relationship_deprecate` (`@require_POST`)
  - `cmdb/<int:pk>/sever/` -> `cmdb_relationship_sever` (`@tenant_admin_required`, `@require_POST`)
- Context keys:
  - List (`templates/assets/itassetmanagement/cmdb_relationship/list.html`):
    `relationships` (`page_obj`), `page_obj`, `paginator`, `total_count`, `active_count`, `spof_count`, `tier1_count`, `status_choices`, `relationship_type_choices`, `ci_type_choices`, `environment_choices`, `criticality_choices`, `search_query`
  - Detail (`templates/assets/itassetmanagement/cmdb_relationship/detail.html`):
    `relationship`, `related_source_edges`, `related_target_edges`
  - Form (`templates/assets/itassetmanagement/cmdb_relationship/form.html`):
    `form`, `relationship` (`obj` or `None`), `is_edit`, `title`

### 3.5 `ItRefreshBoards.py` (Computed Workbench)
- URLs (`it-hardware/refresh-board/`):
  - `it-hardware/refresh-board/` -> `it_refresh_board`
  - `it-hardware/refresh-board/export-csv/` -> `it_refresh_board_export_csv`
- Context keys (`templates/assets/itassetmanagement/it_refresh_board.html`):
  `hardware_rows`, `software_rows`, `cloud_rows`, `sanitization_backlog`, `org_unit_summary`, `org_units`, `horizon_days`, `selected_priority`, `total_refresh_capex`, `overdue_hw_count`, `due_90d_hw_count`, `pending_wipe_count`, `expiring_sw_cloud_count`

### 3.6 `CmdbImpactAnalyses.py` (Computed Workbench)
- URLs (`cmdb/impact-analysis/`):
  - `cmdb/impact-analysis/` -> `cmdb_impact_analysis`
  - `cmdb/impact-analysis/export-csv/` -> `cmdb_impact_analysis_export_csv`
- Context keys (`templates/assets/itassetmanagement/cmdb_impact_analysis.html`):
  `ci_options`, `selected_ci_token`, `selected_ci_label`, `selected_environment`, `environment_choices`, `upstream_nodes`, `downstream_nodes`, `spof_edges`, `total_active_edges`, `total_spof_edges`

---

## 4. Navigation (`apps/core/navigation.py`) Contract

```python
    "11.18": {
        "Hardware Lifecycle Management": "assets:it_hardware_asset_list",
        "Software License Management": "assets:software_license_list",
        "Cloud Asset & Subscription Tracking": "assets:cloud_asset_subscription_list",
        "Configuration Management Database (CMDB)": "assets:cmdb_relationship_list",
        "End-of-Life & Refresh Cycles": "assets:it_refresh_board",
        # Extra live leaf
        "CMDB Impact Analysis": "assets:cmdb_impact_analysis",
    },
```
