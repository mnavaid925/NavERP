# Module 12.12 Review Findings (Sub-module: Training & Competency Management)

Range: `bc9fc6d0e8137f54214ffd3af0019c12e69c6c72...HEAD`

## Consolidated Review Findings

### Critical
- [x] `C1`: `templates/quality/trainingcompetency/training_enrollment/detail.html:257, 279` — Unguarded nullable FK lookups in filter arguments (`default:enrollment.practical_verified_by.username` and `default:enrollment.waived_by.username`) raise `VariableDoesNotExist` (Lesson L10) and 500s when viewing verified enrollments for non-practical courses or enrollments without waivers. (fixed: 079d9c7f fix(quality): guard nullable practical_verified_by and waived_by lookups in enrollment detail)
- [x] `C2`: `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:240-261` — GxP Regulatory Defect: Failing exam score (`score < passing_score`, `is_passed=False`) bypasses failure branch and executes `else:`, marking the enrollment `status="verified"` and auto-issuing a formal `CompetencyCertification`. (fixed: b56bbe68 fix(quality): route failed training completion exam score to failure status)
- [x] `C3`: `apps/quality/views/TrainingCompetency/CompetencyCertifications.py:321-332` — Python loop in `training_compliance_dashboard` executes 4 queries per department for `departments[:6]` (24 queries). (fixed: b245282e perf(quality): consolidate training compliance dashboard department breakdown into single query)

### Important
- [x] `I1`: `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:256, 281` — Multi-model writes updating `TrainingEnrollment` and auto-issuing `CompetencyCertification` with audit log are not wrapped in `transaction.atomic()`. (fixed: 2b3297c6 fix(quality): wrap enrollment completion and verification certification auto-issuance in transaction.atomic)
- [x] `I2`: `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:267-285` — Segregation of Duties (SoD) bypass: Trainee can self-verify their own practical qualification and auto-issue certification. (fixed: f1275819 security(quality): enforce segregation of duties and status precondition on practical verification)
- [x] `I3`: `apps/quality/views/TrainingCompetency/TrainingEnrollments.py:296-311` — Missing authorization gating on regulatory training waivers: any authenticated tenant employee can waive mandatory training. (fixed: df492b67 security(quality): enforce authorization and status guard on training waivers)
- [x] `I4`: `apps/quality/views/TrainingCompetency/CompetencyCertifications.py:202-232` — Missing authorization gating on certification renewal and suspension: any authenticated user can renew or suspend any employee's certification. (fixed: 36c5c6c3 security(quality): enforce authorization gating and status guards on certification renewal and suspension)
- [x] `I5`: `apps/quality/views/TrainingCompetency/CompetencyMatrices.py:156-165` & `QualityTrainingCourses.py:182-189` — Missing status guards and role gating on matrix approval and course activation. (fixed: 339dcc66 security(quality): add authorization and status checks on competency matrix approval and retirement; a1a305f7 security(quality): add authorization and status checks on training course activation and retirement)
- [x] `I6`: `apps/quality/forms/TrainingCompetency/CompetencyMatrices.py:11-28` & `CompetencyCertifications.py:13-29` — Mass assignment / attribution exposure in ModelForms: `CompetencyMatrixForm` exposes `approved_by` and `approval_date`, and `CompetencyCertificationForm` exposes `certified_by` in `Meta.fields`. (fixed: 42214e38 security(quality): exclude approved_by and approval_date from CompetencyMatrixForm; b991a123 security(quality): exclude certified_by and validate cross-record enrollment consistency in CompetencyCertificationForm; d2c48267 security(quality): set certified_by to requesting user upon manual competency certification creation)
- [x] `I7`: `apps/quality/views/TrainingCompetency/QualityTrainingCourses.py:112` & `CompetencyMatrices.py:93` — N+1 queries on `issued_certifications` / `certified_holders` trainee rendering in detail views: `.filter(status="active")` bypasses prefetch cache. (fixed: 424d6dce perf(quality): select_related trainee on competency matrix active certified_holders; bf6bf662 perf(quality): select_related trainee on course active issued_certifications)
- [x] `I8`: `templates/quality/trainingcompetency/{competency_matrix,training_course,training_enrollment,competency_certification}/form.html:28` — Non-existent `.alert` and `.alert-danger` classes in form templates (Lesson L13 / L33). (fixed: fa6b7cf0, db94eeeb, 51d03b2d, b5168bcb style(quality): replace non-existent alert classes across all form templates)
- [x] `I9`: `templates/quality/trainingcompetency/{competency_matrix,training_course,training_enrollment,competency_certification}/detail.html` — Detail pages lack explicit "Back to List" button in `.page-actions`. (fixed: e06265cf, 3d369fd5, 70b9438a, b7275bf4 feat(quality): add Back to List buttons across all 4 detail templates)

### Minor
- [x] `M1`: `templates/quality/trainingcompetency/competency_certification/detail.html:27` — "Renew Validity" button condition `{% if certification.status == 'active' or certification.status == 'expired' %}` hides button when status is `expiring_soon`. (fixed: b7275bf4 feat(quality): allow renewing expiring_soon certifications in detail template)
- [x] `M2`: `templates/quality/trainingcompetency/training_course/list.html:59-108, 205` — View/template filter drift on `controlled_document`: Add document filter dropdown to filter form and append `&controlled_document={{ selected_doc }}` to pagination links. (fixed: e80d59c6 feat(quality): add controlled document filter dropdown and pagination persistence in training course list)
- [x] `M3`: `apps/quality/views/TrainingCompetency/CompetencyCertifications.py:348, 386` — Context key aliases: provide `expiring_certifications`, `department_metrics`, and `active_certifications` in view context dictionaries. (fixed: 0de00fe6 feat(quality): provide context key aliases in training dashboard and dossier views)
- [x] `M4`: `apps/quality/forms/TrainingCompetency/TrainingEnrollments.py:57-63` — Missing `min_value=0, max_value=100` on `TrainingCompletionForm.score` DecimalField. (fixed: 2b217ce1 validation(quality): add min_value 0 and max_value 100 to TrainingCompletionForm score field)
- [x] `M5`: `apps/quality/forms/TrainingCompetency/CompetencyCertifications.py:55-62` — Cross-record mismatch between enrollment, trainee, and course in form `clean()`. (fixed: b991a123 security(quality): validate cross-record enrollment consistency in CompetencyCertificationForm clean)
- [x] `M6`: `apps/quality/models/TrainingCompetency/CompetencyCertifications.py:141` — Define a unified `generate_certificate_hash()` helper method on `CompetencyCertification` and call it consistently. (fixed: 03516605 feat(quality): define unified generate_certificate_hash method on CompetencyCertification; e3134d6e refactor(quality): use cert.generate_certificate_hash() in competency certification renewal)
- [x] `M7`: `templates/quality/trainingcompetency/` — Redundant `.count` calls in templates on evaluated querysets instead of `|length`, and passing score label condition when passing score is 0. (fixed: 37e27807, 4fdd06de, c30d13d5, 4ccf044c perf(quality): replace .count with |length on evaluated querysets and handle passing score 0)

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
