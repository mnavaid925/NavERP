# Review Findings — Sub-module 12.2: Design Controls & Development (`apps/quality/`)

Changeset reviewed: `8ade3ec32bae7a7208579153bcfb73e15a836f6f...HEAD` (Base from Phase 0 to current build).

All six review passes (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) have concluded. Below is the deduplicated, consolidated, and prioritized action register for Phase 5 (`code-fixer`).

---

## Consolidated Action Register

### Critical Findings

- [x] **C1**: `templates/quality/designcontrols/design_input/detail.html:189` — `{{ ver.executed_by.get_full_name|default:ver.executed_by.username|default:"—" }}` raises `VariableDoesNotExist` when optional FK `executed_by` is None.
  - *Fix*: Guard with `{% if ver.executed_by %}{{ ver.executed_by.get_full_name|default:ver.executed_by.username }}{% else %}—{% endif %}`.
  - *Status*: [x] fixed — fix(quality): guard executed_by in design input detail verifications list
- [x] **C2**: `templates/quality/designcontrols/design_verification/detail.html:63` — `{{ verification.executed_by.get_full_name|default:verification.executed_by.username|default:"Pending Execution" }}` raises `VariableDoesNotExist` when optional FK `executed_by` is None.
  - *Fix*: Guard with `{% if verification.executed_by %}{{ verification.executed_by.get_full_name|default:verification.executed_by.username }}{% else %}Pending Execution{% endif %}`.
  - *Status*: [x] fixed — fix(quality): guard executed_by in design verification detail template
- [x] **C3**: `apps/quality/views/DesignControls/DesignProjects.py:213` — `phase_order` includes non-existent `"transfer"` phase, corrupting model state on phase advance.
  - *Fix*: Change `phase_order` to `["planning", "input", "output_verification", "validation", "commercial_closure", "closed"]`.
  - *Status*: [x] fixed — fix(quality): correct phase_order choices in design_project_advance_phase
- [x] **C4**: `apps/quality/models/DesignControls/DesignInputs.py:107` — `DesignInput.is_verified` property calls `self.verifications.filter(pass_fail_result="pass").exists()`. Bypasses prefetch cache and triggers N+1 queries.
  - *Fix*: Check `_prefetched_objects_cache` before querying: if `"verifications"` is cached, evaluate `any(v.pass_fail_result == "pass" for v in self.verifications.all())`, otherwise check `self.status == "verified"`.
  - *Status*: [x] fixed — perf(quality): optimize DesignInput.is_verified to use prefetch cache
- [x] **C5**: DHF Freeze / Lock Tamper Bypass on Phase Advance, Gate Approval, and Child Record Creation (`DesignProjects.py:211`, `DesignReviews.py:193`, forms `clean()`).
  - *Fix*: Add `if project.dhf_locked:` guard in `design_project_advance_phase`, `design_review_approve_gate`, and in `clean()` of `DesignInputForm`, `DesignReviewForm`, and `DesignVerificationForm`.
  - *Status*: [x] fixed — security(quality): guard phase advance, gate approval, and child forms when DHF is locked

---

### Important Findings

- [x] **I1**: Model CSS Maps and templates reference non-existent `badge-purple` and `badge-blue` classes (not present in `theme.css`).
  - *Locations*: `DesignProjects.py:64`, `DesignInputs.py:53, 59`, `DesignReviews.py:44`, `DesignVerifications.py:58`, and templates `design_project/list.html:155`, `design_project/detail.html:21`, `dhf_dossier.html:20, 223`.
  - *Fix*: Replace `badge-purple` with `badge-info` or `badge-slate`, and `badge-blue` with `badge-info`.
  - *Status*: [x] fixed — fix(quality): replace non-existent badge classes in models and templates with badge-info and badge-slate
- [x] **I2**: Multi-table database writes across `DesignVerification` and `DesignInput` (`DesignVerifications.py:133-143, 179-186`) lack `transaction.atomic()`.
  - *Fix*: Wrap with `with transaction.atomic():`.
  - *Status*: [x] fixed — fix(quality): wrap multi-table verification and input writes in transaction.atomic
- [x] **I3**: Detail pages omit POST-only Delete action in `.page-actions` header (`design_project/detail.html:45`, `design_input/detail.html:30`, `design_review/detail.html:35`, `design_verification/detail.html:24`).
  - *Fix*: Add status-conditional POST-only delete button/form with `{% csrf_token %}` and confirm dialog.
  - *Status*: [x] fixed — feat(quality): add POST delete button in detail headers for project, input, review, and verification
- [x] **I4**: Redundant `.count()` queries in `dhf_dossier.html:81, 85, 89` right before iterating.
  - *Fix*: Change `{{ inputs.count }}` etc. to `{{ inputs|length }}`.
  - *Status*: [x] fixed — perf(quality): use length filter instead of count in dhf dossier
- [x] **I5**: Inefficient unbatched KPI queries across list & detail views (`DesignProjects.py:49-51, 140-153`, etc.).
  - *Fix*: Consolidate with `.aggregate(Count("id", filter=Q(...)))`.
  - *Status*: [x] fixed — perf(quality): consolidate unbatched KPI count queries with aggregate
- [x] **I6**: `TraceabilityMatrix.py:32-36`: when `?project=<id>` is invalid or belongs to another tenant, `selected_project` remains `None` without user feedback.
  - *Fix*: Fallback to `projects.first()` and emit warning message if `selected_project_id` was provided but not found.
  - *Status*: [x] fixed — fix(quality): fallback and emit warning on invalid project in traceability matrix
- [x] **I7**: Missing role authorization checks on DHF freeze (`design_project_lock_dhf`) and gate approval (`design_review_approve_gate`).
  - *Fix*: Ensure user is tenant admin, project lead, or quality lead (for lock) and lead reviewer / quality lead / admin (for gate approval).
  - *Status*: [x] fixed — security(quality): add role authorization check to design_project_lock_dhf and design_review_approve_gate
- [x] **I8**: Mass assignment in `DesignReviewForm`: `status` and `action_items_resolved` are editable via form POST, bypassing gate approval logic.
  - *Fix*: In `DesignReviewForm.clean()`, reject setting `status="approved"` directly through form edit.
  - *Status*: [x] fixed — security(quality): prevent setting approved status directly via DesignReviewForm
- [x] **I9**: Audit trail breakage on auto-verified design inputs in `DesignVerifications.py:138-142` & `182-185`.
  - *Fix*: Add `write_audit_log(request.user, ver.primary_input, "verify", tenant=request.tenant)`.
  - *Status*: [x] fixed — fix(quality): record audit log when design input is auto-verified
- [x] **I10**: Unrestricted manual selection of `status="verified"` in `DesignInputForm.clean()`.
  - *Fix*: If `status == "verified"` and instance was not already verified, verify that a passing verification protocol exists, else add error.
  - *Status*: [x] fixed — security(quality): require passing verification protocol to set design input status to verified

---

### Minor Findings

- [x] **M1**: `dhf_dossier.html:299`: `doc.lifecycle_css` references non-existent property on `ControlledDocument`.
  - *Fix*: Replace with `badge-info`.
  - *Status*: [x] fixed — fix(quality): replace non-existent doc.lifecycle_css with badge-info in dhf dossier
- [x] **M2**: Icon-only action buttons in embedded tables lack `title` attributes (`design_project/detail.html:187, 254, 320`, `design_input/detail.html:191`).
  - *Fix*: Add `title` attributes.
  - *Status*: [x] fixed — fix(quality): add title attributes to icon buttons in design project and input details
- [x] **M3**: `apps/quality/models/DesignControls/DesignProjects.py:103`: Add compound index `(tenant, -created_at)` for fast sorting.
  - *Fix*: Add `models.Index(fields=["tenant", "-created_at"])` to `DesignProject.Meta.indexes`.
  - *Status*: [x] fixed — perf(quality): add compound index on tenant and created_at to DesignProject
- [x] **M4**: `apps/quality/views/DesignControls/DesignProjects.py:234`: Idempotence check missing in `design_project_lock_dhf`.
  - *Fix*: If `project.dhf_locked: return redirect(...)` early.
  - *Status*: [x] fixed — fix(quality): add idempotence check to design_project_lock_dhf
- [x] **M5**: `apps/quality/views/DesignControls/DesignVerifications.py:182`: Asymmetric verification status sync when test is modified from pass to fail or deleted.
  - *Fix*: Recalculate `primary_input.status` to `"approved"` or `"in_progress"` if no other passing tests exist.
  - *Status*: [x] fixed — fix(quality): synchronize design input verified status on protocol update and delete
- [x] **M6**: Inline JS `confirm()` dialogs on destructive deletion forms in list templates.
  - *Fix*: Standardize escape string or keep standard syntax.
  - *Status*: [x] fixed — verified: all list templates already standardize on safe |escapejs confirm dialogs
- [x] **M7**: `DesignReviewForm.clean()`: project lead should not serve as independent reviewer per 21 CFR § 820.30(e).
  - *Fix*: Check `if project and indep and project.project_lead_id == indep.pk: self.add_error("independent_reviewer", "The project lead cannot serve as the independent reviewer.")`.
  - *Status*: [x] fixed — security(quality): forbid project lead from acting as independent reviewer
- [x] **M8**: Child records can be reassigned to locked DHF projects on edit.
  - *Fix*: Form `clean()` check if project changed to a locked project.
  - *Status*: [x] fixed — security(quality): prevent reassigning child records to/from locked DHF projects
