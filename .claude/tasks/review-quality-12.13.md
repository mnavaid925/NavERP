# Review Findings: Sub-module 12.13 Customer Complaint Handling

**BASE:** `bc9fc6d0e8137f54214ffd3af0019c12e69c6c72`  
**Scope:** `apps/quality/` (CustomerComplaints models, forms, views, urls, admin, seeder, migration) & `templates/quality/customercomplaints/`

---

## 1. Code Reviewer Findings

### Critical
- **C1: Pagination query parameter corruption traps navigation across all list views**
  - **Files:**
    - `templates/quality/customercomplaints/customer_complaint/list.html:266-280`
    - `templates/quality/customercomplaints/complaint_investigation/list.html:232-246`
    - `templates/quality/customercomplaints/regulatory_report/list.html:230-244`
    - `templates/quality/customercomplaints/field_action/list.html:232-246`
  - **Problem:**
    Pagination links use:
    ```django
    href="?page={{ page_obj.next_page_number }}{% if request.GET.urlencode %}&{{ request.GET.urlencode }}{% endif %}"
    ```
    When navigating from page 1, `request.GET.urlencode` already contains `page=1` (or `page=2` when on page 2). The resulting URL appends duplicate `page` keys (e.g. `?page=2&page=1&status=open`). In Django, `request.GET.get('page')` returns the *last* occurrence in the `QueryDict` (`'1'`), trapping the user on the current page or preventing navigation past page 2.
  - **Fix:**
    Build pagination query parameters without duplicating `page`, or pass a helper or exclude `page` from the encoded query string.

### Important
- **I1: Skewed average cycle time calculation when closed complaints exceed slice limit**
  - **File:** `apps/quality/views/CustomerComplaints/ComplaintTrendingDashboard.py:28-33`
  - **Problem:**
    `total_days = sum(c.days_open for c in closed_with_dates[:200])` slices the first 200, but `avg_cycle_days = round(total_days / total_closed, 1)` divides by `total_closed`. If `total_closed > 200`, the average is artificially deflated.
  - **Fix:**
    Divide by `len(sample)` / `min(total_closed, 200)` or compute average cycle time directly via ORM aggregation.

- **I2: Loss of validation error feedback in customer complaint triage POST redirect**
  - **File:** `apps/quality/views/CustomerComplaints/CustomerComplaints.py:216-218`
  - **Problem:**
    When `ComplaintTriageForm` fails validation, the view flashes a generic message `"Triage submission contained validation errors."` and redirects. Upon redirect, the detail page renders a fresh unbound `triage_form` without field-level error messages.
  - **Fix:**
    Include specific field errors in the error message, e.g. `messages.error(request, f"Triage validation error: {'; '.join(f'{k}: {v[0]}' for k, v in form.errors.items())}")`.

- **I3: Widespread use of invalid badge color classes (`badge-purple` and `badge-blue`)**
  - **Files:**
    - Models:
      - `apps/quality/models/CustomerComplaints/CustomerComplaints.py:76` (`badge-purple`)
      - `apps/quality/models/CustomerComplaints/ComplaintInvestigations.py:49` (`badge-purple`)
      - `apps/quality/models/CustomerComplaints/RegulatoryReports.py:65` (`badge-blue`), `67` (`badge-purple`), `79` (`badge-purple`)
      - `apps/quality/models/CustomerComplaints/FieldActions.py:48` (`badge-purple`), `57` (`badge-purple`)
    - Templates:
      - `templates/quality/customercomplaints/customer_complaint/list.html:201`
      - `templates/quality/customercomplaints/customer_complaint/detail.html:36, 163, 236`
      - `templates/quality/customercomplaints/complaint_investigation/list.html:159, 166`
      - `templates/quality/customercomplaints/complaint_investigation/detail.html:22, 33`
      - `templates/quality/customercomplaints/regulatory_report/list.html:166`
      - `templates/quality/customercomplaints/regulatory_report/detail.html:23`
      - `templates/quality/customercomplaints/field_action/list.html:170`
      - `templates/quality/customercomplaints/field_action/detail.html:23`
  - **Problem:**
    NavERP design standards strictly mandate color-named badges only: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`. `badge-purple` and `badge-blue` are invalid.
  - **Fix:**
    Replace `badge-purple` with `badge-amber` or `badge-info` (or `badge-slate`/`badge-muted`) and `badge-blue` with `badge-info`.

- **I4: Incomplete filter controls in list templates despite view context provisioning**
  - **Files:**
    - `templates/quality/customercomplaints/customer_complaint/list.html:68-120` & `apps/quality/views/CustomerComplaints/CustomerComplaints.py:80-96`
    - `templates/quality/customercomplaints/regulatory_report/list.html:59-101` & `apps/quality/views/CustomerComplaints/RegulatoryReports.py:43-84`
  - **Problem:**
    In `customer_complaint_list`, `customer_options` is passed in context and parsed from `request.GET.get('customer')`, but `customer_complaint/list.html` omits the `<select name="customer">` dropdown.
    In `regulatory_report_list`, `report_type_choices` is passed in context and filtered by the view, but `regulatory_report/list.html` omits the `report_type` dropdown from the filter bar.
  - **Fix:**
    Render the missing filter dropdowns in both templates, using `|stringformat:"d"` for customer PK comparison.

### Minor
- **M1: `ComplaintTriageForm` inherits from `forms.ModelForm` instead of `TenantModelForm`**
  - **File:** `apps/quality/forms/CustomerComplaints/CustomerComplaints.py:72-98`
  - **Problem:**
    `ComplaintTriageForm` inherits from standard `forms.ModelForm`. Consequently, fields (`validity`, `severity`, `reportability`, `complaint_category`, `assigned_to`) lack standard CSS styling classes (`form-select`, `form-input`).
  - **Fix:**
    Inherit from `TenantModelForm` (from `apps.core.forms`).

- **M2: HTML comment leaks into rendered DOM**
  - **Files:**
    - `templates/quality/customercomplaints/customer_complaint/detail.html:72`
    - `templates/quality/customercomplaints/customer_complaint/form.html:30`
    - `templates/quality/customercomplaints/complaint_investigation/detail.html:58`
    - `templates/quality/customercomplaints/complaint_investigation/form.html:30`
    - `templates/quality/customercomplaints/regulatory_report/detail.html:57`
    - `templates/quality/customercomplaints/regulatory_report/form.html:30`
    - `templates/quality/customercomplaints/field_action/detail.html:52`
    - `templates/quality/customercomplaints/field_action/form.html:30`
    - `templates/quality/customercomplaints/complaint_trending_dashboard.html:27`
  - **Problem:**
    Templates use standard HTML comments `<!-- ... -->` instead of server-side Django comments `{# ... #}`, leaking implementation notes into client HTML.
  - **Fix:**
    Convert HTML comments to Django template comments `{# ... #}`.

- **M3: Unbounded edit form status mutation risks un-stamped closure records**
  - **File:** `apps/quality/forms/CustomerComplaints/CustomerComplaints.py:9-20`
  - **Problem:**
    `CustomerComplaintForm` excludes `closed_by` and `closed_at`, but retains `status` in its field list. If an operator flips `status` to `closed` in the general edit form rather than via `customer_complaint_close`, the complaint will have `status="closed"` with `closed_at=None`.
  - **Fix:**
    In `CustomerComplaintForm.clean()`, ensure that if `status == "closed"` and `closed_at` is empty, raise a ValidationError, or exclude `status` from `CustomerComplaintForm`.

- **M4: Hardcoded constant in Pareto chart bar calculation**
  - **File:** `templates/quality/customercomplaints/complaint_trending_dashboard.html:206`
  - **Problem:**
    `style="width: {% widthratio rc.count 20 100 %}%;"` uses a hardcoded maximum of 20 investigations.
  - **Fix:**
    Pass `max_root_cause_count` or calculate width against total investigation count.

---

## 2. Explorer Reviewer Findings

### Important
- **I5: Filter form drops parent `complaint` filter on child list templates**
  - **Files:**
    - `templates/quality/customercomplaints/complaint_investigation/list.html:56-97`
    - `templates/quality/customercomplaints/regulatory_report/list.html:59-101`
    - `templates/quality/customercomplaints/field_action/list.html:56-97`
  - **Problem:**
    `ComplaintInvestigations.py`, `RegulatoryReports.py`, and `FieldActions.py` support filtering by parent complaint (`request.GET.get('complaint')`). When a user arrives via a deep-link from a complaint detail page and then submits the filter bar (e.g. search or status), the `complaint` query param is silently dropped because there is no `<input type="hidden" name="complaint" value="{{ request.GET.complaint }}">`.
  - **Fix:**
    Add `{% if request.GET.complaint %}<input type="hidden" name="complaint" value="{{ request.GET.complaint }}">{% endif %}` to the filter form in all 3 child list templates.

### Minor
- **M5: Missing `customer__name` in `CustomerComplaintAdmin.search_fields`**
  - **File:** `apps/quality/admin.py:1076`
  - **Problem:**
    `search_fields` covers number, title, item_code, complainant_name, etc., but omits `customer__name`.
  - **Fix:**
    Add `"customer__name"` to `CustomerComplaintAdmin.search_fields`.

