# Review Findings — Sub-module 12.2: Design Controls & Development (`apps/quality/`)

Changeset reviewed: `8ade3ec32bae7a7208579153bcfb73e15a836f6f...HEAD` (Base from Phase 0 to current build).

---

## 1. Code Reviewer Pass (`code-reviewer`)

### Critical
1. `templates/quality/designcontrols/design_input/detail.html:189` — `{{ ver.executed_by.get_full_name|default:ver.executed_by.username|default:"—" }}` 500s with `VariableDoesNotExist` when optional FK `executed_by` is None. Fix: Guard with `{% if ver.executed_by %}{{ ver.executed_by.get_full_name|default:ver.executed_by.username }}{% else %}—{% endif %}` (L10).
2. `templates/quality/designcontrols/design_verification/detail.html:63` — `{{ verification.executed_by.get_full_name|default:verification.executed_by.username|default:"Pending Execution" }}` 500s with `VariableDoesNotExist` when optional FK `executed_by` is None. Fix: Guard with `{% if verification.executed_by %}{{ verification.executed_by.get_full_name|default:verification.executed_by.username }}{% else %}Pending Execution{% endif %}` (L10).
3. `apps/quality/views/DesignControls/DesignProjects.py:213` — `phase_order` includes `"transfer"`, which does not exist in `DesignProject.CURRENT_PHASE_CHOICES`, corrupting model phase state and causing subsequent form edits to fail validation. Fix: Change `phase_order` to `["planning", "input", "output_verification", "validation", "commercial_closure", "closed"]`.

### Important
4. `apps/quality/views/DesignControls/DesignProjects.py:211` — `design_project_advance_phase` lacks a view-level status check for locked projects (`dhf_locked=True`) or closed projects. Fix: Add guard `if project.dhf_locked: messages.error(request, "Cannot advance phase on a locked Design History File."); return redirect("quality:design_project_detail", pk=project.pk)`.
5. `apps/quality/views/DesignControls/DesignReviews.py:193` — `design_review_approve_gate` lacks view-level status guards for locked projects or already-approved reviews. Fix: Add guard `if review.project.dhf_locked or review.status == "approved": messages.error(request, "Review cannot be approved in its current state."); return redirect("quality:design_review_detail", pk=review.pk)`.
6. `apps/quality/views/DesignControls/DesignVerifications.py:135` & `apps/quality/views/DesignControls/DesignVerifications.py:180` — Multi-table database writes updating both `DesignVerification` and `DesignInput` (`ver.primary_input.status = "verified"`) are not wrapped in `transaction.atomic()`. Fix: Wrap the form save and `primary_input.save()` in `with transaction.atomic():`.
7. `templates/quality/designcontrols/design_project/detail.html:45` — Detail page omits POST-only Delete action in `page-actions`, violating the CRUD completeness contract. Fix: Add a status-conditional POST-only Delete form with `{% csrf_token %}` and `confirm(...)` to the detail page header.
8. `templates/quality/designcontrols/design_input/detail.html:30` — Detail page omits POST-only Delete action in `page-actions`. Fix: Add a status-conditional POST-only Delete form with `{% csrf_token %}` and `confirm(...)` to the detail page header.
9. `templates/quality/designcontrols/design_review/detail.html:35` — Detail page omits POST-only Delete action in `page-actions`. Fix: Add a status-conditional POST-only Delete form with `{% csrf_token %}` and `confirm(...)` to the detail page header.
10. `templates/quality/designcontrols/design_verification/detail.html:24` — Detail page omits POST-only Delete action in `page-actions`. Fix: Add a status-conditional POST-only Delete form with `{% csrf_token %}` and `confirm(...)` to the detail page header.
11. `apps/quality/models/DesignControls/DesignProjects.py:64` & `apps/quality/models/DesignControls/DesignInputs.py:53, 59` & `apps/quality/models/DesignControls/DesignReviews.py:44` & `apps/quality/models/DesignControls/DesignVerifications.py:58` — CSS maps use non-existent classes `badge-purple` and `badge-blue` (not present in `theme.css`), rendering badges unstyled (L33). Fix: Map `"badge-purple"` to `"badge-info"` or `"badge-slate"`, and `"badge-blue"` to `"badge-info"`.
12. `templates/quality/designcontrols/design_project/list.html:155` & `templates/quality/designcontrols/design_project/detail.html:21` & `templates/quality/designcontrols/dhf_dossier.html:20, 223` — Templates use non-existent class `badge-purple`. Fix: Replace `badge-purple` with a supported theme class (`badge-slate` or `badge-info`).

### Minor
13. `templates/quality/designcontrols/dhf_dossier.html:299` — `doc.lifecycle_css` references a non-existent property on `ControlledDocument`, resulting in empty CSS class for specifications. Fix: Replace `badge {{ doc.lifecycle_css }}` with `badge badge-info` or add `@property def lifecycle_css` to `ControlledDocument`.
14. `apps/quality/views/DesignControls/DesignVerifications.py:182` — Editing a verification protocol from `"pass"` to `"fail"` or deleting it does not check if `primary_input.status` should revert back to `"approved"` if no other passing test exists. Fix: Recalculate `primary_input.status` when test result is modified or deleted.
15. `apps/quality/views/DesignControls/DesignProjects.py:234` — `design_project_lock_dhf` re-executes redundant lock updates if already locked. Fix: Check `if project.dhf_locked:` and return early.

---

## 2. Explorer Pass (`explorer`)

### Critical
- Confirmed C1: `templates/quality/designcontrols/design_input/detail.html:189` — `{{ ver.executed_by.get_full_name|default:ver.executed_by.username|default:"—" }}` throws `VariableDoesNotExist` when optional FK `executed_by` is None.
- Confirmed C2: `templates/quality/designcontrols/design_verification/detail.html:63` — `{{ verification.executed_by.get_full_name|default:verification.executed_by.username|default:"Pending Execution" }}` throws `VariableDoesNotExist` when optional FK `executed_by` is None.
- Confirmed C3: `apps/quality/views/DesignControls/DesignProjects.py:213` — `phase_order` includes non-existent `"transfer"` phase, corrupting model state on phase advance.

### Important
- Confirmed I4: `apps/quality/models/DesignControls/DesignProjects.py:64` and related models — CSS maps define non-existent `badge-purple` and `badge-blue` classes (L33).
- Confirmed I5: Templates hardcode non-existent `badge-purple` class.
- Confirmed I6: `apps/quality/views/DesignControls/DesignProjects.py:211` — `design_project_advance_phase` lacks DHF lock guard.
- Confirmed I7: `apps/quality/views/DesignControls/DesignReviews.py:193` — `design_review_approve_gate` lacks DHF lock guard and redundant approval check.
- Confirmed I8: `apps/quality/views/DesignControls/DesignVerifications.py:135, 180` — Multi-table updates across `DesignVerification` and `DesignInput` lack `transaction.atomic()`.
- Confirmed I9: `templates/quality/designcontrols/{design_project,design_input,design_review,design_verification}/detail.html` — Detail page headers lack POST-only delete actions.

### Minor
- Confirmed M10: `templates/quality/designcontrols/dhf_dossier.html:299` — `doc.lifecycle_css` missing property method on `ControlledDocument`.
- Confirmed M11: `apps/quality/views/DesignControls/DesignVerifications.py:180, 200` — Asymmetric verification status sync when tests fail or are deleted.
- Confirmed M12: `apps/quality/views/DesignControls/DesignProjects.py:234` — Idempotence check missing in `design_project_lock_dhf`.

---

## 3. Frontend Reviewer Pass (`frontend-reviewer`)

### Critical
- Confirmed C1: `templates/quality/designcontrols/design_input/detail.html:189` — `ver.executed_by` None lookup crash (L10).
- Confirmed C2: `templates/quality/designcontrols/design_verification/detail.html:63` — `verification.executed_by` None lookup crash (L10).

### Important
- Confirmed I4 / I5: Model CSS maps and templates define/hardcode non-existent `badge-purple` and `badge-blue` classes (L33).
- Confirmed I9: `templates/quality/designcontrols/{design_project,design_input,design_review,design_verification}/detail.html` — Detail page headers lack POST-only delete actions.

### Minor
- Confirmed M10: `templates/quality/designcontrols/dhf_dossier.html:299` — `doc.lifecycle_css` renders empty.
- M16: `templates/quality/designcontrols/design_project/detail.html:187, 254, 320` & `design_input/detail.html:191` — Icon-only action buttons in embedded tables lack `title` or `aria-label` attributes. Fix: Add `title="View ..."` attributes.

---

## 4. Performance Reviewer Pass (`performance-reviewer`)

### Critical
- C17: `apps/quality/models/DesignControls/DesignInputs.py:107` — `DesignInput.is_verified` property calls `self.verifications.filter(pass_fail_result="pass").exists()`. This forces a new SQL query per row, bypassing Django's prefetch cache in list templates, RTM matrix, and DHF dossier (`1 + N` queries). Fix: Check `_prefetched_objects_cache` before querying, or evaluate from prefetched list.

### Important
- I18: `templates/quality/designcontrols/dhf_dossier.html:81, 85, 89` — Calling `.count` on QuerySets in template right before iterating over them issues redundant SQL `SELECT COUNT(*)` queries. Fix: Use `|length`.
- I19: `apps/quality/views/DesignControls/DesignProjects.py:49-51, 140-153` and related list/detail views — Multiple individual `.count()` queries execute for KPI stat cards instead of unified conditional aggregates (`aggregate(Count("id", filter=Q(...)))`).

### Minor
- Confirmed I8 / M1: `apps/quality/views/DesignControls/DesignVerifications.py:133-143, 179-186` — Multi-model writes (`DesignVerification` + `DesignInput`) lack `with transaction.atomic():`.
- M20: `apps/quality/models/DesignControls/DesignProjects.py:103` — Recommend compound index `(tenant, -created_at)` for fast sorting on large project datasets.

---

## 5. QA Smoke Tester Pass (`qa-smoke-tester`)

### Critical
- None. All 30 endpoints resolved, 0 comment leaks, zero 500 errors on valid and junk parameter sweeps, cross-tenant IDOR returned HTTP 404.

### Important
- Confirmed C17 / I1: `apps/quality/models/DesignControls/DesignInputs.py:107-108` & `apps/quality/views/DesignControls/TraceabilityMatrix.py:47-49` — `is_verified` property triggers N+1 query in `TraceabilityMatrix.py`. Fix: Evaluate using prefetched list or `status == "verified"`.
- I21: `apps/quality/views/DesignControls/TraceabilityMatrix.py:32-36` — When `?project=<id>` is invalid or belongs to another tenant, `selected_project` remains `None` without feedback. Fix: Fall back to `projects.first()` with warning message `messages.warning(request, "Selected design project was not found.")`.

### Minor
- M22: `apps/quality/views/DesignControls/` — Filter context naming variability (`selected_class` vs `selected_project` vs `selected_activity`).
- M23: `templates/quality/designcontrols/{design_project,design_input,design_review,design_verification}/list.html` — Inline `onsubmit="return confirm(...)"` on deletion forms.

