# Review Findings — Sales 8.18: Integration & API Hub (`sales`)

> Reviewing changeset `bbd7b52f0fb78aa15695661dfc53e7ea0d5dc2a2...be283a62c6440920e40118bbe06616d8265bf7a2`.
> All 6 serial reviewer passes completed: `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` → `security-reviewer`.

---

## Verdict
**Approved with Important findings.** No Critical vulnerabilities, active data leaks, or contract breakages. Solid Fernet secret encryption at rest, complete multi-tenant scoping (IDOR immunity), Zero Outbound HTTP simulated actions, and 100% route/contract compliance. Remediation of Important and Minor findings is assigned to the `code-fixer` agent in Phase 5.

---

## Consolidated Findings Register

### Critical
*None.*

---

### Important

- [x] **I1**: `apps/sales/forms/IntegrationApiHub/FieldMappings.py:10` — `SalesFieldMappingForm` does not inherit `TenantUniqueMixin`. Because `tenant` is excluded from form `fields`, Django's `ModelForm.validate_unique()` skips unique validation for tenant-scoped constraints. Submitting a duplicate `(tenant, connector, target_entity, local_field, remote_field)` bypasses form validation and causes an unhandled 500 `IntegrityError` on `obj.save()`.
  - **Fix:** Inherit `TenantUniqueMixin` from `apps.sales.forms._common` in `SalesFieldMappingForm`.
  - **Status:** [x] fixed — `533ec7f9 fix(sales): inherit TenantUniqueMixin in SalesFieldMappingForm for tenant-scoped uniqueness`

- [x] **I2**: `apps/sales/views/IntegrationApiHub/FieldMappings.py:35-37,83-85`, `SyncJobs.py:36-38,88-90`, `SyncRuns.py:39-46` — Integer query parameters (`connector`, `job`) in list filters and form initial dictionaries are checked with `.isdigit()` and cast with `int(...)` without overflow protection. Supplying an over-range integer causes `OverflowError: Python int too large to convert to SQLite INTEGER` on SQLite or `DataError: integer out of range` on PostgreSQL/MariaDB (L11).
  - **Fix:** Pass query parameters through `as_db_int(...)` from `apps.core.crud` before filtering querysets or assigning form initials.
  - **Status:** [x] fixed — `456aaa75, 0d7cc78d, b2b1b151 fix(sales): use as_db_int for connector and job parameters in FieldMappings, SyncJobs, SyncRuns views`

- [x] **I3**: `apps/sales/forms/IntegrationApiHub/FieldMappings.py:45` & `models/IntegrationApiHub/FieldMappings.py:44` — `value_map` field on `SalesFieldMappingForm` does not validate that the parsed JSON payload is a mapping (`dict`). Submitting non-dict JSON (e.g. list, integer, string) or falsy input causes null constraint violations or runtime `TypeError` / `AttributeError` when downstream code calls `.get()` or `.items()`.
  - **Fix:** Add `clean_value_map(self)` to `SalesFieldMappingForm` defaulting empty/falsy values to `{}` and validating `isinstance(data, dict)`.
  - **Status:** [x] fixed — `f009ac40 fix(sales): validate value_map is dictionary in SalesFieldMappingForm`

- [x] **I4**: `templates/sales/integrationapihub/connectors/list.html:157`, `connectors/detail.html:50`, `fieldmappings/list.html:155`, `syncjobs/list.html:164`, `syncjobs/detail.html:46`, `syncruns/list.html:157`, `syncruns/detail.html:41` — Inline JavaScript `confirm('... {{ var }} ...')` attributes interpolate user-controlled variables inside single quotes without the `|escapejs` filter. Single quotes in entity names (e.g. "Vendor's ERP", "Customer's API", "O'Reilly") break inline JavaScript with `Uncaught SyntaxError: Unexpected identifier`.
  - **Fix:** Apply `|escapejs` to all variables embedded within JavaScript `confirm('...')` dialog strings.
  - **Status:** [x] fixed — `e62bc2c0, 41d536aa, 529e7904, 8daf10e0, c4690a16, b37f5490, c1f8f5f1 fix(sales): escape interpolated variables in delete confirm dialogs`

- [x] **I5**: `apps/core/navigation.py:2637-2641` — NavERP.md §8.18 category lens bullets map to `sales:sic_erp_list`, etc., which execute HTTP 302 redirects to `sales:sic_list?category=...`. Once redirected, `request.resolver_match.view_name` becomes `sales:sic_list`, causing `_route_score` to fail matching and losing the active sidebar sub-bullet highlight.
  - **Fix:** In `apps/core/navigation.py`, deep-link via query parameter: `"ERP Integration": "sales:sic_list?category=erp"`, etc. (which `_match_score` natively recognizes and outscores bare routes by parameter count).
  - **Status:** [x] fixed — `22be4b73 fix(core): deep-link sales 8.18 category lenses with query parameters in navigation`

- [x] **I6**: `apps/sales/views/IntegrationApiHub/Dashboard.py:25-29` & `templates/sales/integrationapihub/hub_dashboard.html:87,115,143,171,199` — In `hub_dashboard`, 5 separate category querysets are evaluated via `.count` in template, plus separate counts for total connectors, jobs, runs, healthy, active, generating 11 separate queries on every dashboard load.
  - **Fix:** Precompute category counts via `connectors_qs.values_list("category").annotate(total=models.Count("id"))` and use conditional aggregation for connector/job stats (`total`, `healthy`, `active`). Drops query count from 11 to 5.
  - **Status:** [x] fixed — `20dff126, 655e9b32 fix(sales): precompute category counts and aggregate stats in hub_dashboard`

- [x] **I7**: `apps/sales/models/IntegrationApiHub/SyncRuns.py:61-64`, `Connectors.py:97-100`, `SyncJobs.py:68-71` — Missing multi-tenant composite ordering index `(tenant, -started_at)` on `SalesSyncRun`, missing `(tenant, health_status)` on `SalesIntegrationConnector`, and missing `(tenant, status)` on `SalesSyncJob` for hot filter/order queries.
  - **Fix:** Add `sales_ssr_tenant_start_idx` (`["tenant", "-started_at"]`, 27 chars), `sales_sic_ten_health_idx` (`["tenant", "health_status"]`, 26 chars), and `sales_ssj_ten_status_idx` (`["tenant", "status"]`, 24 chars). Generate and apply migration.
  - **Status:** [x] fixed — `148ddc0f, ae8012e8, c257ee08, 7234e39d fix(sales): add composite indexes and migration 0033`

---

### Minor

- [x] **M1**: `apps/sales/views/IntegrationApiHub/FieldMappings.py:142` — `sfm_delete` unconditionally redirects to `sales:sic_detail` of the parent connector. When deleting from `sales:sfm_list`, navigating away to the connector detail disrupts the list management flow.
  - **Fix:** Support redirecting back to `sales:sfm_list` if requested via `request.POST.get("next")` or referrer.
  - **Status:** [x] fixed — `ba37a6fb, 82c7db61 fix(sales): support next redirect and referrer fallback in sfm_delete`

- [x] **M2**: `apps/sales/views/IntegrationApiHub/Connectors.py:168` & `SyncJobs.py:167` — `save(update_fields=[...])` in `sic_test` and `ssj_trigger` mutates status/metrics but omits `"updated_at"`, leaving the audit timestamp stale.
  - **Fix:** Include `"updated_at"` in `update_fields`.
  - **Status:** [x] fixed — `d90272ff, 64092ba3 fix(sales): include updated_at in sic_test and ssj_trigger update_fields`

- [x] **M3**: `apps/sales/models/IntegrationApiHub/SyncJobs.py:56` — `batch_size = models.PositiveIntegerField(default=100)` accepts `0` at the model validation level.
  - **Fix:** Add `validators=[MinValueValidator(1)]`.
  - **Status:** [x] fixed — `dbd6006b, d1e129a0 fix(sales): add MinValueValidator(1) to SalesSyncJob batch_size and migration 0034`

- [x] **M4**: `templates/sales/integrationapihub/connectors/list.html:137`, `syncruns/list.html:144`, `hub_dashboard.html:59,87,115,143,171,199` — Status badges use hardcoded fallback labels in `{% else %}` branches instead of dynamic `get_FIELD_display`; category badges declare "Active" instead of "Configured"; KPI health ratio uses unconditional green color.
  - **Fix:** Use dynamic model display helpers and align KPI label text.
  - **Status:** [x] fixed — `256f2138, d19112b8, 655e9b32 fix(sales): use dynamic model display helpers and align badge/health labels`

- [x] **M5**: `apps/sales/forms/IntegrationApiHub/{Connectors,FieldMappings}.py`, `templates/sales/integrationapihub/{connectors,fieldmappings,syncjobs,syncruns}/list.html` — Checkbox widget class uses `form-checkbox` instead of theme.css `.form-check`; disabled pagination links omit `aria-disabled="true"` and `tabindex="-1"`.
  - **Fix:** Update widget class and add accessibility attributes.
  - **Status:** [x] fixed — `5fdc6582, 61767cb8, 68f83db7, 73ba6f28, d720bf7b, 5f348000 fix(sales): use form-check class and add pagination accessibility attributes`

- [x] **M6**: `templates/sales/integrationapihub/connectors/detail.html:74,79`, `apps/sales/models/IntegrationApiHub/FieldMappings.py:62-63`, `apps/sales/views/IntegrationApiHub/SyncRuns.py:57-58` — In `sic_detail`, `{{ field_mappings.count }}` runs extra queries before loops; `SalesFieldMapping.__str__` accesses foreign key without caching; filter dropdown querysets pull unused fields.
  - **Fix:** Use `|length` in template, safeguard `__str__`, and use `.only("id", "name", "number")` on filter dropdown querysets.
  - **Status:** [x] fixed — `320a445e, 9b23759f, 7e420b7e fix(sales): use length filter, safeguard __str__, and optimize filter dropdown queries with only()`

- [x] **M7**: `apps/sales/models/IntegrationApiHub/{FieldMappings,SyncJobs,SyncRuns}.py`, `apps/sales/forms/IntegrationApiHub/Connectors.py` — Models lack model-level `clean()` defense-in-depth asserting matching tenant on FKs; connector form has no way to revoke credentials if changing auth method to "none".
  - **Fix:** Add model-level `clean()` assertions and auto-clear `credential_encrypted` when `auth_method == "none"`.
  - **Status:** [x] fixed — `36e03ab8, b1096bcd, 4e2092a0, 8bb19fc4 fix(sales): add model clean() tenant assertions and auto-clear credentials on none auth`
