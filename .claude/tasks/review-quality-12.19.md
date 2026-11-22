# Consolidated Review Findings: Module 12.19 Laboratory Information Management (LIMS)

**Base Commit**: `0a93a42d6c28678b9dd1e5c18eac3ca09e22c3eb`
**Head Commit**: `HEAD`
**Target App**: `apps/quality/` (Sub-module 12.19: LIMS)

---

## Review Passes Summary
1. `code-reviewer` — Completed (identified L10 nullable user FK template crashes, view status guards, worksheet OOS override bug, missing package `__init__.py` files)
2. `explorer` — Completed (verified 25 routes, navigation wiring, pre-build context contracts, identified sample-worksheet cross-check in OOS form)
3. `frontend-reviewer` — Completed (identified L33 `stat-icon red` and `badge-purple`, confirmed zero comment leaks, pagination guards, and CSRF protection)
4. `performance-reviewer` — Completed (identified N+1 query loops in detail views, recommended `select_related` and dashboard single aggregate)
5. `qa-smoke-tester` — Completed (62 runtime URL checks passed 100%, 15/15 cross-tenant IDOR attacks blocked with 404, zero comment leaks)
6. `security-reviewer` — Completed (verified multi-tenant isolation and CSV injection defense, identified `@tenant_admin_required` for GxP OOS closure, cascade deletion risks)

---

## Consolidated Actionable Findings (For Phase 5 Code-Fixer)

### Critical Findings

- [ ] **[C1] Template L10 Crash on Nullable User ForeignKeys in Filter Arguments**
  - **Locations**:
    - `templates/quality/lims_management/oos_investigation/detail.html:109,115` (`investigation.investigation_lead`, `investigation.qa_approver`)
    - `templates/quality/lims_management/lab_test_worksheet/detail.html:95,101` (`worksheet.assigned_analyst`, `worksheet.reviewer`)
    - `templates/quality/lims_management/lab_sample/detail.html:133,143,153,233` (`sample.sampled_by`, `sample.received_by`, `sample.current_custodian`, `w.assigned_analyst`)
    - `templates/quality/lims_management/lab_specification/detail.html:213` (`w.assigned_analyst`)
    - `templates/quality/lims_management/lab_test_worksheet/list.html:123` (`w.assigned_analyst`)
  - **Issue**: `{{ obj.user_fk.get_full_name|default:obj.user_fk.username }}` evaluates the second lookup in the filter argument when `user_fk` is `None`, raising `VariableDoesNotExist` and 500ing in production (Lesson L10).
  - **Fix**: Wrap with explicit `{% if obj.user_fk %}{{ obj.user_fk.get_full_name|default:obj.user_fk.username }}{% else %}...{% endif %}`.

- [ ] **[C2] LabTestWorksheetForm Qualitative OOS Override Bug**
  - **Location**: `apps/quality/forms/LimsManagement/LabTestWorksheets.py:99`
  - **Issue**: Form `clean()` unconditionally executes `cleaned_data["is_within_specification"] = within`, which overwrites a user's manual OOS checkbox (`is_within_specification = False`) whenever numeric limits pass, certifying samples with qualitative defects (discoloration, contamination, particulate matter) as conforming.
  - **Fix**: Only set `is_within_specification` to `False` when numerical limits are breached; do not force `True` when numerical bounds pass:
    ```python
    if not within:
        cleaned_data["is_within_specification"] = False
        if cleaned_data.get("disposition") == "conforms":
            cleaned_data["disposition"] = "oos_flagged"
    ```

---

### Important Findings

- [ ] **[I1] Missing `@tenant_admin_required` Authorization Gate on GxP OOS Closure**
  - **Locations**:
    - `apps/quality/views/LimsManagement/OosInvestigations.py:170`
    - `templates/quality/lims_management/oos_investigation/detail.html:33`
    - `templates/quality/lims_management/oos_investigation/list.html:153`
  - **Issue**: `oos_investigation_close` allows any authenticated user to close an FDA/GxP regulatory OOS investigation and stamps them as `qa_approver`.
  - **Fix**: Add `@tenant_admin_required` decorator to `oos_investigation_close` and wrap close buttons in templates with `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

- [ ] **[I2] Missing View-Level Status Guards on State Transitions**
  - **Locations**:
    - `apps/quality/views/LimsManagement/OosInvestigations.py:171`
    - `apps/quality/views/LimsManagement/LabTestWorksheets.py:162`
  - **Issue**: `oos_investigation_close` allows re-closing an already closed investigation; `lab_test_worksheet_complete` allows completing an already approved, rejected, or cancelled worksheet.
  - **Fix**: Add view-level status checks:
    - In `oos_investigation_close`: `if obj.status == "closed": messages.error(...); return redirect(...)`
    - In `lab_test_worksheet_complete`: `if obj.status not in ["assigned", "in_progress"]: messages.error(...); return redirect(...)`

- [ ] **[I3] Missing Cascade Deletion Guards for GxP Audit Records**
  - **Locations**:
    - `apps/quality/views/LimsManagement/LabSamples.py:143`
    - `apps/quality/views/LimsManagement/LabTestWorksheets.py:146`
  - **Issue**: Deleting an unapproved `LabSample` cascade-deletes all child worksheets and OOS investigations; deleting a `LabTestWorksheet` cascade-deletes child OOS investigations under `CASCADE`.
  - **Fix**:
    - In `lab_sample_delete`: verify `if obj.test_worksheets.exists() or obj.oos_investigations.exists(): messages.error(...); return redirect(...)`
    - In `lab_test_worksheet_delete`: verify `if obj.oos_investigations.exists(): messages.error(...); return redirect(...)`

- [ ] **[I4] Cross-Record Inconsistency Validation in OosInvestigationForm**
  - **Location**: `apps/quality/forms/LimsManagement/OosInvestigations.py:93-105`
  - **Issue**: `OosInvestigationForm` validates tenant scoping but fails to check that `sample == test_worksheet.sample`, allowing a worksheet from Sample A to be linked with Sample B.
  - **Fix**: In `OosInvestigationForm.clean()`, add:
    ```python
    ws = cleaned_data.get("test_worksheet")
    smp = cleaned_data.get("sample")
    if ws and smp and ws.sample_id != smp.id:
        self.add_error("sample", "Selected sample must match the sample linked to the test worksheet.")
    ```

- [ ] **[I5] N+1 Query Loops on Related Worksheets in Detail Views**
  - **Locations**:
    - `apps/quality/views/LimsManagement/LabSamples.py:80`
    - `apps/quality/views/LimsManagement/LabSpecifications.py:72-76`
  - **Issue**: Iterating over `test_worksheets` in `lab_sample_detail` and `lab_specification_detail` triggers N+1 queries when accessing related `specification`, `sample`, and `assigned_analyst`.
  - **Fix**:
    - In `lab_sample_detail`: `sample.test_worksheets.select_related("specification", "assigned_analyst").all()`
    - In `lab_specification_detail`: `specification.test_worksheets.select_related("sample", "assigned_analyst").all()[:15]`

- [ ] **[I6] Missing Package `__init__.py` Files**
  - **Locations**:
    - `apps/quality/models/LimsManagement/__init__.py`
    - `apps/quality/forms/LimsManagement/__init__.py`
    - `apps/quality/views/LimsManagement/__init__.py`
  - **Issue**: Sub-module package folders lack `__init__.py`, violating the Backend Package Structure standard.
  - **Fix**: Create standard re-exporting `__init__.py` files for `models/LimsManagement/`, `forms/LimsManagement/`, and `views/LimsManagement/`.

- [ ] **[I7] Unsupported Theme CSS Badge Class `badge-purple`**
  - **Locations**:
    - `apps/quality/models/LimsManagement/LabSpecifications.py:51` (`"chromatographic"`)
    - `apps/quality/models/LimsManagement/OosInvestigations.py:49` (`"root_cause_found"`)
  - **Issue**: `theme.css` has no `.badge-purple` definition; only `green`, `red`, `amber`, `info`, `muted`, `slate` exist per L33.
  - **Fix**: Change `"badge-purple"` to `"badge-info"`.

- [ ] **[I8] Disallowed `stat-icon red` Class in LIMS Dashboard**
  - **Location**: `templates/quality/lims_management/lims_dashboard.html:66`
  - **Issue**: `stat-icon` only accepts `blue`, `green`, `orange`, `purple`, `slate` (Lesson L33). `red` is invalid and renders unstyled.
  - **Fix**: Change `<div class="stat-icon red ...">` to `<div class="stat-icon orange ...">`.

---

### Minor Findings

- [ ] **[M1] Missing Linked Work Order Display in LabSample Detail**
  - **Location**: `templates/quality/lims_management/lab_sample/detail.html:69`
  - **Issue**: `sample.work_order` is fetched via `select_related` and present in form, but omitted from the metadata grid.
  - **Fix**: Add a detail-item rendering `sample.work_order` linking to `scm:work_order_detail` if present.

- [ ] **[M2] Datetime-Local Widget Format in LabSampleForm**
  - **Location**: `apps/quality/forms/LimsManagement/LabSamples.py:51`
  - **Issue**: `sampled_at` and `received_at` lack `format="%Y-%m-%dT%H:%M"`, causing HTML5 `datetime-local` inputs to render empty on edit.
  - **Fix**: Add `format="%Y-%m-%dT%H:%M"` to the `DateTimeInput` widgets.

- [ ] **[M3] Secondary Foreign Key Query in `oos_investigation_create`**
  - **Location**: `apps/quality/views/LimsManagement/OosInvestigations.py:97-99`
  - **Issue**: Accessing `ws.sample.number` hits the database because `ws` was fetched without `select_related("sample")`.
  - **Fix**: Add `.select_related("sample")` to `LabTestWorksheet.objects.get(...)`.

- [ ] **[M4] Dual `count()` Roundtrips in `lims_dashboard`**
  - **Location**: `apps/quality/views/LimsManagement/LimsDashboard.py:28-29`
  - **Issue**: Two roundtrips to count total and in-testing samples.
  - **Fix**: Combine into single `aggregate(total=Count("id"), in_testing=Count("id", filter=Q(status="in_testing")))`.

- [ ] **[M5] Add Composite Index on `LabSample.storage_condition`**
  - **Location**: `apps/quality/models/LimsManagement/LabSamples.py:159-165`
  - **Issue**: `storage_condition` filter in list view lacks composite index with `tenant`.
  - **Fix**: Add `models.Index(fields=["tenant", "storage_condition"], name="idx_qsmp_ten_storage")`.

- [ ] **[M6] Missing Accessibility Attributes on Related Table Links**
  - **Locations**:
    - `templates/quality/lims_management/lab_sample/detail.html:252,298`
    - `templates/quality/lims_management/lab_specification/detail.html:228`
    - `templates/quality/lims_management/lab_test_worksheet/detail.html:286`
  - **Issue**: Icon-only action links lack `title` and `aria-label`.
  - **Fix**: Add `title="View Detail" aria-label="View Detail"`.

- [ ] **[M7] Readonly Audit Protection for Chain of Custody in LabSampleForm**
  - **Location**: `apps/quality/forms/LimsManagement/LabSamples.py:126`
  - **Issue**: `chain_of_custody_log` should not be editable as an arbitrary plaintext field by any user.
  - **Fix**: Set widget attribute `attrs={"readonly": "readonly", "class": "form-textarea bg-slate-50"}`.

- [ ] **[M8] Add MinValueValidator for Non-Negative Analytical Quantities**
  - **Locations**:
    - `apps/quality/models/LimsManagement/LabSamples.py:116` (`quantity_collected`)
    - `apps/quality/models/LimsManagement/LabTestWorksheets.py:115` (`relative_standard_deviation`)
  - **Issue**: Missing validator allows negative sample quantities or % RSD.
  - **Fix**: Add `validators=[MinValueValidator(Decimal("0"))]`.
