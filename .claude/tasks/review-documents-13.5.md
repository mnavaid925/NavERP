# Review Findings: Sub-module 13.5 Metadata & Indexing (`apps/documents/`)

- **Target App**: `apps.documents` (Sub-module 13.5 Metadata & Indexing)
- **Base Commit**: `854283261e069cdf0964bd22f6749b5491811d06`
- **Head Commit**: `ecca8676d50a89b064dd655a69ea69902c6d3aec`
- **Date**: 2026-11-23

---

## Pass 1: Code Reviewer (`code-reviewer`)

### Critical
- **`REV1-C1`**: Premature `category` lookup in `clean_term_code()` causes false positive validation and unhandled 500 `IntegrityError`
  - *Location*: `apps/documents/forms/MetadataIndexing/TaxonomyTerms.py:51-64`
  - *Detail*: In `TaxonomyTermForm`, `clean_term_code()` attempts to check uniqueness per tenant and category using `self.cleaned_data.get("category")`, but `term_code` appears before `category` in `Meta.fields`. In Django forms, `BaseForm._clean_fields` processes fields sequentially, so `cleaned_data.get("category")` is always `None` when `clean_term_code()` executes. Duplicate category-code pairs pass validation and crash with unhandled 500 `IntegrityError` (`doc_dtax_tnt_cat_code_uniq`) upon save.
  - *Fix*: Move category uniqueness check into `TaxonomyTermForm.clean()`, where both `category` and `term_code` are populated in `cleaned_data`.

### Important
- **`REV1-I1`**: Missing circular reference protection in `TaxonomyTermForm`
  - *Location*: `apps/documents/forms/MetadataIndexing/TaxonomyTerms.py:82-87`
  - *Detail*: Contract 2.3 requires parent not form a circular reference. While `instance.pk` is excluded from the parent queryset, existing descendants are not excluded, and `clean()` has no cycle detection. A user can assign an ancestor to its own child/descendant, creating an infinite loop during tree traversal.
  - *Fix*: Add ancestor traversal cycle check in `TaxonomyTermForm.clean()`.

- **`REV1-I2`**: Missing tenant-scoped uniqueness validation in `DocumentMetadataValueForm`
  - *Location*: `apps/documents/forms/MetadataIndexing/DocumentMetadataValues.py:56-67`
  - *Detail*: Model `DocumentMetadataValue` enforces `UniqueConstraint(fields=["tenant", "document", "version", "field_name"])`. Because `tenant` is excluded from the ModelForm, Django skips checking this uniqueness constraint, and submitting duplicate field names for a document version triggers an unhandled 500 `IntegrityError`.
  - *Fix*: Add tenant-scoped uniqueness validation for `(tenant, document, version, field_name)` in `DocumentMetadataValueForm.clean()`.

- **`REV1-I3`**: Missing data type conformance validation in `DocumentMetadataValueForm`
  - *Location*: `apps/documents/forms/MetadataIndexing/DocumentMetadataValues.py:56-67`
  - *Detail*: Contract 2.2 requires values conform to `data_type`. When `data_type == "json"`, invalid JSON text is accepted; when numeric/date types are selected, empty values bypass type validation.
  - *Fix*: Validate `value_json` with `json.loads` when `data_type == "json"`, and verify corresponding typed field (`value_number`, `value_date`, `value_boolean`) or parseable text is present.

- **`REV1-I4`**: Logic drift in `document_ocr_job_apply`: OCR text not committed when `job.version` is null
  - *Location*: `apps/documents/views/MetadataIndexing/DocumentOcrJobs.py:196-204`
  - *Detail*: In `document_ocr_job_apply`, if an OCR job was created with version=None (the default "Latest Document Version"), `job.version` is null, so `job.version.extracted_text` is never updated even though the UI reports success.
  - *Fix*: Fall back to `job.version or job.document.versions.order_by("-created_at").first()`.

- **`REV1-I5`**: Missing `Prefetch` filtering on children in `taxonomy_term_tree` view
  - *Location*: `apps/documents/views/MetadataIndexing/TaxonomyTerms.py:65`
  - *Detail*: `prefetch_related("children")` does not constrain child items by `tenant` or `is_active=True`, causing inactive child terms to render in tree hierarchy.
  - *Fix*: Use `Prefetch("children", queryset=TaxonomyTerm.objects.filter(tenant=tenant, is_active=True))`.

- **`REV1-I6`**: Schema code format validation missing in `MetadataSchemaForm`
  - *Location*: `apps/documents/forms/MetadataIndexing/MetadataSchemas.py:56-67`
  - *Detail*: Contract 2.1 specifies schema code must be alphanumeric with underscores/hyphens. Current clean method only strips and uppercases, permitting spaces or invalid punctuation.
  - *Fix*: Add regex validation `^[A-Z0-9_-]+$` in `MetadataSchemaForm.clean_code()`.

### Minor
- **`REV1-M1`**: Unused variable `doc_pk` in `metadata_value_delete`
  - *Location*: `apps/documents/views/MetadataIndexing/DocumentMetadataValues.py:169`
  - *Detail*: `doc_pk = val.document_id` is assigned but unused.
  - *Fix*: Remove unused variable.

- **`REV1-M2`**: Floating-point literal assigned to `DecimalField` in `document_ocr_job_process`
  - *Location*: `apps/documents/views/MetadataIndexing/DocumentOcrJobs.py:173`
  - *Detail*: Assigns float `96.50` to `DecimalField`.
  - *Fix*: Use `Decimal("96.50")`.

- **`REV1-M3`**: Duplicate field key detection omitted in `MetadataSchemaForm.clean_fields_definition_json`
  - *Location*: `apps/documents/forms/MetadataIndexing/MetadataSchemas.py:69-88`
  - *Detail*: Validates JSON structure but allows multiple fields with identical `key` values in the schema JSON array.
  - *Fix*: Check for duplicate keys in `seen` set.

---

## Pass 2: Codebase Explorer (`explorer`)

### Important
- **`REV2-I1`**: Circularity protection missing in `TaxonomyTermForm` (corroborates `REV1-I1`)
  - *Location*: `apps/documents/forms/MetadataIndexing/TaxonomyTerms.py:83-87`
  - *Detail*: Excludes immediate self-parenting in `__init__`, but `clean()` does not detect multi-hop descendant cycles (A -> B -> A).
  - *Fix*: Implement recursive ancestor traversal cycle check in `TaxonomyTermForm.clean()`.

- **`REV2-I2`**: Uncaught duplicate `IntegrityError` on `DocumentMetadataValue` creation (corroborates `REV1-I2`)
  - *Location*: `apps/documents/forms/MetadataIndexing/DocumentMetadataValues.py:56-67`
  - *Detail*: Excluded tenant field causes Django's `validate_unique()` to skip `doc_dmeta_tnt_doc_fld_uniq`, crashing on duplicate field names.
  - *Fix*: Explicitly check tenant-scoped uniqueness in `clean()`.

- **`REV2-I3`**: Tags not committed to `Document.tags` and fallback version missing in `document_ocr_job_apply`
  - *Location*: `apps/documents/views/MetadataIndexing/DocumentOcrJobs.py:192-207`
  - *Detail*: When applying OCR results, `job.suggested_tags_json` is not appended to `job.document.tags`, and if `job.version` is None (the default selection), no extracted text is persisted.
  - *Fix*: Resolve `target_version = job.version or job.document.versions.order_by("-version_number").first()` and append suggested tags to `job.document.tags`.

### Minor
- **`REV2-M1`**: Inactive children rendered in taxonomy hierarchy tree (corroborates `REV1-I5`)
  - *Location*: `apps/documents/views/MetadataIndexing/TaxonomyTerms.py:65` and `templates/documents/metadata_indexing/taxonomy_term/tree.html:86-108`
  - *Detail*: `prefetch_related("children")` does not constrain child items by `is_active=True`.
  - *Fix*: Prefetch with `TaxonomyTerm.objects.filter(tenant=tenant, is_active=True)`.

---

## Pass 3: Frontend Reviewer (`frontend-reviewer`)

### Critical
- **`REV3-C1`**: Unsafe user-FK lookup on `taxonomy_term/detail.html` (Lesson L10)
  - *Location*: `templates/documents/metadata_indexing/taxonomy_term/detail.html:101`
  - *Detail*: `{{ taxonomy_term.created_by.get_full_name|default:taxonomy_term.created_by.username }}` is executed without an `{% if %}` guard. When `created_by` is None, evaluating `default:taxonomy_term.created_by.username` raises `VariableDoesNotExist` and 500s.
  - *Fix*: Guard with `{% if taxonomy_term.created_by %}{{ taxonomy_term.created_by.get_full_name|default:taxonomy_term.created_by.username }}{% else %}System{% endif %}`.

- **`REV3-C2`**: Unsafe user-FK lookup on `metadata_schema/detail.html` (Lesson L10)
  - *Location*: `templates/documents/metadata_indexing/metadata_schema/detail.html:93`
  - *Detail*: `{{ schema.created_by.get_full_name|default:schema.created_by.username }}` is executed without an `{% if schema.created_by %}` guard, risking `VariableDoesNotExist` 500 when evaluated in detached/null contexts.
  - *Fix*: Guard with `{% if schema.created_by %}{{ schema.created_by.get_full_name|default:schema.created_by.username }}{% else %}—{% endif %}`.

### Important
- **`REV3-I1`**: Non-existent Lucide icon `schema` renders empty / blank
  - *Location*: `templates/documents/metadata_indexing/metadata_schema/list.html:34, 168`, `document_metadata_value/list.html:20`, `metadata_indexing_dashboard.html:36, 78`
  - *Detail*: `<i data-lucide="schema"></i>` is used in 5 places. `schema` does not exist in Lucide and renders as a blank space.
  - *Fix*: Replace with valid icon `database`, `boxes`, or `table-properties`.

- **`REV3-I2`**: Unescaped JS string interpolation in form onsubmit confirm (Lesson L42)
  - *Location*: `templates/documents/metadata_indexing/metadata_schema/list.html:155`, `taxonomy_term/list.html:163`
  - *Detail*: `onsubmit="return confirm('... {{ item.name }} ...');"` breaks if `item.name` contains an apostrophe, causing JavaScript syntax error.
  - *Fix*: Use `{{ item.name|escapejs }}`.

### Minor
- **`REV3-M1`**: Thesaurus tree inactive children visual distinction
  - *Location*: `templates/documents/metadata_indexing/taxonomy_term/tree.html:88-105`
  - *Detail*: Inactive child terms render identically to active ones.
  - *Fix*: Add `{% if not child.is_active %}` visual opacity / badge.

- **`REV3-M2`**: Tailwind text color classes instead of theme helper utilities
  - *Location*: `templates/documents/metadata_indexing/document_ocr_job/list.html:137`
  - *Detail*: Ad-hoc `text-green-600` / `text-amber-600` instead of `.text-ok` / `.text-warn`.
  - *Fix*: Use theme CSS classes.

---

## Pass 4: Performance Reviewer (`performance-reviewer`)

### Critical
- **`REV4-C1`**: Unindexed hot filters on EAV table `DocumentMetadataValue.data_type` & unusable composite index for `validation_status`
  - *Location*: `apps/documents/models/MetadataIndexing/DocumentMetadataValues.py:92-123`, `views/MetadataIndexing/DocumentMetadataValues.py:33-44`
  - *Detail*: `data_type` has no index, forcing full table scan. The composite index `doc_dmeta_tnt_doc_val_idx` has `document` before `validation_status`, making it unusable when filtering by status alone.
  - *Fix*: Add composite indexes on `(tenant, data_type)`, `(tenant, validation_status)`, and `(tenant, source)`.

### Important
- **`REV4-I1`**: N+1 foreign key lookups in `metadata_schema_detail`
  - *Location*: `apps/documents/views/MetadataIndexing/MetadataSchemas.py:92`
  - *Detail*: Detail view accesses `schema.department.name`, `schema.target_folder.path`, and `schema.created_by.get_full_name` triggering 3 extra queries per request.
  - *Fix*: Add `select_related("department", "target_folder", "created_by")`.

- **`REV4-I2`**: Prefetch cache bypass in `taxonomy_term_detail`
  - *Location*: `apps/documents/views/MetadataIndexing/TaxonomyTerms.py:130-136`
  - *Detail*: Prefetches `children` then calls `.filter(tenant=tenant)`, throwing away the prefetch cache and running 2 queries.
  - *Fix*: Use `Prefetch("children", queryset=TaxonomyTerm.objects.filter(tenant=tenant))` and call `term.children.all()`.

- **`REV4-I3`**: Missing composite index for default ordering and engine filter in `DocumentOcrJob`
  - *Location*: `apps/documents/models/MetadataIndexing/DocumentOcrJobs.py:62-101`
  - *Detail*: `ordering = ["-created_at"]` lacks a `(tenant, -created_at)` index, causing filesort. `ocr_engine` has no index.
  - *Fix*: Add indexes for `(tenant, -created_at)` and `(tenant, ocr_engine)`.

- **`REV4-I4`**: Extra queries in OCR action views (`process` and `apply`)
  - *Location*: `apps/documents/views/MetadataIndexing/DocumentOcrJobs.py:143-158, 193-205`
  - *Detail*: Accesses `job.document.owner` and `job.document.title` without `select_related`.
  - *Fix*: Add `select_related("document__owner")` in process and `select_related("document", "version")` in apply.

### Minor
- **`REV4-M1`**: Inefficient retrieval of heavy `extracted_full_text` `TextField` on list and dashboard views
  - *Location*: `apps/documents/views/MetadataIndexing/DocumentOcrJobs.py:23`, `MetadataIndexingDashboard.py:25`
  - *Detail*: Full text OCR dump is loaded into memory in list queries where it is not displayed.
  - *Fix*: Add `.defer("extracted_full_text")`.

- **`REV4-M2`**: Dead query for `recent_terms` in `metadata_indexing_dashboard`
  - *Location*: `apps/documents/views/MetadataIndexing/MetadataIndexingDashboard.py:26`
  - *Detail*: `recent_terms` is queried and passed to context but not rendered.
  - *Fix*: Render recent terms card in dashboard or remove unused query.

- **`REV4-M3`**: Uncombined count queries on `DocumentOcrJob` in dashboard
  - *Location*: `apps/documents/views/MetadataIndexing/MetadataIndexingDashboard.py:21-22`
  - *Detail*: Triggers two separate count queries for total and pending.
  - *Fix*: Combine using `.aggregate(total=Count("id"), pending=Count("id", filter=...))`.

- **`REV4-M4`**: Missing index on `MetadataSchema(tenant, name)` for default sorting
  - *Location*: `apps/documents/models/MetadataIndexing/MetadataSchemas.py:90-99`
  - *Detail*: Default ordering by `name` performs in-memory sort.
  - *Fix*: Add `models.Index(fields=["tenant", "name"], name="doc_dsch_tnt_name_idx")`.

---

## Pass 5: QA Smoke Tester (`qa-smoke-tester`)

### Critical
- **`REV5-C1`**: Unhandled 500 error & sequence retry exhaustion on duplicate `(category, term_code)` (corroborates `REV1-C1`)
  - *Location*: `apps/documents/forms/MetadataIndexing/TaxonomyTerms.py:51-63`, `models/MetadataIndexing/TaxonomyTerms.py:77`
  - *Detail*: Field ordering causes `category` to be None during `clean_term_code()`, bypassing form validation. On `save()`, MySQL triggers `IntegrityError`, which `TenantNumbered.save()` misdiagnoses as a number allocation collision, retrying 5 times and crashing with 500.
  - *Fix*: Move `(category, term_code)` uniqueness validation into `TaxonomyTermForm.clean()`.

- **`REV5-C2`**: Unhandled 500 error on duplicate `(tenant, document, version, field_name)` when version is set (corroborates `REV1-I2`)
  - *Location*: `apps/documents/forms/MetadataIndexing/DocumentMetadataValues.py:56-67`
  - *Detail*: Submitting an existing field name for a document version triggers `doc_dmeta_tnt_doc_fld_uniq`. `TenantNumbered.save()` retries 5 times and crashes with 500.
  - *Fix*: Add tenant-scoped uniqueness validation in `DocumentMetadataValueForm.clean()`.

- **`REV5-C3`**: Silent data duplication and lack of unique constraint when version is NULL
  - *Location*: `apps/documents/models/MetadataIndexing/DocumentMetadataValues.py:117`, `forms/MetadataIndexing/DocumentMetadataValues.py:56-67`
  - *Detail*: SQL treats `NULL != NULL`. Because `version` is nullable, the existing unique constraint fails to prevent duplicate field names when `version` is None.
  - *Fix*: Add conditional unique constraint for `version__isnull=True` and validate in `DocumentMetadataValueForm.clean()`.

### Important
- **`REV5-I1`**: `metadata_value_validate` falsely marks non-numeric strings as valid
  - *Location*: `apps/documents/views/MetadataIndexing/DocumentMetadataValues.py:189-195`
  - *Detail*: Condition `if val.data_type in ["integer", "decimal"] and val.value_number is None and not val.value_text:` fails to detect non-numeric strings in `value_text` (e.g. `"abc"`), falsely marking the property as valid.
  - *Fix*: Parse `value_text` in a `try...except` block for numbers and dates.

- **`REV5-I2`**: OCR text silently discarded when `job.version` is null, and tags never committed (corroborates `REV1-I4`, `REV2-I3`)
  - *Location*: `apps/documents/views/MetadataIndexing/DocumentOcrJobs.py:188-207`
  - *Detail*: View fails to fall back to current document version when `job.version` is None, and completely ignores `job.suggested_tags_json`.
  - *Fix*: Fall back to latest version and merge tags into `job.document.tags`.

- **`REV5-I3`**: Missing JSON syntax validation in `DocumentMetadataValueForm` when `data_type="json"` (corroborates `REV1-I3`)
  - *Location*: `apps/documents/forms/MetadataIndexing/DocumentMetadataValues.py:7-67`
  - *Detail*: Malformed JSON in `value_json` passes validation and corrupts database values.
  - *Fix*: Add `clean_value_json()` to validate with `json.loads`.

- **`REV5-I4`**: Destructive cascade deletion on parent taxonomy terms and ignored governance
  - *Location*: `apps/documents/models/MetadataIndexing/TaxonomyTerms.py:41-48`, `views/MetadataIndexing/TaxonomyTerms.py:180-192`
  - *Detail*: Deleting a parent term permanently cascades and wipes all child terms without warning, and ignores `is_governed`.
  - *Fix*: In `taxonomy_term_delete`, block deletion if term has children or is governed, or use `on_delete=models.PROTECT`.

### Minor
- **`REV5-M1`**: `TaxonomyTermForm.clean_synonyms_json` accepts JSON object instead of array
  - *Location*: `apps/documents/forms/MetadataIndexing/TaxonomyTerms.py:65-80`
  - *Detail*: `{"a": "b"}` falls through to comma splitting.
  - *Fix*: Validate JSON type is `list`.

- **`REV5-M2`**: Property helpers swallow JSON parse errors silently
  - *Location*: `apps/documents/models/MetadataIndexing/MetadataSchemas.py:113-118`, `TaxonomyTerms.py:94-100`
  - *Detail*: Returns `[]` without logging.
  - *Fix*: Log warning or return empty list cleanly.

- **`REV5-M3`**: Uppercase code normalization missing in `MetadataSchema.save()`
  - *Location*: `apps/documents/models/MetadataIndexing/MetadataSchemas.py:46`
  - *Detail*: `clean_code` uppercases, but model `save()` does not enforce it.
  - *Fix*: Add uppercase normalization in model `save()`.

---

## Pass 6: Security Reviewer (`security-reviewer`)

### High
- **`REV6-H1`**: Stored XSS / JavaScript Injection in Form Onsubmit Handlers
  - *Location*: `templates/documents/metadata_indexing/metadata_schema/list.html:155`, `templates/documents/metadata_indexing/taxonomy_term/list.html:163`
  - *Detail*: Unescaped `{{ item.name }}` inside `onsubmit="return confirm('... {{ item.name }} ...');"` allows JS execution if name contains quotes.
  - *Fix*: Use `{{ item.name|escapejs }}` within JavaScript confirmation strings.

- **`REV6-H2`**: Document Lock Bypass & State Guard Absence in `document_ocr_job_apply`
  - *Location*: `apps/documents/views/MetadataIndexing/DocumentOcrJobs.py:188-207`
  - *Detail*: Does not verify if `job.document.is_locked` by another user; also allows applying non-completed jobs, overwriting document text with empty text.
  - *Fix*: Check `job.status == "completed"` and verify document checkout lock before committing text.

### Medium
- **`REV6-M1`**: Missing Document Checkout Lock Enforcement in Metadata Value Mutations
  - *Location*: `apps/documents/views/MetadataIndexing/DocumentMetadataValues.py:69-175`
  - *Detail*: Users can create, update, or delete metadata values on a document locked by another user.
  - *Fix*: Validate `document.is_locked` against `request.user` before creating, updating, or deleting metadata values.

- **`REV6-M2`**: Unrestricted Deletion of Governed Taxonomy Terms and Enterprise Metadata Schemas
  - *Location*: `apps/documents/views/MetadataIndexing/TaxonomyTerms.py:180-192`, `apps/documents/views/MetadataIndexing/MetadataSchemas.py:140-153`
  - *Detail*: Standard staff users can delete governed taxonomy terms (`is_governed=True`) or company-wide metadata schemas without tenant administrator authorization.
  - *Fix*: Require `@tenant_admin_required` for schema deletion and verify `is_governed` check in taxonomy term deletion.

### Low
- **`REV6-L1`**: Validation Status Tampering via Form Mass Assignment in `DocumentMetadataValueForm`
  - *Location*: `apps/documents/forms/MetadataIndexing/DocumentMetadataValues.py:8-24`
  - *Detail*: `validation_status` exposed in `Meta.fields` allows users to manually set `"valid"` without running validation logic.
  - *Fix*: Exclude `validation_status` from `Meta.fields` and manage it exclusively in `metadata_value_validate`.

- **`REV6-L2`**: Unrestricted Re-processing of Completed/Reviewed OCR Jobs
  - *Location*: `apps/documents/views/MetadataIndexing/DocumentOcrJobs.py:137-184`
  - *Detail*: `document_ocr_job_process` does not check if job is already completed or reviewed, allowing re-running OCR and wiping historical metrics.
  - *Fix*: Guard view to only allow execution when `job.status in ["queued", "failed"]`.





