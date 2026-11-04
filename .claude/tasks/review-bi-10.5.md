# Review Findings — Sub-module 10.5: Data Quality & Cleansing (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.5 Data Quality & Cleansing
- **Module:** 10 Business Intelligence
- **Target app:** `apps/bi`
- **Review date:** 2026-11-04
- **Base SHA:** `37d37b12e750ca499865e43f79037a762e6961cd`
- **Status:** In Progress (Running 6 Review Passes: code-reviewer, explorer, frontend-reviewer, performance-reviewer, qa-smoke-tester, security-reviewer)

---

## Review Passes Log

### Pass 1: code-reviewer

#### Critical
1. `apps/bi/views/DataQuality/DataQualityProfiles.py:111, 139, 167, 225` — `write_audit_log` parameter mismatch: called with 6 arguments `(request.tenant, request.user, "VERB", "DataQualityProfile", pk, message)` instead of `(request.user, profile, action, tenant=request.tenant)`. Causes `TypeError` / 500 on create, edit, delete, and profile run.
2. `apps/bi/views/DataQuality/DataQualityRules.py:129, 157, 185, 245` — `write_audit_log` parameter mismatch: called with 6 arguments instead of `(request.user, rule, action, tenant=request.tenant)`. Causes 500 on create, edit, delete, and evaluate.
3. `apps/bi/views/DataQuality/DataQualityExceptions.py:111, 139, 166, 190` — `write_audit_log` parameter mismatch: called with 6 arguments instead of `(request.user, exc, action, tenant=request.tenant)`. Causes 500 on create, edit, delete, and remediate.
4. `apps/bi/views/DataQuality/DataQualityScorecards.py:107, 135, 163, 253` — `write_audit_log` parameter mismatch: called with 6 arguments instead of `(request.user, scorecard, action, tenant=request.tenant)`. Causes 500 on create, edit, delete, and recalculate.

#### Important
1. `apps/bi/management/commands/seed_bi.py:47-62` — The `--flush` block omits `DataQualityScorecard`, `DataQualityException`, `DataQualityRule`, and `DataQualityProfile` in reverse dependency order, leaving orphaned data on flush.
2. `apps/bi/views/DataQuality/DataQualityExceptions.py:185-188` — `data_quality_exception_remediate` does not clear `resolved_by` and `resolved_at` when status transitions back to non-remediated (`open`, `investigating`).
3. `apps/bi/forms/DataQuality/DataQualityExceptionForms.py:75` — `DataQualityExceptionRemediationForm` inherits from `forms.ModelForm` instead of `TenantModelForm` and does not reject foreign tenant for `assigned_steward`.
4. `templates/bi/data_quality/data_quality_exception/detail.html:126-168` — Remediation form does not render form error blocks (`remediation_form.errors`), and invalid POST silently redirects instead of re-rendering with errors.
5. `templates/bi/data_quality/data_quality_exception/list.html:249, 253` — Pagination links drop `assigned_steward` and `rule` GET query parameters.
6. `templates/bi/data_quality/data_quality_profile/detail.html`, `rule/detail.html`, `exception/detail.html`, `scorecard/detail.html` — Missing "Back to List" button in page-actions toolbar.
7. `templates/bi/data_quality/data_quality_profile/list.html`, `rule/list.html`, `exception/list.html` — List templates omit dropdown filters for foreign key relationships provided by view context (`semantic_model`, `warehouse_table`, `rule`).

#### Minor
1. `templates/bi/data_quality/data_quality_profile/detail.html:82` — Uses unstyled `badge-purple`; change to `badge-info`.
2. `apps/bi/management/commands/seed_bi.py:29` — Command help text omits sub-module 10.5.
3. `apps/bi/forms/DataQuality/DataQualityRuleForms.py:62-72` — `clean_parameters_json` does not validate that parsed JSON is a `dict`.
4. `apps/bi/views/DataQuality/DataQualityScorecards.py:87, 191` — Scorecard rule/exception scoping only explicitly branches for warehouse_table and semantic_model; add data_mart branch.

---

### Pass 2: explorer

#### Critical
1. `apps/bi/views/DataQuality/DataQualityScorecards.py:80-92, 185-195` — Missing `data_mart` scope resolution in Scorecard Detail & Recalculation views: branches only for warehouse_table and semantic_model, falling back to tenant-wide for data_mart scoped scorecards instead of filtering `rules_qs.filter(warehouse_table__data_mart=scorecard.data_mart)`.

#### Important
1. `templates/bi/data_quality/data_quality_profile/list.html:70-115, 190, 194` — Filter bar & pagination omit `semantic_model` (dropdown missing, pagination drops param).
2. `templates/bi/data_quality/data_quality_rule/list.html:78-125, 262, 266` — Filter bar & pagination omit `warehouse_table` and `semantic_model`.
3. `templates/bi/data_quality/data_quality_exception/list.html:81-125, 249, 253` — Filter bar & pagination omit `rule` dropdown and pagination drops `assigned_steward` and `rule`.
4. `apps/bi/views/DataQuality/QualityOverviewViews.py:44` — `critical_exceptions` does not filter for `severity__in=["critical", "fatal"]`.
5. `apps/bi/management/commands/seed_bi.py:45-63` — `--flush` handler omits Sub-module 10.5 models (`DataQualityScorecard`, `DataQualityException`, `DataQualityRule`, `DataQualityProfile`).
6. `apps/bi/forms/DataQuality/DataQualityExceptionForms.py:75` — `DataQualityExceptionRemediationForm` inherits from `forms.ModelForm` instead of `TenantModelForm`, lacking tenant scoping and `reject_foreign`.
7. `templates/bi/data_quality/data_quality_exception/detail.html:125-168` — Remediation form does not display form errors, and invalid POST redirects instead of re-rendering with errors.
8. `templates/bi/data_quality/data_quality_profile/detail.html`, `rule/detail.html`, `exception/detail.html`, `scorecard/detail.html` — Missing "Back to List" navigation action in header toolbar.

#### Minor
1. `templates/bi/data_quality/data_quality_scorecard/detail.html:196` — Unlinked Data Mart domain in detail sidebar; should link to `bi:data_mart_detail`.
2. `templates/bi/data_quality/data_quality_profile/detail.html:82` — Use of non-standard `badge-purple`.
3. `apps/bi/forms/DataQuality/DataQualityRuleForms.py:62-72` — `clean_parameters_json` does not enforce dict structure.
4. `apps/bi/management/commands/seed_bi.py:29` — Command help string omits 10.5.
5. `apps/bi/views/DataQuality/DataQualityScorecards.py:233-242` — Health status assignment logic unreachable failing branch.



