# Master Review Findings: Sub-module 12.14 Management Review & Quality Planning

**Changeset**: `BASE` (`ed5bf098c22bd035a09707951ecc3e17152533ad`) to `HEAD`  
**Target**: `apps/quality/` (Sub-module 12.14)  
**Status**: All Findings Resolved (Burned down by Phase 5 `code-fixer`)

---

## Executive Summary

Sub-module 12.14 introduces comprehensive capabilities for ISO 9001:2015 Clause 9.3 and ISO 13485:2016 Clause 5.6 Management Review and Quality Planning.
All six specialist reviewers (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) executed serially and reported.
All 27 review findings (**6 Critical**, **11 Important**, and **10 Minor**) have been resolved in strict ID order, verified with Django system checks and database migrations, and committed following single-file git commit rules.

---

## 🔴 Critical Findings

- [x] **C1**: fixed — `97bad29f` `fix(quality): resolve CAPA escalation arguments and concurrency guard (C1)`
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviewActions.py:270-295`
  - **Description**: `CapaInvestigation.objects.create` calls invalid arguments `description` (should be `issue_summary`), `containment_action` (should be `containment_actions`), invalid `status="investigation"` (must be `"under_investigation"`), and omits required non-nullable `quality_owner` (set to `request.user`).
  - **Concurrency & Guards**: Add `select_for_update()`, check `locked_action.spawned_capa`, and verify action is not already `completed` or `cancelled`.

- [x] **C2**: fixed — `753400fd` `fix(quality): record formal electronic signature upon management review approval (C2)`
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviews.py:276-286`
  - **Description**: `ElectronicSignatureRecord.objects.create` passed wrong arguments (`meaning` vs `signature_meaning`, `comment` vs `comments`) and omitted mandatory non-nullable `document` and `document_revision`. The exception was swallowed by bare `except Exception: sig_record = None`.
  - **Remediation**: Use `ControlledDocument.objects.filter(tenant=request.tenant).first()` (or create a governance document if none exists), pass `document=doc`, `document_revision=doc.current_revision or "1.0"`, `signature_meaning="management_approval"`, `comments=...`, and attach `review.electronic_signature = sig_record`.

- [x] **C3**: fixed — `2ae85ed5` `fix(quality): annotate aggregate counts in management review CSV export (C3)`
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviews.py:321-364`
  - **Description**: Iterating over `qs` calls `r.total_inputs_count` and `r.total_actions_count` per row, executing `1 + 2*N` database queries (101 queries for N=50).
  - **Remediation**: Annotate `inputs_cnt=Count("inputs", distinct=True)` and `actions_cnt=Count("actions", distinct=True)` on the queryset and output `r.inputs_cnt` and `r.actions_cnt`.

- [x] **C4**: fixed — `ad6832fa` `perf(quality): consolidate KPI dashboard queries with aggregates and group-by (C4)`
  - **Location**: `apps/quality/views/ManagementReview/QualityPlanningDashboard.py:19-75`
  - **Description**: Executes 23 queries per request due to individual RAG counts (4 queries), category choice loop (7 queries), review counts (3 queries), and action counts (4 queries).
  - **Remediation**: Consolidate into `.aggregate()` queries with conditional filters, a single `GROUP BY` query for category counts, remove unused `recent_reviews` query, and supply contract key `objectives_by_category`.

- [x] **C5**: fixed — `9a788e76` `fix(quality): enforce review status guards against post-approval input tampering (C5)`
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviewInputs.py:121, 154, 177, 190, 201`
  - **Description**: Once a `ManagementReview` is in `approved` or `cancelled` status, inputs can still be created, edited, deleted, presented, or accepted, violating ISO 13485 frozen record governance.
  - **Remediation**: Check `review.status in ["approved", "cancelled"]` in create, edit, delete, present, and accept views, rejecting mutations with error messages.

- [x] **C6**: fixed — `a6df8071` `fix(quality): guard action item creation and deletion against closed reviews (C6)`
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviewActions.py:145, 178, 205`
  - **Description**: Once a `ManagementReview` is in `approved` status, action items could be deleted if status was `open` or `in_progress`. Also actions could be assigned to closed reviews.
  - **Remediation**: Reject creation under closed reviews; reject deletion if `action_item.management_review.status == "approved"`.

---

## 🟡 Important Findings

- [x] **I1**: fixed — `122797a2` `fix(quality): correct progress percentage computation for lower_better targets (I1)`
  - **Location**: `apps/quality/models/ManagementReview/QualityObjectives.py:149-162`
  - **Description**: Progress percentage calculation for `target_direction == "lower_better"` produces inverted or negative values when current value exceeds baseline or when baseline is zero.
  - **Remediation**: Ensure correct progress percentage logic: if `current_value <= target_value` return 100; else clamp between 0 and 100 based on relative variance.

- [x] **I2**: fixed — `ae34c83a`, `9bec5b3e`, `94bc56aa`, `bf6aeaa6` `feat(quality): add ManagementReview models/forms/views package inits (I2)`
  - **Locations**:
    - `apps/quality/models/ManagementReview/__init__.py`
    - `apps/quality/forms/ManagementReview/__init__.py`
    - `apps/quality/views/ManagementReview/__init__.py`
  - **Description**: Submodule directories in models, forms, and views lack `__init__.py` re-exporting entities and declaring `__all__`.
  - **Remediation**: Create all three `__init__.py` files with clean re-exports.

- [x] **I3**: fixed — `c37f0f7a`, `655ce216` `fix(quality): provide review context alias in review input and action forms (I3)`
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviewInputs.py:148, 172` and `ManagementReviewActions.py:172, 199`
  - **Description**: Views supply `parent_review` while Contract Section 3.2 specifies `review`.
  - **Remediation**: Pass both `"review": parent_review` and `"parent_review": parent_review` in the context dictionaries.

- [x] **I4**: fixed — `0972aa21` `fix(quality): provide sponsors context and filter in management review list (I4)`
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviews.py:82-101`
  - **Description**: Contract Section 3.2 specifies `sponsors` in context for filter dropdown. View omits it.
  - **Remediation**: Add `"sponsors": User.objects.filter(tenant=request.tenant, is_active=True).order_by("first_name", "last_name", "username")`.

- [x] **I5**: fixed — `6f5631b3` `feat(quality): add POST-delete action button for empty scheduled reviews (I5)`
  - **Location**: `templates/quality/managementreview/management_review/detail.html:48-56`
  - **Description**: Detail view provides Edit, Cancel, and Dossier actions, but lacks a POST-Delete form for draft/scheduled reviews.
  - **Remediation**: Add POST-Delete button with CSRF token and confirmation dialog when `review.status == "scheduled" and not review.inputs.exists() and not review.actions.exists()`.

- [x] **I6**: fixed — `14671fd0`, `66254b6e`, `98630215`, `fc4c601d`, `0056fbda` `feat(quality): add aria-label attributes to action buttons (I6)`
  - **Locations**:
    - `templates/quality/managementreview/quality_objective/list.html`
    - `templates/quality/managementreview/management_review/list.html`
    - `templates/quality/managementreview/management_review/detail.html`
    - `templates/quality/managementreview/management_review_input/list.html`
    - `templates/quality/managementreview/management_review_action/list.html`
  - **Description**: Icon-only action and clear-filter buttons have `title` but lack `aria-label`.
  - **Remediation**: Add matching `aria-label` attributes to all icon-only buttons.

- [x] **I7**: fixed — `2455d486` `fix(quality): enforce role authorization on review approval and cancellation (I7)`
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviews.py:260-318`
  - **Description**: Any logged-in user can approve or cancel a management review. Approval should be restricted to the designated `executive_sponsor`, staff, or superuser.
  - **Remediation**: Check authorization in `management_review_approve` and `management_review_cancel`.

- [x] **I8**: fixed — `425834ca` `fix(quality): enforce action status transitions and independent QA verification (I8)`
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviewActions.py:222-268`
  - **Description**: Action lifecycle views (`start`, `complete`, `verify`) lack status guards (e.g. `verify` allowed on uncompleted items), and `verify` permits the assignee to self-verify.
  - **Remediation**: Validate current status before transition and enforce separation of duties (`assignee != request.user` unless staff).

- [x] **I9**: fixed — `8bf1b777` `fix(quality): guard objective evaluation lifecycle and owner authorization (I9)`
  - **Location**: `apps/quality/views/ManagementReview/QualityObjectives.py:193-211`
  - **Description**: Evaluating an objective resets its status, which could revive a `draft` or `abandoned` objective without authorization. Also lacks owner/staff check.
  - **Remediation**: Block evaluation if status is `draft` or `abandoned`, and require `request.user == objective.owner` or staff/admin.

- [x] **I10**: fixed — `55a05f00` `fix(quality): enforce review active state before drafting minutes (I10)`
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviews.py:230-258`
  - **Description**: Users can draft minutes for scheduled reviews without starting the meeting.
  - **Remediation**: Restrict drafting minutes to `status in ["meeting_active", "minutes_drafting", "pending_approval"]`.

- [x] **I11**: fixed — `ea64dcd1` `perf(quality): select spawned_capa foreign key in action CSV export (I11)`
  - **Location**: `apps/quality/views/ManagementReview/ManagementReviewActions.py:300`
  - **Description**: Accesses `act.spawned_capa.number` in loop without `spawned_capa` in `select_related`.
  - **Remediation**: Add `"spawned_capa"` to `select_related`.

---

## 🟢 Minor Findings

- [x] **M1**: fixed — `2a648aea`, `347b7b04`, `b24b4f50`, `a3368e01` `perf(quality): reuse paginator count in list views (M1)`
  - **Locations**: `QualityObjectives.py:65`, `ManagementReviews.py:60`, `ManagementReviewInputs.py:54`, `ManagementReviewActions.py:64`.
  - **Remediation**: Initialize `paginator = Paginator(qs, PAGE_SIZE)` first and assign `total_count = paginator.count`.

- [x] **M2**: fixed — `301df95e`, `9ba5b800` `perf(quality): pass and render precalculated counts on review detail (M2)`
  - **Location**: `ManagementReviews.py:114-116` and `management_review/detail.html`
  - **Remediation**: Pass `total_inputs_count = len(inputs)`, `total_actions_count = len(actions)`, and `open_actions_count` in view context.

- [x] **M3**: fixed — `34229607`, `44deac5d` `perf(quality): add composite index on action status and due date (M3)`
  - **Location**: `apps/quality/models/ManagementReview/ManagementReviewActions.py:115-121`
  - **Remediation**: Add composite index `models.Index(fields=["tenant", "status", "due_date"], name="idx_qmra_ten_stat_due")`.

- [x] **M4**: fixed — `16bf60a5`, `89434498`, `44deac5d` `perf(quality): add composite sort indexes on objective and review (M4)`
  - **Locations**: `QualityObjectives.py:120-128` (`idx_qobj_ten_yr_crd`) and `ManagementReviews.py:122-128` (`idx_qmrv_ten_date_crd`).
  - **Remediation**: Add `Index(fields=["tenant", "-period_year", "-created_at"], name="idx_qobj_ten_yr_crd")` and `Index(fields=["tenant", "-scheduled_date", "-created_at"], name="idx_qmrv_ten_date_crd")`.

- [x] **M5**: fixed — `5a802875`, `44deac5d` `fix(quality): increase rag_status max_length headroom to 16 chars (M5)`
  - **Location**: `apps/quality/models/ManagementReview/QualityObjectives.py:91`
  - **Remediation**: Update `max_length=16` on `rag_status`.

- [x] **M6**: fixed — `efc86a90` `fix(quality): clamp days_open property to non-negative integers (M6)`
  - **Location**: `apps/quality/models/ManagementReview/ManagementReviewActions.py:131-134`
  - **Remediation**: Return `max(0, (end - start).days)`.

- [x] **M7**: fixed — `14e476da` `feat(quality): add assignee select dropdown to action list filter form (M7)`
  - **Location**: `templates/quality/managementreview/management_review_action/list.html:113`
  - **Remediation**: Add `<select name="assignee">` dropdown to filter grid in action list template.

- [x] **M8**: fixed — `ad6832fa` `perf(quality): slice urgent_actions to [:5] on dashboard (M8)`
  - **Location**: `apps/quality/views/ManagementReview/QualityPlanningDashboard.py:74`
  - **Remediation**: Slice `[:5]`.

- [x] **M9**: fixed — `6e0840d0` `fix(quality): add rel noopener noreferrer to dossier target blank link (M9)`
  - **Location**: `templates/quality/managementreview/management_review/detail.html:23`
  - **Remediation**: Add `rel="noopener noreferrer"` to the `target="_blank"` link.

- [x] **M10**: fixed — `4b78e0a8`, `196a0515`, `a0b9e366`, `7feb8b35`, `b643aa26` `style(quality): dossier print CSS classes and mr-auto on pagination-info (M10)`
  - **Locations**: `management_review/dossier.html:15` and list templates.
  - **Remediation**: Include `.badge-muted, .badge-slate { background: #f1f5f9; color: #475569; }` in print CSS; add `mr-auto` to `.pagination-info`.
