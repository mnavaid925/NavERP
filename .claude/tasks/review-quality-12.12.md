# Module 12.12 Code Review Findings (Sub-module: Training & Competency Management)

Range: `bc9fc6d0e8137f54214ffd3af0019c12e69c6c72...HEAD`

## 1. Code Reviewer Pass

### Verdict
Commit after fixing Critical and Important findings. (2 Critical, 6 Important, 3 Minor).

### Critical
1. `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:256` — Failing exam score (`score < passing_score`, `is_passed=False`) bypasses failure branch and executes `else:`, marking the enrollment `status="verified"` and auto-issuing a formal `CompetencyCertification`. Fix: Add `if not enrollment.is_passed: enrollment.status = "failed"; enrollment.save(); write_audit_log(request.user, enrollment, "complete", tenant=request.tenant); messages.warning(request, f"Score {enrollment.score}% failed to meet passing score of {enrollment.course.passing_score}%."); return redirect("quality:training_enrollment_detail", pk=enrollment.pk)` before the practical verification / auto-issue branch.
2. `templates/quality/trainingcompetency/training_enrollment/detail.html:257` — Unguarded nullable FK inside `|default:` filter argument: `{{ enrollment.practical_verified_by.get_full_name|default:enrollment.practical_verified_by.username }}` raises `VariableDoesNotExist: Failed lookup for key [username] in None` (Lesson L10) and 500s when viewing verified enrollments for non-practical courses where `practical_verified_by` is None. Fix: Guard with `{% if enrollment.practical_verified_by %}{{ enrollment.practical_verified_by.get_full_name|default:enrollment.practical_verified_by.username }}{% else %}Automated / Exam Assessment{% endif %}`.

### Important
1. `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:256, 281` — Multi-model writes updating `TrainingEnrollment` and auto-issuing `CompetencyCertification` with audit log are not wrapped in `transaction.atomic()`. Fix: Wrap both `training_enrollment_complete` and `training_enrollment_verify` auto-issuance blocks in `with transaction.atomic():`.
2. `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:267` — Trainee independence & self-approval bypass: any authenticated tenant user, including `enrollment.trainee`, can call `POST /training/enrollments/<pk>/verify/` to evaluate and verify their own practical OJT demonstration and auto-issue their own certification. Fix: Enforce `if request.user == enrollment.trainee and not request.user.is_tenant_admin: messages.error(request, "Trainees cannot verify their own practical qualification."); return redirect("quality:training_enrollment_detail", pk=enrollment.pk)`.
3. `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:297` — Missing authorization gating on regulatory training waivers: any regular user can waive mandatory training requirements (including their own). Fix: Restrict `training_enrollment_waive` to tenant administrators (`@tenant_admin_required`) or authorized quality supervisors.
4. `apps/quality/views/TrainingCompetency/CompetencyCertifications.py:203, 220` — Missing authorization gating on certification renewal and suspension: any authenticated user can renew or suspend any employee's certification. Fix: Restrict `competency_certification_renew` and `competency_certification_suspend` to tenant admins or authorized certifiers (`request.user.is_tenant_admin`).
5. `apps/quality/views/TrainingCompetency/CompetencyMatrices.py:156` — `competency_matrix_approve` lacks view-level status guard: allows approving already approved or retired matrices via direct POST. Fix: Add `if matrix.status != "draft": messages.error(request, "Only draft matrices can be approved."); return redirect("quality:competency_matrix_detail", pk=matrix.pk)`.
6. `apps/quality/views/TrainingCompetency/QualityTrainingCourses.py:182` — `training_course_activate` lacks view-level status guard: allows activating retired courses. Fix: Add `if course.status not in ("draft", "under_revision"): messages.error(request, "Only draft or under-revision courses can be activated."); return redirect("quality:training_course_detail", pk=course.pk)`.

### Minor
1. `templates/quality/trainingcompetency/competency_certification/detail.html:27` — "Renew Validity" button condition `{% if certification.status == 'active' or certification.status == 'expired' %}` hides the renewal button when database status is `expiring_soon`. Fix: Update to `{% if certification.status == 'active' or certification.status == 'expiring_soon' or certification.status == 'expired' %}`.
2. `templates/quality/trainingcompetency/training_enrollment/detail.html:279` — Nullable `waived_by` inside filter argument `{{ enrollment.waived_by.get_full_name|default:enrollment.waived_by.username }}` lacks guard. Fix: Wrap in `{% if enrollment.waived_by %}...{% else %}—{% endif %}`.
3. `apps/quality/models/TrainingCompetency/CompetencyCertifications.py:141` — Certificate verification hash formula is fragmented with different seed formats across `CompetencyCertification.save()`, `_auto_issue_certification`, and `renew`. Fix: Define a unified `generate_certificate_hash()` helper method on `CompetencyCertification` and call it consistently.

### Done well
- Strict multi-tenancy isolation across all 4 models (`tenant` FK on models inheriting `TenantNumbered`, `quality_scope` and `quality_object` in views, `reject_foreign` and tenant-scoped querysets on all ModelForms).
- Core-spine reuse: `core.Party` for external course providers, `core.OrgUnit` for departments, `accounts.User` for trainees and certifiers, with links to `ControlledDocument`, `DocumentChangeOrder`, and `CapaAction`.
- All design system badge classes strictly adhere to allowed palettes (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`) and all 38 URLs reverse cleanly.

### Suggested tests
- `apps/quality/tests/test_training_competency_views.py`:
  - Assert failing exam score (`score < passing_score`) sets `status="failed"` and does NOT issue a certification.
  - Assert successful exam score on non-practical course sets `status="verified"` and auto-issues active certification.
  - Assert `training_enrollment_detail` renders 200 without error when `practical_verified_by` is None.
  - Assert practical course moves to `completed` and requires supervisor verification.
- `apps/quality/tests/test_training_competency_security.py`:
  - Assert cross-tenant IDOR access to 12.12 detail/action views returns 404.
  - Assert trainee cannot verify their own practical demonstration (`request.user == enrollment.trainee`).
  - Assert non-admin cannot waive training enrollments or delete records.

### Routing
- performance-reviewer: In `apps/quality/views/TrainingCompetency/CompetencyCertifications.py:319-332` (`training_compliance_dashboard`), department metrics loop executes 4 queries per department across `departments[:6]` (24+ queries in view). Consolidate into single aggregate/annotated query.
- security-reviewer: In `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:267, 297` and `CompetencyCertifications.py:203, 220`, verify role gating and auditor/trainee independence on verification, waiver, renewal, and suspension actions.
- frontend-reviewer: In `templates/quality/trainingcompetency/competency_certification/detail.html:27`, verify "Renew Validity" visibility for `expiring_soon` status, and add copy-to-clipboard control for the SHA-256 certificate hash.
