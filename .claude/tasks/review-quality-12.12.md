# Module 12.12 Review Findings (Sub-module: Training & Competency Management)

Range: `bc9fc6d0e8137f54214ffd3af0019c12e69c6c72...HEAD`

## Consolidated Review Findings

### Critical
- [ ] `C1`: `templates/quality/trainingcompetency/training_enrollment/detail.html:257, 279` — Unguarded nullable FK lookups in filter arguments (`default:enrollment.practical_verified_by.username` and `default:enrollment.waived_by.username`) raise `VariableDoesNotExist` (Lesson L10) and 500s when viewing verified enrollments for non-practical courses or enrollments without waivers. Fix: Guard both with `{% if enrollment.practical_verified_by %}` and `{% if enrollment.waived_by %}`.
- [ ] `C2`: `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:240-261` — GxP Regulatory Defect: Failing exam score (`score < passing_score`, `is_passed=False`) bypasses failure branch and executes `else:`, marking the enrollment `status="verified"` and auto-issuing a formal `CompetencyCertification`. Fix: Add failure branch before the practical verification/auto-issue branch: set `status="failed"`, `save()`, write audit log, warning message, redirect to detail.
- [ ] `C3`: `apps/quality/views/TrainingCompetency/CompetencyCertifications.py:321-332` — Python loop in `training_compliance_dashboard` executes 4 queries per department for `departments[:6]` (24 queries). Fix: Consolidate into a single SQL query using `.values("course__competency_matrix__department__id", "course__competency_matrix__department__name")` and conditional aggregation (`Count("id")`, `Count("id", filter=Q(status="verified"))`) on `TrainingEnrollment`.

### Important
- [ ] `I1`: `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:256, 281` — Multi-model writes updating `TrainingEnrollment` and auto-issuing `CompetencyCertification` with audit log are not wrapped in `transaction.atomic()`. Fix: Wrap both `training_enrollment_complete` and `training_enrollment_verify` auto-issuance blocks in `with transaction.atomic():`.
- [ ] `I2`: `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:267-285` — Segregation of Duties (SoD) bypass: Trainee can self-verify their own practical qualification and auto-issue certification. Fix: Add evaluator independence check `if request.user == enrollment.trainee and not getattr(request.user, "is_tenant_admin", False): messages.error(...)` and status preconditions.
- [ ] `I3`: `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:296-311` — Missing authorization gating on regulatory training waivers: any authenticated tenant employee can waive mandatory training. Fix: Restrict to tenant admins or authorized staff (`request.user.is_superuser or getattr(request.user, "is_tenant_admin", False) or getattr(request.user, "is_staff", False)`).
- [ ] `I4`: `apps/quality/views/TrainingCompetency/CompetencyCertifications.py:202-232` — Missing authorization gating on certification renewal and suspension: any authenticated user can renew or suspend any employee's certification. Fix: Restrict renewal and suspension to tenant admins or authorized quality staff.
- [ ] `I5`: `apps/quality/views/TrainingCompetency/CompetencyMatrices.py:156-165` & `QualityTrainingCourses.py:182-189` — Missing status guards and role gating on matrix approval and course activation. Fix: Add role checks and status checks (`matrix.status == "draft"`, `course.status in ("draft", "under_revision")`).
- [ ] `I6`: `apps/quality/forms/TrainingCompetency/CompetencyMatrices.py:11-28` & `CompetencyCertifications.py:13-29` — Mass assignment / attribution exposure in ModelForms: `CompetencyMatrixForm` exposes `approved_by` and `approval_date`, and `CompetencyCertificationForm` exposes `certified_by` in `Meta.fields`. Fix: Exclude `approved_by`, `approval_date`, and `certified_by` from `Meta.fields` and set them in the respective views.
- [ ] `I7`: `apps/quality/views/TrainingCompetency/QualityTrainingCourses.py:112` & `CompetencyMatrices.py:93` — N+1 queries on `issued_certifications` / `certified_holders` trainee rendering in detail views: `.filter(status="active")` bypasses prefetch cache. Fix: Add `.select_related("trainee")` on both filtered querysets.
- [ ] `I8`: `templates/quality/trainingcompetency/{competency_matrix,training_course,training_enrollment,competency_certification}/form.html:28` — Non-existent `.alert` and `.alert-danger` classes in form templates (Lesson L13 / L33). Fix: Replace with `<div class="p-3 mb-6 rounded-md bg-red-50 border border-red-200 text-red-700 text-sm">` and `.form-error`.
- [ ] `I9`: `templates/quality/trainingcompetency/{competency_matrix,training_course,training_enrollment,competency_certification}/detail.html` — Detail pages lack explicit "Back to List" button in `.page-actions`. Fix: Add `<a href="{% url 'quality:<entity>_list' %}" class="btn btn-outline"><i data-lucide="arrow-left"></i> Back to ...</a>`.

### Minor
- [ ] `M1`: `templates/quality/trainingcompetency/competency_certification/detail.html:27` — "Renew Validity" button condition `{% if certification.status == 'active' or certification.status == 'expired' %}` hides button when status is `expiring_soon`. Fix: Include `certification.status == 'expiring_soon'`.
- [ ] `M2`: `templates/quality/trainingcompetency/training_course/list.html:59-108, 205` — View/template filter drift on `controlled_document`: Add document filter dropdown to filter form and append `&controlled_document={{ selected_doc }}` to pagination links.
- [ ] `M3`: `apps/quality/views/TrainingCompetency/CompetencyCertifications.py:348, 386` — Context key aliases: provide `expiring_certifications`, `department_metrics`, and `active_certifications` in view context dictionaries.
- [ ] `M4`: `apps/quality/forms/TrainingCompetency/TrainingEnrollments.py:57-63` — Missing `min_value=0, max_value=100` on `TrainingCompletionForm.score` DecimalField.
- [ ] `M5`: `apps/quality/forms/TrainingCompetency/CompetencyCertifications.py:55-62` — Cross-record mismatch between enrollment, trainee, and course in form `clean()`.
- [ ] `M6`: `apps/quality/models/TrainingCompetency/CompetencyCertifications.py:141` — Define a unified `generate_certificate_hash()` helper method on `CompetencyCertification` and call it consistently.
- [ ] `M7`: `templates/quality/trainingcompetency/` — Redundant `.count` calls in templates on evaluated querysets instead of `|length`, and passing score label condition when passing score is 0.

---

## Individual Reviewer Sections

### 1. Code Reviewer Pass
- Identified Critical C1 (failed exam auto-issuing certification) and C2 (Lesson L10 filter-argument None lookup on `practical_verified_by`).
- Identified Important I1 (transaction.atomic), I2 (trainee self-verification), I3 (waiver gating), I4 (renewal/suspension gating), I5 (matrix approve and course activate guards).
- Identified Minor M1 (renewal button for expiring_soon), M6 (hash generation unification).

### 2. Explorer Pass
- Verified 4-tier package structure, `__init__.py` re-exports, absolute imports, literal URLs before PK routes, `LIVE_LINKS["12.12"]` in `navigation.py`, admin registrations, and idempotent seeder.
- Identified Minor M2 (`controlled_document` filter in course list) and M3 (context key aliases for dashboard/dossier).

### 3. Frontend Reviewer Pass
- Verified 100% adherence to theme.css color-named badge standards (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`), zero comment leaks (L2), pagination guards (L9), and responsive table wrappers.
- Identified Important I8 (`.alert .alert-danger` missing from theme.css) and I9 ("Back to List" button on detail pages).

### 4. Performance Reviewer Pass
- Identified Critical C3 (dashboard department breakdown 4 queries per department loop).
- Identified Important I7 (N+1 queries in course detail and matrix detail) and I1 (`transaction.atomic` on enrollment mutations).
- Identified Minor M7 (`|length` vs `.count` on evaluated querysets).

### 5. QA Smoke Tester Pass
- Ran 54 live tests against seeded database. Confirmed 100% cross-tenant IDOR isolation (17/17 404s), 0 comment leaks, and fuzzing resilience.
- Confirmed runtime crash on C1 (`practical_verified_by.username` in None raising 500) and regulatory defect on C2 (score=45% resulting in verified status and certification).

### 6. Security Reviewer Pass
- Verified IDOR isolation across all models and views, CSRF on all POST forms, deletion gating with `@tenant_admin_required`, and audit logs on mutations.
- Confirmed SoD bypass on practical verification (I2), waiver authorization (I3), renewal/suspension authorization (I4), and mass assignment exposure in forms (I6).
