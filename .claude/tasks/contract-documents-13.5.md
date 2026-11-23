# Module 13.5 Pre-Build Contract — Metadata & Indexing (`apps/documents/`)

> Frozen in Phase 3.1 before any entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["13.5"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.documents` (Extends existing app; claims incremental migration `0007_...`)
- **Package Directories**:
  - `apps/documents/models/MetadataIndexing/`
  - `apps/documents/forms/MetadataIndexing/`
  - `apps/documents/views/MetadataIndexing/`
  - `apps/documents/urls/MetadataIndexing/`
  - `templates/documents/metadata_indexing/{metadata_schema,document_metadata_value,taxonomy_term,document_ocr_job}/{list,detail,form}.html` + `tree.html`, `extract_viewer.html`, `metadata_indexing_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"validate"`, `"extract"`, `"apply"`, `"sync"`, `"cascade"`, `"process"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `documents.Document`, `documents.DocumentVersion`, `documents.DocumentFolder`, `documents.MetadataSchema`, `documents.TaxonomyTerm`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/documents/models/MetadataIndexing/`)

All 4 models inherit `apps.documents.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `MetadataSchema` (`MetadataSchemas.py`)
- **`NUMBER_PREFIX`**: `"DSCH"`
- **`Meta.ordering`**: `["name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Metadata Schema"` / `"Metadata Schemas"`
- **Choices & Badge Maps**:
  - `TARGET_TYPE_CHOICES` (`max_length=40`):
    - `("all", "All Document Types")`
    - `("contract", "Legal Contracts & Agreements")`
    - `("policy", "Corporate Policies & Governance")`
    - `("sop", "Standard Operating Procedures (SOP)")`
    - `("financial", "Financial Invoices & Reports")`
    - `("technical", "Technical Specifications & Manuals")`
    - `("hr", "Human Resources & Personnel Records")`
    - `("procurement", "Procurement & Vendor Documents")`
  - `INHERITANCE_MODE_CHOICES` (`max_length=25`):
    - `("none", "No Inheritance")`
    - `("folder_default", "Folder Default (Optional)")`
    - `("folder_strict", "Folder Cascade (Strict)")`
    - `("template", "Document Template Inheritance")`
  - `STATUS_CSS`:
    - `True: "badge-green"` (Active)
    - `False: "badge-slate"` (Inactive)
  - `TARGET_TYPE_CSS`:
    - `"all": "badge-info"`
    - `"contract": "badge-amber"`
    - `"policy": "badge-slate"`
    - `"sop": "badge-green"`
    - `"financial": "badge-green"`
    - `"technical": "badge-info"`
    - `"hr": "badge-amber"`
    - `"procurement": "badge-slate"`
- **Fields (exact names & types)**:
  - `name`: `CharField(max_length=150)`
  - `code`: `CharField(max_length=50, help_text="Unique schema slug identifier e.g. NDA_SCHEMA")`
  - `description`: `TextField(blank=True)`
  - `target_type`: `CharField(max_length=40, choices=TARGET_TYPE_CHOICES, default="all", db_index=True)`
  - `department`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="metadata_schemas")`
  - `target_folder`: `ForeignKey("documents.DocumentFolder", on_delete=models.SET_NULL, null=True, blank=True, related_name="metadata_schemas")`
  - `fields_definition_json`: `TextField(default="[]", help_text="JSON list of field definitions: key, label, data_type, required, default, choices")`
  - `inheritance_mode`: `CharField(max_length=25, choices=INHERITANCE_MODE_CHOICES, default="folder_default", db_index=True)`
  - `is_required`: `BooleanField(default=False, help_text="Mandatory schema completion before document publish")`
  - `allow_custom_fields`: `BooleanField(default=True, help_text="Allow ad-hoc key-value additions")`
  - `version_number`: `PositiveIntegerField(default=1)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_metadata_schemas")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dsch_ten_num_uniq")` (21 chars)
  - `UniqueConstraint(fields=["tenant", "code"], name="doc_dsch_tnt_code_uniq")` (22 chars)
  - `models.Index(fields=["tenant", "target_type", "is_active"], name="doc_dsch_tnt_tgt_act_idx")` (24 chars)

---

### 1.2 `DocumentMetadataValue` (`DocumentMetadataValues.py`)
- **`NUMBER_PREFIX`**: `"DMETA"`
- **`Meta.ordering`**: `["document", "field_name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document Metadata Value"` / `"Document Metadata Values"`
- **Choices & Badge Maps**:
  - `DATA_TYPE_CHOICES` (`max_length=20`):
    - `("text", "Text / String")`
    - `("textarea", "Long Text / Paragraph")`
    - `("integer", "Integer Number")`
    - `("decimal", "Decimal / Currency")`
    - `("date", "Calendar Date")`
    - `("datetime", "Date & Timestamp")`
    - `("boolean", "Boolean Flag (Yes/No)")`
    - `("dropdown", "Dropdown Single-Select")`
    - `("multi_select", "Multi-Select Tags")`
    - `("json", "Structured JSON Object")`
  - `SOURCE_CHOICES` (`max_length=25`):
    - `("manual_entry", "Manual User Entry")`
    - `("folder_inherited", "Inherited from Folder")`
    - `("template_inherited", "Inherited from Template")`
    - `("ai_extracted", "AI / OCR Extracted")`
    - `("bulk_updated", "Bulk Batch Updated")`
  - `VALIDATION_STATUS_CHOICES` (`max_length=25`):
    - `("valid", "Valid & Conforming")`
    - `("invalid", "Validation Failed")`
    - `("pending_validation", "Pending Verification")`
  - `DATA_TYPE_CSS`:
    - `"text": "badge-info"`, `"textarea": "badge-info"`, `"integer": "badge-slate"`, `"decimal": "badge-green"`, `"date": "badge-amber"`, `"datetime": "badge-amber"`, `"boolean": "badge-slate"`, `"dropdown": "badge-info"`, `"multi_select": "badge-info"`, `"json": "badge-slate"`
  - `SOURCE_CSS`:
    - `"manual_entry": "badge-slate"`
    - `"folder_inherited": "badge-info"`
    - `"template_inherited": "badge-info"`
    - `"ai_extracted": "badge-amber"`
    - `"bulk_updated": "badge-muted"`
  - `VALIDATION_STATUS_CSS`:
    - `"valid": "badge-green"`
    - `"invalid": "badge-red"`
    - `"pending_validation": "badge-amber"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="metadata_values", db_index=True)`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.CASCADE, null=True, blank=True, related_name="metadata_values")`
  - `schema`: `ForeignKey("documents.MetadataSchema", on_delete=models.SET_NULL, null=True, blank=True, related_name="metadata_values")`
  - `field_name`: `CharField(max_length=100, db_index=True)`
  - `field_label`: `CharField(max_length=150, blank=True)`
  - `data_type`: `CharField(max_length=20, choices=DATA_TYPE_CHOICES, default="text")`
  - `value_text`: `TextField(blank=True)`
  - `value_number`: `DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)`
  - `value_date`: `DateField(null=True, blank=True)`
  - `value_boolean`: `BooleanField(null=True, blank=True)`
  - `value_json`: `TextField(blank=True, default="")`
  - `source`: `CharField(max_length=25, choices=SOURCE_CHOICES, default="manual_entry", db_index=True)`
  - `is_overridden`: `BooleanField(default=False, help_text="True if inherited value was modified manually")`
  - `validation_status`: `CharField(max_length=25, choices=VALIDATION_STATUS_CHOICES, default="valid", db_index=True)`
  - `validation_error`: `TextField(blank=True)`
  - `last_validated_at`: `DateTimeField(null=True, blank=True)`
  - `updated_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="updated_metadata_values")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dmeta_ten_num_uniq")` (22 chars)
  - `UniqueConstraint(fields=["tenant", "document", "version", "field_name"], name="doc_dmeta_tnt_doc_fld_uniq")` (26 chars)
  - `models.Index(fields=["tenant", "document", "validation_status"], name="doc_dmeta_tnt_doc_val_idx")` (25 chars)
  - `models.Index(fields=["tenant", "field_name"], name="doc_dmeta_tnt_fld_idx")` (21 chars)

---

### 1.3 `TaxonomyTerm` (`TaxonomyTerms.py`)
- **`NUMBER_PREFIX`**: `"DTAX"`
- **`Meta.ordering`**: `["category", "name"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Taxonomy Term"` / `"Taxonomy Terms"`
- **Choices & Badge Maps**:
  - `CATEGORY_CHOICES` (`max_length=30`):
    - `("general", "General Enterprise Taxonomy")`
    - `("legal", "Legal & Contracts Thesaurus")`
    - `("finance", "Financial & Accounting Terms")`
    - `("compliance", "Regulatory Compliance & Risk")`
    - `("technical", "Engineering & Specifications")`
    - `("hr", "Human Resources & Workforce")`
    - `("procurement", "Procurement & SCM Thesaurus")`
    - `("industry", "Industry Standard Classifications")`
  - `CATEGORY_CSS`:
    - `"general": "badge-info"`
    - `"legal": "badge-amber"`
    - `"finance": "badge-green"`
    - `"compliance": "badge-red"`
    - `"technical": "badge-info"`
    - `"hr": "badge-amber"`
    - `"procurement": "badge-slate"`
    - `"industry": "badge-slate"`
  - `STATUS_CSS`:
    - `True: "badge-green"` (Active)
    - `False: "badge-slate"` (Inactive)
- **Fields (exact names & types)**:
  - `name`: `CharField(max_length=150)`
  - `term_code`: `CharField(max_length=60, help_text="Canonical term code e.g. TAX_CONFIDENTIALITY")`
  - `category`: `CharField(max_length=30, choices=CATEGORY_CHOICES, default="general", db_index=True)`
  - `parent`: `ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children", db_index=True)`
  - `description`: `TextField(blank=True)`
  - `synonyms_json`: `TextField(default="[]", help_text="JSON list of synonyms e.g. ['NDA', 'Proprietary Info']")`
  - `external_code`: `CharField(max_length=100, blank=True, help_text="Cross-reference standard code e.g. ISO 27001 / NAICS")`
  - `is_governed`: `BooleanField(default=True, help_text="Governed term requiring admin approval to alter")`
  - `usage_count`: `PositiveIntegerField(default=0)`
  - `is_active`: `BooleanField(default=True, db_index=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_taxonomy_terms")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_dtax_ten_num_uniq")` (21 chars)
  - `UniqueConstraint(fields=["tenant", "category", "term_code"], name="doc_dtax_tnt_cat_code_uniq")` (26 chars)
  - `models.Index(fields=["tenant", "category", "is_active"], name="doc_dtax_tnt_cat_act_idx")` (24 chars)

---

### 1.4 `DocumentOcrJob` (`DocumentOcrJobs.py`)
- **`NUMBER_PREFIX`**: `"DOCR"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Document OCR Job"` / `"Document OCR Jobs"`
- **Choices & Badge Maps**:
  - `STATUS_CHOICES` (`max_length=25`):
    - `("queued", "Queued for Processing")`
    - `("processing", "OCR & Analysis In Progress")`
    - `("completed", "Completed Successfully")`
    - `("failed", "Processing Failed")`
    - `("reviewed", "Reviewed & Applied")`
  - `OCR_ENGINE_CHOICES` (`max_length=40`):
    - `("internal_heuristic", "Internal Heuristic Text Extractor")`
    - `("tesseract_ocr", "Tesseract Open Source OCR Engine")`
    - `("azure_document_intelligence", "Microsoft Azure Document Intelligence")`
    - `("aws_textract", "AWS Textract Intelligent Parser")`
    - `("google_vision_ocr", "Google Cloud Vision Document AI")`
  - `STATUS_CSS`:
    - `"queued": "badge-slate"`
    - `"processing": "badge-amber"`
    - `"completed": "badge-green"`
    - `"failed": "badge-red"`
    - `"reviewed": "badge-info"`
  - `OCR_ENGINE_CSS`:
    - `"internal_heuristic": "badge-slate"`
    - `"tesseract_ocr": "badge-info"`
    - `"azure_document_intelligence": "badge-green"`
    - `"aws_textract": "badge-amber"`
    - `"google_vision_ocr": "badge-info"`
- **Fields (exact names & types)**:
  - `document`: `ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="ocr_jobs", db_index=True)`
  - `version`: `ForeignKey("documents.DocumentVersion", on_delete=models.CASCADE, null=True, blank=True, related_name="ocr_jobs")`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="queued", db_index=True)`
  - `ocr_engine`: `CharField(max_length=40, choices=OCR_ENGINE_CHOICES, default="internal_heuristic")`
  - `extracted_full_text`: `TextField(blank=True, help_text="Full text content extracted from document OCR")`
  - `confidence_score`: `DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Extraction confidence score (0-100%)")`
  - `page_count`: `PositiveIntegerField(default=1)`
  - `suggested_category`: `CharField(max_length=100, blank=True)`
  - `suggested_tags_json`: `TextField(default="[]", help_text="JSON list of AI suggested tags")`
  - `extracted_entities_json`: `TextField(default="{}", help_text="JSON dictionary of extracted structured entities (dates, parties, amounts, invoice #s)")`
  - `has_handwriting`: `BooleanField(default=False)`
  - `has_barcode`: `BooleanField(default=False)`
  - `processing_duration_ms`: `PositiveIntegerField(default=0)`
  - `error_message`: `TextField(blank=True)`
  - `applied_to_document`: `BooleanField(default=False, help_text="True if OCR text & tags have been committed to document master")`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_ocr_jobs")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="doc_docr_ten_num_uniq")` (21 chars)
  - `models.Index(fields=["tenant", "status", "created_at"], name="doc_docr_tnt_sta_dt_idx")` (24 chars)
  - `models.Index(fields=["tenant", "document", "status"], name="doc_docr_tnt_doc_sta_idx")` (24 chars)

---

## 2. Forms Contract (`apps/documents/forms/MetadataIndexing/`)

All forms must inherit `django.forms.ModelForm`, accept `tenant=None` in `__init__`, save `self.tenant = tenant`, and filter all FK querysets:
`self.fields['field'].queryset = Model.objects.filter(tenant=self.tenant)`.
Form `clean()` methods must validate cross-tenant integrity using `reject_foreign(...)` or explicit `tenant` checks.

### 2.1 `MetadataSchemaForm` (`MetadataSchemas.py`)
- **Model**: `MetadataSchema`
- **Fields**: `["name", "code", "description", "target_type", "department", "target_folder", "fields_definition_json", "inheritance_mode", "is_required", "allow_custom_fields", "is_active"]`
- **Excluded**: `["tenant", "number", "version_number", "created_by", "created_at", "updated_at"]`
- **Validation**:
  - `code` must be uppercase alphanumeric with underscores/hyphens.
  - `fields_definition_json` must be valid JSON list of dicts with `key`, `label`, `data_type`.
  - FKs (`department`, `target_folder`) must belong to `tenant`.

### 2.2 `DocumentMetadataValueForm` (`DocumentMetadataValues.py`)
- **Model**: `DocumentMetadataValue`
- **Fields**: `["document", "version", "schema", "field_name", "field_label", "data_type", "value_text", "value_number", "value_date", "value_boolean", "value_json", "source", "validation_status"]`
- **Excluded**: `["tenant", "number", "is_overridden", "validation_error", "last_validated_at", "updated_by", "created_at", "updated_at"]`
- **Validation**:
  - `document` must belong to tenant.
  - If `version` is set, `version.document` must match `document`.
  - Value must conform to `data_type`.

### 2.3 `TaxonomyTermForm` (`TaxonomyTerms.py`)
- **Model**: `TaxonomyTerm`
- **Fields**: `["name", "term_code", "category", "parent", "description", "synonyms_json", "external_code", "is_governed", "is_active"]`
- **Excluded**: `["tenant", "number", "usage_count", "created_by", "created_at", "updated_at"]`
- **Validation**:
  - `term_code` must be unique per tenant and category.
  - `synonyms_json` must be valid JSON list of strings or comma-separated list.
  - `parent` must belong to tenant and not form circular reference.

### 2.4 `DocumentOcrJobForm` (`DocumentOcrJobs.py`)
- **Model**: `DocumentOcrJob`
- **Fields**: `["document", "version", "ocr_engine"]`
- **Excluded**: `["tenant", "number", "status", "extracted_full_text", "confidence_score", "page_count", "suggested_category", "suggested_tags_json", "extracted_entities_json", "has_handwriting", "has_barcode", "processing_duration_ms", "error_message", "applied_to_document", "created_by", "created_at", "updated_at"]`
- **Validation**:
  - `document` must belong to tenant.
  - `version` if provided must belong to `document`.

---

## 3. Views & URLs Contract (`apps/documents/views/MetadataIndexing/` & `urls/MetadataIndexing/`)

Every URL route module exposes `urlpatterns = [...]` prefixed into `apps.documents.urls` under `app_name = "documents"`.
Literal routes precede `<int:pk>` routes.
All views are decorated with `@login_required` (and privileged mutation views with `@tenant_admin_required`).

### 3.1 MetadataSchema Routes & Context Keys
- `GET/POST /documents/schemas/` $\rightarrow$ `metadata_schema_list`
  - Context: `schemas`, `page_obj`, `q`, `target_type`, `is_active`, `target_type_choices`, `is_paginated`
- `GET/POST /documents/schemas/create/` $\rightarrow$ `metadata_schema_create`
  - Context: `form`, `is_edit: False`
- `GET /documents/schemas/<int:pk>/` $\rightarrow$ `metadata_schema_detail`
  - Context: `schema`, `obj`, `fields_list`, `values_count`, `target_type_badge`, `status_badge`
- `GET/POST /documents/schemas/<int:pk>/edit/` $\rightarrow$ `metadata_schema_edit`
  - Context: `form`, `schema`, `obj`, `is_edit: True`
- `POST /documents/schemas/<int:pk>/delete/` $\rightarrow$ `metadata_schema_delete`

### 3.2 DocumentMetadataValue Routes & Context Keys
- `GET/POST /documents/metadata/` $\rightarrow$ `metadata_value_list`
  - Context: `metadata_values`, `page_obj`, `q`, `data_type`, `source`, `validation_status`, `data_type_choices`, `source_choices`, `validation_status_choices`, `is_paginated`
- `GET/POST /documents/metadata/create/` $\rightarrow$ `metadata_value_create`
  - Context: `form`, `is_edit: False`
- `GET /documents/metadata/<int:pk>/` $\rightarrow$ `metadata_value_detail`
  - Context: `metadata_value`, `obj`, `status_badge`, `source_badge`, `data_type_badge`
- `GET/POST /documents/metadata/<int:pk>/edit/` $\rightarrow$ `metadata_value_edit`
  - Context: `form`, `metadata_value`, `obj`, `is_edit: True`
- `POST /documents/metadata/<int:pk>/delete/` $\rightarrow$ `metadata_value_delete`
- `POST /documents/metadata/<int:pk>/validate/` $\rightarrow$ `metadata_value_validate`
  - Runs validation on single value and returns redirect.

### 3.3 TaxonomyTerm Routes & Context Keys
- `GET/POST /documents/taxonomy/` $\rightarrow$ `taxonomy_term_list`
  - Context: `taxonomy_terms`, `page_obj`, `q`, `category`, `is_active`, `category_choices`, `is_paginated`
- `GET /documents/taxonomy/tree/` $\rightarrow$ `taxonomy_term_tree`
  - Context: `root_terms`, `category_groups`, `selected_category`
- `GET/POST /documents/taxonomy/create/` $\rightarrow$ `taxonomy_term_create`
  - Context: `form`, `is_edit: False`
- `GET /documents/taxonomy/<int:pk>/` $\rightarrow$ `taxonomy_term_detail`
  - Context: `taxonomy_term`, `obj`, `child_terms`, `synonyms_list`, `category_badge`, `status_badge`
- `GET/POST /documents/taxonomy/<int:pk>/edit/` $\rightarrow$ `taxonomy_term_edit`
  - Context: `form`, `taxonomy_term`, `obj`, `is_edit: True`
- `POST /documents/taxonomy/<int:pk>/delete/` $\rightarrow$ `taxonomy_term_delete`

### 3.4 DocumentOcrJob Routes & Context Keys
- `GET/POST /documents/ocr-jobs/` $\rightarrow$ `document_ocr_job_list`
  - Context: `ocr_jobs`, `page_obj`, `q`, `status`, `ocr_engine`, `status_choices`, `ocr_engine_choices`, `is_paginated`
- `GET/POST /documents/ocr-jobs/create/` $\rightarrow$ `document_ocr_job_create`
  - Context: `form`, `is_edit: False`
- `GET /documents/ocr-jobs/<int:pk>/` $\rightarrow$ `document_ocr_job_detail`
  - Context: `ocr_job`, `obj`, `status_badge`, `engine_badge`, `extracted_entities`, `suggested_tags`
- `GET /documents/ocr-jobs/<int:pk>/viewer/` $\rightarrow$ `document_ocr_job_viewer`
  - Context: `ocr_job`, `obj`, `extracted_entities`, `suggested_tags`
- `POST /documents/ocr-jobs/<int:pk>/process/` $\rightarrow$ `document_ocr_job_process`
  - Executes heuristic OCR text extraction and AI entity extraction on document.
- `POST /documents/ocr-jobs/<int:pk>/apply/` $\rightarrow$ `document_ocr_job_apply`
  - Applies OCR full-text to `version.extracted_text` and tags to document.
- `POST /documents/ocr-jobs/<int:pk>/delete/` $\rightarrow$ `document_ocr_job_delete`

### 3.5 Metadata & Indexing Dashboard
- `GET /documents/metadata-dashboard/` $\rightarrow$ `metadata_indexing_dashboard`
  - Context: `total_schemas`, `total_values`, `total_terms`, `total_ocr_jobs`, `recent_schemas`, `recent_jobs`, `pending_ocr_count`, `recent_terms`

---

## 4. Templates Contract

Paths strictly follow `templates/documents/metadata_indexing/<entity>/<page>.html`:
1. `templates/documents/metadata_indexing/metadata_schema/list.html`
2. `templates/documents/metadata_indexing/metadata_schema/detail.html`
3. `templates/documents/metadata_indexing/metadata_schema/form.html`
4. `templates/documents/metadata_indexing/document_metadata_value/list.html`
5. `templates/documents/metadata_indexing/document_metadata_value/detail.html`
6. `templates/documents/metadata_indexing/document_metadata_value/form.html`
7. `templates/documents/metadata_indexing/taxonomy_term/list.html`
8. `templates/documents/metadata_indexing/taxonomy_term/detail.html`
9. `templates/documents/metadata_indexing/taxonomy_term/form.html`
10. `templates/documents/metadata_indexing/taxonomy_term/tree.html`
11. `templates/documents/metadata_indexing/document_ocr_job/list.html`
12. `templates/documents/metadata_indexing/document_ocr_job/detail.html`
13. `templates/documents/metadata_indexing/document_ocr_job/form.html`
14. `templates/documents/metadata_indexing/document_ocr_job/extract_viewer.html`
15. `templates/documents/metadata_indexing/metadata_indexing_dashboard.html`

All templates extend `"base.html"`. All badges use `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate` ONLY.
All list templates implement search input `q`, status/filter dropdowns, table with Actions column (view, edit, delete with CSRF confirm), and guarded pagination (`has_previous` / `has_next`).

---

## 5. Navigation Wire-Up (`apps/core/navigation.py`)

`LIVE_LINKS["13.5"]` mapping all 5 NavERP.md feature bullets:
```python
    # 13.5 Metadata & Indexing
    "13.5": {
        "Custom Metadata Schema": "documents:metadata_schema_list",
        "Auto-Tagging & AI Classification": "documents:document_ocr_job_list",
        "Full-Text Indexing & OCR": "documents:document_ocr_job_list",
        "Controlled Vocabulary & Thesauri": "documents:taxonomy_term_list",
        "Metadata Inheritance & Propagation": "documents:metadata_value_list",
    },
```
