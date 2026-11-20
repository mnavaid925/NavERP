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


## 2. Explorer Pass

### Verdict
Commit after fixing Critical and Important findings (2 Critical, 6 Important, 3 Minor).

### Critical
1. `templates/quality/trainingcompetency/training_enrollment/detail.html:257` — Unguarded nullable FK lookup in filter argument causes 500 error (Lesson L10): `{{ enrollment.practical_verified_by.get_full_name|default:enrollment.practical_verified_by.username }}` evaluates `enrollment.practical_verified_by.username` as an argument to `default:` before calling the filter. When viewing enrollments for non-practical courses where `practical_verified_by` is None, this raises `VariableDoesNotExist: Failed lookup for key [username] in None`. Fix: Guard with `{% if enrollment.practical_verified_by %}{{ enrollment.practical_verified_by.get_full_name|default:enrollment.practical_verified_by.username }}{% else %}Automated / Exam Assessment{% endif %}`. Also guard line 279 (`waived_by`) with `{% if enrollment.waived_by %}...{% else %}—{% endif %}`.
2. `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:256` — Failed exam score auto-issues formal qualification certification: In `training_enrollment_complete`, when trainee exam score is below passing (`score < course.passing_score`), `is_passed` is set to `False`, but the view continues into `else:`, sets `enrollment.status = "verified"` and calls `_auto_issue_certification()`. Fix: Add failure check before verification to set status="failed", save, audit log, and return redirect with warning.

### Important
1. `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:256, 281` — Multi-table writes not wrapped in atomic transaction: Status updates to `TrainingEnrollment` and auto-issuance of `CompetencyCertification` with audit log are executed without `transaction.atomic()`. Fix: Wrap both `training_enrollment_complete` and `training_enrollment_verify` auto-issuance blocks in `with transaction.atomic():`.
2. `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:267` — Trainee practical self-verification vulnerability: Any authenticated tenant user (including `enrollment.trainee`) can POST to `/training/enrollments/<pk>/verify/` and verify their own practical qualification and auto-issue their own certificate. Fix: Enforce supervisor independence: `if request.user == enrollment.trainee and not request.user.is_tenant_admin: messages.error(...)`.
3. `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:297` — Missing authorization gating on regulatory waivers: Any standard authenticated employee can waive training requirements (including their own). Fix: Restrict `training_enrollment_waive` to tenant administrators or staff.
4. `apps/quality/views/TrainingCompetency/CompetencyCertifications.py:203, 220` — Missing role authorization on renewal and suspension: Any authenticated user can renew or suspend any employee's competency certification via direct POST. Fix: Gate with `if not (request.user.is_tenant_admin or request.user.is_staff): messages.error(...)`.
5. `apps/quality/views/TrainingCompetency/CompetencyMatrices.py:156` — Missing status guard on matrix approval: `competency_matrix_approve` permits approving already approved or retired matrices via direct POST. Fix: Add `if matrix.status != "draft": messages.error(...)`.
6. `apps/quality/views/TrainingCompetency/QualityTrainingCourses.py:182` — Missing status guard on course activation: `training_course_activate` permits activating retired courses. Fix: Add `if course.status not in ("draft", "under_revision"): messages.error(...)`.

### Minor
1. `templates/quality/trainingcompetency/competency_certification/detail.html:27` — "Renew Validity" button hidden for `expiring_soon` status: Condition `{% if certification.status == 'active' or certification.status == 'expired' %}` prevents users from renewing certifications currently flagged as `expiring_soon`. Fix: Update to include `certification.status == 'expiring_soon'`.
2. `templates/quality/trainingcompetency/training_course/list.html:59-108, 205` — View/template filter drift on `controlled_document`: `training_course_list` view passes `documents` and `selected_doc` in context and filters on `controlled_document`, but `training_course/list.html` omits the document dropdown from the filter grid and omits `&controlled_document={{ selected_doc }}` from the pagination links. Fix: Add `<select name="controlled_document">` to the filter form and append to pagination links.
3. `apps/quality/views/TrainingCompetency/CompetencyCertifications.py:348, 386` — Context key naming divergence from contract: In `training_compliance_dashboard`, context keys are `"expiring_list"` and `"dept_metrics"` (contract noted `expiring_certifications` and `department_metrics`). In `employee_training_dossier`, context key is `"certifications"` (contract noted `active_certifications`). Fix: Provide contract keys as aliases in view context dicts.

### Done well
- Strict tenant scoping across all models (`TenantNumbered`), views (`quality_scope`, `quality_object`), forms (`reject_foreign`, tenant-filtered querysets), and foreign key validations.
- Navigation `LIVE_LINKS["12.12"]` precisely maps all 5 sub-module areas.
- Clean seeder integration with 100% idempotent seeding.


## 3. Frontend Reviewer Pass

### Verdict
Commit after fixing Critical and Important findings (2 Critical, 2 Important, 3 Minor).

### Critical
1. `templates/quality/trainingcompetency/training_enrollment/detail.html:257` — Missing `{% if %}` null-guard on nullable FK inside filter argument (Lesson L10): `enrollment.practical_verified_by` accessed as `default:enrollment.practical_verified_by.username` when `None`. Fix: Guard with `{% if enrollment.practical_verified_by %}{{ enrollment.practical_verified_by.get_full_name|default:enrollment.practical_verified_by.username }}{% else %}—{% endif %}`.
2. `templates/quality/trainingcompetency/training_enrollment/detail.html:279` — Missing `{% if %}` null-guard on nullable FK inside filter argument (Lesson L10): `enrollment.waived_by` accessed as `default:enrollment.waived_by.username` when `None`. Fix: Guard with `{% if enrollment.waived_by %}{{ enrollment.waived_by.get_full_name|default:enrollment.waived_by.username }}{% else %}—{% endif %}`.

### Important
1. `templates/quality/trainingcompetency/{competency_matrix,training_course,training_enrollment,competency_certification}/form.html:28` — Non-existent `.alert` and `.alert-danger` classes in form templates (Lesson L13 / L33): neither `.alert` nor `.alert-danger` exists in `static/css/theme.css`. Fix: Replace `<div class="alert alert-danger mb-6">` with `<div class="p-3 mb-6 rounded-md bg-red-50 border border-red-200 text-red-700 text-sm">` and wrap errors in `<div class="form-error font-medium">`.
2. `templates/quality/trainingcompetency/{competency_matrix,training_course,training_enrollment,competency_certification}/detail.html` — Detail pages lack explicit "Back to List" button in `.page-actions`. Fix: In each detail template's `.page-actions` container, add `<a href="{% url 'quality:<entity>_list' %}" class="btn btn-outline"><i data-lucide="arrow-left"></i> Back to ...</a>`.

### Minor
1. `templates/quality/trainingcompetency/competency_certification/detail.html:211`, `employee_training_dossier.html:45` — Dark mode styling on modal and profile banner: Add `dark:bg-slate-800 dark:text-slate-100 dark:border-slate-700` and `dark:bg-slate-800/60 dark:border-slate-700`.
2. `templates/quality/trainingcompetency/{competency_matrix,training_course,training_enrollment,competency_certification}/list.html` — Semantic HTML in `.empty-state` blocks: Use `<h3 class="font-medium text-slate-800">` and `<p class="text-sm text-slate-500">` inside empty-state to align with theme.css rules.
3. List templates — Explicit `aria-label` on icon-only action buttons: Add `aria-label` attributes alongside existing `title` attributes.

### Done well
- 100% adherence to theme.css color-named badge standards (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`). Zero non-existent semantic badges.
- Zero multi-line `{# ... #}` comment leaks (L2).
- All list pages guard pagination with `has_previous`/`has_next` (L9) and preserve search/filter query parameters.
- All FK filter comparisons use `|stringformat:"d"`. All tables wrapped in `.table-wrap`.


## 4. Performance Reviewer Pass

### Verdict
Commit after fixing Critical and Important findings (1 Critical, 4 Important, 4 Minor).

### Critical
1. `apps/quality/views/TrainingCompetency/CompetencyCertifications.py:321-332` — Dashboard department breakdown executes 4 queries per department in a Python loop (24 queries for 6 departments). Fix: Consolidate into a single SQL query using `.values("course__competency_matrix__department__id", "course__competency_matrix__department__name")` and conditional aggregation (`Count("id")`, `Count("id", filter=Q(status="verified"))`) on `TrainingEnrollment`.

### Important
1. `apps/quality/views/TrainingCompetency/QualityTrainingCourses.py:112` — N+1 query in `training_course_detail` on `issued_certifications` trainee rendering: calling `.filter(status="active")` bypasses prefetch cache. Fix: Add `.select_related("trainee")` on the filtered queryset.
2. `apps/quality/views/TrainingCompetency/CompetencyMatrices.py:93` — N+1 query in `competency_matrix_detail` on `certified_holders` trainee rendering: calling `.filter(status="active")` bypasses prefetch cache. Fix: Add `.select_related("trainee")` on the filtered queryset.
3. `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:231, 267` — Multi-table mutations in `training_enrollment_complete` and `training_enrollment_verify` lack `transaction.atomic`. Fix: Wrap mutations in `transaction.atomic()`.
4. `apps/quality/views/TrainingCompetency/` — KPI stat card queries in list views and dashboard not consolidated via `.aggregate()`. Fix: Consolidate separate count queries into single `.aggregate()` calls with conditional `Count('id', filter=Q(...))`.

### Minor
1. `apps/quality/models/TrainingCompetency/` — Missing composite indexes for model default ordering and hot filter combinations (`(tenant, -assigned_date, -created_at)`, `(tenant, status, due_date)`, `(tenant, -issue_date, -created_at)`, `(tenant, status, valid_until)`).
2. `apps/quality/views/TrainingCompetency/CompetencyCertifications.py:365` — Heavy User model query in `employee_training_dossier` without column deferral. Fix: Add `.only("id", "username", "first_name", "last_name")`.
3. `templates/quality/trainingcompetency/` — Redundant `.count` calls in templates on evaluated querysets instead of `|length`. Fix: Use `|length` on querysets iterated in the same template.
4. `templates/quality/trainingcompetency/training_course/detail.html` — Repeated property count queries on `QualityTrainingCourse` in detail template. Fix: Precompute in view and pass as context dict.

### Done well
- Strict multi-tenancy scoping across all queries.
- Proper pagination (`Paginator(qs, 15)`) applied after filters.
- Primary list `select_related` coverage on foreign keys.
- Safe idempotent seeding within transaction.atomic.


## 5. QA Smoke Tester Pass

### Verdict
Conditional Fail (2 Critical, 1 Important, 1 Minor). 50 of 54 runtime checks passed.

### Critical
1. `templates/quality/trainingcompetency/training_enrollment/detail.html:257` — Template Variable Lookup Crash (HTTP 500) on Verified Enrollments without Practical Evaluator: `enrollment.practical_verified_by.username` in `default:` argument raises `VariableDoesNotExist` when `practical_verified_by` is None. Fix: Guard with `{% if enrollment.practical_verified_by %}` block.
2. `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:240-261` — GxP Regulatory Defect: Training Completion View Issues Certification to Trainees Who Failed Exam. Candidate scoring below passing score has status set to `verified` and receives formal `CompetencyCertification`. Fix: Check `if not enrollment.is_passed: enrollment.status = "failed"; enrollment.save(); write_audit_log(...); messages.warning(...); return redirect(...)`.

### Important
1. `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:267-285` — Segregation of Duties Violation: Trainee Can Self-Verify Their Own Practical Competency. Trainee can submit POST to verify their own practical qualification. Fix: Add evaluator independence check `if request.user == enrollment.trainee and not request.user.is_tenant_admin: messages.error(...); return redirect(...)`.

### Minor
1. `templates/quality/trainingcompetency/training_enrollment/detail.html:94` — Missing Default Fallback in Enrollment Detail Exam Score Display: passing score label displayed even when passing score is 0. Fix: Guard label with `if enrollment.course.passing_score > 0`.

### Done well
- 100% Cross-Tenant IDOR Isolation: 17 of 17 cross-tenant IDOR attack probes returned strict 404 Not Found.
- Zero raw template comment leaks on all 16 tested GET views.
- Robust resilience/fuzzing: all 8 fuzz tests with junk parameters returned HTTP 200 without crashes.
- CSV exports fully compliant.
- State machines for Matrix approve/retire, Course activate/retire, and Certification renew/suspend transition cleanly.
