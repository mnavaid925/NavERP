# Module 13.4 Pre-Build Contract — Document Storage & Repository (`apps/documents/`)

> Frozen in Phase 3.1 before any Phase 3.2 scaffolding or entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["13.4"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.documents` (Extends existing app; claims incremental migration `0006_...`)
- **Package Directories**:
  - `apps/documents/models/StorageRepository/`
  - `apps/documents/forms/StorageRepository/`
  - `apps/documents/views/StorageRepository/`
  - `apps/documents/urls/StorageRepository/`
  - `templates/documents/storage_repository/{document_folder,storage_volume,document_relationship,document_batch_import}/{list,detail,form}.html` + `tree.html`, `graph.html`, `process.html`, `repository_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"import"`, `"process"`, `"verify"`, `"link"`, `"unlink"`, `"rollover"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `documents.Document`, `documents.DocumentFolder`, `documents.StorageVolume`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/documents/models/StorageRepository/`)

All 4 models inherit `apps.documents.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `DocumentFolder` (`DocumentFolders.py`)
- **`NUMBER_PREFIX`**: `"DFLD"`
- **`Meta.ordering`**: `["path", "name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Folder"` / `"Document Folders"`
- **Choices & Badge Maps**:
  - `CLASSIFICATION_CHOICES` (`max_length=25`):
    - `("public", "Public")`
    - `("internal", "Internal Use Only")`
    - `("confidential", "Confidential")`
    - `("restricted", "Strictly Restricted")`
  - `DOCUMENT_TYPE_CHOICES` (`max_length=40`):
    - `("general", "General Document")`
    - `("contract", "Legal Contract & Agreement")`
    - `("policy", "Corporate Policy & Governance")`
    - `("sop", "Standard Operating Procedure (SOP)")`
    - `("report", "Business & Operational Report")`
    - `("specification", "Technical Specification")`
    - `("proposal", "Commercial Proposal / Pitch")`
    - `("technical", "Technical & Engineering Doc")`
  - `CLASSIFICATION_CSS`:
    - `"public": "badge-green"`
    - `"internal": "badge-info"`
    - `"confidential": "badge-amber"`
    - `"restricted": "badge-red"`
  - `STATUS_CSS`:
    - `True: "badge-green"` (Active)
    - `False: "badge-slate"` (Inactive / Archived)
- **Fields (exact names & types)**:
  - `name`: `CharField(max_length=150)`
  - `slug`: `SlugField(max_length=160, blank=True)`
  - `parent`: `ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children", db_index=True)`
  - `path`: `CharField(max_length=500, blank=True, help_text="Materialized path e.g. /Corporate/Legal/")`
  - `description`: `TextField(blank=True)`
  - `color_code`: `CharField(max_length=20, default="#3B82F6")`
  - `icon_name`: `CharField(max_length=50, default="folder")`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="document_folders")`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_document_folders")`
  - `default_classification`: `CharField(max_length=25, choices=CLASSIFICATION_CHOICES, default="internal", db_index=True)`
  - `default_document_type`: `CharField(max_length=40, choices=DOCUMENT_TYPE_CHOICES, default="general", blank=True)`
  - `is_virtual`: `BooleanField(default=False, db_index=True)`
  - `virtual_criteria_json`: `TextField(blank=True, default="{}")`
  - `is_system`: `BooleanField(default=False)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dfld_ten_num_uniq")` (21 chars)
  - `UniqueConstraint(fields=["tenant", "parent", "slug"], name="doc_dfld_tnt_par_slug_uniq")` (26 chars)
  - `models.Index(fields=["tenant", "parent", "is_active"], name="doc_dfld_tnt_par_act_idx")` (24 chars)
  - `models.Index(fields=["tenant", "path"], name="doc_dfld_tnt_path_idx")` (21 chars)

### 1.2 `StorageVolume` (`StorageVolumes.py`)
- **`NUMBER_PREFIX`**: `"DSTG"`
- **`Meta.ordering`**: `["name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Storage Volume"` / `"Storage Volumes"`
- **Choices & Badge Maps**:
  - `BACKEND_TYPE_CHOICES` (`max_length=30`):
    - `("local_filesystem", "Local Server Filesystem")`
    - `("network_nas", "Network Attached Storage (NAS / NFS)")`
    - `("s3_compatible", "AWS S3 / Compatible Object Storage")`
    - `("azure_blob", "Microsoft Azure Blob Storage")`
    - `("google_cloud_storage", "Google Cloud Storage (GCS)")`
    - `("air_gapped", "Air-Gapped Secure On-Premises SAN")`
  - `TIER_CHOICES` (`max_length=25`):
    - `("hot", "Hot Tier (High-Speed NVMe/SSD)")`
    - `("warm", "Warm Tier (Standard Disk/Object)")`
    - `("cold", "Cold Tier (Infrequent Access)")`
    - `("glacier_archive", "Archive Tier (Deep Archive/Tape)")`
  - `COMPRESSION_CHOICES` (`max_length=20`):
    - `("none", "None (Uncompressed)")`
    - `("gzip", "Gzip")`
    - `("zstandard", "Zstandard (Zstd)")`
  - `ENCRYPTION_CHOICES` (`max_length=20`):
    - `("none", "None (Plaintext)")`
    - `("aes_256", "AES-256 Server-Side")`
    - `("kms_managed", "Enterprise KMS Managed Key")`
  - `TIER_CSS`:
    - `"hot": "badge-red"`
    - `"warm": "badge-amber"`
    - `"cold": "badge-info"`
    - `"glacier_archive": "badge-slate"`
  - `BACKEND_CSS`:
    - `"local_filesystem": "badge-slate"`
    - `"network_nas": "badge-info"`
    - `"s3_compatible": "badge-amber"`
    - `"azure_blob": "badge-info"`
    - `"google_cloud_storage": "badge-green"`
    - `"air_gapped": "badge-slate"`
- **Fields (exact names & types)**:
  - `name`: `CharField(max_length=150)`
  - `code`: `CharField(max_length=50, db_index=True)`
  - `backend_type`: `CharField(max_length=30, choices=BACKEND_TYPE_CHOICES, default="local_filesystem", db_index=True)`
  - `tier`: `CharField(max_length=25, choices=TIER_CHOICES, default="hot", db_index=True)`
  - `base_path`: `CharField(max_length=255, help_text="Mount path or bucket name")`
  - `region`: `CharField(max_length=50, blank=True)`
  - `endpoint_url`: `CharField(max_length=255, blank=True)`
  - `max_capacity_bytes`: `BigIntegerField(default=107374182400)`
  - `utilized_bytes`: `BigIntegerField(default=0)`
  - `utilized_percentage`: `DecimalField(max_digits=5, decimal_places=2, default=0.0)`
  - `warning_threshold_pct`: `PositiveIntegerField(default=85)`
  - `is_default`: `BooleanField(default=False, db_index=True)`
  - `is_full`: `BooleanField(default=False, db_index=True)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `compression_type`: `CharField(max_length=20, choices=COMPRESSION_CHOICES, default="none")`
  - `deduplication_enabled`: `BooleanField(default=True)`
  - `encryption_type`: `CharField(max_length=20, choices=ENCRYPTION_CHOICES, default="aes_256")`
  - `rollover_volume`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="overflow_sources")`
  - `description`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dstg_ten_num_uniq")` (21 chars)
  - `UniqueConstraint(fields=["tenant", "code"], name="doc_dstg_tnt_code_uniq")` (22 chars)
  - `models.Index(fields=["tenant", "backend_type", "tier"], name="doc_dstg_tnt_bknd_tier_idx")` (26 chars)
  - `models.Index(fields=["tenant", "is_default", "is_active"], name="doc_dstg_tnt_def_act_idx")` (24 chars)

### 1.3 `DocumentRelationship` (`DocumentRelationships.py`)
- **`NUMBER_PREFIX`**: `"DREL"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Relationship"` / `"Document Relationships"`
- **Choices & Badge Maps**:
  - `RELATIONSHIP_TYPE_CHOICES` (`max_length=30`):
    - `("parent_child", "Parent / Child Document Family")`
    - `("supersedes", "Supersedes / Superseded By")`
    - `("references", "References / Cited By")`
    - `("derived_from", "Derived From (Variant/Draft)")`
    - `("contract_exhibit", "Contract Master / Exhibit / SOW")`
    - `("supporting_evidence", "Supporting Evidence / Attachment")`
    - `("amendment", "Legal Amendment / Addendum")`
  - `DEPENDENCY_CHOICES` (`max_length=25`):
    - `("informational", "Informational Link")`
    - `("contractual", "Contractual Dependency")`
    - `("strict_blocking", "Strict Blocking Prerequisite")`
  - `RELATIONSHIP_TYPE_CSS`:
    - `"parent_child": "badge-info"`
    - `"supersedes": "badge-amber"`
    - `"references": "badge-slate"`
    - `"derived_from": "badge-info"`
    - `"contract_exhibit": "badge-green"`
    - `"supporting_evidence": "badge-slate"`
    - `"amendment": "badge-amber"`
  - `DEPENDENCY_CSS`:
    - `"informational": "badge-slate"`
    - `"contractual": "badge-info"`
    - `"strict_blocking": "badge-red"`
- **Fields (exact names & types)**:
  - `source_document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="outgoing_relationships", db_index=True)`
  - `target_document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="incoming_relationships", db_index=True)`
  - `relationship_type`: `CharField(max_length=30, choices=RELATIONSHIP_TYPE_CHOICES, default="references", db_index=True)`
  - `is_bidirectional`: `BooleanField(default=True)`
  - `dependency_level`: `CharField(max_length=25, choices=DEPENDENCY_CHOICES, default="informational")`
  - `description`: `CharField(max_length=255, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_document_relationships")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_drel_ten_num_uniq")` (21 chars)
  - `UniqueConstraint(fields=["tenant", "source_document", "target_document", "relationship_type"], name="doc_drel_tnt_rel_uniq")` (21 chars)
  - `models.Index(fields=["tenant", "source_document", "relationship_type"], name="doc_drel_tnt_src_rel_idx")` (24 chars)
  - `models.Index(fields=["tenant", "target_document", "relationship_type"], name="doc_drel_tnt_tgt_rel_idx")` (24 chars)

### 1.4 `DocumentBatchImport` (`DocumentBatchImports.py`)
- **`NUMBER_PREFIX`**: `"DBLK"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Batch Import"` / `"Document Batch Imports"`
- **Choices & Badge Maps**:
  - `SOURCE_TYPE_CHOICES` (`max_length=25`):
    - `("zip_archive", "ZIP Archive Package")`
    - `("file_manifest", "Manifest CSV + Files")`
    - `("multi_file", "Direct Multi-File Staging")`
    - `("legacy_migration", "Legacy ECM Migration Export")`
  - `STATUS_CHOICES` (`max_length=30`):
    - `("draft", "Draft Definition")`
    - `("queued", "Queued for Ingestion")`
    - `("extracting", "Extracting Archive")`
    - `("validating", "Validating Files & Formats")`
    - `("processing", "Ingesting into Repository")`
    - `("completed", "Successfully Ingested")`
    - `("partially_completed", "Completed with Warnings / Failures")`
    - `("failed", "Ingestion Failed")`
  - `SOURCE_TYPE_CSS`:
    - `"zip_archive": "badge-info"`
    - `"file_manifest": "badge-amber"`
    - `"multi_file": "badge-slate"`
    - `"legacy_migration": "badge-green"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"queued": "badge-slate"`
    - `"extracting": "badge-amber"`
    - `"validating": "badge-amber"`
    - `"processing": "badge-info"`
    - `"completed": "badge-green"`
    - `"partially_completed": "badge-amber"`
    - `"failed": "badge-red"`
- **Fields (exact names & types)**:
  - `batch_name`: `CharField(max_length=150)`
  - `source_type`: `CharField(max_length=25, choices=SOURCE_TYPE_CHOICES, default="zip_archive", db_index=True)`
  - `target_folder`: `ForeignKey("documents.DocumentFolder", on_delete=models.SET_NULL, null=True, blank=True, related_name="batch_imports")`
  - `storage_volume`: `ForeignKey("documents.StorageVolume", on_delete=models.SET_NULL, null=True, blank=True, related_name="batch_imports")`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `archive_file`: `FileField(upload_to="documents/bulk_imports/%Y/%m/", null=True, blank=True)`
  - `total_files_detected`: `PositiveIntegerField(default=0)`
  - `processed_files_count`: `PositiveIntegerField(default=0)`
  - `success_files_count`: `PositiveIntegerField(default=0)`
  - `failed_files_count`: `PositiveIntegerField(default=0)`
  - `total_bytes_processed`: `BigIntegerField(default=0)`
  - `log_summary`: `TextField(blank=True)`
  - `error_details`: `TextField(blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_document_batch_imports")`
  - `started_at`: `DateTimeField(null=True, blank=True)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dblk_ten_num_uniq")` (21 chars)
  - `models.Index(fields=["tenant", "status", "created_at"], name="doc_dblk_tnt_stat_date_idx")` (26 chars)
  - `models.Index(fields=["tenant", "target_folder", "status"], name="doc_dblk_tnt_fld_stat_idx")` (25 chars)

---

## 2. Forms Contract (`apps/documents/forms/StorageRepository/`)

All forms inherit `forms.ModelForm` and enforce tenant scoping in `__init__` and `clean()`.

### 2.1 `DocumentFolderForm` (`DocumentFolders.py`)
- **Model**: `DocumentFolder`
- **Fields**: `["name", "slug", "parent", "department", "owner", "color_code", "icon_name", "default_classification", "default_document_type", "is_virtual", "virtual_criteria_json", "is_active", "description"]`
- **Excluded**: `tenant`, `number`, `path`, `is_system`, `created_at`, `updated_at`.
- **Validation**:
  - `clean_name()`: Rejects empty strings.
  - `clean()`: Prevents cyclical parent relationships (`parent == self` or parent's ancestors contain self). Enforces valid JSON in `virtual_criteria_json` when `is_virtual` is True.

### 2.2 `StorageVolumeForm` (`StorageVolumes.py`)
- **Model**: `StorageVolume`
- **Fields**: `["name", "code", "backend_type", "tier", "base_path", "region", "endpoint_url", "max_capacity_bytes", "warning_threshold_pct", "is_default", "is_active", "compression_type", "deduplication_enabled", "encryption_type", "rollover_volume", "description"]`
- **Excluded**: `tenant`, `number`, `utilized_bytes`, `utilized_percentage`, `is_full`, `created_at`, `updated_at`.
- **Validation**:
  - `clean_code()`: Validates alphanumeric/hyphen code format.
  - `clean()`: Validates `rollover_volume != self`. If `is_default` is True, unsets `is_default` on sibling volumes within the same tenant.

### 2.3 `DocumentRelationshipForm` (`DocumentRelationships.py`)
- **Model**: `DocumentRelationship`
- **Fields**: `["source_document", "target_document", "relationship_type", "is_bidirectional", "dependency_level", "description"]`
- **Excluded**: `tenant`, `number`, `created_by`, `created_at`, `updated_at`.
- **Validation**:
  - `clean()`: Enforces `source_document != target_document` (no self-reference). Validates both documents belong to `self.tenant`.

### 2.4 `DocumentBatchImportForm` (`DocumentBatchImports.py`)
- **Model**: `DocumentBatchImport`
- **Fields**: `["batch_name", "source_type", "target_folder", "storage_volume", "archive_file"]`
- **Excluded**: `tenant`, `number`, `status`, `total_files_detected`, `processed_files_count`, `success_files_count`, `failed_files_count`, `total_bytes_processed`, `log_summary`, `error_details`, `created_by`, `started_at`, `completed_at`, `created_at`, `updated_at`.
- **Validation**:
  - `clean()`: If `source_type == "zip_archive"`, ensures `archive_file` is provided and has `.zip` extension.

---

## 3. URLs & Views Contract (`apps/documents/views/` & `urls/`)

All views function-based with `@login_required` (mutations require tenant scoping).

### 3.1 DocumentFolder Routes
- `storage/folders/` -> `name="folder_list"` (View: `folder_list`)
  - **Context Keys**: `folders`, `page_obj`, `q`, `is_virtual`, `department`, `departments`, `status`, `total_count`
- `storage/folders/tree/` -> `name="folder_tree"` (View: `folder_tree`)
  - **Context Keys**: `root_folders`, `tree_json`
- `storage/folders/create/` -> `name="folder_create"` (View: `folder_create`)
  - **Context Keys**: `form`, `title`
- `storage/folders/<int:pk>/` -> `name="folder_detail"` (View: `folder_detail`)
  - **Context Keys**: `folder`, `subfolders`, `documents`, `page_obj`, `total_files`, `total_bytes`
- `storage/folders/<int:pk>/edit/` -> `name="folder_edit"` (View: `folder_edit`)
  - **Context Keys**: `form`, `folder`, `is_edit`, `title`
- `storage/folders/<int:pk>/delete/` -> `name="folder_delete"` (View: `folder_delete`, POST-only)

### 3.2 StorageVolume Routes
- `storage/volumes/` -> `name="storage_volume_list"` (View: `storage_volume_list`)
  - **Context Keys**: `volumes`, `page_obj`, `q`, `backend_type`, `tier`, `backend_choices`, `tier_choices`, `total_count`, `total_capacity_gb`, `total_utilized_gb`
- `storage/volumes/create/` -> `name="storage_volume_create"` (View: `storage_volume_create`)
  - **Context Keys**: `form`, `title`
- `storage/volumes/<int:pk>/` -> `name="storage_volume_detail"` (View: `storage_volume_detail`)
  - **Context Keys**: `volume`, `batch_imports`, `rollover_sources`
- `storage/volumes/<int:pk>/edit/` -> `name="storage_volume_edit"` (View: `storage_volume_edit`)
  - **Context Keys**: `form`, `volume`, `is_edit`, `title`
- `storage/volumes/<int:pk>/delete/` -> `name="storage_volume_delete"` (View: `storage_volume_delete`, POST-only)

### 3.3 DocumentRelationship Routes
- `storage/relationships/` -> `name="relationship_list"` (View: `relationship_list`)
  - **Context Keys**: `relationships`, `page_obj`, `q`, `relationship_type`, `type_choices`, `total_count`
- `storage/relationships/graph/` -> `name="relationship_graph"` (View: `relationship_graph`)
  - **Context Keys**: `relationships`, `nodes_json`, `links_json`
- `storage/relationships/create/` -> `name="relationship_create"` (View: `relationship_create`)
  - **Context Keys**: `form`, `title`
- `storage/relationships/<int:pk>/` -> `name="relationship_detail"` (View: `relationship_detail`)
  - **Context Keys**: `relationship`, `source_doc`, `target_doc`
- `storage/relationships/<int:pk>/edit/` -> `name="relationship_edit"` (View: `relationship_edit`)
  - **Context Keys**: `form`, `relationship`, `is_edit`, `title`
- `storage/relationships/<int:pk>/delete/` -> `name="relationship_delete"` (View: `relationship_delete`, POST-only)

### 3.4 DocumentBatchImport Routes
- `storage/batch-imports/` -> `name="batch_import_list"` (View: `batch_import_list`)
  - **Context Keys**: `batch_imports`, `page_obj`, `q`, `status`, `source_type`, `status_choices`, `source_choices`, `total_count`
- `storage/batch-imports/create/` -> `name="batch_import_create"` (View: `batch_import_create`)
  - **Context Keys**: `form`, `title`
- `storage/batch-imports/<int:pk>/` -> `name="batch_import_detail"` (View: `batch_import_detail`)
  - **Context Keys**: `batch_import`, `target_folder`, `storage_volume`, `log_lines`, `error_lines`
- `storage/batch-imports/<int:pk>/edit/` -> `name="batch_import_edit"` (View: `batch_import_edit`)
  - **Context Keys**: `form`, `batch_import`, `is_edit`, `title`
- `storage/batch-imports/<int:pk>/delete/` -> `name="batch_import_delete"` (View: `batch_import_delete`, POST-only)
- `storage/batch-imports/<int:pk>/process/` -> `name="batch_import_process"` (View: `batch_import_process`, POST-only)
  - **Context Keys**: `batch_import`, `result_summary`

### 3.5 RepositoryDashboard Route
- `storage/dashboard/` -> `name="repository_dashboard"` (View: `repository_dashboard`)
  - **Context Keys**: `total_folders`, `total_volumes`, `total_relationships`, `total_imports`, `total_capacity_bytes`, `total_utilized_bytes`, `capacity_utilization_pct`, `recent_imports`, `volumes`, `top_folders`

---

## 4. Navigation Wiring (`LIVE_LINKS["13.4"]`)
```python
    "13.4": {
        "Folder Hierarchy & Taxonomy": "documents:folder_list",
        "Cloud & On-Premises Deployment": "documents:storage_volume_list",
        "Storage Tiering & Optimization": "documents:storage_volume_list",
        "Document Linking & Relationships": "documents:relationship_list",
        "Bulk Upload & Import": "documents:batch_import_list",
    },
```
