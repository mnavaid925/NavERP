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
