# Review Findings — Sub-module 10.5: Data Quality & Cleansing (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.5 Data Quality & Cleansing
- **Module:** 10 Business Intelligence
- **Target app:** `apps/bi`
- **Review date:** 2026-11-04
- **Base SHA:** `37d37b12e750ca499865e43f79037a762e6961cd`
- **Status:** Complete (All 6 Review Passes Finished: code-reviewer, explorer, frontend-reviewer, performance-reviewer, qa-smoke-tester, security-reviewer)

---

## Prioritized Findings (Deduplicated)

### Critical Findings

- [x] **[C1] Universal `write_audit_log` parameter mismatch crashes all 16 POST mutations across all 4 entities** — fixed in 290b4521 (also 25282bb1, f1fc1079, c656e1da)
  - **Found by:** code-reviewer, explorer, qa-smoke-tester, security-reviewer
  - **Locations:**
    - `apps/bi/views/DataQuality/DataQualityProfiles.py:111, 139, 167, 225`
    - `apps/bi/views/DataQuality/DataQualityRules.py:129, 157, 185, 245`
    - `apps/bi/views/DataQuality/DataQualityExceptions.py:111, 139, 166, 190`
    - `apps/bi/views/DataQuality/DataQualityScorecards.py:107, 135, 163, 253`
  - **Description:** `write_audit_log` signature is `(user, obj, action, changes=None, tenant=None)` but called with 6 positional arguments `(request.tenant, request.user, "<action>", "<Model>", pk, message)`. This raises `TypeError` on every mutating POST, causing 500 server crashes. On delete views, it is called after `instance.delete()`, losing valid target references.
  - **Fix:** Update all call sites to `write_audit_log(request.user, instance, "<action>", tenant=request.tenant)`. On delete views, call before `instance.delete()`.

- [x] **[C2] `AttributeError: 'WarehouseTable' object has no attribute 'columns_metadata_json'` on Profile Run POST** — fixed in bdddf111
  - **Found by:** qa-smoke-tester, security-reviewer
  - **Location:** `apps/bi/views/DataQuality/DataQualityProfiles.py:188`
  - **Description:** When running a profile on a warehouse table, line 188 attempts to read `profile.warehouse_table.columns_metadata_json`. The actual column definition field on `WarehouseTable` is `schema_definition`. Any profile execution crashes with HTTP 500.
  - **Fix:** Update line 188 to `cols_meta = profile.warehouse_table.schema_definition or []`.

- [x] **[C3] Missing `data_mart` scope resolution in Scorecard Detail & Recalculation views** — fixed in 07319e6c
  - **Found by:** explorer, security-reviewer, qa-smoke-tester, code-reviewer
  - **Location:** `apps/bi/views/DataQuality/DataQualityScorecards.py:80-92, 185-195`
  - **Description:** `DataQualityScorecard` supports `scope_type = "data_mart"` with FK `data_mart`. Detail and recalculation views branch only for `warehouse_table` and `semantic_model`, falling back to tenant-wide rule/exception evaluation and corrupting domain scorecard metrics.
  - **Fix:** Add an explicit `elif scorecard.scope_type == "data_mart" and scorecard.data_mart:` branch that filters `rules_qs.filter(warehouse_table__data_mart=scorecard.data_mart)` and `exceptions_qs.filter(Q(warehouse_table__data_mart=scorecard.data_mart) | Q(semantic_model__data_mart=scorecard.data_mart))`.

---

### Important Findings

- [x] **[I1] Seeder `--flush` command atomic wipe omits Sub-module 10.5 models** — fixed in e691a4fb
  - **Found by:** code-reviewer, explorer, security-reviewer
  - **Location:** `apps/bi/management/commands/seed_bi.py:47-62`
  - **Description:** `--flush` omits `DataQualityScorecard`, `DataQualityException`, `DataQualityRule`, and `DataQualityProfile`. Flushing deletes parent models without cleaning up 10.5 records, leaving orphaned records and triggering unique constraint violations on re-seed.
  - **Fix:** Prepend deletion of `DataQualityScorecard`, `DataQualityException`, `DataQualityRule`, and `DataQualityProfile` in reverse dependency order in the flush block.

- [x] **[I2] `DataQualityExceptionRemediationForm` missing `TenantModelForm` inheritance & `reject_foreign`** — fixed in 4337f6f0
  - **Found by:** code-reviewer, explorer, security-reviewer
  - **Location:** `apps/bi/forms/DataQuality/DataQualityExceptionForms.py:75-103`
  - **Description:** Inherits directly from `forms.ModelForm` instead of `TenantModelForm`, lacking tenant scoping and `reject_foreign` validation for `assigned_steward`.
  - **Fix:** Subclass `TenantModelForm` and add `clean()` calling `reject_foreign(self, cleaned, ["assigned_steward"])`.

- [x] **[I3] Inconsistent resolution lifecycle state in exception triage & edit** — fixed in 338c00cd
  - **Found by:** code-reviewer, qa-smoke-tester, security-reviewer
  - **Location:** `apps/bi/views/DataQuality/DataQualityExceptions.py:137-148, 180-192`
  - **Description:** When transitioning status back to `open` or `investigating`, `resolved_by` and `resolved_at` are retained. In general edit form, transitioning to `remediated` never sets `resolved_by` or `resolved_at`.
  - **Fix:** Synchronize resolution fields: if `status == "remediated"`, stamp `resolved_by = request.user` and `resolved_at = timezone.now()` if not set; else clear both to `None`.

- [x] **[I4] Remediation form in exception detail suppresses validation errors on failed submission** — fixed in 0b1177bd (and cd0db465)
  - **Found by:** code-reviewer, explorer, qa-smoke-tester, security-reviewer
  - **Locations:** `templates/bi/data_quality/data_quality_exception/detail.html:126-168`, `apps/bi/views/DataQuality/DataQualityExceptions.py:199-201`
  - **Description:** The detail template omits `{{ remediation_form.errors }}`, and invalid POST redirects with a generic error message, silently swallowing validation error reasons.
  - **Fix:** Render form/field errors in `detail.html` and pass specific error descriptions in `messages.error` upon redirect.

- [x] **[I5] List templates omit FK filter dropdowns and drop active filter query parameters in pagination** — fixed in 2cbe3056 (also c67f8fcc, 424c6686)
  - **Found by:** code-reviewer, explorer, frontend-reviewer, qa-smoke-tester
  - **Locations:**
    - `templates/bi/data_quality/data_quality_profile/list.html:70-115, 190, 194`
    - `templates/bi/data_quality/data_quality_rule/list.html:78-125, 262, 266`
    - `templates/bi/data_quality/data_quality_exception/list.html:81-125, 249, 253`
  - **Description:** Profile list omits `semantic_model` dropdown and drops it in pagination. Rule list omits `warehouse_table` and `semantic_model` dropdowns and drops both in pagination. Exception list omits `rule` dropdown and drops `assigned_steward` and `rule` in pagination.
  - **Fix:** Add missing `<select>` filter dropdowns to the filter bars and preserve all active filter parameters in pagination links.

- [x] **[I6] Overview dashboard `critical_exceptions` query missing critical/fatal severity filter** — fixed in bcfda934
  - **Found by:** explorer, security-reviewer
  - **Location:** `apps/bi/views/DataQuality/QualityOverviewViews.py:40-44`
  - **Description:** Filters only `status__in=["open", "investigating"]` without `severity__in=["critical", "fatal"]`, displaying non-critical advisory items on the critical attention queue.
  - **Fix:** Add `severity__in=["critical", "fatal"]` to `critical_exceptions` query.

- [x] **[I7] Redundant 7-query sequential aggregation on Quality Overview dashboard** — fixed in 679b1bdd
  - **Found by:** performance-reviewer
  - **Location:** `apps/bi/views/DataQuality/QualityOverviewViews.py:26, 51-58`
  - **Description:** Issues 7 separate sequential SQL queries on every dashboard load instead of a single `.aggregate()`.
  - **Fix:** Combine all 7 metric averages into a single `.aggregate()` call.

- [x] **[I8] 11 sequential queries executed during Scorecard Recalculation** — fixed in b5e1bf54
  - **Found by:** performance-reviewer
  - **Location:** `apps/bi/views/DataQuality/DataQualityScorecards.py:192-209`
  - **Description:** Recalculate executes 5 separate count queries and loops 6 individual dimension queries.
  - **Fix:** Fetch all dimension averages in a single grouped query `rules_qs.values_list("dimension").annotate(avg_pass=Avg("pass_rate_pct"))` and combine rule counts using conditional aggregation `Count("id", filter=Q(...))`.

- [x] **[I9] Missing composite database indexes on `DataQualityRule` and `DataQualityException`** — fixed in 61c6521b (models: 13e65e29, ac14ef51)
  - **Found by:** performance-reviewer
  - **Locations:**
    - `apps/bi/models/DataQuality/DataQualityRules.py:121-128`
    - `apps/bi/models/DataQuality/DataQualityExceptions.py:114-121`
  - **Description:** Missing composite indexes for tenant-scoped foreign keys and sort columns:
    - `DataQualityRule`: `(tenant, warehouse_table)`, `(tenant, semantic_model)`, `(tenant, -last_run_at)`
    - `DataQualityException`: `(tenant, profile)`, `(tenant, assigned_steward)`, `(tenant, warehouse_table)`, `(tenant, semantic_model)`
  - **Fix:** Add indexes to `Meta.indexes` and generate/apply migration 0014.

- [x] **[I10] Theme.css non-existent badge modifier `badge-purple`** — fixed in 5946a9d4
  - **Found by:** code-reviewer, explorer, frontend-reviewer, qa-smoke-tester
  - **Location:** `templates/bi/data_quality/data_quality_profile/detail.html:82`
  - **Description:** Uses unstyled `badge-purple` which does not exist in `theme.css`.
  - **Fix:** Replace with `badge-info`.

---

### Minor Findings

- [x] **[M1] Missing "Back to List" navigation action button in detail view header toolbars** — fixed in 9105b196 (also d22216f1, c60d8e06, bd3162d2)
  - **Found by:** code-reviewer, explorer, frontend-reviewer, qa-smoke-tester
  - **Locations:** `profile/detail.html:34-54`, `rule/detail.html:35-55`, `exception/detail.html:45-58`, `scorecard/detail.html:45-65`
  - **Fix:** Add standard `<a href="{% url 'bi:<entity>_list' %}" class="btn btn-outline"><i data-lucide="arrow-left"></i><span>Back to <Entity></span></a>` to `.page-actions`.

- [x] **[M2] Unbounded queryset evaluation in `data_quality_scorecard_detail`** — fixed in 37870246
  - **Found by:** performance-reviewer
  - **Location:** `apps/bi/views/DataQuality/DataQualityScorecards.py:81-89`
  - **Fix:** Slice `evaluated_rules` with `[:25]`.

- [x] **[M3] `clean_parameters_json` does not validate that parsed JSON is a `dict`** — fixed in ea3dbe11
  - **Found by:** code-reviewer, explorer, security-reviewer
  - **Location:** `apps/bi/forms/DataQuality/DataQualityRuleForms.py:62-72`
  - **Fix:** Add `if not isinstance(val, dict): raise forms.ValidationError("Parameters must be a JSON object (dictionary).")`.

- [x] **[M4] Command help text in `seed_bi.py` omits Sub-module 10.5** — fixed in aed1099e
  - **Found by:** code-reviewer, explorer
  - **Location:** `apps/bi/management/commands/seed_bi.py:29`
  - **Fix:** Update command help string to include "10.5 Data Quality & Cleansing".

- [x] **[M5] Unlinked Data Mart domain in scorecard detail sidebar** — fixed in 54665711
  - **Found by:** explorer
  - **Location:** `templates/bi/data_quality/data_quality_scorecard/detail.html:196`
  - **Fix:** Wrap `{{ scorecard.data_mart.name }}` with `<a href="{% url 'bi:data_mart_detail' scorecard.data_mart.pk %}">`.

- [x] **[M6] Unreachable health status failing branch in `data_quality_scorecard_recalculate`** — fixed in edf45d6b
  - **Found by:** explorer, security-reviewer
  - **Location:** `apps/bi/views/DataQuality/DataQualityScorecards.py:233-242`
  - **Fix:** Explicitly check `if scorecard.overall_quality_score < Decimal("60.00") or scorecard.grade == "F": scorecard.health_status = "failing"`.

- [x] **[M7] Missing composite index for `meets_sla` on `DataQualityScorecard`** — fixed in 2ffbe273 (model: e66dc5a6)
  - **Found by:** performance-reviewer
  - **Location:** `apps/bi/models/DataQuality/DataQualityScorecards.py:129-135`
  - **Fix:** Add `models.Index(fields=["tenant", "meets_sla"], name="idx_bdqs_ten_msla")` to `Meta.indexes`.

- [x] **[M8] Large JSON fields loaded unnecessarily for filter dropdowns** — fixed in de7fbc1b (also fdded508, 187112e9)
  - **Found by:** performance-reviewer
  - **Locations:** `DataQualityProfiles.py:61-62`, `DataQualityRules.py:70-71`, `DataQualityExceptions.py:67-68`
  - **Fix:** Use `.only("id", "name")`.

- [x] **[M9] Multiple single count queries in list view stat cards** — fixed in 9b018e62 (also 047c5632, f8576ea5, e52503f2)
  - **Found by:** performance-reviewer
  - **Locations:** `DataQualityProfiles.py:53-55`, `DataQualityRules.py:62-64`, `DataQualityExceptions.py:58-61`, `DataQualityScorecards.py:47-49`
  - **Fix:** Combine using conditional aggregation `Count("id", filter=Q(...))`.

- [x] **[M10] Missing `title` or `aria-label` on icon-only table action buttons** — fixed in afbafa34 (also 98614618, a3528704, 359af1d2)
  - **Found by:** frontend-reviewer
  - **Locations:** `quality_overview.html:192, 253, 325, 386`, `profile/detail.html:210`, `rule/detail.html:180`, `scorecard/detail.html:215, 272`
  - **Fix:** Add `title="View ..."` and `aria-label="View ..."`.

---

## Review Passes Log

### Pass 1: code-reviewer
- Critical: `write_audit_log` parameter mismatch across all 4 views (16 call sites).
- Important: `seed_bi.py` `--flush` omissions; exception resolution reset; `DataQualityExceptionRemediationForm` tenant scoping; remediation form error rendering; pagination parameter loss; missing "Back to List" button; missing FK dropdown filters.
- Minor: `badge-purple`; `seed_bi.py` help text; `clean_parameters_json` dict check; scorecard data_mart scope branch.

### Pass 2: explorer
- Critical: Missing `data_mart` scope resolution in Scorecard Detail & Recalculation views.
- Important: Filter bar & pagination omit `semantic_model`, `warehouse_table`, `rule`; `critical_exceptions` query missing severity filter; `--flush` handler omits 10.5 models; `DataQualityExceptionRemediationForm` tenant validation; remediation error display; missing "Back to List" button.
- Minor: Unlinked data mart; `badge-purple`; `clean_parameters_json` dict validation; help string; health status branch.

### Pass 3: frontend-reviewer
- Critical: None.
- Important: `badge-purple` in profile detail; filter parameter `assigned_steward` dropped in pagination.
- Minor: Missing "Back to List" buttons in detail headers; missing `title`/`aria-label` on icon buttons.

### Pass 4: performance-reviewer
- Critical: None.
- Important: Redundant 7-query aggregation on dashboard; 11 sequential queries on Scorecard Recalculate; un-sliced queryset in Scorecard Detail; missing composite indexes on `DataQualityRule` and `DataQualityException`.
- Minor: Large JSON fields loaded for filter dropdowns; multiple single count queries in list stat cards; index on `(tenant, meets_sla)`.

### Pass 5: qa-smoke-tester
- Critical: `AttributeError: 'WarehouseTable' object has no attribute 'columns_metadata_json'` on Profile Run POST (`DataQualityProfiles.py:188`); `write_audit_log` parameter mismatch raises `TypeError` across all 16 mutation endpoints.
- Important: Incomplete resolution state reset in exception remediation; scorecard ignores `data_mart` scope; missing FK dropdown filters and pagination parameter loss in list templates.
- Minor: Detail page headers missing "Back to List"; `badge-purple`.

### Pass 6: security-reviewer
- Critical: `write_audit_log` parameter mismatch causes DoS on all 16 mutations and audit trail repudiation; `AttributeError` on profile run causes DoS.
- Important: `DataQualityExceptionRemediationForm` missing `TenantModelForm` and `reject_foreign`; missing `data_mart` scoping in scorecards; inconsistent resolution lifecycle state; suppressed remediation errors in template; seeder flush incomplete.
- Minor: `clean_parameters_json` non-dict JSON; `critical_exceptions` missing severity filter; unreachable health status branch.
