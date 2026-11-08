# Consolidated Review Findings — Sub-module 10.18: Collaboration & Data Storytelling (`apps/bi`)

- **Sub-module:** 10.18 Collaboration & Data Storytelling
- **Base SHA:** `769f20c68026ef80014849af810e720d14d817b4`
- **Head SHA:** `f78af891d8c2bb4aeb84f6831f853a007a258e4c`
- **Date:** 2026-11-08
- **Reviewers Executed Serially:**
  1. `code-reviewer` — Architecture, clean signatures, exception guards
  2. `explorer` — Contract alignment, re-exports, navigation consistency
  3. `frontend-reviewer` — Theme classes, comment leak, pagination, accessibility, dark mode
  4. `performance-reviewer` — Query patterns, N+1 detection, select_related, indexing
  5. `qa-smoke-tester` — Runtime verification (59 checks across 23 URLs, IDOR, POST tests)
  6. `security-reviewer` — Tenant isolation, AuthN/AuthZ, XSS, injection, token validation

---

## Findings Summary

| Severity | Total | Status |
|---|---|---|
| **Critical** | 3 | 3 Open |
| **Important** | 11 | 11 Open |
| **Minor** | 15 | 15 Open |
| **Total** | **29** | **29 Open** |

---

## Critical Findings

- [ ] **`C1`**: Inverted `reject_foreign` call signatures across all 4 forms causing `AttributeError: 'Tenant' object has no attribute 'get'` and HTTP 500 on all form submissions.
  - **Files:**
    - `apps/bi/forms/CollaborationStorytelling/BiSharedWorkspaces.py:59`
    - `apps/bi/forms/CollaborationStorytelling/BiDataStories.py:55`
    - `apps/bi/forms/CollaborationStorytelling/BiVisualComments.py:55-67`
    - `apps/bi/forms/CollaborationStorytelling/BiDecisionLogs.py:68-76`
  - **Fix:** Replace field-level `clean_<fk>` methods with form-level `def clean(self): cleaned = super().clean(); reject_foreign(self, cleaned, [...]); return cleaned`.

- [ ] **`C2`**: Cross-tenant User assignment (IDOR) via unscoped User FK dropdowns in forms.
  - **Files:**
    - `apps/bi/forms/CollaborationStorytelling/BiSharedWorkspaces.py:49-56` (`owner`)
    - `apps/bi/forms/CollaborationStorytelling/BiDataStories.py:45-52` (`author`)
    - `apps/bi/forms/CollaborationStorytelling/BiDecisionLogs.py:58-65` (`decision_maker`)
  - **Fix:** In `__init__`, scope `owner`, `author`, `decision_maker` querysets to `tenant=self.tenant`, and add them to `reject_foreign(self, cleaned, [...])`.

- [ ] **`C3`**: Missing cross-tenant FK validation for `widget` in `BiVisualCommentForm` and `BiDecisionLogForm`.
  - **Files:**
    - `apps/bi/forms/CollaborationStorytelling/BiVisualComments.py:53-67`
    - `apps/bi/forms/CollaborationStorytelling/BiDecisionLogs.py:66-76`
  - **Fix:** Include `"widget"` in `reject_foreign(self, cleaned, [...])` in both forms.

---

## Important Findings

- [ ] **`I1`**: Unvalidated embed token in `bi_data_story_export_office`.
  - **File:** `apps/bi/views/CollaborationStorytelling/BiDataStories.py:222-225`
  - **Fix:** Check `token` against `story.office_embed_token` using `secrets.compare_digest` if `story.office_embed_token` is present; return `JsonResponse({"error": "Invalid or missing embed token"}, status=403)`.

- [ ] **`I2`**: N+1 Query in `BiVisualComment` list view on `parent_comment`.
  - **Files:** `apps/bi/views/CollaborationStorytelling/BiVisualComments.py:19-21` & `templates/bi/collaboration_storytelling/bivisualcomment/list.html:154-157`
  - **Fix:** Add `"parent_comment"` to `.select_related(...)` in `bi_visual_comment_list`.

- [ ] **`I3`**: Unescaped dynamic model titles/names in inline JavaScript `confirm()` dialogs across list templates.
  - **Files:**
    - `templates/bi/collaboration_storytelling/bisharedworkspace/list.html:193`
    - `templates/bi/collaboration_storytelling/bidatastory/list.html:187`
    - `templates/bi/collaboration_storytelling/bidecisionlog/list.html:192`
  - **Fix:** Apply `|escapejs` to all dynamic variables inside JS strings.

- [ ] **`I4`**: Filter & pagination desynchronization in Visual Comments list view.
  - **Files:** `apps/bi/views/CollaborationStorytelling/BiVisualComments.py:80` & `templates/bi/collaboration_storytelling/bivisualcomment/list.html:72-120, 244, 252`
  - **Fix:** Add Story `<select>` to filter card and preserve `&story={{ request.GET.story }}` in pagination links.

- [ ] **`I5`**: Incomplete `--flush` purge in `seed_bi.py:104-167`.
  - **File:** `apps/bi/management/commands/seed_bi.py:104-167`
  - **Fix:** Add `BiDecisionLog.objects.all().delete()`, `BiVisualComment.objects.all().delete()`, `BiDataStory.objects.all().delete()`, and `BiSharedWorkspace.objects.all().delete()` to the flush atomic block.

- [ ] **`I6`**: CSS / Style Injection via unvalidated color fields (L26).
  - **Files:**
    - `apps/bi/models/CollaborationStorytelling/BiSharedWorkspaces.py:60` (`color`)
    - `apps/bi/models/CollaborationStorytelling/BiDecisionLogs.py:104` (`marker_color`)
  - **Fix:** Add `RegexValidator(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", "Enter a valid hex color, e.g. #3b82f6")` to model fields.

- [ ] **`I7`**: Missing composite index on `(tenant, workspace)` in `BiDecisionLog`.
  - **File:** `apps/bi/models/CollaborationStorytelling/BiDecisionLogs.py:132-139`
  - **Fix:** Add `models.Index(fields=["tenant", "workspace"], name="idx_dlog_ten_wspc")` to `BiDecisionLog.Meta.indexes`.

- [ ] **`I8`**: Cross-record integrity check between `dashboard` and `widget`.
  - **Files:**
    - `apps/bi/forms/CollaborationStorytelling/BiVisualComments.py`
    - `apps/bi/forms/CollaborationStorytelling/BiDecisionLogs.py`
  - **Fix:** In form `clean()`, if both `dashboard` and `widget` are provided, verify `widget.dashboard_id == dashboard.id`.

- [ ] **`I9`**: Lack of author / permission gate on comment editing and deletion.
  - **File:** `apps/bi/views/CollaborationStorytelling/BiVisualComments.py:165-214`
  - **Fix:** Ensure `request.user == comment.author or request.user.is_superuser or getattr(request, 'is_tenant_admin', False)`.

- [ ] **`I10`**: Dark Mode missing variants on hardcoded background and surface classes across 10.18 templates.
  - **Files:**
    - `templates/bi/collaboration_storytelling/bidatastory/presentation.html:39, 53, 88`
    - `templates/bi/collaboration_storytelling/bidatastory/detail.html:57, 106, 143`
    - `templates/bi/collaboration_storytelling/bisharedworkspace/detail.html:60`
    - `templates/bi/collaboration_storytelling/bivisualcomment/detail.html:63, 103, 124`
    - `templates/bi/collaboration_storytelling/bidecisionlog/detail.html:50, 58, 66, 75, 81`
    - Form error blocks: `templates/bi/collaboration_storytelling/*/form.html:29`
  - **Fix:** Pair surface classes with `dark:` variants (`dark:bg-slate-800/60`, `dark:bg-slate-900`, `dark:border-slate-700`, `dark:text-slate-200`).

- [ ] **`I11`**: Spacebar navigation & scroll default in presentation mode.
  - **File:** `templates/bi/collaboration_storytelling/bidatastory/presentation.html:131-137`
  - **Fix:** Update keydown listener to check `e.code === 'Space' || e.key === ' '` and call `e.preventDefault()`.

---

## Minor Findings

- [ ] **`M1`**: Self-referencing comment cycle risk.
  - **File:** `apps/bi/forms/CollaborationStorytelling/BiVisualComments.py:51`
  - **Fix:** In `__init__`, exclude `self.instance.pk` from `parent_comment` queryset and validate `parent_comment != self.instance` in `clean()`.

- [ ] **`M2`**: `bi_visual_comment_create` omits `report` and `widget` from `initial` dict when replying to a parent comment.
  - **File:** `apps/bi/views/CollaborationStorytelling/BiVisualComments.py:105-113`
  - **Fix:** Set `initial["report"] = p.report` and `initial["widget"] = p.widget`.

- [ ] **`M3`**: Detail template `bidecisionlog/detail.html` omits rendering of linked `decision.widget`.
  - **File:** `templates/bi/collaboration_storytelling/bidecisionlog/detail.html:95-141`
  - **Fix:** Add grid display entry for linked widget in "Linked Analytical Assets" section.

- [ ] **`M4`**: Redundant SQL `COUNT(*)` in Visual Comment detail view via `{{ replies.count }}`.
  - **File:** `templates/bi/collaboration_storytelling/bivisualcomment/detail.html:114`
  - **Fix:** Replace `{{ replies.count }}` with `{{ replies|length }}` to leverage the evaluated queryset cache.

- [ ] **`M5`**: Full model column loading in filter dropdown querysets in `bi_visual_comment_list`.
  - **File:** `apps/bi/views/CollaborationStorytelling/BiVisualComments.py:67`
  - **Fix:** Use `.only("id", "title")` on story/dashboard dropdown querysets.

- [ ] **`M6`**: Page size standard alignment across list views (`Paginator(qs, 20)` vs NavERP default 15).
  - **Files:** `apps/bi/views/CollaborationStorytelling/*.py`
  - **Fix:** Change `per_page=20` to `per_page=15` across all 4 list views.

- [ ] **`M7`**: Missing composite indexes for filtered status/choice columns `(tenant, priority)` on `BiVisualComment` and `(tenant, default_access_level)` on `BiSharedWorkspace`.
  - **Files:**
    - `apps/bi/models/CollaborationStorytelling/BiVisualComments.py:141`
    - `apps/bi/models/CollaborationStorytelling/BiSharedWorkspaces.py:99`
  - **Fix:** Add composite indexes to Meta of both models.

- [ ] **`M8`**: Unbounded numeric coordinates on `BiVisualComment` (`coordinate_x`, `coordinate_y`).
  - **Files:**
    - `apps/bi/models/CollaborationStorytelling/BiVisualComments.py:102-111`
    - `apps/bi/forms/CollaborationStorytelling/BiVisualComments.py:26-27`
  - **Fix:** Add `min_value=0.0, max_value=100.0` to form fields and `MinValueValidator(0.0), MaxValueValidator(100.0)` to model fields.

- [ ] **`M9`**: Status badge color mapping inconsistency in sub-tables.
  - **Files:** `templates/bi/collaboration_storytelling/bidatastory/detail.html:151` and `bisharedworkspace/detail.html:180`
  - **Fix:** Map `in_review`/`acknowledged` to `badge-info`, `proposed` to `badge-amber`, `revoked` to `badge-red`.

- [ ] **`M10`**: Filter card `<label>` elements missing `for=""` attributes and controls missing matching `id=""`.
  - **Files:** `templates/bi/collaboration_storytelling/*/list.html`
  - **Fix:** Add matching `id` and `for` attributes.

- [ ] **`M11`**: External link in `bidatastory/detail.html:183` missing `rel="noopener noreferrer"`.
  - **File:** `templates/bi/collaboration_storytelling/bidatastory/detail.html:183`
  - **Fix:** Add `rel="noopener noreferrer"`.

- [ ] **`M12`**: RTL alignment on list search inputs.
  - **Files:** `templates/bi/collaboration_storytelling/*/list.html:76-77`
  - **Fix:** Use logical utilities `ps-9` and `start-3`.

- [ ] **`M13`**: Stage navigation buttons missing explicit `type="button"`.
  - **File:** `templates/bi/collaboration_storytelling/bidatastory/presentation.html:23, 27`
  - **Fix:** Add `type="button"`.

- [ ] **`M14`**: Visual Comment detail view displays resolved metadata even when comment status is open/in_review.
  - **File:** `templates/bi/collaboration_storytelling/bivisualcomment/detail.html:163`
  - **Fix:** Guard with `{% if comment.status == 'resolved' and comment.resolved_by %}`.

- [ ] **`M15`**: Visual Comment form validation on status transitions.
  - **File:** `apps/bi/forms/CollaborationStorytelling/BiVisualComments.py:24`
  - **Fix:** Disallow transitioning to `resolved` without setting resolution metadata in `clean()`.
