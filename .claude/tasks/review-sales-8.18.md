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

---

## Pass 2: Explorer (`explorer`)

**Verdict:** Commit after fixing Important findings. 100% Contract & route compliance.

### Critical
*None.*

### Important
- **EX-I1**: `apps/sales/views/IntegrationApiHub/Dashboard.py:48-70` & `apps/core/navigation.py:2637-2641` — NavERP.md §8.18 category lens bullets map to `sales:sic_erp_list`, `sales:sic_marketing_list`, etc., which execute HTTP 302 redirects to `sales:sic_list?category=...`. Once redirected, `request.resolver_match.view_name` becomes `sales:sic_list`. In `resolve_nav()`, `_route_score("sales:sic_erp_list", "sales:sic_list")` returns `-1`. Consequently, clicking "ERP Integration" or other category bullets causes the sidebar to highlight "Connectors" instead of the active category bullet.
  - **Fix:** In `apps/core/navigation.py`, deep-link via query parameter: `"ERP Integration": "sales:sic_list?category=erp"` (which `_match_score` natively recognizes and outscores bare routes by parameter count).
- **EX-I2**: `apps/sales/views/IntegrationApiHub/FieldMappings.py:36-38`, `SyncJobs.py:36-38`, `SyncRuns.py:39-46` — Missing overflow protection on FK filters in list views (same as CR-I2).
- **EX-I3**: `apps/sales/forms/IntegrationApiHub/FieldMappings.py:10` — Missing `TenantUniqueMixin` on `SalesFieldMappingForm` (same as CR-I1).

### Minor
- **EX-M1**: `apps/sales/views/IntegrationApiHub/Dashboard.py:25-29` & `templates/sales/integrationapihub/hub_dashboard.html:87,115,143,171,199` — In `hub_dashboard`, category querysets (`erp_connectors`, etc.) are passed to context, and the template calls `.count` on each (`{{ erp_connectors.count }}`), resulting in 5 extra database COUNT queries on dashboard load. Pre-compute category counts in view context or aggregate.
- **EX-M2**: `apps/sales/views/IntegrationApiHub/FieldMappings.py:142` — Context/Referrer inconsistency on `sfm_delete` (same as CR-M1).
- **EX-M3**: `apps/sales/models/IntegrationApiHub/SyncJobs.py:56` — `batch_size` field allows 0 (same as CR-M4).
- **EX-M4**: `apps/sales/views/IntegrationApiHub/Connectors.py:168` & `SyncJobs.py:167` — Omission of `updated_at` in `update_fields` (same as CR-M2).

---

## Pass 3: Frontend Reviewer (`frontend-reviewer`)

**Verdict:** Commit after fixing Important findings. Strict design-system badge compliance, zero comment leaks, safe pagination guards.

### Critical
*None.*

### Important
- **FE-I1**: Missing `|escapejs` in JavaScript `confirm()` dialogs across list and detail templates:
  - `templates/sales/integrationapihub/connectors/list.html:157` (`conn.name`)
  - `templates/sales/integrationapihub/connectors/detail.html:50` (`connector.name`)
  - `templates/sales/integrationapihub/fieldmappings/list.html:155` (`map.local_field`, `map.remote_field`)
  - `templates/sales/integrationapihub/syncjobs/list.html:164` (`job.name`)
  - `templates/sales/integrationapihub/syncjobs/detail.html:46` (`job.name`)
  - `templates/sales/integrationapihub/syncruns/list.html:157` (`run.number`)
  - `templates/sales/integrationapihub/syncruns/detail.html:41` (`run.number`)
  - **Issue:** Entity names containing apostrophes/quotes (e.g. "Vendor's ERP", "Customer's API", "O'Reilly") break inline JavaScript with `Uncaught SyntaxError: Unexpected identifier`.
  - **Fix:** Apply `|escapejs` to all variables embedded inside JavaScript dialog strings (same as CR-M3, promoted to Important).

### Minor
- **FE-M1**: `templates/sales/integrationapihub/hub_dashboard.html:87,115,143,171,199` — Badges declare `{{ erp_connectors.count }} Active`, etc., but the view querysets filter only by `category` without checking `is_active=True`. Change badge text to `{{ erp_connectors.count }} Configured` to match KPI terminology.
- **FE-M2**: `templates/sales/integrationapihub/hub_dashboard.html:59` — Hardcoded `text-green-700` unconditionally applied to `{{ healthy_count }}/{{ connectors_count }}` even when 0 connectors or health is degraded. Use neutral `text-slate-900` or condition color.
- **FE-M3**: `apps/sales/forms/IntegrationApiHub/Connectors.py:42`, `FieldMappings.py:35-37` — Form widgets use `class: "form-checkbox"` instead of theme.css `.form-check`.
- **FE-M4**: `templates/sales/integrationapihub/{connectors,fieldmappings,syncjobs,syncruns}/list.html` — Disabled previous/next pagination links omit `aria-disabled="true"` and `tabindex="-1"`. Add accessibility attributes.

---

## Pass 4: Performance Reviewer (`performance-reviewer`)

**Verdict:** Commit after fixing Important findings. Good prefetching and pagination; needs aggregation for dashboard counts and index coverage on tenant-scoped query paths.

### Critical
*None.*

### Important
- **PRF-I1**: `apps/sales/views/IntegrationApiHub/Dashboard.py:25-29` & `templates/sales/integrationapihub/hub_dashboard.html:87,115,143,171,199` — In `hub_dashboard`, 5 separate category querysets are evaluated via `.count` in template, plus separate counts for total connectors, jobs, runs, healthy, active, generating 11 separate queries on every dashboard load.
  - **Fix:** Precompute category counts via `connectors_qs.values_list("category").annotate(total=models.Count("id"))` and use conditional aggregation for connector/job stats (`total`, `healthy`, `active`). Drops query count from 11 to 5.
- **PRF-I2**: `apps/sales/models/IntegrationApiHub/SyncRuns.py:61-64` — Missing multi-tenant composite ordering index `(tenant, -started_at)` on `SalesSyncRun`. `SalesSyncRun.objects.filter(tenant=tenant).order_by("-started_at")` in list and dashboard causes full tenant scan + filesort on high-volume audit run log table.
  - **Fix:** Add `models.Index(fields=["tenant", "-started_at"], name="sales_ssr_tenant_start_idx")` (27 chars <= 30) in `SalesSyncRun.Meta.indexes`.
- **PRF-I3**: `apps/sales/models/IntegrationApiHub/Connectors.py:97-100` & `SyncJobs.py:68-71` — Missing index coverage on `(tenant, health_status)` for `SalesIntegrationConnector` and `(tenant, status)` for `SalesSyncJob` for dashboard/list filters.
  - **Fix:** Add `sales_sic_ten_health_idx` (`["tenant", "health_status"]`, 26 chars) and `sales_ssj_ten_status_idx` (`["tenant", "status"]`, 24 chars).

### Minor
- **PRF-M1**: `apps/sales/views/IntegrationApiHub/Connectors.py:74-76` & `templates/sales/integrationapihub/connectors/detail.html:74,79` — In `sic_detail`, `{{ field_mappings.count }}` and `{{ sync_jobs.count }}` run 2 SQL queries before loops evaluate. Use `{{ field_mappings|length }}` and `{{ sync_jobs|length }}`.
- **PRF-M2**: `apps/sales/models/IntegrationApiHub/FieldMappings.py:62-63` — `SalesFieldMapping.__str__` accesses foreign key `self.connector.name`. Safeguard `__str__` to avoid FK lookup if not cached.
- **PRF-M3**: `apps/sales/views/IntegrationApiHub/SyncRuns.py:57-58` — Filter dropdown querysets load full model instances. Apply `.only("id", "name", "number")` to connector and sync job filter querysets.



