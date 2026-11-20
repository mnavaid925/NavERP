# Review Findings: Sub-module 12.14 Management Review & Quality Planning

**Changeset**: `BASE` (`ed5bf098c22bd035a09707951ecc3e17152533ad`) to `HEAD`  
**Target**: `apps/quality/` (Sub-module 12.14)  
**Status**: Review in progress (Reviewer 5 of 6 completed)

---

## 1. Code Reviewer Pass (`code-reviewer`)

### Critical
- **C1**: `management_review_action_escalate_capa` crashes with `TypeError` and `IntegrityError` (500 Error).
  - **File**: `apps/quality/views/ManagementReview/ManagementReviewActions.py:278-286`
  - **Details**: When escalating to CAPA, `CapaInvestigation.objects.create` is invoked with invalid keyword arguments: `description` instead of `issue_summary`, `containment_action` instead of `containment_actions`, `status="investigation"` instead of `under_investigation`, and missing non-nullable required `quality_owner` field.
  - **Impact**: Guaranteed 500 runtime crash when escalating an action to CAPA.

- **C2**: `ElectronicSignatureRecord` creation fails silently during executive review approval.
  - **File**: `apps/quality/views/ManagementReview/ManagementReviews.py:302-315`
  - **Details**: In `management_review_approve`, `ElectronicSignatureRecord.objects.create` is called with invalid parameters (`signature_meaning` instead of `meaning`, `comments` instead of `comment`) and omits required non-nullable fields `document` and `document_revision` (since `ElectronicSignatureRecord` was designed for `ControlledDocument`). Because of general `try/except Exception`, the creation fails silently and `review.electronic_signature` is left `NULL`, violating 21 CFR Part 11 requirements.
  - **Impact**: Audit trail and regulatory compliance failure for signed management reviews.

### Important
- **I1**: Logic error in `QualityObjective.progress_percent` property for `lower_better` targets.
  - **File**: `apps/quality/models/ManagementReview/QualityObjectives.py:149-162`
  - **Details**: When `target_direction == "lower_better"` and baseline is provided, the ratio calculation is flawed: `achieved = self.baseline_value - self.current_value`, `needed = self.baseline_value - self.target_value`, but when `current_value > baseline_value`, achieved is negative, leading to unexpected progress results. When baseline is null or 0, `pct = int((self.target_value / self.current_value) * 100)` is inverted (e.g. current=20, target=10 gives 50% instead of 0%).
  - **Impact**: Inaccurate KPI reporting on executive dashboards and scorecards.

- **I2**: N+1 query loop and contract violation in `quality_planning_dashboard`.
  - **File**: `apps/quality/views/ManagementReview/QualityPlanningDashboard.py:36-53`
  - **Details**: Dashboard view executes 4 individual count queries for RAG status and 7 individual count queries in a loop for categories. Furthermore, the context passes `category_counts` while the contract pinned `objectives_by_category`.
  - **Impact**: Excessive database queries per request and context contract drift.

- **I3**: Missing contract-required context key `sponsors` in `management_review_list`.
  - **File**: `apps/quality/views/ManagementReview/ManagementReviews.py:50`
  - **Details**: Contract pinned `sponsors` (distinct executive sponsors for filter dropdown), but the view only passes `organizers`.
  - **Impact**: Missing filter choices in UI.

- **I4**: Missing state tampering checks on inputs and actions when associated review is `approved`.
  - **Files**: `apps/quality/views/ManagementReview/ManagementReviewInputs.py` and `ManagementReviewActions.py`
  - **Details**: If a `ManagementReview` is already in `approved` / closed status, edit and delete views for inputs and actions do not verify that the parent review is open, allowing mutation of regulatory records post-approval.
  - **Impact**: Regulatory compliance risk allowing modification of frozen management review records.

### Minor
- **M1**: Context key drift in input/action create/edit views (`parent_review` vs contract-pinned `review`).
  - **Files**: `apps/quality/views/ManagementReview/ManagementReviewInputs.py` and `ManagementReviewActions.py`
  - **Details**: Views pass `parent_review` while contract specifies `review`.
  - **Impact**: Potential template breakage if referencing `review`.

- **M2**: Headroom on `QualityObjective.rag_status` choices (`max_length=10` vs L65 recommendation of `>= 12`).
  - **File**: `apps/quality/models/ManagementReview/QualityObjectives.py:91`
  - **Details**: Longest choice is `"neutral"` (7 chars); `max_length=10` only has 3 chars of headroom.
  - **Impact**: Minor constraint headroom hygiene.

- **M3**: Potential negative integer on `ManagementReviewAction.days_open`.
  - **File**: `apps/quality/models/ManagementReview/ManagementReviewActions.py:131-134`
  - **Details**: If `completion_date` precedes `created_at.date()`, `days_open` can be negative.
  - **Impact**: Clamping with `max(0, ...)` needed.


---

## 2. Architectural Explorer Pass (`explorer`)

### Critical
- **C1 (duplicate/confirmed)**: Runtime crash in `management_review_action_escalate_capa` due to `CapaInvestigation` field mismatches.
  - **File**: `apps/quality/views/ManagementReview/ManagementReviewActions.py:278-286`
  - **Details**: Same as Code Reviewer C1 (`description` vs `issue_summary`, `containment_action` vs `containment_actions`, missing `quality_owner`, `status="investigation"` vs `"under_investigation"`).

- **C2 (duplicate/confirmed)**: Silent failure of `ElectronicSignatureRecord` creation in `management_review_approve`.
  - **File**: `apps/quality/views/ManagementReview/ManagementReviews.py:276-286`
  - **Details**: Same as Code Reviewer C2 (missing non-nullable `document` and `document_revision`, wrong param names `meaning` and `comment`).

### Important
- **I5**: Missing submodule package `__init__.py` files.
  - **Files**:
    - `apps/quality/models/ManagementReview/__init__.py`
    - `apps/quality/forms/ManagementReview/__init__.py`
    - `apps/quality/views/ManagementReview/__init__.py`
  - **Details**: Sibling submodules (`CustomerComplaints`, `AuditManagement`, `TrainingCompetency`) each have package `__init__.py` files re-exporting entity modules and declaring `__all__`. While `urls/ManagementReview/__init__.py` exists, `models`, `forms`, and `views` sub-packages lack `__init__.py` files.
  - **Impact**: Incomplete package layout; importing from `apps.quality.models.ManagementReview` fails.

- **I6 (confirmed I2)**: Contract context key mismatch in `quality_planning_dashboard` (`objectives_by_category` vs `category_counts`).
  - **File**: `apps/quality/views/ManagementReview/QualityPlanningDashboard.py:85`
  - **Details**: Passes `category_counts` instead of contract key `objectives_by_category`.

- **I7 (confirmed I3)**: Missing `sponsors` in `management_review_list` context.
  - **File**: `apps/quality/views/ManagementReview/ManagementReviews.py:82-101`
  - **Details**: Contract Section 3.2 specifies `sponsors: User.objects.filter(tenant=request.tenant, is_active=True)`. View omits it.

- **I8 (confirmed M1)**: Contract context key mismatch in input and action create/edit forms (`parent_review` vs `review`).
  - **Files**: `apps/quality/views/ManagementReview/ManagementReviewInputs.py:148,172` and `ManagementReviewActions.py:172,199`
  - **Details**: Context passes `parent_review` instead of contract-specified `review`.

### Minor
- **M4**: Filter form missing Assignee `<select>` dropdown in `templates/quality/managementreview/management_review_action/list.html:113`.
  - **Details**: View supports filtering by `assignee` and provides `assignees` and `selected_assignee`, and line 113 checks `selected_assignee` for the reset pill, but there is no `<select name="assignee">` input in the template.

- **M5**: Slicing divergence in `urgent_actions` on dashboard (`[:6]` vs `[:5]`).
  - **File**: `apps/quality/views/ManagementReview/QualityPlanningDashboard.py:74`
  - **Details**: Contract specifies `urgent_actions: top 5 open actions ordered by due date`; view slices `[:6]`.


---

## 3. Frontend Reviewer Pass (`frontend-reviewer`)

### Critical
- None. (Zero comment leaks, zero illegal badge classes, zero broken URLs, zero broken filter comparisons).

### Important
- **I9**: Missing POST-Delete form on Management Review detail page.
  - **File**: `templates/quality/managementreview/management_review/detail.html:48-56`
  - **Details**: Rule 4 requires detail pages to provide Edit / POST-Delete / Back actions. Draft and scheduled reviews can be deleted from list, but detail only has "Cancel Review".
  - **Fix**: Add POST-Delete form with CSRF and confirm dialog when `review.status != 'approved' and review.status != 'cancelled'`.

- **I10**: Missing `aria-label` attributes on icon-only buttons.
  - **Files**:
    - `templates/quality/managementreview/quality_objective/list.html:114, 194, 197, 202`
    - `templates/quality/managementreview/management_review/list.html:114, 187, 191, 196`
    - `templates/quality/managementreview/management_review/detail.html:344, 347, 418, 421`
    - `templates/quality/managementreview/management_review_input/list.html:114, 184, 187, 192`
    - `templates/quality/managementreview/management_review_action/list.html:114, 186, 190, 195`
  - **Details**: Icon-only buttons have `title` but lack `aria-label` for screen reader accessibility (Rule 10).

### Minor
- **M6**: Add `rel="noopener noreferrer"` to external dossier window link.
  - **File**: `templates/quality/managementreview/management_review/detail.html:23`

- **M7**: Add `.badge-muted` & `.badge-slate` to dossier print stylesheet.
  - **File**: `templates/quality/managementreview/management_review/dossier.html:15`

- **M8**: Align `.pagination-info` to the left with `mr-auto` in list templates.
  - **Files**: List templates (`quality_objective`, `management_review`, `management_review_input`, `management_review_action`).

- **M9 (confirmed M4)**: Add `<select name="assignee">` to filter form in `management_review_action/list.html` or reconcile line 113.


---

## 4. Performance Reviewer Pass (`performance-reviewer`)

### Critical
- **C3**: N+1 queries in Management Review CSV export (`ManagementReviews.py:360-361`).
  - **Details**: `management_review_export_csv` evaluates `r.total_inputs_count` and `r.total_actions_count` per row, firing `1 + 2*N` SQL queries.
  - **Fix**: Annotate `inputs_cnt=Count("inputs", distinct=True)` and `actions_cnt=Count("actions", distinct=True)` on queryset before iterating.

- **C4**: Severe KPI metric query splitting in Quality Planning Dashboard (`QualityPlanningDashboard.py:36-74`).
  - **Details**: Executes 23 separate queries per page hit (repeated count queries for RAG status, category loop, reviews counts, and action counts).
  - **Fix**: Consolidate into SQL `.aggregate()` with conditional filters and single `GROUP BY` for category counts, dropping from 23 queries to 6 queries (-74%).

### Important
- **I11**: N+1 foreign key traversal in Action CSV export (`ManagementReviewActions.py:300, 336`).
  - **Details**: Accesses `act.spawned_capa.number` in loop without `spawned_capa` in `select_related`.
  - **Fix**: Add `"spawned_capa"` to `select_related`.

- **I12**: Redundant duplicate `qs.count()` in all four list views (`QualityObjectives.py`, `ManagementReviews.py`, `ManagementReviewInputs.py`, `ManagementReviewActions.py`).
  - **Details**: Views run `total_count = qs.count()`, then `paginator.get_page()` immediately runs `count()` again.
  - **Fix**: Use `total_count = paginator.count`.

- **I13**: Repeated queries via uncached model properties on Management Review detail (`detail.html:86-96`).
  - **Details**: Calls `review.total_inputs_count`, `review.total_actions_count`, and `review.open_actions_count` when view already loaded `inputs` and `actions` lists.
  - **Fix**: Pass `total_inputs_count = len(inputs)`, `total_actions_count = len(actions)`, and `open_actions_count` in context.

- **I14**: Missing composite index for active workflow and due date slices on `ManagementReviewAction`.
  - **Details**: Active queries filter by `(tenant, status, due_date)`.
  - **Fix**: Add composite index `models.Index(fields=["tenant", "status", "due_date"], name="idx_qmra_ten_stat_due")` (20 chars).

### Minor
- **M10**: Redundant single-column `db_index=True` on fields already covered by `(tenant, <field>)` composite indexes.
- **M11**: Missing composite sort indexes for default pagination on `QualityObjective` (`tenant, -period_year, -created_at`) and `ManagementReview` (`tenant, -scheduled_date, -created_at`).
- **M12**: Seeder query lookups in `_seed_submodule_12_14` fetching full model instances rather than `.only("id")`.


---

## 5. QA Smoke Tester Pass (`qa-smoke-tester`)

### Critical
- **C1 (runtime verified 500)**: `POST /quality/actions/<pk>/escalate-capa/` crashes with HTTP 500 (`TypeError: CapaInvestigation() got unexpected keyword arguments: 'description', 'containment_action'`).
  - **Details**: Confirmed in test client execution. Invalid parameters (`description`, `containment_action`, missing required `quality_owner`, invalid `status="investigation"`).

### Important
- **C2 (runtime verified silent failure)**: `POST /quality/reviews/<pk>/approve/` silently fails to create `ElectronicSignatureRecord`.
  - **Details**: Confirmed in test client execution. Swallowed exception results in `review.electronic_signature` permanently `None`.

### Verification Summary
- **Total Endpoints Tested**: 62 (GET views, filtered lists, junk params, pagination, CSV exports, PDF dossier, workflow action POSTs, and cross-tenant IDOR).
- **Pass Rate**: 61 / 62 PASSED (1 HTTP 500, 1 silent integrity failure).
- **Zero Comment Leaks**: No `{#`, `{%`, or unrendered `{{` template tags leaked in rendered HTML.
- **Tenant Isolation**: 15 / 15 cross-tenant IDOR checks returned strict HTTP 404 on Globex records.
