# Research — Module 3: Human Resource Management, Sub-module 3.21 Performance Improvement (hrm-performance-improvement)

Fourth and final Performance-Management sub-module (after 3.18 Goal Setting, 3.19 Performance Review, 3.20
Continuous Feedback) — the **corrective-action / disciplinary layer**: structured Performance Improvement Plans
(PIPs), progressive disciplinary warning letters, and manager coaching logs. These are the most sensitive HRM
records in the system (disciplinary/legal exposure), so confidentiality is the design crux, not an afterthought.

## Leaders surveyed (with source links)

Dedicated software vendor pages specifically branding a "PIP / warning-letter / coaching" module are thinner than
for mainstream performance-review features — most vendors bundle corrective action into "Performance Management"
or "Employee Relations Case Management" generically. Coverage below reflects what was actually found (per the
research-agent Guardrails: report only what was found, do not invent).

1. **Lattice** — performance-suite leader; PIPs are a first-class, branded feature (structured plans + built-in HR
   approval + progress tracking + analytics) — [Platform: PIPs](https://lattice.com/platform/performance/pips),
   [Help Center: Performance Improvement Plans (PIP)](https://help.lattice.com/hc/en-us/articles/7122107700247-Performance-Improvement-Plans-PIP)
2. **PerformYard** — performance-management suite with the most detailed public PIP feature page found (full
   section breakdown, approval workflow, progress automation, visibility model) —
   [Performance Improvement Plan Software](https://www.performyard.com/performance-improvement-plans)
3. **BambooHR** — HRIS leader; positions PIPs as a documented HR process/glossary concept and commonly
   integrates with dedicated performance vendors (Lattice, 15Five, Culture Amp, Leapsome, Engagedly, PerformYard)
   rather than shipping a deeply-branded native PIP module —
   [HR Glossary: Performance Improvement](https://www.bamboohr.com/resources/hr-glossary/performance-improvement)
4. **15Five** — continuous-performance leader; favors OKRs/weekly check-ins/engagement over a dedicated PIP
   product (per comparison coverage, no dedicated PIP feature surfaced) —
   [Confirm: Lattice vs 15Five vs BambooHR](https://www.confirm.com/blog/lattice-vs-15five-vs-bamboohr)
5. **SAP SuccessFactors** — enterprise HCM suite; supports disciplinary-measures templates (date, employee
   details, acknowledgment) and can auto-launch a PIP workflow off a "Below Expectations" review rating in
   Performance & Goals — [SAP Community: PIPs Beyond the 90-Day Termination Process](https://community.sap.com/t5/human-capital-management-blog-posts-by-members/sap-successfactors-performance-improvement-plans-beyond-the-90-day/ba-p/14150451),
   [SAP SuccessFactors Performance & Goals](https://www.sap.com/products/hcm/performance-goals.html)
6. **Workday** — enterprise HCM; PIP/corrective-action content found was primarily university/enterprise HR
   *policy* guidance (Indiana University, Ohio State, UW) rather than Workday product documentation — no
   Workday-specific PIP feature page surfaced in this pass; noted as a gap —
   [Indiana University: Performance Improvement / Corrective Action](https://hr.iu.edu/relations/ca/performance.html)
7. **Keka** (India/APAC HRIS leader) — ships warning-letter *templates/guidance* (attendance, misconduct,
   negligence, dress code) and documents that disciplinary workflows should progress verbal → written, framed
   as "legally defensible and fully auditable" —
   [Keka: How to Write a Warning Letter](https://www.keka.com/warning-letter-to-employee),
   [Keka: Disciplinary Action (Glossary)](https://www.keka.com/glossary/disciplinary-action)
8. **Darwinbox** (APAC HRIS leader) — HR glossary describes the standard 4-type ladder (verbal → written →
   suspension → termination) and a 5-step disciplinary framework (identify → investigate → communicate → act →
   follow-up); no Darwinbox-specific in-product screenshots/fields surfaced —
   [Darwinbox: Disciplinary Action](https://darwinbox.com/hr-glossary/disciplinary-action)
9. **greytHR** (India HRIS leader) — community forum confirms "disciplinary warning" is a live, discussed
   product concept among customers, but no official feature-page detail surfaced in this pass —
   [greytHR Community: Disciplinary Warning](https://community.greythr.com/t/disciplinary-warning/8644)
10. **Culture Amp** — performance-suite vendor; the most complete *structural* PIP guide found (basic details,
    performance issue, expected standards, improvement goals, support/resources, timeline & check-ins,
    measurement criteria, possible outcomes, acknowledgment) with a worked 60-day/bi-weekly-check-in example —
    [Culture Amp: Performance Improvement Plan — In-Depth Guide](https://www.cultureamp.com/blog/performance-improvement-plan-guide)
11. **HR Acuity** — dedicated employee-relations case-management vendor; frames PIPs as case records
    ("conversations, follow-ups, documentation, and outcomes... in a single, secure system") with guided
    check-in reminders — closest analog to what 3.21's confidentiality/audit design should achieve —
    [HR Acuity: PIPs — Understanding What They Are](https://www.hracuity.com/blog/pip/)
12. **AIHR** (HR practice/analyst body, cited for the progressive-discipline ladder used across most vendors'
    glossaries) — canonical 4-stage ladder (verbal → written → final/suspension → termination) with
    per-stage documentation requirements and incident categories (attendance, conduct, performance, policy) —
    [AIHR: Progressive Discipline — 5 Steps](https://www.aihr.com/blog/progressive-discipline/)
13. **Jackson Lewis** (employment-law firm, cited for the legal/compliance angle every enterprise HRIS vendor
    designs around) — documents the "PIP must appear corrective, not punitive" defensibility standard, the
    "record check-ins/feedback/whether expectations were met" evidentiary requirement, and the real-world
    linkage of a PIP's content to prior performance-review findings —
    [Jackson Lewis: Performance Management — Employer Strategies as PIPs Come Under Scrutiny](https://www.jacksonlewis.com/insights/performance-management-employer-strategies-pips-come-under-scrutiny)
14. **Engagedly / Trakstar / Leapsome / Zoho People / ELMO** — surveyed via comparison/search coverage
    (PerformYard-vs-Trakstar, PerformYard-vs-Engagedly, Zoho People feature pages); PIP/disciplinary-specific
    feature detail did not surface distinctly beyond "supports PIPs within the broader performance suite" — noted
    as a coverage gap rather than invented — [PerformYard vs Trakstar](https://www.performyard.com/compare/performyard-vs-trakstar),
    [Engagedly: PerformYard vs Trakstar comparisons](https://engagedly.com/blog/performyard-alternatives/),
    [Zoho People: Employee Management System](https://www.zoho.com/people/employee-management-system.html)

## Feature catalog by sub-module

### 3.21 Performance Improvement — PIP Management

- **PIP creation from a template with a structured section set** — Basic details (employee, role, manager,
  start/end date), performance-issue description, expected standards, improvement goals, support/resources,
  timeline & check-in schedule, measurement criteria, possible outcomes, acknowledgment · seen in: PerformYard,
  Culture Amp, HR Acuity · priority: **must-have** · spine: new table `PerformanceImprovementPlan` (fields carry
  the described sections; FK subject/manager to `hrm.EmployeeProfile`) · buildable now
- **Initiation trigger from a poor review / off a rating threshold** — SAP SuccessFactors can auto-launch a PIP
  workflow when a Performance & Goals rating is "Below Expectations"; Jackson Lewis notes real PIPs explicitly
  cite the employee's prior annual review findings · seen in: SAP SuccessFactors, Jackson Lewis (legal framing) ·
  priority: **must-have** (as an optional link, not a hard auto-trigger for v1) · spine: nullable FK
  `triggering_review` → `hrm.PerformanceReview` · buildable now
- **SMART improvement goals/expectations tied to the plan** — measurable, specific, time-bound expectations
  ("respond to 90% of client emails within 24 hours for 4 weeks") distinct from vague criticism · seen in:
  PeopleGoal, Culture Amp, general PIP guidance · priority: **must-have** · spine: text field(s) on the PIP
  (`improvement_goals`) plus optionally FK'ing 3.18 `Objective` rows created *for* the PIP (an employee's
  improvement objective can literally be an `Objective` scoped to the PIP window) · buildable now — the
  Objective-link is a stretch, text-field summary is the v1 floor
- **Defined timeline: 30/60/90-day options** — shorter plans (~30 days) for narrow/behavioral issues, longer
  (60–90 days) for complex skill gaps requiring coaching + practice + consistency · seen in: Culture Amp, AIHR,
  general PIP literature (near-universal across every source surveyed) · priority: **must-have** · spine:
  `start_date`/`end_date` (or a `duration_days` choice field) on the PIP · buildable now
- **Scheduled review checkpoints / check-ins with progress ratings** — PerformYard automates check-in date
  scheduling and prompts both manager and employee for status updates against goals/milestones; Culture Amp's
  worked example uses bi-weekly check-ins inside a 60-day plan; HR Acuity frames this as "guided check-ins and
  reminders" so plans don't drift · seen in: PerformYard, Culture Amp, HR Acuity, SAP SuccessFactors · priority:
  **must-have** · spine: new child table `PIPCheckIn` (or `PIPReviewPoint`), FK to the PIP, `checkin_date`,
  progress narrative, a status/rating field · buildable now
- **Support & resources tracked alongside the plan** — coaching, training, more-frequent 1:1s, clearer
  prioritization — the plan documents what the ORGANIZATION will provide, not just what the employee must do (the
  "not punitive" defensibility framing) · seen in: Culture Amp, Jackson Lewis · priority: **must-have** (as a
  text field; a separate resource-catalog table is over-scope for this pass) · spine: text field
  (`support_provided`) on the PIP; optionally FK a 3.20 `OneOnOneMeeting` cadence — deferred to link, but the
  text field ships now · buildable now
- **Standardized, admin-customizable templates** — admins can create/rename PIP templates matching company
  culture/policy language · seen in: Lattice, PerformYard · priority: **nice-to-have** · spine: would need a new
  `PIPTemplate` catalog table (mirrors `hrm.ReviewTemplate`) — **defer**; a single flexible model with free-text
  goal/expectation fields covers v1 without a template layer
- **Built-in HR approval workflow before employee notification** — a PIP must be signed off by HR before the
  employee sees it (protects against a manager unilaterally issuing one) · seen in: Lattice, PerformYard ·
  priority: **must-have** · spine: a `status` lifecycle field on the PIP (`draft`/`pending_hr_approval` or folded
  into `active`) — model as explicit states so the workflow is enforceable, not just descriptive · buildable now
- **Employee acknowledgment / sign-off logs** — Lattice explicitly calls out "employee acknowledgment logs";
  PerformYard's "sign-off and acknowledgment workflows for HR, managers, and employees"; Culture Amp lists
  signatures from both manager and employee as a required section · seen in: Lattice, PerformYard, Culture Amp,
  HR Acuity · priority: **must-have** · spine: `acknowledged_at`/`acknowledged_by` timestamp fields on the PIP
  (mirrors `PerformanceReview.acknowledged_at`/`acknowledged_by` field-for-field) · buildable now
- **Timeline adjustments / mid-plan extension** — Lattice references "timeline adjustments as circumstances
  change"; Culture Amp's outcome model explicitly includes "extension" as a distinct path (progress exists but
  more time is needed) · seen in: Lattice, Culture Amp · priority: **must-have** · spine: an `extended` outcome
  value + an `extended_end_date` field on the PIP (rather than a separate extension-request table) · buildable
  now
- **Structured completion outcomes** — the near-universal 3-way (sometimes 4-way) outcome model: **successful**
  (return to normal performance management), **extended** (more time granted), **failed/termination** (expectations
  not met, action escalates up to termination) · seen in: Culture Amp (3-way), general PIP literature, SAP
  SuccessFactors (explicitly ties the 90-day PIP to a termination-process endpoint), Jackson Lewis (legal
  documentation of the failure path) · priority: **must-have** · spine: `outcome` choice field
  (`successful`/`extended`/`failed`/`terminated`) + `outcome_date`/`outcome_notes` on the PIP; a `failed`/
  `terminated` outcome should be a manually-set flag this pass — NOT an automatic FK into `SeparationCase`
  (3.9 offboarding) since that cross-sub-module wiring is bigger than one pass · buildable now (flag only);
  auto-creating a `SeparationCase` on `terminated` outcome is **defer**
- **Analytics / trend surfacing across PIPs** — Lattice explicitly markets "analytics to surface trends
  individual plans can't show" (coaching gaps, repeat-offender patterns across managers/departments) · seen in:
  Lattice · priority: **nice-to-have** · spine: a computed dashboard view (mirrors 3.20's `feedback_dashboard` —
  a view, not a model) reading PIP/`outcome`/`status` aggregates · **defer** to a later pass (BI-module territory
  once PIPs exist)
- **Centralized, secure single-system storage of conversations/follow-ups/documentation/outcomes** — HR Acuity's
  core value prop ("everything lives in one secure system") · seen in: HR Acuity · priority: **must-have** (this
  is the confidentiality/access-control requirement, addressed structurally below, not a separate feature) ·
  spine: the tenant-scoped model set itself + the view-layer confidentiality gate · buildable now

### 3.21 Performance Improvement — Warning Letters

- **Progressive discipline ladder: verbal → written → final/suspension → termination** — the standard 3–4 level
  escalation nearly every HR glossary and vendor documents identically · seen in: AIHR, Darwinbox, Keka, general
  HR policy sources (UW, Duke, Ohio State, Indiana University) · priority: **must-have** · spine: `level` choice
  field on `WarningLetter` (`verbal`/`written`/`final`/`suspension`) — termination itself is out of scope (that's
  `SeparationCase` in 3.9 offboarding, already built; a warning letter can optionally note it preceded one)
  · buildable now
- **Incident categorization** — attendance/tardiness, conduct/misconduct/insubordination, performance
  (incomplete work, missed deadlines), policy violation (safety, device misuse, dress code) · seen in: AIHR,
  Darwinbox, Keka (attendance/misconduct/negligence/dress-code templates) · priority: **must-have** · spine:
  `category` choice field on `WarningLetter` · buildable now
- **Incident/issue documentation with specifics** — date, time, specific actions/behaviors, which policy was
  violated — vague criticism is explicitly called out as insufficient (legal-defensibility requirement) · seen
  in: AIHR, Jackson Lewis, Keka · priority: **must-have** · spine: `incident_date`, `description` (specific
  behaviors), `policy_reference` fields on `WarningLetter` · buildable now
- **Issued-by / issued-to with escalation context (prior warnings referenced)** — Darwinbox's termination stage
  requires confirming "all previous warnings and actions" documented and aligned; a later-stage warning should be
  able to reference the ones before it · seen in: Darwinbox, AIHR · priority: **must-have** · spine:
  `issued_to`/`issued_by` FK to `hrm.EmployeeProfile`; optional self-FK `prior_warning` (or simply derive "prior
  warnings" as a query over the same employee + earlier `issued_date` — cheaper, no self-FK needed) · buildable
  now
- **Employee acknowledgment / signature / response** — every source (AIHR, Culture Amp, Keka, PerformYard)
  requires the employee sign to confirm receipt, and several allow the employee to add a written response/comment
  (AIHR: "allowing the employee to explain themself") · seen in: AIHR, Keka, general HR policy sources · priority:
  **must-have** · spine: `acknowledged_at`/`acknowledged_by` (mirrors PIP/Review pattern) + `employee_response`
  text field · buildable now
- **Expiry of a warning after a defined period** — implied by every progressive-discipline framework (a stale
  verbal warning from 2 years ago shouldn't count toward today's escalation decision), though no source gave an
  exact universal duration — company-policy-dependent · seen in: general progressive-discipline literature (AIHR
  notes escalation timeframes aren't universally standardized) · priority: **nice-to-have** · spine: an
  `expiry_date` field (optional, tenant sets policy) — a derived `is_active`/`is_expired` property reads it ·
  buildable now (field is cheap even if the escalation-suggestion logic is deferred)
- **Letter generation / print / formal document output** — Keka explicitly ships pre-built warning-letter
  *templates* (verbal/written/final wording per category) that render into a formal document; this mirrors
  NavERP's existing `relieving_letter.html`-style print pages (3.9 offboarding already has this pattern) · seen
  in: Keka, PeopleStrong (warning-letter samples) · priority: **must-have** · spine: no new model — a
  print/detail template (`warningletter/print.html` alongside the CRUD triple), same pattern as
  `hrm/offboarding/relieving_letter.html` · buildable now (template-layer, not a model)
- **Investigation step before action** — Darwinbox's 5-step framework places "Investigation — gather relevant
  evidence" between identification and communication · seen in: Darwinbox · priority: **nice-to-have** · spine:
  could be a `status` value (`under_investigation`) before `issued`, or simply captured in `description` free
  text · **defer** the dedicated investigation-workflow state; `draft` status covers the pre-issue gap for v1
- **Connection to a triggering PIP or standalone** — a warning letter can be issued independent of a PIP (a
  single conduct incident) or as part of an active PIP's documented escalation · seen in: general disciplinary
  literature (the PIP and warning-letter tracks are related but not identical — a PIP is about *performance*, a
  warning letter can be about *conduct* too) · priority: **must-have** · spine: nullable FK
  `related_pip` → `PerformanceImprovementPlan` · buildable now

### 3.21 Performance Improvement — Coaching Notes

- **Manager coaching log / "manager journal"** — a running, dated log of private observations a manager keeps
  on a direct report throughout the year, referenceable later when writing a formal review — explicitly described
  as separate from the shared 1:1 notes/action items already built in 3.20 · seen in: general coaching-software
  research (PerformSpark, AppMaster), described as a "manager journal" pattern feeding into performance reviews ·
  priority: **must-have** · spine: new table `CoachingNote`, append-only style (mirrors how `GoalCheckIn` rows
  ARE a KeyResult's history — no separate "history" table) · buildable now
- **Private vs. shared distinction for coaching content** — coaching-software research explicitly separates a
  manager's *private* note ("Coach on meeting prep") from a *shared* action item ("Send agenda 24h before next
  1:1") — private notes track patterns/prep, shared items track mutual accountability · seen in: general coaching
  software research (Ambition, AppMaster) · priority: **must-have** · spine: `CoachingNote` is manager-only by
  default (mirrors `PerformanceReview.private_notes`/`OneOnOneMeeting.manager_private_notes` — never rendered to
  the coached employee); NavERP already has the shared-item mechanism (`MeetingActionItem`, 3.20) so 3.21 does
  NOT need to rebuild a shared-item table — a coaching note can optionally reference an existing
  `OneOnOneMeeting`/`MeetingActionItem` instead of duplicating one
- **Optional link to an active PIP** — a coaching note is frequently written *because of* an active PIP (the
  manager logs each coaching touchpoint that the PIP's "support & resources" section promised) but can equally
  stand alone (day-to-day coaching unrelated to any formal corrective action) · seen in: Culture Amp (support
  section implies ongoing coaching touchpoints), general PIP literature · priority: **must-have** · spine:
  nullable FK `related_pip` → `PerformanceImprovementPlan` · buildable now
- **Session/note history retrieval, pulled up while writing a formal review** — "the manager journal feature
  allows you to log private notes on team members throughout the year and pull them up directly while filling
  out a review" — directly informs 3.21's design goal of feeding forward into 3.19 · seen in: general coaching
  software research · priority: **nice-to-have** (the retrieval-into-review-form UX is a stretch goal; the notes
  existing and being queryable by employee is the v1 floor) · spine: `CoachingNote.employee` FK makes "all
  coaching notes for this person" a simple filtered queryset — no new join table needed; wiring it INTO the
  `PerformanceReview` form's context is a nice-to-have, not required this pass
- **Coaching topic/category tagging** — general coaching-session software (GetApp/Capterra coaching-category
  results) supports tagging notes by theme (skill development, behavior, career growth) for later retrieval ·
  seen in: general coaching-software comparison coverage · priority: **nice-to-have** · spine: a lightweight
  `category`/`topic` choice or free-text field on `CoachingNote` · buildable now (cheap field, not a catalog)

## Recommended build scope (this pass — 4 models)

- **`PerformanceImprovementPlan`** `[PIP-]` (`TenantNumbered`) — the corrective-action plan header. Fields
  justified by: PerformYard's section breakdown + Culture Amp's structural checklist + Lattice's approval/
  acknowledgment/analytics framing + SAP SuccessFactors' rating-trigger + Jackson Lewis' legal-documentation
  requirements.
  - `subject` FK `hrm.EmployeeProfile` (the employee on the plan), `manager` FK `hrm.EmployeeProfile` (who owns
    it — usually the direct manager, could differ from the current employment manager if escalated)
  - `triggering_review` — nullable FK `hrm.PerformanceReview` (optional link back to the 3.19 review that
    prompted this)
  - `status` — choices e.g. `draft` / `pending_hr_approval` / `active` / `closed` (the HR-sign-off-before-
    employee-sees-it workflow from Lattice/PerformYard)
  - `outcome` — choices `` (blank while open) / `successful` / `extended` / `failed` / `terminated` (Culture
    Amp's 3-way + the SAP/Jackson-Lewis termination-endpoint framing) + `outcome_date`, `outcome_notes`
  - `performance_issue` (text — the specific gap, not vague criticism), `expected_standards` (text),
    `improvement_goals` (text — the SMART expectations), `support_provided` (text — training/coaching/resources
    the org commits to), `measurement_criteria` (text)
  - `start_date`, `end_date`, `extended_end_date` (nullable — the extension path)
  - `acknowledged_at`, `acknowledged_by` (FK `hrm.EmployeeProfile`) — mirrors `PerformanceReview` field-for-field
  - `hr_approved_at`, `hr_approved_by` (FK `hrm.EmployeeProfile`) — the approval-workflow gate
  - Confidentiality: visible only to `subject`, `manager`, and tenant admin/HR — mirror `_can_view_review`/
    `_visible_reviews_q` exactly (subject-or-owner-only, no team/public tier — a PIP is never "team visible" the
    way 3.20 Feedback can be)

- **`PIPCheckIn`** `[PCI-]` (`TenantNumbered`, child of the PIP) — the scheduled review-checkpoint row. Fields
  justified by: PerformYard's automated check-in scheduling/status-update prompts + Culture Amp's bi-weekly
  worked example + HR Acuity's "guided check-ins and reminders."
  - `pip` FK `PerformanceImprovementPlan` (`related_name="checkins"`)
  - `checkin_date` (scheduled date), `completed_at` (nullable — actually held vs. just scheduled)
  - `progress_notes` (text — the shared narrative, both manager and employee facing per PerformYard's dual-
    prompt model)
  - `progress_rating` — a small enum (`on_track` / `at_risk` / `off_track`) or a numeric scale — the checkpoint's
    assessment, mirrors how `GoalCheckIn` captures a KeyResult's periodic snapshot
  - Confidentiality inherits from the parent PIP (no independent gate needed — same visible-to-subject/manager/
    admin set)

- **`WarningLetter`** `[WRN-]` (`TenantNumbered`) — the progressive-discipline document. Fields justified by:
  AIHR's 4-stage ladder + Darwinbox's category/escalation framing + Keka's category templates + the universal
  employee-acknowledgment requirement.
  - `issued_to` FK `hrm.EmployeeProfile`, `issued_by` FK `hrm.EmployeeProfile`
  - `level` — choices `verbal` / `written` / `final` / `suspension` (the standard ladder)
  - `category` — choices `attendance` / `conduct` / `performance` / `policy_violation`
  - `incident_date`, `description` (specific behaviors/actions, per the legal-defensibility requirement),
    `policy_reference` (which policy/handbook section was violated)
  - `related_pip` — nullable FK `PerformanceImprovementPlan` (a warning can stand alone or escalate out of an
    active PIP)
  - `status` — choices `draft` / `issued` / `acknowledged` / `expired`
  - `acknowledged_at`, `acknowledged_by` (FK `hrm.EmployeeProfile`), `employee_response` (text — the employee's
    optional written comment/rebuttal)
  - `expiry_date` (nullable — company-policy-dependent staleness window; a derived `is_active` property reads it)
  - Confidentiality: same subject-or-manager-or-admin-only gate as the PIP — arguably even stricter (never
    "team-visible")

- **`CoachingNote`** `[CN-]` (`TenantNumbered`, append-only style) — the manager's private coaching log. Fields
  justified by: the "manager journal" pattern (private notes logged over time, pulled into formal reviews) + the
  private-vs-shared distinction from coaching-software research + the optional PIP linkage.
  - `employee` FK `hrm.EmployeeProfile` (the coached party), `coach` FK `hrm.EmployeeProfile` (almost always the
    manager, named generically since a skip-level or HRBP could also coach)
  - `related_pip` — nullable FK `PerformanceImprovementPlan` (this coaching touchpoint fulfills the PIP's
    support-and-resources commitment) — optional, most coaching notes will be standalone day-to-day observations
  - `note_date` (when the coaching moment happened — may differ from `created_at`)
  - `category`/`topic` — light free-text or small choice field (skill development / behavior / career growth /
    other)
  - `content` (text — the observation/coaching log itself)
  - Confidentiality: **manager/coach + admin only** — this is the one 3.21 model NOT automatically visible to
    its own subject employee (mirrors `OneOnOneMeeting.manager_private_notes` exactly: a coaching note is a
    manager's private working document, never rendered on the coached employee's own view, unlike the PIP/warning
    letter which the employee explicitly must see and acknowledge)

All four models FK `hrm.EmployeeProfile` by string (never a new employee table); `PIPCheckIn` is the only child
row (mirrors the `ReviewRating`→`PerformanceReview` / `KeyResult`→`Objective` child-row shape already established
in 3.18/3.19). No new core-spine entity is introduced and nothing posts to the GL — this is a pure HR-process
sub-module, consistent with 3.18/3.19/3.20.

**The confidentiality gate to build (view-layer, mirrors 3.19/3.20 exactly):**
- `_can_view_pip(request, pip)` / `_visible_pips_q(request)` — admin, OR `profile.pk in (pip.subject_id,
  pip.manager_id)`. No team/public tier (unlike 3.20 Feedback) — a PIP is confidential to only its two named
  parties + HR.
- `_can_view_warning(request, letter)` / `_visible_warnings_q(request)` — same subject-or-issuer-or-admin shape.
- `_can_view_coaching_note(request, note)` — admin OR `profile.pk == note.coach_id` **only** (the coached
  employee is explicitly EXCLUDED — this is the strictest gate in the whole performance-management cluster,
  deliberately narrower than the PIP/warning gates because a coaching note is the manager's private working
  document, not a document the subject has any right to see or acknowledge).
- `_can_edit_pip`/`_can_edit_warning` — status-locked once acknowledged (mirrors `_can_edit_review`'s
  `status == "draft"` gate) plus author/manager/admin check.
- `hr_approved_by`/`acknowledged_by` fields must never be reachable by the subject employee before the
  appropriate lifecycle stage — mirror the `_can_view_review` "the subject must never reach the edit form to
  read [private notes]" pattern precisely.

## Deferred (later passes / integrations)

- **`PIPTemplate` catalog** (admin-customizable PIP form templates, mirrors `hrm.ReviewTemplate`) — v1 ships one
  flexible `PerformanceImprovementPlan` model with free-text sections instead; a template layer is additive later
  if tenants need per-policy wording variants.
- **Auto-creating a `SeparationCase` (3.9 offboarding) on a `terminated` PIP/warning outcome** — this is
  cross-sub-module automation; this pass only sets the `outcome` flag. Wiring PIP-failure → offboarding kickoff
  is a natural follow-on once 3.21 exists, but is bigger than one sub-module pass.
- **Analytics/trend dashboard across PIPs and warnings** (Lattice's "surface trends individual plans can't
  show" — repeat-manager or repeat-department patterns) — a computed view once there's enough data volume;
  candidate for the BI module (10) or a later HRM analytics pass, not this one.
- **Investigation-workflow state** (Darwinbox's identify→investigate→communicate→act→follow-up 5-step framework)
  — folded into `draft` status + free-text `description` for v1; a dedicated `under_investigation` status/evidence
  log is deferred.
- **Warning-letter self-FK escalation chain** (`prior_warning` pointer) — deferred in favor of deriving "prior
  warnings for this employee" via a simple query (`WarningLetter.objects.filter(issued_to=x,
  incident_date__lt=this.incident_date)`) — cheaper than a stored link, avoids a self-referential FK for a value
  that's fully derivable.
- **Wiring `CoachingNote` retrieval into the `PerformanceReview` create/edit form** (the "manager journal" UX of
  pulling notes up while writing a review) — the notes exist and are queryable by employee this pass; surfacing
  them inline in the 3.19 review form is a nice-to-have follow-on, not required to ship 3.21.
- **PIP support-and-resources structured sub-table** (a catalog of "training assigned" / "1:1 cadence" rows
  instead of a free-text field) — `support_provided` ships as text this pass; a structured resource-tracking
  child table is over-scope.
- **Letter e-signature / external delivery integration** (formal e-sign, email delivery receipts) — the
  `acknowledged_at`/`acknowledged_by` fields capture an in-app acknowledgment this pass; a real e-signature
  integration (DocuSign-style) is Module-0/integration territory, later.
- **Workday-specific PIP/corrective-action feature detail** — no Workday product page was found describing a
  distinct native PIP feature (results were policy pages from customer universities, not Workday documentation);
  flagged as a research gap rather than invented content.
