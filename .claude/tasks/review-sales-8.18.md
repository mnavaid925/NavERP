# Review Findings — Sales 8.18: Integration & API Hub (`sales`)

> Reviewing changeset `bbd7b52f0fb78aa15695661dfc53e7ea0d5dc2a2...be283a62c6440920e40118bbe06616d8265bf7a2`.
> Six serial reviewer passes: `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` → `security-reviewer`.

---

## Pass 1: Code Reviewer (`code-reviewer`)

**Verdict:** Commit after fixing Important findings.

### Critical
*None.*

### Important
- **CR-I1**: `apps/sales/forms/IntegrationApiHub/FieldMappings.py:10` — `SalesFieldMappingForm` does not inherit `TenantUniqueMixin`. Because `tenant` is excluded from form `fields`, Django's `ModelForm.validate_unique()` excludes `tenant` from unique validation. Submitting a duplicate `(tenant, connector, target_entity, local_field, remote_field)` bypasses form validation and causes an unhandled 500 `IntegrityError` on `obj.save()` instead of rendering a clean validation error.
  - **Fix:** Inherit `TenantUniqueMixin` from `apps.sales.forms._common` in `SalesFieldMappingForm`.
- **CR-I2**: `apps/sales/views/IntegrationApiHub/FieldMappings.py:37`, `SyncJobs.py:38`, `SyncRuns.py:42,45` — GET parameter FK filters parse via `isdigit()` and directly `int(...)` into `.filter(...)` without overflow protection. Passing an over-range integer (e.g. `?connector=999999999999999999999999999999`) causes `OverflowError: Python int too large to convert to SQLite INTEGER` on test and production database drivers (L11).
  - **Fix:** Use `as_db_int(request.GET.get("connector", ""))` and `as_db_int(request.GET.get("job", ""))` before applying `.filter(...)`.
- **CR-I3**: `apps/sales/forms/IntegrationApiHub/FieldMappings.py:45` — `value_map` field on `SalesFieldMapping` needs validation in `clean_value_map` to default empty values to `{}` and reject non-dict JSON payloads to avoid null constraint violations or TypeError at runtime.
  - **Fix:** Add `clean_value_map(self)` returning `{}` when falsy or verifying `isinstance(data, dict)`.

### Minor
- **CR-M1**: `apps/sales/views/IntegrationApiHub/FieldMappings.py:98` — `sfm_delete` redirects to `sales:sic_detail` of the parent connector, which may be unexpected when deleting from the full field mapping list view. Support redirecting back to `sales:sfm_list` if no connector or based on referrer.
- **CR-M2**: `apps/sales/views/IntegrationApiHub/Connectors.py:126`, `SyncJobs.py:134` — `sic_test` and `ssj_trigger` update status/statistics using `update_fields=[...]` without including `"updated_at"`.
- **CR-M3**: Confirm dialogs in templates (`connectors/detail.html`, `fieldmappings/detail.html`, `syncjobs/detail.html`) output object names in inline JS `confirm('...')` without `|escapejs`.
- **CR-M4**: `apps/sales/models/IntegrationApiHub/SyncJobs.py` — `batch_size` uses `PositiveIntegerField(default=100)` allowing 0 at the model level. Add `MinValueValidator(1)`.
- **CR-M5**: `templates/sales/integrationapihub/connectors/list.html:137`, `syncruns/list.html:144` — Status badges use hardcoded fallback labels in `{% else %}` branches instead of dynamic model display (`get_health_status_display` / `get_status_display`).
