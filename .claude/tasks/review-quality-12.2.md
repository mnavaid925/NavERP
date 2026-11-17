# Review Findings — Sub-module 12.2: Design Controls & Development (`apps/quality/`)

Changeset reviewed: `8ade3ec32bae7a7208579153bcfb73e15a836f6f...HEAD` (Base from Phase 0 to current build).

All six review passes (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) have concluded. Below is the deduplicated, consolidated, and prioritized action register for Phase 5 (`code-fixer`).

---

## Consolidated Action Register

### Critical Findings

- [ ] **C1**: `templates/quality/designcontrols/design_input/detail.html:189` — `{{ ver.executed_by.get_full_name|default:ver.executed_by.username|default:"—" }}` raises `VariableDoesNotExist` when optional FK `executed_by` is None.
  - *Fix*: Guard with `{% if ver.executed_by %}{{ ver.executed_by.get_full_name|default:ver.executed_by.username }}{% else %}—{% endif %}`.
- [ ] **C2**: `templates/quality/designcontrols/design_verification/detail.html:63` — `{{ verification.executed_by.get_full_name|default:verification.executed_by.username|default:"Pending Execution" }}` raises `VariableDoesNotExist` when optional FK `executed_by` is None.
  - *Fix*: Guard with `{% if verification.executed_by %}{{ verification.executed_by.get_full_name|default:verification.executed_by.username }}{% else %}Pending Execution{% endif %}`.
- [ ] **C3**: `apps/quality/views/DesignControls/DesignProjects.py:213` — `phase_order` includes non-existent `"transfer"` phase, corrupting model state on phase advance.
  - *Fix*: Change `phase_order` to `["planning", "input", "output_verification", "validation", "commercial_closure", "closed"]`.
- [ ] **C4**: `apps/quality/models/DesignControls/DesignInputs.py:107` — `DesignInput.is_verified` property calls `self.verifications.filter(pass_fail_result="pass").exists()`. Bypasses prefetch cache and triggers N+1 queries.
  - *Fix*: Check `_prefetched_objects_cache` before querying: if `"verifications"` is cached, evaluate `any(v.pass_fail_result == "pass" for v in self.verifications.all())`, otherwise check `self.status == "verified"`.
- [ ] **C5**: DHF Freeze / Lock Tamper Bypass on Phase Advance, Gate Approval, and Child Record Creation (`DesignProjects.py:211`, `DesignReviews.py:193`, forms `clean()`).
  - *Fix*: Add `if project.dhf_locked:` guard in `design_project_advance_phase`, `design_review_approve_gate`, and in `clean()` of `DesignInputForm`, `DesignReviewForm`, and `DesignVerificationForm`.

---

### Important Findings

- [ ] **I1**: Model CSS Maps and templates reference non-existent `badge-purple` and `badge-blue` classes (not present in `theme.css`).
  - *Locations*: `DesignProjects.py:64`, `DesignInputs.py:53, 59`, `DesignReviews.py:44`, `DesignVerifications.py:58`, and templates `design_project/list.html:155`, `design_project/detail.html:21`, `dhf_dossier.html:20, 223`.
  - *Fix*: Replace `badge-purple` with `badge-info` or `badge-slate`, and `badge-blue` with `badge-info`.
- [ ] **I2**: Multi-table database writes across `DesignVerification` and `DesignInput` (`DesignVerifications.py:133-143, 179-186`) lack `transaction.atomic()`.
  - *Fix*: Wrap with `with transaction.atomic():`.
- [ ] **I3**: Detail pages omit POST-only Delete action in `.page-actions` header (`design_project/detail.html:45`, `design_input/detail.html:30`, `design_review/detail.html:35`, `design_verification/detail.html:24`).
  - *Fix*: Add status-conditional POST-only delete button/form with `{% csrf_token %}` and confirm dialog.
- [ ] **I4**: Redundant `.count()` queries in `dhf_dossier.html:81, 85, 89` right before iterating.
  - *Fix*: Change `{{ inputs.count }}` etc. to `{{ inputs|length }}`.
- [ ] **I5**: Inefficient unbatched KPI queries across list & detail views (`DesignProjects.py:49-51, 140-153`, etc.).
  - *Fix*: Consolidate with `.aggregate(Count("id", filter=Q(...)))`.
- [ ] **I6**: `TraceabilityMatrix.py:32-36`: when `?project=<id>` is invalid or belongs to another tenant, `selected_project` remains `None` without user feedback.
  - *Fix*: Fallback to `projects.first()` and emit warning message if `selected_project_id` was provided but not found.
- [ ] **I7**: Missing role authorization checks on DHF freeze (`design_project_lock_dhf`) and gate approval (`design_review_approve_gate`).
  - *Fix*: Ensure user is tenant admin, project lead, or quality lead (for lock) and lead reviewer / quality lead / admin (for gate approval).
- [ ] **I8**: Mass assignment in `DesignReviewForm`: `status` and `action_items_resolved` are editable via form POST, bypassing gate approval logic.
  - *Fix*: In `DesignReviewForm.clean()`, reject setting `status="approved"` directly through form edit.
- [ ] **I9**: Audit trail breakage on auto-verified design inputs in `DesignVerifications.py:138-142` & `182-185`.
  - *Fix*: Add `write_audit_log(request.user, ver.primary_input, "verify", tenant=request.tenant)`.
- [ ] **I10**: Unrestricted manual selection of `status="verified"` in `DesignInputForm.clean()`.
  - *Fix*: If `status == "verified"` and instance was not already verified, verify that a passing verification protocol exists, else add error.

---

### Minor Findings

- [ ] **M1**: `dhf_dossier.html:299`: `doc.lifecycle_css` references non-existent property on `ControlledDocument`.
  - *Fix*: Replace with `badge-info`.
- [ ] **M2**: Icon-only action buttons in embedded tables lack `title` attributes (`design_project/detail.html:187, 254, 320`, `design_input/detail.html:191`).
  - *Fix*: Add `title` attributes.
- [ ] **M3**: `apps/quality/models/DesignControls/DesignProjects.py:103`: Add compound index `(tenant, -created_at)` for fast sorting.
  - *Fix*: Add `models.Index(fields=["tenant", "-created_at"])` to `DesignProject.Meta.indexes`.
- [ ] **M4**: `apps/quality/views/DesignControls/DesignProjects.py:234`: Idempotence check missing in `design_project_lock_dhf`.
  - *Fix*: If `project.dhf_locked: return redirect(...)` early.
- [ ] **M5**: `apps/quality/views/DesignControls/DesignVerifications.py:182`: Asymmetric verification status sync when test is modified from pass to fail or deleted.
  - *Fix*: Recalculate `primary_input.status` to `"approved"` or `"in_progress"` if no other passing tests exist.
- [ ] **M6**: Inline JS `confirm()` dialogs on destructive deletion forms in list templates.
  - *Fix*: Standardize escape string or keep standard syntax.
- [ ] **M7**: `DesignReviewForm.clean()`: project lead should not serve as independent reviewer per 21 CFR § 820.30(e).
  - *Fix*: Check `if project and indep and project.project_lead_id == indep.pk: self.add_error("independent_reviewer", "The project lead cannot serve as the independent reviewer.")`.
- [ ] **M8**: Child records can be reassigned to locked DHF projects on edit.
  - *Fix*: Form `clean()` check if project changed to a locked project.
