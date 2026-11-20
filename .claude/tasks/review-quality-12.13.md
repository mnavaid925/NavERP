# Consolidated Review Findings: Sub-module 12.13 Customer Complaint Handling

**BASE:** `bc9fc6d0e8137f54214ffd3af0019c12e69c6c72`  
**Scope:** `apps/quality/` (CustomerComplaints models, forms, views, urls, admin, seeder, migration) & `templates/quality/customercomplaints/`  
**Reviewers:** `code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`

---

## Verdict
**CONDITIONAL APPROVAL (Fixes Required Before Phase 6 Tests)**  
The sub-module demonstrates high architectural rigor: 100% tenant isolation, full `@tenant_admin_required` and `@require_POST` authorization, zero raw SQL, comprehensive CSRF protection, clean idempotent seeding, and 55/55 runtime test assertions passed. To achieve enterprise QMS production compliance, the critical mass-assignment status bypass, statutory record protection, pagination parameter corruption, cycle-time formula, and theme badge classes must be resolved in Phase 5.

---

## Critical

- [ ] **C1: Pagination query parameter corruption traps navigation across all list views**
  - **Files:**
    - `templates/quality/customercomplaints/customer_complaint/list.html:266-280`
    - `templates/quality/customercomplaints/complaint_investigation/list.html:232-246`
    - `templates/quality/customercomplaints/regulatory_report/list.html:230-244`
    - `templates/quality/customercomplaints/field_action/list.html:232-246`
  - **Problem:**
    Pagination links construct `href="?page={{ page_obj.next_page_number }}{% if request.GET.urlencode %}&{{ request.GET.urlencode }}{% endif %}"`. Moving past page 1 results in stacked parameters (`?page=2&page=1&status=open`). In Django, `request.GET.get('page')` retrieves the last parameter (`'1'`), trapping the user on the current page.
  - **Fix:**
    Pass clean filter query strings without duplicating `page` (e.g. `href="?page={{ page_obj.next_page_number }}{% if filter_querystring %}&{{ filter_querystring }}{% endif %}"` or template parameter cleaning).

- [ ] **C2: Mass assignment and workflow status bypass across all 4 ModelForms**
  - **Files:**
    - `apps/quality/forms/CustomerComplaints/CustomerComplaints.py:11-20`
    - `apps/quality/forms/CustomerComplaints/ComplaintInvestigations.py:12-19`
    - `apps/quality/forms/CustomerComplaints/RegulatoryReports.py:12-18`
    - `apps/quality/forms/CustomerComplaints/FieldActions.py:12-17`
    - Templates: `templates/quality/customercomplaints/{customer_complaint,complaint_investigation,regulatory_report,field_action}/form.html`
  - **Problem:**
    Forms do not exclude lifecycle-controlled statuses (`status`, `submission_status`), completion timestamps (`termination_date`, `submission_date`, `customer_letter_date`), or closure stamps. Users can set `status="closed"` or `status="approved"` directly upon create/edit, bypassing triage review, statutory vigilance screening, and QA approval.
  - **Fix:**
    Add `status`, `submission_status`, `termination_date`, `submission_date`, `customer_letter_date`, `qa_approved_by`, `qa_approved_date` to `Meta.exclude` in all 4 forms. Remove `status` dropdowns from the general create/edit templates (state transitions must happen through dedicated action views).

- [ ] **C3: Statutory regulatory reports and investigations cascade deleted without protection**
  - **Files:**
    - `apps/quality/models/CustomerComplaints/RegulatoryReports.py:85-90`
    - `apps/quality/models/CustomerComplaints/ComplaintInvestigations.py:55-60`
    - `apps/quality/views/CustomerComplaints/CustomerComplaints.py:182-189`
    - `apps/quality/views/CustomerComplaints/RegulatoryReports.py:180-189`
  - **Problem:**
    `complaint = models.ForeignKey(..., on_delete=models.CASCADE)` allows deleting a complaint to permanently destroy statutory regulatory reports already filed with FDA or EU authorities, violating 21 CFR 803 and EU MDR vigilance retention rules. Furthermore, `regulatory_report_delete` permits deleting submitted reports.
  - **Fix:**
    Change `complaint` FK `on_delete` to `models.PROTECT` on `RegulatoryReport` and `ComplaintInvestigation`. In `customer_complaint_delete`, verify that no filed regulatory reports (`submission_status != 'draft'`) or approved investigations exist. In `regulatory_report_delete`, block deletion if `submission_status in ['submitted', 'acknowledged']`.

- [ ] **C4: Mathematical skew and in-memory slicing mismatch in average cycle time calculation**
  - **File:** `apps/quality/views/CustomerComplaints/ComplaintTrendingDashboard.py:28-34`
  - **Problem:**
    `total_days = sum(c.days_open for c in closed_with_dates[:200])` sums only up to 200 items, but divides by `total_closed`. If `total_closed > 200`, the metric is deflated. In addition, loading 200 full Django model instances into Python memory is wasteful.
  - **Fix:**
    Use `values_list("closed_at", "date_received")` and divide by `len(closed_dates)`:
    ```python
    closed_dates = list(base_complaints.filter(status="closed", closed_at__isnull=False, date_received__isnull=False).values_list("closed_at", "date_received"))
    avg_cycle_days = round(sum((ca.date() - dr).days for ca, dr in closed_dates) / len(closed_dates), 1) if closed_dates else 0.0
    ```

---

## Important

- [ ] **I1: Widespread use of invalid/unsupported theme badge classes (`badge-purple` and `badge-blue`)**
  - **Files:**
    - `apps/quality/models/CustomerComplaints/CustomerComplaints.py:76`
    - `apps/quality/models/CustomerComplaints/ComplaintInvestigations.py:49`
    - `apps/quality/models/CustomerComplaints/RegulatoryReports.py:65, 67, 79`
    - `apps/quality/models/CustomerComplaints/FieldActions.py:48, 57`
    - All 13 templates in `templates/quality/customercomplaints/`
  - **Problem:**
    `theme.css` specifies ONLY `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`. `badge-purple` and `badge-blue` render unstyled.
  - **Fix:**
    Replace `badge-purple` with `badge-amber` or `badge-info` / `badge-slate`, and `badge-blue` with `badge-info`.

- [ ] **I2: Missing status guards on edit views (post-closure / post-approval tampering)**
  - **Files:**
    - `apps/quality/views/CustomerComplaints/CustomerComplaints.py:158`
    - `apps/quality/views/CustomerComplaints/ComplaintInvestigations.py:144`
    - `apps/quality/views/CustomerComplaints/RegulatoryReports.py:156`
    - `apps/quality/views/CustomerComplaints/FieldActions.py:140`
  - **Problem:**
    Edit views allow modifying records that are already `closed`, `approved`, `submitted`, or `closed_terminated`.
  - **Fix:**
    Add guard at start of each edit view: redirect with error message if record is in a finalized state.

- [ ] **I3: Missing pre-condition guards and segregation of duties on lifecycle action views**
  - **Files:** `apps/quality/views/CustomerComplaints/`
    - `CustomerComplaints.py:194, 223` (`customer_complaint_triage`, `customer_complaint_close`)
    - `ComplaintInvestigations.py:181` (`complaint_investigation_complete`)
    - `RegulatoryReports.py:193, 211` (`regulatory_report_submit`, `regulatory_report_acknowledge`)
    - `FieldActions.py:179` (`field_action_close`)
  - **Problem:**
    Action endpoints do not check current lifecycle state before transitioning. In `complaint_investigation_complete`, lead investigator can self-approve their own investigation without independent check.
  - **Fix:**
    Enforce state checks: triage only from intake/under_triage; close only when investigations approved; report submit only from draft; ack only from submitted; investigation approval requires separate QA user or tenant admin.

- [ ] **I4: Loss of validation error feedback in customer complaint triage POST redirect**
  - **File:** `apps/quality/views/CustomerComplaints/CustomerComplaints.py:216-218`
  - **Problem:**
    When `ComplaintTriageForm` fails validation, the view flashes generic error message without specific field error text.
  - **Fix:**
    Format field errors in message: `messages.error(request, f"Triage validation error: {'; '.join(f'{k}: {v[0]}' for k, v in form.errors.items())}")`.

- [ ] **I5: Incomplete filter controls in list templates despite view context provisioning**
  - **Files:**
    - `templates/quality/customercomplaints/customer_complaint/list.html`
    - `templates/quality/customercomplaints/regulatory_report/list.html`
  - **Problem:**
    `customer_complaint_list` passes `customer_options` but template lacks customer `<select>`; `regulatory_report_list` passes `report_type_choices` but template lacks report_type dropdown.
  - **Fix:**
    Add `<select name="customer">` and `<select name="report_type">` to the respective filter bars.

- [ ] **I6: Filter form drops parent `complaint` filter on child list templates**
  - **Files:**
    - `templates/quality/customercomplaints/complaint_investigation/list.html:56-97`
    - `templates/quality/customercomplaints/regulatory_report/list.html:59-101`
    - `templates/quality/customercomplaints/field_action/list.html:56-97`
  - **Problem:**
    Submitting the filter bar drops the active `complaint` query parameter.
  - **Fix:**
    Add `{% if request.GET.complaint %}<input type="hidden" name="complaint" value="{{ request.GET.complaint }}">{% endif %}`.

- [ ] **I7: Missing `for` attributes in QA Triage form labels**
  - **File:** `templates/quality/customercomplaints/customer_complaint/detail.html:411-445`
  - **Problem:**
    Eight form field labels lack `for` attributes referencing field input IDs.
  - **Fix:**
    Add `for="{{ triage_form.<field>.id_for_label }}"` to all eight labels.

- [ ] **I8: Redundant child queries (.count(), .exists(), for loop) in complaint detail view**
  - **Files:** `apps/quality/views/CustomerComplaints/CustomerComplaints.py:110-112` & `templates/quality/customercomplaints/customer_complaint/detail.html`
  - **Problem:**
    Passing raw querysets causes 7 separate queries to render 3 child lists.
  - **Fix:**
    Evaluate querysets to lists with `select_related` in the view, and use `|length` and `{% if %}` in the template.

- [ ] **I9: Foreign key traversal in `ComplaintInvestigation.__str__` causes hidden queries**
  - **File:** `apps/quality/models/CustomerComplaints/ComplaintInvestigations.py:138-139`
  - **Problem:**
    `self.complaint.number` in `__str__` fires synchronous query during audit logging when `complaint` is not pre-fetched.
  - **Fix:**
    Change `__str__` to: `return f"{self.number} - Complaint Investigation"`.

- [ ] **I10: Redundant sequential COUNT queries in KPI stat cards**
  - **Files:** List views across `CustomerComplaints`, `ComplaintInvestigations`, `RegulatoryReports`, `FieldActions`
  - **Problem:**
    Multiple sequential count queries fired per page.
  - **Fix:**
    Consolidate into single `aggregate(Count(...), Count(...))` where practical.

- [ ] **I11: Immutable parent foreign key during edit mode**
  - **Files:**
    - `apps/quality/forms/CustomerComplaints/ComplaintInvestigations.py`
    - `apps/quality/forms/CustomerComplaints/RegulatoryReports.py`
  - **Problem:**
    In edit mode, `complaint` dropdown allows reassigning records to a different complaint.
  - **Fix:**
    Disable or exclude `complaint` when `self.instance.pk` is present.

- [ ] **I12: Missing composite database indexes on tenant + filter columns**
  - **Files:** `CustomerComplaints.py`, `RegulatoryReports.py`, `FieldActions.py`
  - **Problem:**
    Missing composite indexes for hot `(tenant, customer)`, `(tenant, submission_status)`, `(tenant, initiating_complaint)` filters.
  - **Fix:**
    Add composite indexes in `Meta.indexes`.

---

## Minor

- [ ] **M1: `ComplaintTriageForm` inherits from `forms.ModelForm` instead of `TenantModelForm`**
  - **File:** `apps/quality/forms/CustomerComplaints/CustomerComplaints.py:72`
  - **Fix:** Inherit from `TenantModelForm`.

- [ ] **M2: HTML comment leaks into rendered browser DOM**
  - **Files:** All 13 templates in `templates/quality/customercomplaints/`
  - **Fix:** Convert `<!-- ... -->` to Django comments `{# ... #}`.

- [ ] **M3: Hardcoded max constant in Root Cause Pareto chart bar width**
  - **File:** `templates/quality/customercomplaints/complaint_trending_dashboard.html:206`
  - **Fix:** Compute width dynamically against max count or total investigations.

- [ ] **M4: Missing `customer__name` in `CustomerComplaintAdmin.search_fields`**
  - **File:** `apps/quality/admin.py:1076`
  - **Fix:** Add `"customer__name"` to `search_fields`.

- [ ] **M5: Dark mode missing on narrative container boxes**
  - **Files:** `complaint_investigation/detail.html:71`, `regulatory_report/detail.html:63`, `complaint_trending_dashboard.html:91`
  - **Fix:** Add `dark:bg-slate-800 dark:border-slate-700`.

- [ ] **M6: Icon and dot collision inside `.badge`**
  - **Files:** `customer_complaint/detail.html:42`, `complaint_investigation/detail.html:33`
  - **Fix:** Remove nested `<i>` from `.badge`.

- [ ] **M7: Breadcrumb separator class discrepancy**
  - **Files:** All 13 templates
  - **Fix:** Use `<span class="sep">/</span>`.

- [ ] **M8: CSV export endpoints ignore GET filter parameters**
  - **Files:** `CustomerComplaints.py`, `ComplaintInvestigations.py`, `RegulatoryReports.py`, `FieldActions.py`
  - **Fix:** Apply active search and status filters to export querysets.

- [ ] **M9: Missing temporal validation on dates**
  - **Files:** `CustomerComplaints.py`, `RegulatoryReports.py`
  - **Fix:** Ensure `date_received <= timezone.now().date()` and `date_of_occurrence <= date_received`.
