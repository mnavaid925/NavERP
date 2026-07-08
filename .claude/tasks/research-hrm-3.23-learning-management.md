# Research — HRM Sub-module 3.23: Learning Management (LMS) (hrm)

> Scope note: this file researches **only** NavERP.md sub-module **3.23 Learning Management (LMS)** inside
> Module 3 (HRM) — the self-paced digital-learning layer. It explicitly builds **on top of** the already-built
> **3.22 Training Management** (`hrm.TrainingCourse` catalog + `hrm.TrainingSession` ILT occurrences) rather than
> duplicating a course table, and explicitly excludes **3.24 Training Administration** (nomination, ILT attendance,
> post-training feedback, auto-certificates, training budget), which is a separate future sub-module.

## Leaders surveyed (with source links)
1. **Docebo** — AI-first enterprise LMS with a content marketplace, learning plans, and full SCORM/xAPI/AICC support — [Learn LMS](https://www.docebo.com/products/learn-lms/), [SCORM guide](https://www.docebo.com/learning-network/blog/scorm-compliant-lms/)
2. **TalentLMS** — SMB-friendly LMS, industry reference implementation for gamification (points/badges/levels/leaderboards/rewards) — [Features (G2)](https://www.g2.com/products/talentlms/features), [Gamification](https://www.talentlms.com/features/gamification-lms)
3. **Cornerstone OnDemand (Cornerstone Learning)** — enterprise LMS with role-based/adaptive learning paths and automated certification renewal/compliance tracking — [Learning Management](https://www.cornerstoneondemand.com/platform/learning-management-lms/)
4. **SAP SuccessFactors Learning** — enterprise LMS embedded in SAP HCM; SCORM/AICC/xAPI content, quiz/assessment scoring reported back to the LMS, real-time progress dashboards — [SCORM support](https://help.sap.com/docs/successfactors-learning/implementing-structured-content/aicc-and-scorm-support-for-sap-successfactors-learning), [Review](https://research.com/software/reviews/sap-successfactors-learning)
5. **360Learning** — collaborative-learning LMS with in-app authoring, AI-suggested quiz questions, sequenced "must complete in order" paths, and a 3-part gamification engine (Challenge mode / Achievements / Leaderboard) — [Features (G2)](https://www.g2.com/products/360learning/features), [Gamification](https://support.360learning.com/hc/en-us/articles/115002193943-Find-out-more-about-Gamification)
6. **Absorb LMS** — enterprise LMS; built-in quiz engine (multiple question types, auto-grading), learning-path sequencing, customizable achievement badges/points/leaderboards — [Features (G2)](https://www.g2.com/products/absorb-software-absorb-lms/features), [Gamification](https://www.absorblms.com/blog/lms-gamification-examples-best-practices)
7. **SAP Litmos** — SMB/mid-market LMS; large stock-content library, curriculum-style learning paths (ordered course sequences), certificates & badges, one-click completion reporting — [Features](https://www.sap.com/mena/products/hcm/litmos-solutions/features.html)
8. **LearnUpon** — LMS distinguishing linear "Learning Paths" (Course A → B → certificate) from conditional "Learning Journeys" (if/then branching); SCORM 1.2/2004 + xAPI (Tin Can) import — [Features (G2)](https://www.g2.com/products/learnupon-lms/features), [SCORM/xAPI](https://www.learnupon.com/features/scorm-xapi-compliant/), [Learning path settings](https://support.learnupon.com/hc/en-us/articles/4408869912465-Learning-path-settings-details-enrollment-access-and-credits)
9. **iSpring Learn** — authoring-tool-centric LMS; role/performance-based personalized learning paths as a core strength; points, badges, leaderboards, and auto-certificates on completion — [Features](https://www.ispring.com/features)
10. **Adobe Learning Manager** — enterprise LMS with a built-in Learning Record Store (LRS) that natively ingests xAPI statements (own + 3rd-party) for unified learner analytics; points/badges/leaderboards with achievement levels (bronze/silver/gold/platinum); skill-gap tracking — [xAPI](https://league.adobe.com/docs/learning-manager/using/admin/xapi.html), [Gamification](https://helpx.adobe.com/lu_en/captivate-prime/learners/feature-summary/gamification.html)
11. **Moodle Workplace** — open-source-based enterprise LMS; "Programs" feature sequences courses into pathways with completion rules (All in order / All in any order / At least N), integrates Programs with Certifications for auto-requalification, manager "Team overview" progress dashboards — [Programs](https://moodle.com/news/moodle-workplace-4-0-programs/), [Certifications](https://www.catalyst-eu.net/blog/2024/12/19/managing-learning-pathways-and-certifications-in-moodle-workplace)

## Feature catalog by sub-module

All five groups below are the NavERP.md 3.23 bullets. Every feature is scoped to **self-paced digital learning**
content that hangs off the existing `hrm.TrainingCourse` catalog row — none of it re-creates a course table.

### 3.23 Course Content — Videos, documents, SCORM packages
- **Multi-format content items (video/document/SCORM/external link/text)** — a course is built from an ordered list of content pieces, each a different media type · seen in: Docebo, TalentLMS, SAP SuccessFactors, SAP Litmos, iSpring Learn · priority: table-stakes · spine: new table `LearningContentItem`, FK to existing `hrm.TrainingCourse` · buildable now
- **SCORM 1.2 / SCORM 2004 package support** — upload a zipped SCORM package that reports completion/score back via the SCORM runtime API · seen in: Docebo, SAP SuccessFactors, LearnUpon, SAP Litmos · priority: table-stakes · spine: new table (content_type='scorm' + package file field) · buildable now for storage/metadata; the **SCORM JS runtime handshake is integration/later** (needs a SCORM player, not a plain Django view)
- **xAPI (Tin Can) support + Learning Record Store (LRS)** — richer, non-course-bound activity statements (video watched, page viewed, quiz answered) captured centrally for analytics · seen in: Docebo, SAP SuccessFactors, LearnUpon, Adobe Learning Manager · priority: differentiator · spine: would need a new xAPI-statement table · integration/later (LRS is a specialized service)
- **AICC support** — legacy content-packaging standard still requested by enterprise buyers · seen in: Docebo, SAP SuccessFactors, Adobe Learning Manager · priority: common (mostly enterprise) · spine: same content-item table, another `content_type` choice · integration/later (low priority, legacy)
- **Ordered lessons/modules within a course** — content items have an explicit sequence learners progress through · seen in: Docebo, iSpring Learn, Absorb LMS · priority: table-stakes · spine: `sequence` field on `LearningContentItem`, `Meta.ordering` · buildable now
- **Mandatory vs. optional content items** — some lessons are required for completion, others supplemental · seen in: Absorb LMS, Cornerstone · priority: common · spine: `is_required` boolean on `LearningContentItem` · buildable now
- **AI-generated course content from a document/prompt** — auto-build structured lessons/quizzes from an uploaded doc · seen in: 360Learning (AI Content Builder), TalentLMS (TalentCraft), Docebo Creator · priority: differentiator · spine: n/a · integration/later (external AI service)
- **Content-provider marketplace (pre-built course library)** — thousands of licensed off-the-shelf courses · seen in: Docebo (30k+ courses), SAP Litmos (95k+ courses) · priority: differentiator · spine: n/a · integration/later (3rd-party licensing deal, not a data-model concern)

### 3.23 Learning Paths — Role-based learning journeys
- **Ordered multi-course path/curriculum** — a named sequence of courses a learner must complete, in order, to finish the path · seen in: SAP Litmos, LearnUpon, Docebo, Moodle Workplace (Programs) · priority: table-stakes · spine: new tables `LearningPath` (header) + `LearningPathItem` (ordered `hrm.TrainingCourse` refs) · buildable now
- **Role/job-based targeting** — a path is auto-relevant to (or auto-assigned to) a designation/department/org-branch · seen in: Cornerstone ("Role-based onboarding and learning paths"), Docebo (assign to org-chart branch/group), iSpring Learn (role-based paths) · priority: table-stakes (this is literally the NavERP.md bullet name) · spine: reuse existing HRM masters `hrm.Designation` / `hrm.Department` (3.2) — no new "Role" table · buildable now
- **Flexible completion rules for path sub-groups** — "all courses in order", "all in any order", or "at least N of M" · seen in: Moodle Workplace (Programs) · priority: differentiator · spine: could extend `LearningPathItem` with a group/rule field · buildable now (lightweight), full rule engine later
- **Adaptive/conditional ("if/then") learning journeys** — branching enrollment logic based on role, performance, or prior course outcome · seen in: Cornerstone (adaptive paths), LearnUpon (Learning Journeys), 360Learning (dynamic-group auto-enrollment) · priority: differentiator · spine: would need a rules table · integration/later (out of scope for a first pass — flag as future path automation)
- **Path-level certificate on completion** — finishing every mandatory course in a path issues a certificate · seen in: LearnUpon, Moodle Workplace, SAP Litmos · priority: common · spine: reuses `hrm.TrainingCourse.is_certification`; the **auto-generation/issuance of the certificate document is 3.24 (Certificates)** · buildable now to flag eligibility (`LearningProgress` reaching 100%), issuance mechanics deferred
- **Prerequisite gating between path courses** — can't start course B until course A is done · seen in: Cornerstone, Moodle Workplace · priority: common · spine: reuses existing `hrm.TrainingCourse.prerequisite_course` self-FK (3.22) — already modeled, just needs path-level enforcement · buildable now

### 3.23 Assessments — Quizzes, tests, certifications
- **Quiz/test attached to a course** — a scored knowledge check gates completion · seen in: all 11 surveyed products · priority: table-stakes · spine: lightweight — fields live directly on `LearningContentItem` when `content_type='assessment'` (see Recommended build scope) rather than a separate question-bank schema · buildable now (light version)
- **Multiple question types (MCQ, true/false, drag-and-drop, fill-in-blank, open-ended)** — a full question-authoring engine · seen in: TalentLMS, Absorb LMS, LearnUpon · priority: table-stakes among dedicated LMS products, but **would blow the 3–4-model budget for this pass** (needs a Question + Choice + Attempt-Answer schema) · spine: new tables (deferred) · integration/**later pass**, not this one
- **Pass threshold + max attempts** — a configurable score to pass and a cap on retries · seen in: Absorb LMS, LearnUpon, SAP SuccessFactors · priority: table-stakes · spine: `pass_threshold_percent` / `max_attempts` fields on the light `LearningContentItem` assessment variant · buildable now
- **Time-limited tests** — a countdown timer per attempt · seen in: LearnUpon, Absorb LMS · priority: common · spine: `time_limit_minutes` field · buildable now (field only; timer UX is a later template concern)
- **Automated grading + immediate feedback** — auto-scored on submit · seen in: Absorb LMS, LearnUpon, SAP SuccessFactors · priority: table-stakes · spine: score computed and written to `LearningProgress.score` · buildable now once a real question engine exists — **for this pass, score/pass are recorded fields, not computed from a question bank** (manual/simple scoring, or scored externally and posted back)
- **AI-suggested quiz questions from course content** — auto-generate assessment questions · seen in: 360Learning · priority: differentiator · spine: n/a · integration/later
- **Certification exams with validity/expiry & renewal reminders** — an assessment that grants a time-limited certification, with expiry tracking · seen in: Cornerstone, Moodle Workplace · priority: differentiator · spine: reuses `hrm.TrainingCourse.is_certification` / `certification_validity_months` (already built in 3.22) — LMS assessment just needs to be the "how it was earned" record · buildable now (link, not duplicate)

### 3.23 Gamification — Badges, points, leaderboards
- **Points for activity** — points awarded for completing lessons, quizzes, logins, streaks · seen in: TalentLMS, Absorb LMS, iSpring Learn, Adobe Learning Manager, 360Learning · priority: table-stakes (among products that do gamification at all) · spine: `points_earned` integer field on `LearningProgress` · buildable now
- **Achievement badges** — a badge awarded for a milestone (course completed, N quizzes passed, streak) · seen in: TalentLMS, Absorb LMS, iSpring Learn, Adobe Learning Manager, 360Learning · priority: common · spine: **deferred to a later pass** — this is a *different* badge concept from HRM 3.20's `KudosBadge` (peer-to-peer recognition catalog); an LMS achievement-badge catalog + award table would be a 5th/6th model and is dropped from this pass's budget · integration/**later pass**
- **Levels** — learners "level up" based on points/courses/badges thresholds · seen in: TalentLMS, Adobe Learning Manager (bronze/silver/gold/platinum) · priority: common · spine: computable from `LearningProgress.points_earned` aggregate — no new table needed for a simple tier · buildable now as a computed property/threshold, not stored
- **Leaderboards** — ranked list of learners by points/badges/courses/certifications · seen in: TalentLMS, Absorb LMS, iSpring Learn, Adobe Learning Manager, 360Learning · priority: table-stakes (among gamified LMS) · spine: a **computed query** (`LearningProgress` grouped/annotated by employee, summed `points_earned`) — no new table needed · buildable now
- **Challenge mode / peer competitions** — time-boxed point competitions between learners or teams · seen in: 360Learning · priority: differentiator · spine: n/a · integration/later
- **Redeemable rewards (discounts/prizes) for points** — points convert to a tangible reward · seen in: TalentLMS · priority: differentiator (mostly relevant to external/paid-course LMS use cases, less to internal corporate ERPs) · spine: n/a · integration/later — likely never needed for an internal ERP LMS

### 3.23 Progress Tracking — Completion status, time spent
- **Per-learner completion status per course** — not-started / in-progress / completed (/ failed / expired) · seen in: all 11 surveyed products · priority: table-stakes · spine: new table `LearningProgress` (employee × course), `status` choice field · buildable now
- **Percent-complete** — a 0–100% progress bar per course/path · seen in: Docebo, SAP Litmos, Moodle Workplace · priority: table-stakes · spine: `percent_complete` field on `LearningProgress` · buildable now
- **Time spent tracking** — cumulative minutes/hours a learner spent in the content · seen in: SAP SuccessFactors ("course launch, completion, time spent... automatically reported"), Docebo · priority: table-stakes · spine: `time_spent_minutes` field on `LearningProgress` · buildable now (self-reported/computed from session deltas — precise in-content timing requires a JS player, deferred)
- **Manager/team progress dashboard** — a rollup view for managers of their team's completion · seen in: Moodle Workplace (Team overview), SAP SuccessFactors, Cornerstone · priority: common · spine: a view/query over `LearningProgress` filtered by `hrm.EmployeeProfile.manager` (already exists) · buildable now (a list/report view, no new table)
- **Compliance/expiry tracking + renewal reminders** — flags on courses/certifications nearing or past expiry · seen in: Cornerstone, Moodle Workplace, SAP Litmos · priority: common · spine: reuses `hrm.TrainingCourse.certification_validity_months`; reminder *sending* is integration/later (notifications) · buildable now for the expiry **calculation** (a property comparing `completed_at` + validity window to today)
- **Real-time dashboards / predictive analytics** — org-wide learning analytics, skill-gap prediction · seen in: SAP SuccessFactors, Adobe Learning Manager · priority: differentiator · spine: n/a (reporting layer over `LearningProgress`) · integration/later (or a later reports pass)
- **Auto-enrollment based on user attributes (job role, hire date, location)** — dynamic-rule enrollment into paths/courses · seen in: 360Learning, Moodle Workplace (dynamic rules) · priority: differentiator · spine: could extend `LearningPath.target_designation` matching at hire time · integration/later (needs a signal/automation layer)

## Recommended build scope (this pass — 4 models)

Per the tight 3–4-model instruction, **assessments-with-a-question-bank is deferred** (it alone would need
Question + Choice + Attempt-Answer tables). Instead, "Assessments" ships as a **lightweight variant of the content
item** (pass threshold / attempts / time limit as plain fields, no stored question bank), and "Gamification"
ships as **plain fields + computed queries** (points on the progress row; badges, levels-as-a-table, and
leaderboard persistence are all deferred — a leaderboard is just `LearningProgress` grouped/summed by employee).

- **`LearningContentItem`** [no number prefix — a `TenantOwned` child row, same shape as `hrm.ClearanceItem`] —
  covers **Course Content** + the light **Assessments** variant.
  - `course` (FK `hrm.TrainingCourse`, `related_name="content_items"`, `CASCADE`) — reuses the existing 3.22 course catalog; no new course table.
  - `title`, `description`
  - `content_type` choices: `video` / `document` / `scorm` / `external_link` / `text` / `assessment` (Docebo/TalentLMS/SAP SuccessFactors/SAP Litmos multi-format pattern)
  - `sequence` (PositiveIntegerField, default 0) — ordered lesson position (Docebo, iSpring Learn)
  - `is_required` (bool, default True) — mandatory vs. optional lesson (Absorb LMS, Cornerstone)
  - `estimated_duration_minutes` (nullable) — informs `LearningProgress.time_spent_minutes` targets
  - content fields: `video_url` (URLField, blank), `document_file` / `scorm_package` (FileField, blank), `external_url` (URLField, blank), `body_text` (TextField, blank) — only the field matching `content_type` is expected filled (validated in `clean()`)
  - assessment-only fields (used when `content_type='assessment'`, validated required together): `pass_threshold_percent` (default 70), `max_attempts` (default 1), `time_limit_minutes` (nullable) — LearnUpon/Absorb LMS pattern, no question sub-table this pass
  - `Meta.ordering = ["course", "sequence"]`

- **`LearningPath`** [`TenantNumbered`, prefix `LNP`] — covers **Learning Paths** header.
  - `title`, `description`
  - `target_designation` (FK `hrm.Designation`, null/blank) — role-based targeting (Cornerstone, iSpring Learn) — reuses the existing 3.2 organization master, no new "Role" table
  - `target_department` (FK `hrm.Department`, null/blank) — org-branch targeting (Docebo)
  - `is_mandatory` (bool, default False) — compliance-style path vs. optional development path
  - `is_active` (bool, default True)

- **`LearningPathItem`** [`TenantOwned` child of `LearningPath`, same child pattern as `hrm.ClearanceItem`] —
  covers **Learning Paths** ordered content.
  - `path` (FK `LearningPath`, `related_name="items"`, CASCADE)
  - `course` (FK `hrm.TrainingCourse`, `related_name="path_items"`, PROTECT) — reuses 3.22 course catalog; **prerequisite gating between path courses reuses the existing `hrm.TrainingCourse.prerequisite_course` self-FK** rather than a new rule field
  - `sequence` (PositiveIntegerField, default 0) — ordered completion sequence (SAP Litmos, LearnUpon, Moodle Workplace Programs)
  - `is_mandatory` (bool, default True) — path-level override of course requiredness
  - `unique_together = ("tenant", "path", "course")`; `Meta.ordering = ["path", "sequence"]`

- **`LearningProgress`** [`TenantOwned`, unique per employee×course] — covers **Progress Tracking**, assessment
  *outcomes* (not authoring), and lightweight **Gamification**.
  - `employee` (FK `hrm.EmployeeProfile`, `related_name="learning_progress"`) — the learner; reuses the existing 3.1 person master (itself a `core.Party`), no new learner table
  - `course` (FK `hrm.TrainingCourse`, `related_name="learner_progress"`) — what's being tracked
  - `learning_path` (FK `LearningPath`, null/blank, `SET_NULL`) — "enrolled via this path", if applicable
  - `status` choices: `not_started` / `in_progress` / `completed` / `failed` / `expired` (all 11 products) — default `not_started`
  - `percent_complete` (PositiveIntegerField 0–100, default 0) — Docebo/SAP Litmos/Moodle Workplace pattern
  - `time_spent_minutes` (PositiveIntegerField, default 0) — SAP SuccessFactors pattern
  - `score` (DecimalField, null/blank) + `passed` (bool, null/blank) — outcome of the course's `assessment`-type content item(s) (Absorb LMS/LearnUpon auto-grading pattern — the *grading logic* is simple/manual this pass, no question bank)
  - `attempt_count` (PositiveIntegerField, default 0) — respects the content item's `max_attempts`
  - `points_earned` (PositiveIntegerField, default 0) — TalentLMS/Absorb LMS/iSpring Learn/Adobe Learning Manager gamification points; **leaderboards and level tiers are computed queries/properties over this field, not new tables**
  - `started_at`, `completed_at` (nullable DateTimeField) — drives the certification-expiry calculation against `hrm.TrainingCourse.certification_validity_months`
  - `unique_together = ("tenant", "employee", "course")`; indexes on `(tenant, employee)`, `(tenant, course)`, `(tenant, status)`

All four models reuse existing HRM/core masters (`hrm.TrainingCourse`, `hrm.EmployeeProfile`, `hrm.Designation`,
`hrm.Department`) and post nothing to the accounting ledger or stock spine — LMS is a pure people/learning-data
domain, consistent with 3.20/3.22's "no new core-spine entity" pattern.

## Deferred (later passes / integrations)

- **Question-bank assessment authoring** (Question, Choice, per-attempt Answer tables, multiple question types,
  AI-suggested questions) — would need 2–3 more tables; this pass ships pass/fail + score as recorded outcomes
  only, no authored question bank. (TalentLMS, Absorb LMS, LearnUpon, 360Learning)
- **SCORM runtime / xAPI LRS integration** — the JS SCORM API handshake and a proper Learning Record Store for
  xAPI statements are specialized runtime services, not a plain Django CRUD pass. This pass stores the SCORM
  package file + metadata only. (Docebo, SAP SuccessFactors, LearnUpon, Adobe Learning Manager)
  Vulnerability note: any future SCORM upload/extraction handler MUST validate archive contents (zip-slip /
  path-traversal guard) before writing extracted files to disk — do not trust package internals.
- **Achievement badge catalog + award table** — a real LMS badge system (icon, criteria, award log) is distinct
  from HRM 3.20's `KudosBadge` (peer recognition) and would be a 5th/6th model; this pass keeps gamification to
  `points_earned` + computed leaderboard/levels. (TalentLMS, Absorb LMS, iSpring Learn, Adobe Learning Manager)
- **Adaptive/conditional ("if/then") learning journeys** and **dynamic auto-enrollment rules** (by job role, hire
  date, location) — needs a rules/automation engine layered on `LearningPath`. (Cornerstone, LearnUpon, 360Learning,
  Moodle Workplace)
- **Content marketplace / licensed course library** — a commercial content-licensing integration, not a data-model
  concern. (Docebo, SAP Litmos)
- **AI content/quiz generation** — external AI service integration. (360Learning, TalentLMS, Docebo)
- **Predictive analytics / org-wide skill-gap dashboards** — a reporting-layer feature to revisit once enough
  `LearningProgress` data exists. (SAP SuccessFactors, Adobe Learning Manager)
- **3.24 Training Administration (sibling sub-module, NOT built here):**
  - **Nomination** — employee nomination/approval workflow for being enrolled (into a `TrainingSession` or a
    `LearningPath`/course).
  - **Attendance Tracking** — per-`TrainingSession` (ILT) attendance marking — distinct from this sub-module's
    self-paced `LearningProgress.status`/`percent_complete`.
  - **Training Feedback** — post-training evaluation forms.
  - **Certificates** — auto-generation/issuance of the completion certificate document. This pass only computes
    *eligibility* (`LearningProgress.status == 'completed'` + `hrm.TrainingCourse.is_certification`); the PDF/print
    artifact and its issuance record belong to 3.24.
  - **Training Budget** — budget allocation/utilization rollups (these would aggregate `TrainingSession.actual_cost`
    from 3.22, not anything in 3.23).

---

## Summary for the `todo` agent

**Module:** HRM sub-module 3.23 Learning Management (LMS), `apps/hrm` (extension of the already-built app).

**Products surveyed (11):** Docebo, TalentLMS, Cornerstone OnDemand, SAP SuccessFactors Learning, 360Learning,
Absorb LMS, SAP Litmos, LearnUpon, iSpring Learn, Adobe Learning Manager, Moodle Workplace.

**Recommended build scope — 4 models, all extending the existing 3.22 `hrm.TrainingCourse` catalog (no new course
table, no core-spine changes):**
1. **`LearningContentItem`** (child of `TrainingCourse`) — video/document/SCORM/external-link/text lessons,
   ordered by `sequence`, plus a lightweight `content_type='assessment'` variant (pass_threshold_percent,
   max_attempts, time_limit_minutes) — no question bank this pass.
2. **`LearningPath`** [`LNP-`] — role-based journey header, targets `hrm.Designation`/`hrm.Department`.
3. **`LearningPathItem`** (child of `LearningPath`) — ordered `TrainingCourse` references, reuses
   `TrainingCourse.prerequisite_course` for gating instead of a new rule field.
4. **`LearningProgress`** — per-`EmployeeProfile`×`TrainingCourse` completion status/percent/time-spent/score/
   points, unique per employee+course; leaderboards/levels are computed queries over `points_earned`, not new
   tables.

**Deferred:** question-bank assessment authoring, SCORM runtime/xAPI LRS wiring, an achievement-badge catalog
(distinct from 3.20 `KudosBadge`), adaptive/conditional paths + auto-enrollment rules, content marketplace, AI
content/quiz generation, predictive analytics — and everything under sibling sub-module **3.24 Training
Administration** (nomination, ILT attendance, feedback, certificate issuance, training budget).

File written: `C:\xampp\htdocs\NavERP\.claude\tasks\research-hrm-3.23-learning-management.md`
