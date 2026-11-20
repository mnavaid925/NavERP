# Master Review Findings: Sub-module 12.14 Management Review & Quality Planning

**Changeset**: `BASE` (`ed5bf098c22bd035a09707951ecc3e17152533ad`) to `HEAD`  
**Target**: `apps/quality/` (Sub-module 12.14)  
**Status**: All 6 Reviewer Passes Completed (Ready for Phase 5 `code-fixer`)

---

## Executive Summary

Sub-module 12.14 introduces comprehensive capabilities for ISO 9001:2015 Clause 9.3 and ISO 13485:2016 Clause 5.6 Management Review and Quality Planning.
All six specialist reviewers (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) have executed serially and reported.
Findings have been deduplicated, cross-verified, and prioritized into **6 Critical**, **11 Important**, and **10 Minor** action items.

---

## 🔴 Critical Findings

- [ ] **C1**: `management_review_action_escalate_capa` crashes with `TypeError` and `IntegrityError` (HTTP 500).
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviewActions.py:270-295`
  - **Description**: `CapaInvestigation.objects.create` calls invalid arguments `description` (should be `issue_summary`), `containment_action` (should be `containment_actions`), invalid `status="investigation"` (must be `"under_investigation"`), and omits required non-nullable `quality_owner` (set to `request.user`).
  - **Concurrency & Guards**: Add `select_for_update()`, check `locked_action.spawned_capa`, and verify action is not already `completed` or `cancelled`.

- [ ] **C2**: `ElectronicSignatureRecord` creation fails silently on review approval leaving signature NULL.
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviews.py:276-286`
  - **Description**: `ElectronicSignatureRecord.objects.create` passed wrong arguments (`meaning` vs `signature_meaning`, `comment` vs `comments`) and omitted mandatory non-nullable `document` and `document_revision`. The exception was swallowed by bare `except Exception: sig_record = None`.
  - **Remediation**: Use `ControlledDocument.objects.filter(tenant=request.tenant).first()` (or create a governance document if none exists), pass `document=doc`, `document_revision=doc.current_revision or "1.0"`, `signature_meaning="management_approval"`, `comments=...`, and attach `review.electronic_signature = sig_record`.

- [ ] **C3**: N+1 queries in Management Review CSV export (`ManagementReviews.py:360-361`).
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviews.py:321-364`
  - **Description**: Iterating over `qs` calls `r.total_inputs_count` and `r.total_actions_count` per row, executing `1 + 2*N` database queries (101 queries for N=50).
  - **Remediation**: Annotate `inputs_cnt=Count("inputs", distinct=True)` and `actions_cnt=Count("actions", distinct=True)` on the queryset and output `r.inputs_cnt` and `r.actions_cnt`.

- [ ] **C4**: Severe KPI query splitting (23 queries vs 6 queries) in Quality Planning Dashboard.
  - **Location**: `apps/quality/views/ManagementReview/QualityPlanningDashboard.py:19-75`
  - **Description**: Executes 23 queries per request due to individual RAG counts (4 queries), category choice loop (7 queries), review counts (3 queries), and action counts (4 queries).
  - **Remediation**: Consolidate into `.aggregate()` queries with conditional filters, a single `GROUP BY` query for category counts, remove unused `recent_reviews` query, and supply contract key `objectives_by_category`.

- [ ] **C5**: Post-Approval State Tampering & Record Alteration on `ManagementReviewInput`.
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviewInputs.py:121, 154, 177, 190, 201`
  - **Description**: Once a `ManagementReview` is in `approved` or `cancelled` status, inputs can still be created, edited, deleted, presented, or accepted, violating ISO 13485 frozen record governance.
  - **Remediation**: Check `review.status in ["approved", "cancelled"]` in create, edit, delete, present, and accept views, rejecting mutations with error messages.

- [ ] **C6**: Post-Approval Action Item Deletion & Closed Review Mutation on `ManagementReviewAction`.
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviewActions.py:145, 178, 205`
  - **Description**: Once a `ManagementReview` is in `approved` status, action items could be deleted if status was `open` or `in_progress`. Also actions could be assigned to closed reviews.
  - **Remediation**: Reject creation under closed reviews; reject deletion if `action_item.management_review.status == "approved"`.

---

## 🟡 Important Findings

- [ ] **I1**: Logic error in `QualityObjective.progress_percent` property for `lower_better` targets.
  - **Location**: `apps/quality/models/ManagementReview/QualityObjectives.py:149-162`
  - **Description**: Progress percentage calculation for `target_direction == "lower_better"` produces inverted or negative values when current value exceeds baseline or when baseline is zero.
  - **Remediation**: Ensure correct progress percentage logic: if `current_value <= target_value` return 100; else clamp between 0 and 100 based on relative variance.

- [ ] **I2**: Missing submodule package `__init__.py` files.
  - **Locations**:
    - `apps/quality/models/ManagementReview/__init__.py`
    - `apps/quality/forms/ManagementReview/__init__.py`
    - `apps/quality/views/ManagementReview/__init__.py`
  - **Description**: Submodule directories in models, forms, and views lack `__init__.py` re-exporting entities and declaring `__all__`.
  - **Remediation**: Create all three `__init__.py` files with clean re-exports.

- [ ] **I3**: Contract context key mismatches in review input and action forms (`parent_review` vs `review`).
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviewInputs.py:148, 172` and `ManagementReviewActions.py:172, 199`
  - **Description**: Views supply `parent_review` while Contract Section 3.2 specifies `review`.
  - **Remediation**: Pass both `"review": parent_review` and `"parent_review": parent_review` in the context dictionaries.

- [ ] **I4**: Missing contract-required context key `sponsors` in `management_review_list`.
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviews.py:82-101`
  - **Description**: Contract Section 3.2 specifies `sponsors` in context for filter dropdown. View omits it.
  - **Remediation**: Add `"sponsors": User.objects.filter(tenant=request.tenant, is_active=True).order_by("first_name", "last_name", "username")`.

- [ ] **I5**: Missing POST-Delete form on Management Review detail page.
  - **Location**: `templates/quality/managementreview/management_review/detail.html:48-56`
  - **Description**: Detail view provides Edit, Cancel, and Dossier actions, but lacks a POST-Delete form for draft/scheduled reviews.
  - **Remediation**: Add POST-Delete button with CSRF token and confirmation dialog when `review.status == "scheduled" and not review.inputs.exists() and not review.actions.exists()`.

- [ ] **I6**: Missing `aria-label` attributes on icon-only buttons.
  - **Locations**:
    - `templates/quality/managementreview/quality_objective/list.html`
    - `templates/quality/managementreview/management_review/list.html`
    - `templates/quality/managementreview/management_review/detail.html`
    - `templates/quality/managementreview/management_review_input/list.html`
    - `templates/quality/managementreview/management_review_action/list.html`
  - **Description**: Icon-only action and clear-filter buttons have `title` but lack `aria-label`.
  - **Remediation**: Add matching `aria-label` attributes to all icon-only buttons.

- [ ] **I7**: Missing privilege/role authorization on Executive Review Approval and Cancellation.
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviews.py:260-318`
  - **Description**: Any logged-in user can approve or cancel a management review. Approval should be restricted to the designated `executive_sponsor`, staff, or superuser.
  - **Remediation**: Check authorization in `management_review_approve` and `management_review_cancel`.

- [ ] **I8**: Missing status transition validation & self-verification bypass on action lifecycle.
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviewActions.py:222-268`
  - **Description**: Action lifecycle views (`start`, `complete`, `verify`) lack status guards (e.g. `verify` allowed on uncompleted items), and `verify` permits the assignee to self-verify.
  - **Remediation**: Validate current status before transition and enforce separation of duties (`assignee != request.user` unless staff).

- [ ] **I9**: Objective lifecycle tampering in `quality_objective_evaluate`.
  - **Location**: `apps/quality/views/ManagementReview/QualityObjectives.py:193-211`
  - **Description**: Evaluating an objective resets its status, which could revive a `draft` or `abandoned` objective without authorization. Also lacks owner/staff check.
  - **Remediation**: Block evaluation if status is `draft` or `abandoned`, and require `request.user == objective.owner` or staff/admin.

- [ ] **I10**: Review workflow state bypass in `management_review_draft_minutes`.
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviews.py:230-258`
  - **Description**: Users can draft minutes for scheduled reviews without starting the meeting.
  - **Remediation**: Restrict drafting minutes to `status in ["meeting_active", "minutes_drafting", "pending_approval"]`.

- [ ] **I11**: N+1 foreign key traversal in Action CSV export (`ManagementReviewActions.py:300, 336`).
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviewActions.py:300`
  - **Description**: Accesses `act.spawned_capa.number` in loop without `spawned_capa` in `select_related`.
  - **Remediation**: Add `"spawned_capa"` to `select_related`.

---

## 🟢 Minor Findings

- [ ] **M1**: Redundant duplicate `qs.count()` in all four list views (`total_count = paginator.count`).
  - **Locations**: `QualityObjectives.py:65`, `ManagementReviews.py:60`, `ManagementReviewInputs.py:54`, `ManagementReviewActions.py:64`.
  - **Remediation**: Initialize `paginator = Paginator(qs, PAGE_SIZE)` first and assign `total_count = paginator.count`.

- [ ] **M2**: Repeated queries via uncached model properties on Management Review detail (`detail.html:86-96`).
  - **Location**: `ManagementReviews.py:114-116` and `management_review/detail.html`
  - **Remediation**: Pass `total_inputs_count = len(inputs)`, `total_actions_count = len(actions)`, and `open_actions_count` in view context.

- [ ] **M3**: Missing composite index for active workflow and due date on `ManagementReviewAction`.
  - **Location**: `apps/quality/models/ManagementReview/ManagementReviewActions.py:115-121`
  - **Remediation**: Add composite index `models.Index(fields=["tenant", "status", "due_date"], name="idx_qmra_ten_stat_due")`.

- [ ] **M4**: Missing composite sort indexes for default pagination on `QualityObjective` and `ManagementReview`.
  - **Locations**: `QualityObjectives.py:120-128` (`idx_qobj_ten_yr_crd`) and `ManagementReviews.py:122-128` (`idx_qmrv_ten_date_crd`).
  - **Remediation**: Add `Index(fields=["tenant", "-period_year", "-created_at"], name="idx_qobj_ten_yr_crd")` and `Index(fields=["tenant", "-scheduled_date", "-created_at"], name="idx_qmrv_ten_date_crd")`.

- [ ] **M5**: Headroom on `QualityObjective.rag_status` choices (`max_length=10` vs L65 recommendation of `>= 12`).
  - **Location**: `apps/quality/models/ManagementReview/QualityObjectives.py:91`
  - **Remediation**: Update `max_length=16` on `rag_status`.

- [ ] **M6**: Clamping potential negative integer on `ManagementReviewAction.days_open`.
  - **Location**: `apps/quality/models/ManagementReview/ManagementReviewActions.py:131-134`
  - **Remediation**: Return `max(0, (end - start).days)`.

- [ ] **M7**: Filter form missing `<select name="assignee">` in `management_review_action/list.html`.
  - **Location**: `templates/quality/managementreview/management_review_action/list.html:113`
  - **Remediation**: Add `<select name="assignee">` dropdown to filter grid in action list template.

- [ ] **M8**: Slicing divergence in `urgent_actions` on dashboard (`[:5]` instead of `[:6]`).
  - **Location**: `apps/quality/views/ManagementReview/QualityPlanningDashboard.py:74`
  - **Remediation**: Slice `[:5]`.

- [ ] **M9**: Add `rel="noopener noreferrer"` to external dossier window link.
  - **Location**: `templates/quality/managementreview/management_review/detail.html:23`
  - **Remediation**: Add `rel="noopener noreferrer"` to the `target="_blank"` link.

- [ ] **M10**: Add `.badge-muted` & `.badge-slate` to dossier print stylesheet and `mr-auto` on list `.pagination-info`.
  - **Locations**: `management_review/dossier.html:15` and list templates.
  - **Remediation**: Include `.badge-muted, .badge-slate { background: #f1f5f9; color: #475569; }` in print CSS; add `mr-auto` to `.pagination-info`.
