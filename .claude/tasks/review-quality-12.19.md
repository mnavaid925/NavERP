# Review Findings: Module 12.19 Laboratory Information Management (LIMS)

**Base Commit**: `0a93a42d6c28678b9dd1e5c18eac3ca09e22c3eb`
**Head Commit**: `HEAD`
**Target App**: `apps/quality/` (Sub-module 12.19: LIMS)

---

## Review Passes
1. `code-reviewer`
2. `explorer`
3. `frontend-reviewer`
4. `performance-reviewer`
5. `qa-smoke-tester`
6. `security-reviewer`

---

### Pass 1: `code-reviewer` Findings

#### Critical
- `templates/quality/lims_management/oos_investigation/detail.html:115` — `{{ investigation.qa_approver.get_full_name|default:investigation.qa_approver.username|default:"Pending QA Closure" }}` evaluates filter argument when `qa_approver` is None, raising `VariableDoesNotExist` and 500ing on every open or in-progress OOS event (Lesson L10). Fix: wrap in `{% if investigation.qa_approver %}{{ investigation.qa_approver.get_full_name|default:investigation.qa_approver.username }}{% else %}Pending QA Closure{% endif %}` (and apply same guard to `investigation.investigation_lead` at line 109).
- `templates/quality/lims_management/lab_test_worksheet/detail.html:101` — `{{ worksheet.reviewer.get_full_name|default:worksheet.reviewer.username|default:"Pending Review" }}` crashes with 500 on all unreviewed worksheets where `reviewer` is None (Lesson L10). Fix: wrap in `{% if worksheet.reviewer %}{{ worksheet.reviewer.get_full_name|default:worksheet.reviewer.username }}{% else %}Pending Review{% endif %}` (and apply same guard to `worksheet.assigned_analyst` at line 95).
- `templates/quality/lims_management/lab_sample/detail.html:133` — `sample.sampled_by`, `sample.received_by` (line 143), `sample.current_custodian` (line 153), and child worksheet `w.assigned_analyst` (line 233) all use `|default:fk.username` in filter arguments without `{% if fk %}` guards, crashing with 500 when any optional FK is None (Lesson L10). Fix: guard each with `{% if fk %}{{ fk.get_full_name|default:fk.username }}{% else %}—{% endif %}`.

#### Important
- `templates/quality/lims_management/lab_specification/detail.html:213` — Child analytical worksheet table uses `{{ w.assigned_analyst.get_full_name|default:w.assigned_analyst.username|default:"Unassigned" }}` without `{% if w.assigned_analyst %}` guard, causing 500 when displaying specifications with unassigned worksheets (Lesson L10). Fix: wrap in `{% if w.assigned_analyst %}{{ w.assigned_analyst.get_full_name|default:w.assigned_analyst.username }}{% else %}Unassigned{% endif %}`.
- `templates/quality/lims_management/lab_test_worksheet/list.html:123` — Worksheet list table uses `{{ w.assigned_analyst.get_full_name|default:w.assigned_analyst.username|default:"Unassigned" }}` without `{% if w.assigned_analyst %}`, causing 500 on the list page if any worksheet has `assigned_analyst=None` (Lesson L10). Fix: wrap in `{% if w.assigned_analyst %}{{ w.assigned_analyst.get_full_name|default:w.assigned_analyst.username }}{% else %}Unassigned{% endif %}`.
- `apps/quality/views/LimsManagement/LabTestWorksheets.py:161` — `lab_test_worksheet_complete` lacks view-level status guard, allowing direct POST to reset already-approved, rejected, or cancelled worksheets back to `review_pending` and overwrite `completion_timestamp`. Fix: enforce `if obj.status not in ["assigned", "in_progress"]: messages.error(request, ...); return redirect(...)`.
- `apps/quality/views/LimsManagement/OosInvestigations.py:170` — `oos_investigation_close` lacks view-level status guard, allowing direct POST to overwrite `closed_at` and `qa_approver` on already-closed investigations. Fix: enforce `if obj.status == "closed": messages.error(request, ...); return redirect(...)`.
- `apps/quality/forms/LimsManagement/LabTestWorksheets.py:99` — Form `clean()` unconditionally sets `cleaned_data["is_within_specification"] = within`, which overwrites user's explicit manual OOS flag (`is_within_specification = False`) whenever numerical bounds pass, ignoring qualitative defects. Fix: only set `if not within: cleaned_data["is_within_specification"] = False`.
- `apps/quality/models/LimsManagement/__init__.py:1` — `apps/quality/models/LimsManagement/`, `apps/quality/forms/LimsManagement/`, and `apps/quality/views/LimsManagement/` are missing package `__init__.py` files, violating Backend Package Structure contract (CLAUDE.md). Fix: create standard package `__init__.py` files for each directory.

#### Minor
- `apps/quality/models/LimsManagement/LabSpecifications.py:51` — `TEST_CATEGORY_CSS["chromatographic"] = "badge-purple"` and `apps/quality/models/LimsManagement/OosInvestigations.py:49` (`STATUS_CSS["root_cause_found"] = "badge-purple"`) use `badge-purple`, not defined in `static/css/theme.css` (only `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate` exist per L33). Fix: replace `"badge-purple"` with `"badge-info"`.
- `apps/quality/views/LimsManagement/LabSamples.py:143` — `lab_sample_delete` only guards against status `approved`, `in_testing`, `testing_completed`, but does not guard against deleting a registered/received sample that has attached `test_worksheets` or `oos_investigations`, which cascade-deletes testing history under `on_delete=CASCADE`. Fix: check `if obj.test_worksheets.exists() or obj.oos_investigations.exists(): messages.error(...)`.
- `templates/quality/lims_management/lab_sample/detail.html:69` — `sample.work_order` is fetched in `select_related` by `lab_sample_detail` view and present in `LabSampleForm`, but omitted from the metadata display grid `<dl class="detail-grid">`. Fix: add a `detail-item` displaying `sample.work_order`.
- `apps/quality/forms/LimsManagement/LabSamples.py:51` — `"sampled_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"})` lacks `format="%Y-%m-%dT%H:%M"`, causing HTML5 `datetime-local` inputs to render empty when editing an existing sample. Fix: add `format="%Y-%m-%dT%H:%M"`.
