# Review Findings — Module 12.15: Process Validation & Verification

**Base Commit**: `e36ab82193a2ca5bd650bfc6dc7ddbaf738ec83c`
**Target Submodule**: 12.15 Process Validation & Verification (`quality` app)
**Reviewers Executed (Serial)**:
1. `code-reviewer`
2. `explorer`
3. `frontend-reviewer`
4. `performance-reviewer`
5. `qa-smoke-tester`
6. `security-reviewer`

---

## Summary of Findings

| Severity | Count | Summary |
|---|---|---|
| **Critical** | 4 | Seeder choice drift; Cleaning validation limit calculation flaw; None-safety filter crash on nullable FKs; Unfiltered full-table CSV exports |
| **Important** | 9 | Falsy decimal zero index logic; Missing local package `__init__.py` files; Missing cross-field validation for calculation basis; Missing `blank=True` / `required=False` on defaulted form fields; Unauthorized `stat-icon red`; Form field omission in CSV form template; Missing composite indexes `(tenant, -created_at)`; Unbuffered CSV direct iteration; Missing index on target completion date |
| **Minor** | 11 | Revalidation overdue rejected/superseded exclusion; HTML entity polish; Missing filter dropdowns in list templates; Missing hyperlink on linked deviation; Awkward null string concatenation; Accessibility aria-labels on action buttons; Accessibility progress bar ARIA attributes; Missing index on analytical method; Redundant table joins in export/dashboard/list views; Explicit UTF-8 charset on CSV responses |

---

## Critical Findings

- [x] **[C1] Multiple Invalid Choice Literals in `seed_quality.py` (`_seed_submodule_12_15`)** — fixed in 74d455d1
  - **Location**: `apps/quality/management/commands/seed_quality.py:4745-4890`
  - **Issue**: The demo data seeder `_seed_submodule_12_15` passes choice strings that do not exist on the models' `CHOICES` tuples (`weight_mass` vs `fill_volume_weight`, `highly_capable` vs `capable_excellent`, `approved` vs `completed`, `matrix_verified` vs `verified_100_percent`, `traditional_csv` vs `traditional_v_model`, `on_premises` vs `on_premise`, `sampling_in_progress` vs `in_cleaning_runs`). Causes badge lookup failures and breaks dashboard KPI filtering.
  - **Fix**: Update `_seed_submodule_12_15` in `apps/quality/management/commands/seed_quality.py` to use canonical choice keys.

- [x] **[C2] `CleaningValidation.calculate_limits()` Logic Flaw Overriding Chosen `calculation_basis`** — fixed in 56a664eb
  - **Location**: `apps/quality/models/ProcessValidation/CleaningValidations.py:196-235`
  - **Issue**: Sequential `else: limits.append(...)` appends alternate calculations when a specific basis is chosen, causing `min(limits)` to take the minimum across all formulas rather than strictly honoring the selected calculation basis (`ten_ppm_limit`, `therapeutic_dose`, `toxicological_pde`).
  - **Fix**: Restructure `calculate_limits()` using explicit `if/elif/elif/else` branches for `"ten_ppm_limit"`, `"therapeutic_dose"`, `"toxicological_pde"`, and `"most_stringent"`.

- [x] **[C3] None-Safety Filter Crashes on Nullable User Foreign Keys in Detail Templates** — fixed in 713174c1, 1acdbf3e, 3b407674
  - **Location**:
    - `templates/quality/processvalidation/validation_protocol/detail.html:191` (`final_approver`)
    - `templates/quality/processvalidation/process_capability_study/detail.html:238` (`approved_by`)
    - `templates/quality/processvalidation/cleaning_validation/detail.html:261` (`qa_approver`)
  - **Issue**: `{{ fk.get_full_name|default:fk.username }}` evaluates `fk.username` in filter argument when `fk` is `None`, raising `VariableDoesNotExist` and crashing with HTTP 500 per Lesson L10.
  - **Fix**: Wrap all three in `{% if fk %}` guards.

- [x] **[C4] Unfiltered Full-Table CSV Export DoS & Memory Inefficiency** — fixed in 99afadfb, 0f622dc3, 72875547, 013be67e
  - **Location**:
    - `apps/quality/views/ProcessValidation/ValidationProtocols.py:173`
    - `apps/quality/views/ProcessValidation/ProcessCapabilityStudies.py:152`
    - `apps/quality/views/ProcessValidation/ComputerSystemValidations.py:165`
    - `apps/quality/views/ProcessValidation/CleaningValidations.py:161`
  - **Issue**: Export views ignore `request.GET` filter parameters and stream all tenant records, causing full-table scans and potential worker memory exhaustion.
  - **Fix**: Apply the list view filtering logic (`q`, `status`, `stage`, etc.) to `qs` in each export view before streaming.

---

## Important Findings

- [x] **[I1] Falsy `Decimal("0")` Comparison in `ProcessCapabilityStudy.calculate_indices()`** — fixed in 060b555f
  - **Location**: `apps/quality/models/ProcessValidation/ProcessCapabilityStudies.py:182`
  - **Issue**: `target_index = self.cpk_index or self.ppk_index` treats `Decimal("0.000")` as falsy, falling back to `ppk_index` when `cpk_index` is zero.
  - **Fix**: Use `self.cpk_index if self.cpk_index is not None else self.ppk_index`.

- [x] **[I2] Missing Package `__init__.py` Files in `models/ProcessValidation`, `forms/ProcessValidation`, `views/ProcessValidation`** — fixed in 70bbf859, acd9e02d, b1fa564e
  - **Location**:
    - `apps/quality/models/ProcessValidation/__init__.py`
    - `apps/quality/forms/ProcessValidation/__init__.py`
    - `apps/quality/views/ProcessValidation/__init__.py`
  - **Issue**: Submodule subdirectories lack local package `__init__.py` re-export files required by NavERP architectural standard.
  - **Fix**: Create `__init__.py` in each directory and re-export classes/functions with `__all__`.

- [x] **[I3] Missing Cross-Field Consistency Validation in `CleaningValidationForm.clean()`** — fixed in 9c8b43db
  - **Location**: `apps/quality/forms/ProcessValidation/CleaningValidations.py:91-104`
  - **Issue**: If a user selects `calculation_basis="therapeutic_dose"` or `"toxicological_pde"` and leaves dose/PDE fields empty, form passes validation but limits silently cannot be computed.
  - **Fix**: Enforce required fields for the chosen `calculation_basis` in `CleaningValidationForm.clean()`.

- [ ] **[I4] Form Validation Failure on Model Fields with `default` but Lacking `blank=True` in Forms**
  - **Location**:
    - `apps/quality/forms/ProcessValidation/ValidationProtocols.py:14-44` (`deviations_encountered`, `test_runs_completed`)
    - `apps/quality/forms/ProcessValidation/ComputerSystemValidations.py:13-43` (`urs_requirements_count`, `test_scripts_count`, `deviations_found_count`, `periodic_review_frequency_months`)
  - **Issue**: Metric fields with defaults in models are required in ModelForms because they lack `blank=True`, causing form validation errors when omitted on creation.
  - **Fix**: In form `__init__`, set `required = False` on these defaulted fields.

- [ ] **[I5] Unauthorized Stat Icon Modifier Variant `stat-icon red` Used in Stat Cards**
  - **Location**:
    - `templates/quality/processvalidation/validation_protocol/list.html:56`
    - `templates/quality/processvalidation/validation_protocol/detail.html:48, 70`
    - `templates/quality/processvalidation/process_capability_study/list.html:56`
    - `templates/quality/processvalidation/process_capability_study/detail.html:37, 75`
    - `templates/quality/processvalidation/computer_system_validation/list.html:56`
    - `templates/quality/processvalidation/computer_system_validation/detail.html:48`
    - `templates/quality/processvalidation/cleaning_validation/list.html:56`
    - `templates/quality/processvalidation/cleaning_validation/detail.html:73`
    - `templates/quality/processvalidation/process_validation_dashboard.html:63`
  - **Issue**: Design system only allows `stat-icon blue/green/orange/purple/slate`. `red` is unauthorized.
  - **Fix**: Replace `stat-icon red` with `stat-icon orange` across all 11 locations.

- [ ] **[I6] Form Field Omission in `computer_system_validation/form.html`**
  - **Location**: `templates/quality/processvalidation/computer_system_validation/form.html:133-154`
  - **Issue**: `last_review_date` is defined in `ComputerSystemValidationForm.Meta.fields` but omitted from the template.
  - **Fix**: Add the `last_review_date` form-group block in Section 3 of `form.html`.

- [ ] **[I7] Missing Composite Indexes on `(tenant, -created_at)` Across All 4 Models**
  - **Location**:
    - `apps/quality/models/ProcessValidation/ValidationProtocols.py:154-159`
    - `apps/quality/models/ProcessValidation/ProcessCapabilityStudies.py:130-134`
    - `apps/quality/models/ProcessValidation/ComputerSystemValidations.py:145-149`
    - `apps/quality/models/ProcessValidation/CleaningValidations.py:168-171`
  - **Issue**: Missing composite index on `("tenant", "-created_at")`, causing database filesorts on all paginated views.
  - **Fix**: Add composite indexes with names `<= 30` characters (`idx_qval_ten_created`, `idx_qcpk_ten_created`, `idx_qcsv_ten_created`, `idx_qcln_ten_created`).

- [ ] **[I8] Unbuffered Direct Queryset Iteration Without `.iterator(chunk_size=1000)` in CSV Exports**
  - **Location**: All 4 export views in `apps/quality/views/ProcessValidation/`
  - **Issue**: Direct queryset evaluation populates Django's internal cache with all rows in memory.
  - **Fix**: Iterate using `qs.iterator(chunk_size=1000)`.

- [ ] **[I9] Missing Index on `ValidationProtocol.target_completion_date`**
  - **Location**: `apps/quality/models/ProcessValidation/ValidationProtocols.py:84, 154-159`
  - **Issue**: Overdue range filter queries scan unindexed dates.
  - **Fix**: Add composite index `idx_qval_ten_target_due` on `("tenant", "target_completion_date")`.

---

## Minor Findings

- [ ] **[M1] `is_revalidation_overdue` and Dashboard Overdue Filter Over-reporting for Rejected/Superseded Protocols**
  - **Location**: `apps/quality/models/ProcessValidation/ValidationProtocols.py:174-177`, `apps/quality/views/ProcessValidation/ProcessValidationDashboard.py:23`
  - **Fix**: Exclude `"rejected"` and `"superseded"` protocols.

- [ ] **[M2] HTML Entity Usage in Template Stat Tiles**
  - **Location**: `templates/quality/processvalidation/process_capability_study/list.html:43`, `templates/quality/processvalidation/process_validation_dashboard.html:49`
  - **Fix**: Replace `&ge;` with `>=`.

- [ ] **[M3] Missing `revalidation_trigger` Dropdown in `validation_protocol/list.html` Filter Bar**
  - **Location**: `templates/quality/processvalidation/validation_protocol/list.html:68-120`
  - **Fix**: Add `revalidation_trigger` dropdown to filter grid and clear-filter condition.

- [ ] **[M4] Missing `validation_approach` Dropdown in `computer_system_validation/list.html` Filter Bar**
  - **Location**: `templates/quality/processvalidation/computer_system_validation/list.html:68-110`
  - **Fix**: Add `approach` select element to filter grid and clear-filter condition.

- [ ] **[M5] Missing Hyperlink on `linked_deviation` in `cleaning_validation/detail.html`**
  - **Location**: `templates/quality/processvalidation/cleaning_validation/detail.html:267-270`
  - **Fix**: Link to `quality:process_deviation_detail` when present.

- [ ] **[M6] Awkward Null Display Concatenating "None mm"**
  - **Location**: `templates/quality/processvalidation/process_capability_study/detail.html:102`
  - **Fix**: Guard with `{% if capability_study.target_nominal %}`.

- [ ] **[M7] Accessibility: Action Icon Buttons Missing `aria-label`**
  - **Location**: Table action columns in all 4 list templates
  - **Fix**: Add explicit `aria-label` to `.btn-icon` elements.

- [ ] **[M8] Accessibility: Progress Bar Missing ARIA Attributes**
  - **Location**: `templates/quality/processvalidation/validation_protocol/list.html:166-168`
  - **Fix**: Add `role="progressbar"` and ARIA value attributes.

- [ ] **[M9] Missing Database Index on `CleaningValidation.analytical_method`**
  - **Location**: `apps/quality/models/ProcessValidation/CleaningValidations.py:61, 109, 168-171`
  - **Fix**: Add composite index `idx_qcln_ten_method` on `("tenant", "analytical_method")`.

- [ ] **[M10] Redundant `select_related` Table Joins in CSV Exports, Dashboard Recent Queries, and List Views**
  - **Location**: Export, dashboard, and list views in `apps/quality/views/ProcessValidation/`
  - **Fix**: Prune foreign keys not referenced in outputs or templates.

- [ ] **[M11] Missing Explicit UTF-8 Charset in CSV Export Content-Type**
  - **Location**: All 4 export views in `apps/quality/views/ProcessValidation/`
  - **Fix**: Specify `content_type="text/csv; charset=utf-8"`.
