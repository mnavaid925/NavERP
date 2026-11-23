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


