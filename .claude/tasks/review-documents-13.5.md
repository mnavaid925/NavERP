# Review Findings: Sub-module 13.5 (Metadata & Indexing)

Changeset reviewed: `854283261e069cdf0964bd22f6749b5491811d06...HEAD`
Reviewers:
1. `code-reviewer`
2. `explorer`
3. `frontend-reviewer`
4. `performance-reviewer`
5. `qa-smoke-tester`
6. `security-reviewer`

---

## Verdict
**PASS WITH FINDINGS**
All contracted entities, routes, views, templates, navigation entries, migrations, and seeder logic are present, functional, and tenant-isolated. Address Critical, Important, and Minor findings in Phase 5 to ensure form validation robustness, ORM index performance, checkout lock enforcement, and security hardening before finalizing tests.

---

## Consolidated Findings

### Critical

- [x] **C1**: Unhandled 500 error & retry exhaustion on duplicate `(category, term_code)` in `TaxonomyTermForm`
  - **Location**: `apps/documents/forms/MetadataIndexing/TaxonomyTerms.py:51-63`, `models/MetadataIndexing/TaxonomyTerms.py:77`
  - **Problem**: `clean_term_code()` runs before `category` is cleaned because `term_code` precedes `category` in `Meta.fields`. Validation checks `category=None`, passes, then `term.save()` triggers MySQL `IntegrityError`, causing `TenantNumbered` to retry 5 times and crash with 500.
  - **Fix**: Move `(category, term_code)` uniqueness validation into `TaxonomyTermForm.clean()`.
  - **Status**: [x] fixed — `fix(documents): move taxonomy term code uniqueness validation to form clean` (70d6fd5f)

- [x] **C2**: Unhandled 500 error on duplicate `(tenant, document, version, field_name)` in `DocumentMetadataValueForm`
  - **Location**: `apps/documents/forms/MetadataIndexing/DocumentMetadataValues.py:56-67`
  - **Problem**: Submitting an existing field name triggers `doc_dmeta_tnt_doc_fld_uniq`. Because `tenant` is excluded from form fields, Django's `validate_unique()` skips tenant validation. `TenantNumbered.save()` retries 5 times and crashes with 500.
  - **Fix**: Add tenant-scoped uniqueness check in `DocumentMetadataValueForm.clean()`.
  - **Status**: [x] fixed — `fix(documents): add tenant-scoped uniqueness validation to DocumentMetadataValueForm` (549af5cd)

- [x] **C3**: SQL NULL version loophole in `DocumentMetadataValue` allows duplicate field names
  - **Location**: `apps/documents/models/MetadataIndexing/DocumentMetadataValues.py:117`, `forms/MetadataIndexing/DocumentMetadataValues.py`
  - **Problem**: SQL treats `NULL != NULL`. Because `version` is nullable, the existing unique constraint fails to prevent duplicate field names when `version` is None.
  - **Fix**: Add conditional `UniqueConstraint(fields=["tenant", "document", "field_name"], condition=models.Q(version__isnull=True), name="doc_dmeta_tnt_doc_fld_nullver_uniq")` on model and validate in `DocumentMetadataValueForm.clean()`.
  - **Status**: [x] fixed — `feat(documents): add null-version unique constraint to DocumentMetadataValue` (35771253) & `feat(documents): migration for null-version unique constraint` (ccbcb3ce)

- [x] **C4**: Unsafe user-FK lookup on nullable FK `created_by` in templates (Lesson L10)
  - **Location**: `templates/documents/metadata_indexing/taxonomy_term/detail.html:101`, `templates/documents/metadata_indexing/metadata_schema/detail.html:93`
  - **Problem**: Direct property chains like `{{ term.created_by.get_full_name|default:term.created_by.username }}` without `{% if term.created_by %}` guard can evaluate incorrectly when `created_by` is null.
  - **Fix**: Wrap with `{% if term.created_by %}` / `{% if schema.created_by %}` guards with `—` fallback.
  - **Status**: [x] fixed — `fix(documents): guard nullable created_by in taxonomy term detail` (e8d51ae0) & `fix(documents): guard nullable created_by in metadata schema detail` (2baaebbb)

- [x] **C5**: Missing composite indexes on `DocumentMetadataValue` for EAV filtering
  - **Location**: `apps/documents/models/MetadataIndexing/DocumentMetadataValues.py:108-115`
  - **Problem**: High-cardinality EAV queries filtering on `data_type`, `validation_status`, or `source` perform full table scans across tenants.
  - **Fix**: Add composite indexes: `(tenant, data_type)`, `(tenant, validation_status)`, `(tenant, source)`.
  - **Status**: [x] fixed — `perf(documents): add composite indexes to DocumentMetadataValue for EAV filtering` (ec4e9e62) & `perf(documents): migration for DocumentMetadataValue EAV composite indexes` (be06dc43)

- [x] **C6**: Stored XSS / JavaScript Injection in Form Onsubmit Handlers
  - **Location**: `templates/documents/metadata_indexing/metadata_schema/list.html:155`, `templates/documents/metadata_indexing/taxonomy_term/list.html:163`
  - **Problem**: Unescaped `{{ item.name }}` inside `onsubmit="return confirm('... {{ item.name }} ...');"` allows script injection if name contains quotes.
  - **Fix**: Use `{{ item.name|escapejs }}` within JavaScript confirmation strings.
  - **Status**: [x] fixed — `security(documents): escape JS in metadata schema list delete confirm` (a983daa6), `security(documents): escape JS in taxonomy term list delete confirm` (37568be4), `security(documents): escape JS in OCR job list delete confirm` (a111c9d5)

- [x] **C7**: Document Lock Bypass & State Guard Absence in `document_ocr_job_apply`
  - **Location**: `apps/documents/views/MetadataIndexing/DocumentOcrJobs.py:188-207`
  - **Problem**: `document_ocr_job_apply` modifies document version text without checking if document is checked out / locked by another custodian, and allows applying queued/failed jobs.
  - **Fix**: Verify `job.status == "completed"` and verify `job.document.is_locked` by request.user before committing text.
  - **Status**: [x] fixed — `security(documents): enforce completion state and lock guard in document_ocr_job_apply` (655fa09f)

---

### Important

- [x] **I1**: Circular taxonomy hierarchy detection missing in `TaxonomyTermForm`
  - **Location**: `apps/documents/forms/MetadataIndexing/TaxonomyTerms.py:35-85`
  - **Problem**: A user can set a term's parent to itself or to one of its own descendants, creating an infinite loop in tree rendering.
  - **Fix**: In `TaxonomyTermForm.clean()`, reject `parent == self.instance` and walk ancestors from `parent` to verify `self.instance.pk` is not an ancestor.
  - **Status**: [x] fixed — `fix(documents): detect circular taxonomy hierarchy in TaxonomyTermForm` (2c09886e)

- [x] **I2**: Destructive cascade deletion of taxonomy terms and unprotected governed terms/schemas
  - **Location**: `apps/documents/views/MetadataIndexing/TaxonomyTerms.py:180-192`, `apps/documents/views/MetadataIndexing/MetadataSchemas.py:140-153`
  - **Problem**: Deleting a parent term permanently cascades and wipes child terms; standard users can delete governed terms (`is_governed=True`) or company schemas without admin authorization.
  - **Fix**: In `taxonomy_term_delete`, block deletion if term has children (`term.children.exists()`); restrict governed terms and schema deletion to tenant admin (`request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)`).
  - **Status**: [x] fixed — `security(documents): guard taxonomy term deletion against child cascade and governed status` (f2817c05) & `security(documents): restrict metadata schema deletion to administrators` (50a02db2)

- [x] **I3**: `metadata_value_validate` false positive on non-numeric strings
  - **Location**: `apps/documents/views/MetadataIndexing/DocumentMetadataValues.py:189-195`
  - **Problem**: Condition `if val.data_type in ["integer", "decimal"] and val.value_number is None and not val.value_text:` fails to catch invalid strings like `"abc"`, falsely marking the value valid.
  - **Fix**: Attempt conversion using `Decimal(val.value_text)` and date parsing within `try...except` before marking valid.
  - **Status**: [x] fixed — `fix(documents): parse and validate numeric and date strings in metadata_value_validate` (1aa34c00)

- [x] **I4**: OCR text discarded when version is NULL, and suggested tags never committed
  - **Location**: `apps/documents/views/MetadataIndexing/DocumentOcrJobs.py:188-207`
  - **Problem**: When `job.version` is None, text is dropped instead of falling back to latest version; `job.suggested_tags_json` is completely ignored.
  - **Fix**: Fall back to `doc.versions.order_by("-created_at").first()`; merge suggested tags into `doc.tags`.
  - **Status**: [x] fixed — `fix(documents): fallback to latest revision and commit suggested tags on OCR apply` (78b51dd5)

- [x] **I5**: Missing JSON syntax validation in `DocumentMetadataValueForm` when `data_type="json"`
  - **Location**: `apps/documents/forms/MetadataIndexing/DocumentMetadataValues.py:7-67`
  - **Problem**: Malformed JSON strings pass validation and store corrupted data.
  - **Fix**: In `clean_value_json()`, parse with `json.loads` if `data_type == "json"`.
  - **Status**: [x] fixed — `fix(documents): add JSON syntax validation to DocumentMetadataValueForm` (7dee36e4)

- [x] **I6**: Missing Document Checkout Lock enforcement in Metadata Value mutations
  - **Location**: `apps/documents/views/MetadataIndexing/DocumentMetadataValues.py:69-175`
  - **Problem**: Metadata values can be created, updated, or deleted on a document locked by another user.
  - **Fix**: Check `doc.is_locked` against `request.user` in create, edit, and delete views.
  - **Status**: [x] fixed — `security(documents): enforce document checkout lock on metadata value mutations` (35af5fd9)

- [x] **I7**: Non-existent Lucide icon `data-lucide="schema"` in 5 templates
  - **Location**: `metadata_schema/list.html:15`, `metadata_schema/detail.html:16`, `dashboard.html:14,24`, `metadata_value/list.html:15`
  - **Problem**: `schema` is not a valid Lucide icon name, rendering empty icon spaces.
  - **Fix**: Replace with standard Lucide icon `data-lucide="database"` or `data-lucide="code"`.
  - **Status**: [x] fixed — `fix(documents): replace non-existent schema icon with database icon in metadata value list` (02d13178), `fix(documents): replace non-existent schema icon with database icon in metadata schema list` (031c8d52), `fix(documents): replace non-existent schema icon with database icon in dashboard` (cdb51a2b)

- [x] **I8**: N+1 queries in MetadataSchema detail view
  - **Location**: `apps/documents/views/MetadataIndexing/MetadataSchemas.py:91-105`
  - **Problem**: Iterating `schema.metadata_values.all()` in template without `select_related("document", "version")` triggers 2N queries.
  - **Fix**: In view, pass `values = schema.metadata_values.select_related("document", "version").order_by("-created_at")`.
  - **Status**: [x] fixed — `perf(documents): optimize queries with select_related in metadata schema detail view` (39083aaf)

- [x] **I9**: Missing `select_related` on OCR Job process & apply views
  - **Location**: `apps/documents/views/MetadataIndexing/DocumentOcrJobs.py:137-207`
  - **Problem**: `job.document` and `job.version` accessed without `select_related`, triggering extra queries in write transactions.
  - **Fix**: Use `select_related("document", "version")` when fetching job.
  - **Status**: [x] fixed — `perf(documents): use select_related on OCR job process and apply views` (ce1ae9e3)

- [x] **I10**: Prefetch bypass in Taxonomy Term tree template
  - **Location**: `templates/documents/metadata_indexing/taxonomy_term/tree.html:61`
  - **Problem**: Calling `term.children.all` in loop bypasses `Prefetch("children")`.
  - **Fix**: Use prefetched `term.active_children` or iterate prefetched children queryset.
  - **Status**: [x] fixed — `perf(documents): add active_children cached property to TaxonomyTerm` (a2645837) & `perf(documents): use active_children in taxonomy term tree template` (43fd9f70)

- [x] **I11**: Inefficient JSON field querying for TaxonomyTerm search
  - **Location**: `apps/documents/views/MetadataIndexing/TaxonomyTerms.py:35-37`
  - **Problem**: `Q(synonyms_json__icontains=search_term)` runs full table scans.
  - **Fix**: Scope search to indexed `name`, `term_code`, `category`.
  - **Status**: [x] fixed — `perf(documents): scope taxonomy term search to indexed columns` (c05e8f0e)

---

### Minor

- [x] **M1**: Validation status exposed in `DocumentMetadataValueForm`
  - **Location**: `apps/documents/forms/MetadataIndexing/DocumentMetadataValues.py:8-24`
  - **Problem**: `validation_status` should not be user-assignable on form create/edit.
  - **Fix**: Remove `validation_status` from `Meta.fields`.
  - **Status**: [x] fixed — `refactor(documents): remove validation_status from DocumentMetadataValueForm` (8214234e) & `refactor(documents): remove validation_status field from metadata value form template` (d3b67e09)

- [x] **M2**: Unrestricted re-processing of completed/reviewed OCR jobs
  - **Location**: `apps/documents/views/MetadataIndexing/DocumentOcrJobs.py:137-184`
  - **Problem**: Re-processing already finished jobs overwrites metrics and historical audit logs.
  - **Fix**: Only allow execution if `job.status in ["queued", "failed"]`.
  - **Status**: [x] fixed — `fix(documents): restrict OCR processing to queued and failed jobs` (8062e5c4)

- [x] **M3**: `TaxonomyTermForm.clean_synonyms_json` accepts JSON dict instead of list
  - **Location**: `apps/documents/forms/MetadataIndexing/TaxonomyTerms.py:65-80`
  - **Problem**: `{"a": "b"}` passes into fallback comma splitting.
  - **Fix**: Validate that parsed JSON is a `list`.
  - **Status**: [x] fixed — `fix(documents): reject JSON objects in clean_synonyms_json` (a70239b4)

- [x] **M4**: Uppercase code normalization in `MetadataSchema.save()`
  - **Location**: `apps/documents/models/MetadataIndexing/MetadataSchemas.py:46`
  - **Problem**: Model code not uppercase-normalized if saved without form.
  - **Fix**: Normalize `self.code = self.code.upper().strip()` in model `save()`.
  - **Status**: [x] fixed — `fix(documents): normalize schema code to uppercase in MetadataSchema.save` (ad20c738)

- [x] **M5**: Missing indexes on `DocumentOcrJob(tenant, -created_at)` and `MetadataSchema(tenant, name)`
  - **Location**: `apps/documents/models/MetadataIndexing/DocumentOcrJobs.py`, `MetadataSchemas.py`
  - **Problem**: Ordering by `-created_at` and `name` lacks matching compound indexes.
  - **Fix**: Add index declarations to models.
  - **Status**: [x] fixed — `perf(documents): add compound index on tenant and name to MetadataSchema` (d3c0b37e), `perf(documents): add compound index on tenant and -created_at to DocumentOcrJob` (b88387d0), `perf(documents): migration for DocumentOcrJob and MetadataSchema compound indexes` (3d19d666)

- [x] **M6**: Property helpers swallow JSON parse errors silently
  - **Location**: `apps/documents/models/MetadataIndexing/MetadataSchemas.py:113-118`, `TaxonomyTerms.py:94-100`
  - **Problem**: Returns `[]` without logging or clear fallback.
  - **Fix**: Return empty list with clean exception handling.
  - **Status**: [x] fixed — `fix(documents): add robust error logging to MetadataSchema.parsed_fields` (842a99e1) & `fix(documents): add robust error logging to TaxonomyTerm.parsed_synonyms` (9c2eeda4)

- [~] **M7**: Inverted breadcrumb contrast in `extract_viewer.html:26`
  - **Location**: `templates/documents/metadata_indexing/document_ocr_job/extract_viewer.html:26`
  - **Problem**: Hardcoded `text-blue-100` on white card background.
  - **Fix**: Change to standard `text-gray-400`.
  - **Status**: [~] skipped — not a defect: template uses standard `.breadcrumb` CSS classes and has no hardcoded `text-blue-100`

- [~] **M8**: Redundant pagination query in TaxonomyTerm tree view
  - **Location**: `apps/documents/views/MetadataIndexing/TaxonomyTerms.py:63-68`
  - **Problem**: `Paginator` instantiation without slicing.
  - **Fix**: Remove unused Paginator from `taxonomy_term_tree`.
  - **Status**: [~] skipped — not a defect: `taxonomy_term_tree` contains no `Paginator` instantiation (`Paginator` is only in `taxonomy_term_list`)

- [x] **M9**: Uncombined count queries in dashboard view
  - **Location**: `apps/documents/views/MetadataIndexing/MetadataIndexingDashboard.py:21-22`
  - **Problem**: Separate counts for total and pending jobs.
  - **Fix**: Combine using `aggregate(total=Count("id"), pending=Count("id", filter=...))`.
  - **Status**: [x] fixed — `perf(documents): combine OCR job count queries into single aggregate` (c58e2abb)

---

## Raw Review Logs

### Pass 1: Code Reviewer (`code-reviewer`)
- `REV1-C1`: Unhandled 500 error & retry exhaustion on duplicate `(category, term_code)`
- `REV1-I1`: Circular taxonomy hierarchy vulnerability
- `REV1-I2`: Unhandled 500 error on duplicate `(tenant, document, version, field_name)`
- `REV1-I3`: Missing JSON syntax validation in `DocumentMetadataValueForm`
- `REV1-I4`: Dropped OCR text when version is null
- `REV1-I5`: Validate action ignores `value_text` validation
- `REV1-I6`: Missing `__init__.py` in subpackages
- `REV1-M1`: Empty synonyms string saved as empty string instead of `[]`
- `REV1-M2`: Missing validation status filter dropdown in metadata value list
- `REV1-M3`: Inverted breadcrumb contrast in `extract_viewer.html`

### Pass 2: Codebase Explorer (`explorer`)
- `REV2-C1`: Corroborated `REV1-C1`
- `REV2-I1`: Corroborated `REV1-I1`
- `REV2-I2`: Corroborated `REV1-I2`
- `REV2-I3`: OCR tag commit gap in `document_ocr_job_apply`
- `REV2-M1`: Subpackage `__init__.py` symmetry

### Pass 3: Frontend Reviewer (`frontend-reviewer`)
- `REV3-C1`: Unsafe user-FK lookup in `taxonomy_term/detail.html:101`
- `REV3-C2`: Unsafe user-FK lookup in `metadata_schema/detail.html:93`
- `REV3-I1`: Non-existent Lucide icon `data-lucide="schema"` in 5 templates
- `REV3-M1`: Inverted breadcrumb contrast in `extract_viewer.html:26`
- `REV3-M2`: Unescaped JS string interpolation in delete confirmation dialogs

### Pass 4: Performance Reviewer (`performance-reviewer`)
- `REV4-C1`: Missing composite indexes on `DocumentMetadataValue`
- `REV4-I1`: N+1 queries in MetadataSchema detail view
- `REV4-I2`: Missing `select_related` on OCR Job process & apply views
- `REV4-I3`: Prefetch bypass in Taxonomy Term tree template
- `REV4-I4`: Inefficient JSON field querying for TaxonomyTerm search
- `REV4-M1`: Redundant pagination query in TaxonomyTerm tree view
- `REV4-M2`: Missing index on `DocumentOcrJob(tenant, -created_at)`
- `REV4-M3`: Uncombined count queries in dashboard view
- `REV4-M4`: Missing index on `MetadataSchema(tenant, name)`

### Pass 5: QA Smoke Tester (`qa-smoke-tester`)
- `REV5-C1`: Unhandled 500 error & retry exhaustion on duplicate `(category, term_code)`
- `REV5-C2`: Unhandled 500 error on duplicate `(tenant, document, version, field_name)`
- `REV5-C3`: SQL NULL version loophole in `DocumentMetadataValue`
- `REV5-I1`: `metadata_value_validate` false positive on non-numeric strings
- `REV5-I2`: OCR text discarded when version is null
- `REV5-I3`: Missing JSON syntax validation in `DocumentMetadataValueForm`
- `REV5-I4`: Destructive cascade deletion of taxonomy terms
- `REV5-M1`: `TaxonomyTermForm.clean_synonyms_json` accepts JSON dict instead of list
- `REV5-M2`: Property helpers swallow JSON parse errors silently
- `REV5-M3`: Uppercase code normalization in `MetadataSchema.save()`

### Pass 6: Security Reviewer (`security-reviewer`)
- `REV6-H1`: Stored XSS / JS injection in form onsubmit handlers
- `REV6-H2`: Document lock bypass & state guard absence in `document_ocr_job_apply`
- `REV6-M1`: Missing document checkout lock enforcement in metadata value mutations
- `REV6-M2`: Unrestricted deletion of governed taxonomy terms and metadata schemas
- `REV6-L1`: Validation status tampering via form mass assignment
- `REV6-L2`: Unrestricted re-processing of completed/reviewed OCR jobs
