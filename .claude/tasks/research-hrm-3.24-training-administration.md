# Research — Module 3: HRM, Sub-module 3.24 Training Administration (hrm)

Scope note: this is the FINAL sub-module of the 3.22 (ILT) / 3.23 (LMS) / 3.24 (Administration)
training cluster. 3.24 adds the **operational/administrative layer** — it must not re-model the
catalog (`TrainingCourse`), the ILT occurrence (`TrainingSession`), or self-paced progress
(`LearningProgress`) already built. Every model proposed below is a thin transactional record that
FKs into those three.

## Leaders surveyed (with source links)

1. **SAP SuccessFactors Learning** — enterprise LMS/L&D-ops suite; the reference implementation for
   multi-step nomination/approval routing — [Approval Processes in Learning](https://help.sap.com/docs/SAP_SUCCESSFACTORS_LEARNING/34a1028152724c90be47806388f27141/a6c7d9a1e3ac4a46b46ba444bb111914.html), [SAP SuccessFactors Learning Approval Roles](https://help.sap.com/docs/successfactors-learning/creating-learning-approval-processes/sap-successfactors-learning-approval-roles)
2. **Cornerstone OnDemand** — enterprise LMS; strong on automated enrollment rules, audit-ready
   certificate/attendance history, recurring-certification cycles — [Cornerstone Learning Management](https://www.cornerstoneondemand.com/platform/learning-management-lms/), [Cornerstone Learning Features (G2)](https://www.g2.com/products/cornerstone-learning/features)
3. **Docebo** — LMS with a mature ILT/VILT module — session attendance-sheet marking, manual
   completion override, per-session evaluation/score, certificate download from the learner's
   activity feed — [Attending ILT courses](https://help.docebo.com/hc/en-us/articles/11393414619666-Attending-Instructor-Led-Training-ILT-courses-), [Certificates and certifications](https://help.docebo.com/hc/en-us/articles/22057130562066-Certificates-and-certifications), [Downloading the session attendance sheet](https://help.docebo.com/hc/en-us/articles/20348260730130-Downloading-the-session-attendance-sheet)
4. **TalentLMS** — SMB-friendly LMS; in-course Survey units (multiple-choice / Likert / free-text)
   for post-training reaction feedback, expiring certificates — [How to work with surveys](https://help.talentlms.com/hc/en-us/articles/9652304284956-How-to-work-with-surveys-in-TalentLMS), [TalentLMS Certifications](https://www.talentlms.com/blog/talentlms-certifications-lms-feature/), [Collecting training feedback](https://www.talentlms.com/blog/collect-training-feedback-with-talentlms/)
5. **SAP Litmos** — corporate LMS; manager nomination/recommend-and-approve flow, automated ILT/VILT
   attendance taking, certificate templates with per-curriculum certificates + expiry
   notifications — [Litmos features](https://www.litmos.com/features), [LMS Review: SAP Litmos](https://talentedlearning.com/lms-review-litmos-pro/)
6. **Absorb LMS** — enterprise LMS; certification lifecycle (generation/renewal/expiration) with
   customizable certificate templates, ILT resource + attendance management — [Absorb LMS Features (G2)](https://www.g2.com/products/absorb-software-absorb-lms/features), [Best solutions for tracking employee training](https://www.absorblms.com/resources/articles/best-employee-training-tracking-software)
7. **Arlo** — training-provider management system; mobile attendance marking that auto-triggers
   certificate issuance on "Completed/Passed/Paid" criteria, full certificate audit trail
   (who/when approved) — [Certificates overview](https://support.arlo.co/hc/en-gb/articles/211907383-Certificates-overview), [Certification & licence management](https://www.arlo.co/certification-licence-management)
8. **Training Orchestra** — the budget/cost-tracking specialist among training-management systems:
   multi-site budgets in local currency, real-time allocation adjustment, forecast-vs-actual
   variance, cost-vs-performance ROI reporting — [Budget Tracking Tools](https://trainingorchestra.com/training-management-system/budget-and-cost-tracking/), [TMS Features: Budget Optimization](https://trainingorchestra.com/tms-features-managing-training-budget-and-financial-performance/)
9. **Moodle Workplace** — open-source-derived corporate LMS; Certifications-tied-to-Programs with
   recertification cycles, dynamic rule-based auto-assignment, certification activity log for
   compliance audit — [Certifications - MoodleDocs](https://docs.moodle.org/502/en/Certifications), [Certifications in Moodle Workplace](https://www.tituslearning.com/moodle-workplace-fea/certifications-in-moodle-workplace/)
10. **Workday Learning** — HCM-embedded LMS; Manager Enroll task (manager-initiated nomination +
    "Assign as Required Learning" with due date), non-editable Official Learning Transcript for
    licensure/compliance audits, expiry reminders — [Training and Certifications](https://www.workday.com/en-us/services/training-certifications.html), [Workday Learning overview](https://www.training-central.net/2026/01/06/workday-learning/)
11. **Zoho People** (secondary confirm) — SMB HRMS LMS module; approval-flow + feedback-category
    config, participation certificates on completion — [Zoho People training](https://www.zoho.com/spark/custom-training/people.html), [Zoho Learn certification & badges](https://help.zoho.com/portal/en/kb/zoho-learn/learning/authors/certification-and-badges)

Also referenced (domain background, not a vendor): Kirkpatrick Level-1 "Reaction" evaluation
best-practice guidance (course/trainer/facilitator rating + open comments as the standard
post-training survey shape) — [TrainingCheck: Level 1 – Participant Reaction](https://www.trainingcheck.com/help-centre-2/guide-to-training-evaluation/creating-evaluations-at-the-different-levels/level-1-participant-reaction/), [Measuring Kirkpatrick Level 1 Reaction](https://tribalhabits.com/measuring-kirkpatrick-level-1-reaction/).

## Feature catalog by sub-module

### 3.24 Nomination — Employee nomination, approval

- **Self- or manager-initiated nomination** — an employee requests a seat, or a manager nominates a
  direct report · seen in: SAP SuccessFactors Learning (Employee/Manager approval roles), SAP Litmos
  (manager recommend-and-approve), Workday Learning (Manager Enroll task) · priority: table-stakes
  · spine: new table `TrainingNomination`, `nominated_by`/`employee` reuse `hrm.EmployeeProfile`
  · buildable now
- **Multi-step approval routing (manager → HR, configurable role chain)** — up to N approval steps
  with named roles (Manager L1/L2, HRBP) · seen in: SAP SuccessFactors Learning (up to 6 approval
  steps) · priority: differentiator (full N-step engine); a single manager-or-HR approver field
  is table-stakes (mirrors the existing `LeaveRequest.approver` pattern) · spine: reuse
  `EmployeeProfile.employment.manager` (a `core.Party`) for the "is this person the nominee's
  manager" permission check + `approver` FK to `settings.AUTH_USER_MODEL` for the decision record
  (exact `LeaveRequest`/`LeaveEncashment` precedent) · buildable now (single-approver); full
  role-chain engine deferred
- **Capacity-aware nomination / waitlist queue** — a nomination against a full session auto-queues
  instead of erroring · seen in: SAP Litmos (waitlist + approvals config for ILT/VILT), and it is
  the EXPLICIT deferred hook already written into `TrainingSession.waitlist_enabled`'s help text
  ("the queue itself is 3.24 Nomination") · priority: table-stakes for this repo (it's a promised
  seam) · spine: `TrainingNomination.status="waitlisted"` computed against
  `TrainingSession.capacity` vs. approved-nomination count · buildable now
- **Assign as Required / mandatory training push** — HR/manager force-assigns (skips the
  "request" step; goes straight to an accepted nomination) with a due date · seen in: Workday
  Learning ("Assign as Required Learning" + due date), Cornerstone (automated enrollment rules by
  role/department/milestone) · priority: common · spine: `nomination_type="hr_assigned"` +
  `due_date` field on the same model, no new table · buildable now (a rule-based AUTO-trigger off
  job role/department is integration/later — this pass supports the manual "assign" action)
- **Withdraw / cancel a nomination** — nominee or approver can withdraw before the session starts
  · seen in: SAP SuccessFactors Learning (withdrawal is itself an approvable action) · priority:
  common · spine: `status="cancelled"` + `cancelled_reason`, same pattern as
  `LeaveRequest.cancelled_reason` · buildable now

### 3.24 Attendance Tracking — Session attendance, completion

- **Per-session, per-attendee attendance marking (present/absent/partial/late)** — instructor or
  admin marks each registrant · seen in: Docebo ("Manage attendance", printable attendance sheet),
  SAP Litmos (automated attendance taking), Arlo (mobile attendance marking) · priority:
  table-stakes · spine: new table `TrainingAttendance` (tenant, `session` FK `TrainingSession`,
  `employee` FK `EmployeeProfile`) — unique per (tenant, session, employee) · buildable now
- **Walk-in / unregistered attendee capture** — someone attends without a prior nomination · seen
  in: Docebo (printable sheet supports adding walk-ins at the door) · priority: common · spine:
  `TrainingAttendance.nomination` FK is nullable — a null nomination + `is_walk_in=True` marks it
  · buildable now
- **Session-level completion status, independent of attendance presence** — an ILT course is
  "complete" once required sessions/evaluation criteria are met, sometimes overridden manually by
  an admin · seen in: Docebo (manual completion override + optional score/attached file) · priority:
  table-stakes · spine: `TrainingAttendance.completion_status` (`completed`/`incomplete`/`no_show`)
  on the same row — no second table · buildable now
- **Check-in / check-out timestamps** — actual arrival/departure captured for audit/duration proof
  · seen in: Arlo (mobile check-in), Cornerstone (audit-ready documentation of every interaction)
  · priority: common · spine: `check_in_time`/`check_out_time` on `TrainingAttendance` · buildable
  now
- **QR-code / self-check-in kiosk** — attendee scans a code to mark themselves present · seen in:
  Arlo, Cornerstone (mobile-first attendance) · priority: differentiator · integration/later (needs
  a scanning UI/device flow beyond one Django pass) — the underlying `TrainingAttendance` row this
  pass is what such a UI would eventually write to

### 3.24 Training Feedback — Post-training evaluation

- **Post-session course + trainer rating (Kirkpatrick Level-1 "Reaction")** — numeric rating(s) on
  content quality, relevance, and the trainer/facilitator, plus free-text comments · seen in:
  TalentLMS (in-course Survey units: multiple-choice/Likert/free-text), Training Orchestra
  (feedback feeds its cost-vs-performance ROI report), Kirkpatrick-model best-practice guidance
  (course/trainer/facilitator + 1 open-text is the standard shape) · priority: table-stakes ·
  spine: new table `TrainingFeedback`, `attendance` FK `TrainingAttendance` (so a rating always
  ties to a specific attended session) · buildable now
- **Anonymous feedback option** — the giver is hidden from ordinary viewers (HR/admin can still
  see) · seen in: implied by every enterprise LMS's survey config (also an existing NavERP
  precedent: 3.20 `Feedback.is_anonymous` masks-on-render, keeps the FK) · priority: common ·
  spine: `TrainingFeedback.is_anonymous` boolean, same mask-on-render pattern as
  `hrm.Feedback` (3.20) · buildable now
- **Would-recommend / net-promoter-style question** — a single "would you recommend this
  training?" boolean/score, easy to roll up · seen in: TalentLMS survey templates (satisfaction +
  recommend framing) · priority: common · spine: `would_recommend` boolean on `TrainingFeedback` ·
  buildable now
- **Multi-level evaluation (Level 2 knowledge test, Level 3 on-the-job application, Level 4 ROI)**
  — the full 4-level Kirkpatrick model, usually a delayed 30/60/90-day follow-up survey · seen in:
  Kirkpatrick-model literature; enterprise LMS "evaluation" modules (SAP SuccessFactors Learning,
  Cornerstone) gesture at this via custom surveys · priority: differentiator · integration/later
  (a delayed-survey scheduler + a real question-bank engine is out of scope for a 4-model pass;
  `LearningContentItem(content_type="assessment")` already covers in-course Level-2 knowledge
  checks for LMS courses — this pass only adds the Level-1 reaction form for ILT sessions)

### 3.24 Certificates — Auto-generate completion certificates

- **Auto-issue a certificate on completion, no manual step** — the system fires certificate
  creation the moment a course/session is marked complete · seen in: Cornerstone (audit-ready
  certificate issuance records), Docebo (certificate appears on the learner's activity feed at
  completion), Arlo (auto-trigger on "Completed/Passed" criteria) · priority: table-stakes · spine:
  new table `TrainingCertificate` (NUMBER_PREFIX `CERT`), created from either a completed
  `TrainingAttendance` (ILT path) or a completed `LearningProgress` with
  `course.is_certification=True` (LMS path) — **no duplicate course/completion data**, both are
  FKs · buildable now (the trigger is a view-layer action button this pass, not an async signal)
- **Certificate number + verification** — a unique, checkable certificate ID/QR so a third party
  can validate authenticity · seen in: Arlo (full audit trail of who/when approved), Cornerstone
  (audit-ready documentation) · priority: common · spine: `TrainingCertificate.number` (the
  existing `TenantNumbered` `CERT-00001` machinery) + a `verification_code` (UUID) field — no new
  numbering concept needed · buildable now
- **Expiry date computed from the course's certification validity, with renewal reminders** — the
  certificate's expiry is NOT hand-typed, it derives from `certification_validity_months` · seen
  in: SAP Litmos (certificate expiration notifications + renewal-rule management), Absorb LMS
  (renewal/expiration lifecycle tracking), Moodle Workplace (recertification cycles + automated
  expiry reminders), TalentLMS (certificates can expire after a set period) · priority:
  table-stakes · spine: reuse `TrainingCourse.certification_validity_months` — copy the EXACT
  month-math helper already written for `LearningProgress.certification_expires_on` (stdlib
  `calendar.monthrange` day-clamp) rather than re-deriving it · buildable now (the reminder EMAIL
  is integration/later; the computed/stored `expiry_date` is buildable now)
- **Custom certificate template / branded PDF with mail-merge fields** — admin-designed layout,
  logo, signature, auto-filled name/date/course · seen in: Absorb LMS (customizable certificate
  templates), SAP Litmos (upload certificate templates, define displayed fields), Arlo (Word
  mail-merge) · priority: common · integration/later — a template designer + PDF renderer is a
  distinct feature slice; this pass stores the certificate **record** (number, issue/expiry date,
  recipient, verification code) that a later PDF-generation pass would render from. Flag
  `TrainingCertificate` with a placeholder `certificate_file` FileField so a manually-uploaded/
  generated PDF has somewhere to live without blocking on the renderer.
- **Revoke / void a certificate** — HR can invalidate a wrongly-issued certificate · seen in: Arlo
  (audit trail includes changes), Cornerstone (full historical tracking) · priority: common ·
  spine: `TrainingCertificate.status` (`issued`/`revoked`/`expired`) — `expired` is a computed
  property (like `LearningProgress.is_certification_expired`), only `revoked` is a stored
  transition · buildable now

### 3.24 Training Budget — Budget allocation, utilization

- **Per-department / per-cost-center training budget allocation for a period** — HR/Finance sets
  how much a department can spend on training this year · seen in: Training Orchestra (multi-site
  budgets, per-area allocation), Workday Learning (department-filterable reporting implies
  department-level budget ownership) · priority: table-stakes (as a concept) · spine: **reuse,
  don't rebuild** — `hrm.CostCenterProfile` (3.2, already built) already carries
  `budget_annual`/`budget_year` per `core.OrgUnit(kind="cost_center")`. A NEW `TrainingBudget`
  table would duplicate this unless it needs to ring-fence a training-only sub-pool distinct from
  the department's whole budget · priority for a NEW table: differentiator, not table-stakes ·
  **buildable now as a reuse, not as new fields** — see Recommended build scope for the decision
- **Budget utilization = actual/forecast spend vs. allocation, with variance** — compares money
  actually spent on training against what was allocated · seen in: Training Orchestra (track
  remaining budget, compare actual vs. forecast, simulate scenarios) · priority: differentiator
  (this is Training Orchestra's specialty feature, not universal table-stakes across the other 10
  leaders) · spine: **fully computed, no new table** — aggregate `TrainingSession.actual_cost`
  (and `estimated_cost` for forecast) across sessions whose attendees (`TrainingAttendance.employee`)
  belong to a given `core.OrgUnit` department, for a given period, then divide by
  `CostCenterProfile.budget_annual` · buildable now (as a report/dashboard query), not a stored
  model
- **Cost-vs-performance ROI reporting** — combines budget data with feedback/outcome scores to
  justify training spend · seen in: Training Orchestra (cost-vs-performance reports) · priority:
  differentiator · integration/later (needs both `TrainingBudget` aggregates AND
  `TrainingFeedback`/`LearningProgress` outcome data joined — a reporting-pass concern, not a model)
- **Multi-currency budget tracking** — budgets and spend tracked in local currency per site ·
  seen in: Training Orchestra (multiple training sites globally, local currencies) · priority:
  differentiator · spine: already possible — `TrainingSession.currency` FKs `accounting.Currency`
  (global master) · buildable now (no new field needed) for the spend side; a currency-aware
  budget ALLOCATION would need one, deferred

## Recommended build scope (this pass — 4 models)

Five NavERP.md bullets, four-model budget. **Training Budget does not get a dedicated model this
pass** — it folds into a computed aggregate/report over data the other three sub-modules (3.22's
`TrainingSession.actual_cost`/`estimated_cost` and 3.2's `CostCenterProfile.budget_annual`) already
provide, matching the research finding that budget *tracking* (Training Orchestra's specialty) is a
differentiator, not a table-stakes stored-model feature across the other ~9 leaders surveyed. The
four models below cover Nomination, Attendance, Feedback, and Certificates — the four genuinely
transactional, per-employee records that need their own row and lifecycle.

- **`TrainingNomination`** [`NOM-`, `TenantNumbered`] — fields: `session` (FK `TrainingSession`,
  PROTECT), `employee` (FK `EmployeeProfile`, the nominee), `nominated_by` (FK `EmployeeProfile`,
  null=self-nominated), `nomination_type` (`self`/`manager`/`hr_assigned`), `status`
  (`draft`/`pending`/`approved`/`rejected`/`waitlisted`/`cancelled`), `approver` (FK
  `settings.AUTH_USER_MODEL`, mirrors `LeaveRequest.approver`), `approved_at`, `due_date`,
  `decision_note`, `cancelled_reason`. `clean()`/`save()` compute `waitlisted` vs. `approved` by
  comparing the count of already-approved nominations against `session.capacity` (fulfills the
  `TrainingSession.waitlist_enabled` help-text promise). Justified by: nomination/approval routing
  (SAP SuccessFactors Learning, SAP Litmos, Workday Learning), capacity/waitlist queue (SAP Litmos,
  the existing `TrainingSession` docstring seam), assign-as-required (Workday Learning), withdraw
  (SAP SuccessFactors Learning). Reuses `TrainingSession`, `EmployeeProfile`,
  `EmployeeProfile.employment.manager` for the approver-permission check.

- **`TrainingAttendance`** [`TenantOwned`, unique per (tenant, session, employee)] — fields:
  `session` (FK `TrainingSession`, CASCADE), `employee` (FK `EmployeeProfile`, CASCADE),
  `nomination` (FK `TrainingNomination`, null=blank — null + `is_walk_in=True` for an unregistered
  attendee), `attendance_status` (`registered`/`present`/`absent`/`partial`/`excused`),
  `completion_status` (`completed`/`incomplete`/`no_show`), `check_in_time`, `check_out_time`,
  `is_walk_in`, `notes`. Justified by: present/absent/partial marking + walk-ins (Docebo, Arlo, SAP
  Litmos), completion independent of attendance (Docebo's manual override), check-in/out
  timestamps (Arlo, Cornerstone audit trail). Reuses `TrainingSession` + `EmployeeProfile` +
  (optionally) `TrainingNomination`.

- **`TrainingFeedback`** [`TenantOwned`, unique per (tenant, attendance)] — fields: `attendance`
  (OneToOneField or FK `TrainingAttendance`, CASCADE — ties every rating to a real attended
  session), `course_rating` (1–5), `trainer_rating` (1–5), `content_rating` (1–5, optional),
  `would_recommend` (bool), `comments` (text), `is_anonymous` (bool, mask-on-render like the 3.20
  `Feedback` precedent), `submitted_at`. Justified by: Kirkpatrick Level-1 course+trainer rating +
  open comments (TalentLMS survey units, Kirkpatrick best-practice guidance), anonymous option
  (existing 3.20 `Feedback.is_anonymous` pattern), would-recommend (TalentLMS). Reuses
  `TrainingAttendance` (no duplicate session/employee FKs).

- **`TrainingCertificate`** [`CERT-`, `TenantNumbered`] — fields: `employee` (FK `EmployeeProfile`),
  `course` (FK `TrainingCourse`, PROTECT — the certifying course, from either path below),
  `source_attendance` (FK `TrainingAttendance`, null=blank — the ILT completion that earned it),
  `source_progress` (FK `LearningProgress`, null=blank — the LMS completion that earned it;
  `clean()` requires exactly one of `source_attendance`/`source_progress`), `certificate_name`
  (defaults from `course.certification_name`), `issue_date`, `expiry_date` (computed at save time
  from `course.certification_validity_months` using the SAME month-math helper as
  `LearningProgress.certification_expires_on` — do not re-derive it, extract/reuse), `status`
  (`issued`/`revoked`), `verification_code` (UUID, unique per tenant), `certificate_file`
  (FileField, optional — a later PDF-render/upload target), `issued_by` (FK
  `settings.AUTH_USER_MODEL`), `revoked_reason`. Justified by: auto-issue on completion (Cornerstone,
  Docebo, Arlo), certificate number + verification (Arlo audit trail, Cornerstone), computed expiry
  from course validity (SAP Litmos, Absorb LMS, Moodle Workplace, TalentLMS), revoke/void (Arlo,
  Cornerstone). Reuses `TrainingCourse.is_certification`/`certification_name`/
  `certification_validity_months` (3.22) and `LearningProgress` (3.23) — issues the artifact, does
  not recompute eligibility.

## Deferred (later passes / integrations)

- **Full N-step configurable approval-role engine** (SAP SuccessFactors Learning-style Manager
  L1/L2/HRBP chains) — this pass ships a single `approver` field (the `LeaveRequest` precedent);
  a role-chain engine is a distinct, reusable HRM-wide capability (leave/PIP/nomination could all
  use it), out of scope for one sub-module.
- **Rule-based auto-nomination / auto-enrollment** (assign training automatically when an employee
  joins a department/role, per Cornerstone's automated enrollment rules) — needs an event/trigger
  framework; this pass supports manual "assign as required" only.
- **QR-code self-check-in kiosk flow** (Arlo, Cornerstone) — a device/scanning UI beyond a single
  Django CRUD pass; the `TrainingAttendance` row this pass creates is what such a flow would
  eventually write to.
- **Multi-level Kirkpatrick evaluation (L2 knowledge test / L3 on-the-job / L4 ROI) with delayed
  30/60/90-day follow-up surveys** — this pass ships only the Level-1 reaction form
  (`TrainingFeedback`); Level-2 knowledge checks for self-paced courses already exist via
  `LearningContentItem(content_type="assessment")` (3.23) and are out of scope to duplicate here.
- **Branded certificate template designer + PDF mail-merge rendering** (Absorb LMS, SAP Litmos,
  Arlo's Word mail-merge) — this pass stores the certificate record + a placeholder file field;
  the rendering engine is a distinct feature slice.
- **Certificate/nomination expiry email reminders** — needs the notification/scheduler
  infrastructure; the computed `expiry_date`/waitlist fields this pass produces are what a
  reminder job would query.
- **Dedicated `TrainingBudget` allocation model (ring-fenced training-only sub-pool per
  department/period, separate from the general `CostCenterProfile.budget_annual`)** — deferred;
  this pass ships utilization as a computed aggregate over `TrainingSession.actual_cost`/
  `estimated_cost` joined via `TrainingAttendance` to `core.OrgUnit`, compared against the
  EXISTING `CostCenterProfile.budget_annual`/`budget_year`. If Finance later needs a true
  training-specific budget pool (distinct from the department's overall budget), that's a
  one-model follow-up, not part of this 4-model pass.
- **Cost-vs-performance ROI reporting** (Training Orchestra's differentiator: budget × outcome
  score correlation) — needs both the budget aggregate and `TrainingFeedback`/`LearningProgress`
  outcome data joined; a reporting-pass concern once both sides exist.
- **Multi-currency training budget allocation** (Training Orchestra: per-site budgets in local
  currency) — the SPEND side already supports currency via `TrainingSession.currency`; a
  currency-aware ALLOCATION is deferred with the dedicated-budget-model item above.
