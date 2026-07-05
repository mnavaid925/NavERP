# Research — Module 3.19: Performance Review (hrm)

## Grounding (read before recommending)
- Employees are `core.Party` + `hrm.EmployeeProfile` (`apps/hrm/models.py:230`). A review's subject/reviewer is
  always an `EmployeeProfile` FK — never a raw `Party`/`User`.
- **Manager chain is derived, not stored on EmployeeProfile.** `EmployeeProfile.manager` (line 320-322) is a
  `@property` that reads `self.employment.manager` — and `core.Employment.manager` (core/models.py:175) is a
  `ForeignKey("core.Party", ...)`. So a manager-review / reporting-chain query filters via
  `EmployeeProfile.objects.filter(employment__manager=some_party)`, never a new manager FK on the review models.
- **3.18 Goal Setting is already built** and must be referenced, not rebuilt: `GoalPeriod` (line 4889, per-tenant
  named cycle catalog, not auto-numbered — `PERIOD_TYPE_CHOICES` quarterly/half_yearly/annual/custom, `STATUS_CHOICES`
  draft/active/closed/archived), `Objective` (line 4947, `OBJ-` prefix, FK `owner→EmployeeProfile`,
  FK `goal_period→GoalPeriod`, derived `progress_pct`/`health_status`), `KeyResult` (line 5058, `KR-` prefix, FK
  `objective→Objective`, derived `progress_pct`), `GoalCheckIn` (line 5151, `GCI-` prefix, append-only history log).
  A 3.19 review's "goal achievement" section pulls the employee's `Objective` set for the period — it does not
  duplicate objective/KR fields.
- `TenantOwned`/`TenantNumbered` abstract bases (hrm/models.py:39-70+) are the house pattern: `tenant` FK
  (`related_name="+"`), `created_at`/`updated_at`, and (`TenantNumbered`) an auto `number` from `NUMBER_PREFIX` via
  `next_number()` with a retry-on-collision loop. `GoalPeriod` uses the lighter `TenantOwned` (small catalog, named
  not numbered) — `ReviewCycle` should follow the same pattern since it's the same "named cycle" shape.
- **39 NUMBER_PREFIX values already in use** across `apps/hrm/models.py` (checked via grep): `EMP, LA, LR, ENC, TS,
  OT, ATT, REG, ONBT, ONB, AST, SEP, EI, FNF, EDOC, ELC, JDTMPL, JR, CAND, APP, CETMPL, CC, INTV, IFB, OLTMPL, OFR,
  BGV, SST, ESS, PRC, PSL, SCR, ITD, TXC, POB, BRC, OBJ, KR, GCI`. Also checked `apps/accounting` and `apps/crm` for
  cross-app clashes (not required since prefixes are scoped by model via `next_number(type(self), ...)`, but kept
  distinct for readability): none of the proposed prefixes below collide.
- `NavERP-ERD.md` (roadmap table, line 465) already names `PerformanceReview` as a Module-3 extension entity reusing
  the spine (`Party` employee role · `Employment` · `OrgUnit` · `JournalEntry` for payroll) — confirming this is the
  expected direction, not a net-new concept.

## Leaders surveyed (with source links)
1. **Lattice** — growth-stage all-in-one performance suite (goals+reviews+feedback+comp); AI-drafted reviews,
   auto-created calibration groups from org chart — [Performance platform page](https://lattice.com/platform/performance), [Lattice appraisal software guide](https://lattice.com/articles/how-to-evaluate-and-choose-employee-appraisal-software)
2. **15Five** — "Best-Self Review®"; strongest documented review-cycle *data model* (cycle = participants + review
   types + timeline + question templates), 9-box Talent Matrix, Private Manager Assessment section — [Best-Self Review feature overview](https://success.15five.com/hc/en-us/articles/360002700091-Best-Self-Review-Feature-Overview), [Perform product page](https://www.15five.com/products/perform)
3. **Culture Amp** — "Unified Performance Cycle" unifying self-reflection + peer + upward + manager review into one
   flow; Calibration Views + Ratings Preview for bias reduction — [Performance reviews feature page](https://www.cultureamp.com/platform/features/performance-reviews), [Support: unified cycle](https://support.cultureamp.com/en/articles/7048424-launch-a-performance-review-cycle)
4. **Leapsome** — competency framework is the connective tissue across reviews/goals/feedback; live heatmap / 9-box
   calibration; supports project-based, 360°, leadership, external review types — [Performance reviews product page](https://www.leapsome.com/product/performance-reviews), [Competency framework page](https://www.leapsome.com/product/competency-framework)
5. **BambooHR** — mid-market Pro-tier performance add-on; self/manager/peer/**skip-level** review types, up to 10
   custom questions per cycle, goal integration; calibration explicitly noted as thinner than enterprise rivals — [Performance management platform page](https://www.bamboohr.com/platform/performance-management/)
6. **Betterworks** — enterprise continuous-performance suite; **Calibration is sold/positioned as its own module**
   with side-by-side comparison + "fairness rules"; all major feedback types (one-off/scheduled/peer/upward/360) — [Performance review software product page](https://www.betterworks.com/product/performance-review-software), [Best 360 tools guide](https://www.betterworks.com/magazine/best-360-degree-feedback-tools)
7. **PerformYard** — 360 feedback lives *inside* the same review cycle (not a separate survey tool); **flexible
   form-per-participant-type** (peer form ≠ manager form ≠ self form); explicit calibration how-to guide — [Performance reviews product page](https://www.performyard.com/performance-reviews), [360 feedback product page](https://www.performyard.com/360-feedback), [Calibration guide article](https://www.performyard.com/articles/performance-calibration)
8. **Trakstar (Mitratech)** — 360 reviews configurable as up/down/lateral, **anonymous or named** per relationship;
   calibration + anonymous feedback as its bias-mitigation pair — [360 review software page](https://www.trakstar.com/solutions/performance-management-software/360-review-software/), [Performance review software page](https://www.trakstar.com/solutions/performance-management-software/performance-review-software/)
9. **SAP SuccessFactors** — enterprise benchmark for **calibration mechanics**: percentage or numeric distribution
   guideline (bell curve, e.g. 5/20/50/20/5 on a 5-pt scale), Stack Ranker (side-by-side team ranking), Bin View /
   Matrix Grid drag-and-drop rating adjustment — [Overview of Calibration (SAP Help)](https://help.sap.com/docs/successfactors-performance-and-goals/implementing-and-managing-calibration/overview-of-calibration), [Stack Ranker spec (SAP KB 2087388)](https://userapps.support.sap.com/sap/support/knowledge/en/2087388)
10. **Workday Talent** — 9-box **performance × potential** grid; calibration submission **rolls up the management
    chain** to a top-org sign-off; distinguishes `Overall Rating – Manager` from a separate `Calibrated Rating`
    field used downstream in comp — [9-box talent review guide](https://www.confirm.com/blog/9-box-performance-review-talent-evaluation-guide), [Workday calibration FAQ](https://kognitivinc.com/blog/workday-calibration-faq/)

*(Also skimmed for corroboration/differentiators, not separately fetched at full depth: **Engagedly** — AI
auto-assignment of employees to review cycles, AI-calibrated feedback — [Engagedly performance reviews page](https://engagedly.com/product/performance-reviews/); **Synergita** — reviewer *nomination* by the employee for 360,
promotion-cycle + appraisal-letter distribution as a named feature, HiPo (high-potential) score — [Synergita 360 feedback page](https://www.synergita.com/performance-management-software/360-degree-feedback). Rating-scale mechanics (5-point
standard, BARS) cross-checked against [Lattice's rating-scale guide](https://lattice.com/articles/how-to-pick-a-performance-review-rating-scale) and [PerformYard's rating-scales guide](https://www.performyard.com/articles/performance-review-ratings-scales-examples).)*

## Feature catalog by sub-module

### 3.19.1 Review Cycles
- **Named recurring cycle (annual / half-yearly / quarterly / custom)** — the container that scopes every review
  instance to a time window and a set of participants · seen in: 15Five, Culture Amp, PerformYard, Lattice ·
  priority: table-stakes · spine: **new table `ReviewCycle`**, structurally parallel to the already-built
  `hrm.GoalPeriod` (same `PERIOD_TYPE_CHOICES`/`STATUS_CHOICES` shape, different domain) · buildable now
- **Cycle phases/windows (self-assessment window → manager-review window → calibration window → results-release
  date)** — sequenced sub-deadlines inside one cycle · seen in: 15Five ("timeline" in the cycle definition),
  Culture Amp (phased unified cycle), Workday (roll-up submission deadline) · priority: common · spine: fields on
  `ReviewCycle` (phase date fields), no new table needed for this pass · buildable now
- **Optional link to a `GoalPeriod`** so a review cycle can align to (or literally reuse) the same quarter/year as
  the OKR period · seen in: BambooHR ("goal integration"), Lattice, PerformYard (goal check-ins inside the review) ·
  priority: common · spine: **reuse `hrm.GoalPeriod`** via FK (nullable — not every cycle needs an aligned OKR
  period) · buildable now
- **Auto-launch / lifecycle-triggered cycles** (e.g. auto-start N days before an employee's work anniversary) ·
  seen in: 15Five ("Lifecycle Reviews"), Engagedly (AI auto-assignment) · priority: differentiator · spine: would
  need a scheduling/cron mechanism · integration/later
- **Reviewee/participant roster per cycle** (who is being reviewed, and by whom, this cycle) · seen in: every
  product surveyed (it's the cycle's core purpose) · priority: table-stakes · spine: **reuse `EmployeeProfile`** —
  captured on the `PerformanceReview` instance (subject) rather than a separate roster table for this pass ·
  buildable now

### 3.19.2 Self-Assessment
- **Employee self-evaluation form, completed before the manager sees it** — a distinct review "instance" of
  `review_type=self` scoped to the same subject+cycle · seen in: Culture Amp (mandatory self-review baseline),
  PerformYard ("completes a self-evaluation before their manager review"), Trakstar, 15Five, BambooHR · priority:
  table-stakes · spine: **new table** — one row of `PerformanceReview` with `review_type="self"` and
  `subject == reviewer` · buildable now
- **Self-review visible to manager alongside their own rating (side-by-side comparison of self vs. manager view)**
  · seen in: PerformYard ("both perspectives appearing in the review form to surface gaps"), Culture Amp · priority:
  common · spine: a query-time join of the self + manager `PerformanceReview` rows for the same subject+cycle, no
  new field · buildable now
- **Manager can comment on / annotate the employee's self-reflection** · seen in: Culture Amp · priority: common ·
  spine: could reuse a `ReviewRating.comments` field on a manager-authored row referencing the same competency; for
  this pass, keep to the coarser "manager review references the self review's rating" comparison — full
  threaded-comment-on-answer is a nice-to-have, not required for the 4-model scope · buildable now (simple version)
- **Goal/OKR self-reflection section** (employee reflects on their `Objective`/`KeyResult` progress for the period
  as part of self-assessment) · seen in: BambooHR, Lattice, PerformYard ("goal check-ins... inside your performance
  review cycles") · priority: common · spine: **reuse `hrm.Objective`/`hrm.KeyResult`** — the review template can
  flag a section as "goal-review" and the detail page pulls the subject's Objectives for the cycle's linked
  `GoalPeriod`; no new goal fields · buildable now

### 3.19.3 Manager Review
- **Manager evaluation form** — same review-instance shape as self-assessment but `review_type="manager"`,
  authored by the subject's manager (resolved via `EmployeeProfile.manager` → `employment.manager`, a `core.Party`)
  · seen in: all 10 products · priority: table-stakes · spine: **new table**, reuses `EmployeeProfile.manager`
  derived property to resolve/validate the reviewer, no new manager FK anywhere · buildable now
- **Overall rating on a configurable scale** (5-point is the de-facto standard: Unsatisfactory→Needs
  Improvement→Meets→Exceeds→Outstanding) · seen in: every product; scale mechanics cross-checked via Lattice's and
  PerformYard's rating-scale guides · priority: table-stakes · spine: `PerformanceReview.overall_rating`
  (choice/decimal field), scale defined on the `ReviewTemplate` · buildable now
- **Per-competency / per-criterion ratings with comments** (not just one overall number) · seen in: 15Five
  ("Competency ratings"/"Objectives ratings" as separate calibration inputs), Leapsome (competency framework
  *drives* review questions), Culture Amp, BambooHR ("up to 10 custom assessment questions") · priority:
  table-stakes · spine: **new table `ReviewRating`** (one row per competency/question per review instance) ·
  buildable now
- **Behaviorally Anchored Rating Scale (BARS)** — each rating level defined by a concrete behavioral example
  instead of a generic label, for more consistent manager ratings · seen in: 15Five ("customize the opinion scale
  using behaviorally anchored ratings"), cross-checked in the rating-scale research · priority: differentiator ·
  spine: could be a `description`/`anchor_text` field per scale point on `ReviewTemplate`; keep simple (label +
  numeric value) for this pass, BARS anchor text is a natural v2 field addition · buildable now (simplified)
- **Private manager-only section** (promotion/compensation notes not visible to the employee) · seen in: 15Five
  ("Private Manager Assessment... not visible to the employee") · priority: differentiator · spine:
  `PerformanceReview.manager_private_notes` (a field gated from the employee-facing detail view) · buildable now
- **Skip-level / grandparent review** (the manager's manager also reviews) · seen in: BambooHR (named review type) ·
  priority: differentiator · spine: same `review_type` choice mechanism, one more choice value; not core to this
  pass's 4-model scope — note as an easy `review_type` choice addition, not a new table · buildable now (cheap)
- **Weighted overall-rating formula** (e.g. competencies 40% + goals 40% + values 20% = overall) · seen in:
  research on rating-scale best practice (Harvard model cited); Lattice/15Five imply a "rubric formula" behind
  Performance Ratings+ · priority: differentiator · spine: a `weight` field per `ReviewRating` row (mirrors the
  already-built `Objective.weight`/`KeyResult.weight` pattern exactly) so overall can be a derived weighted mean,
  not a stored duplicate · buildable now
- **Review workflow states** (draft → submitted → shared-with-employee → acknowledged) · seen in: implied across
  all products (submission gates visibility; Workday's roll-up chain is an explicit multi-stage submit) · priority:
  table-stakes · spine: `PerformanceReview.status` choice field · buildable now
- **Employee acknowledgment / e-signature on the completed review** · seen in: standard appraisal-cycle practice
  across all surveyed tools (submission → employee sign-off before the cycle closes) · priority: common · spine:
  `PerformanceReview.acknowledged_at`/`acknowledged_by` fields · buildable now

### 3.19.4 360° Feedback
- **Multi-rater participant types in one cycle**: self, manager, peer, upward (direct-report-on-manager), skip-level,
  external · seen in: 15Five, Culture Amp, BambooHR, Betterworks, Trakstar, Leapsome (all list this same set with
  minor naming differences) · priority: table-stakes · spine: `review_type` CharField choices on `PerformanceReview`
  (self/manager/peer/upward/skip_level/external) — one instance per rater, not a separate "participant" table for
  self/manager/upward (those are 1:1 with the subject); **peer/360 needs a real many-rater table** since several
  peers rate the same subject in the same cycle
- **Peer/360 multi-rater collection with rater-nominated participants** (the employee or manager nominates who the
  peer raters are) · seen in: Synergita ("employees able to nominate their reviewers"), Culture Amp (self-review
  mandatory baseline for a 360), PerformYard (peer input folded into the same cycle) · priority: common · spine:
  **reuse `PerformanceReview`** with `review_type="peer"`/`"upward"` rows, `reviewer` FK ≠ `subject` FK — no
  separate "participant" table needed since each peer's feedback IS a `PerformanceReview` row scoped to the same
  cycle+subject · buildable now
- **Anonymous vs. named feedback per relationship type** (peer/upward feedback can be shown anonymized to the
  subject while manager review is always named) · seen in: Trakstar ("anonymous or visible... your choice"),
  Culture Amp · priority: common · spine: `is_anonymous` boolean on `PerformanceReview` (or on `ReviewTemplate` as
  a per-review-type default) — display logic masks `reviewer` on the subject-facing detail page · buildable now
- **Per-participant-type form/template differences** (the peer form ≠ the manager form ≠ the self form, even
  within the same cycle) · seen in: PerformYard ("modify the form so peer review is different than manager review,
  which is different than self review") · priority: common · spine: `ReviewTemplate.review_type` scoping — a cycle
  can have multiple templates, one per review_type · buildable now
- **Structured competency framework driving 360 questions** (the same competency catalog used for manager review
  also generates the peer/self/upward question set) · seen in: Leapsome (this is their core differentiator) ·
  priority: differentiator · spine: **reuse `ReviewRating`'s competency concept** across all review_types — same
  `ReviewTemplate` → `ReviewRating` shape regardless of who's rating · buildable now
- **External reviewer** (a client/vendor contact outside the org contributes 360 feedback) · seen in: Leapsome
  ("external reviews") · priority: differentiator · spine: would need to relax `reviewer` from `EmployeeProfile`-only
  to also allow a `core.Party` (non-employee) — deferred; not needed for the initial internal-360 scope ·
  integration/later

### 3.19.5 Calibration
- **Calibration session grouping reviews for cross-manager comparison** (typically by department/org-unit/level) ·
  seen in: Lattice ("auto-create calibration groups from... org chart"), Culture Amp ("Calibration Views"),
  Betterworks, SAP SuccessFactors, Workday · priority: table-stakes · spine: could be its own table, but for a
  4-model pass this is better expressed as a **calibration status + calibrated-rating field pair on
  `PerformanceReview`** (mirrors Workday's explicit `Overall Rating – Manager` vs. `Calibrated Rating` distinction)
  rather than a 5th model — defer the dedicated `CalibrationSession` grouping table
- **Distinct pre-calibration ("manager rating") vs. post-calibration ("calibrated rating") values, with an audit
  trail of the adjustment** · seen in: Workday (explicit two-field distinction used differently downstream in
  comp), SAP SuccessFactors (Bin View "edit a source form"), 15Five ("adjust those ratings in real-time") ·
  priority: table-stakes · spine: `PerformanceReview.manager_rating` (as submitted) +
  `PerformanceReview.calibrated_rating` (nullable, set during calibration) + `calibration_notes` — no new table for
  this pass · buildable now
- **Rating distribution guideline / bell curve** (target percentage or headcount per rating band, e.g.
  5%/20%/50%/20%/5% on a 5-point scale) · seen in: SAP SuccessFactors (named feature with exact mechanics
  documented), Betterworks ("fairness rules"), Lattice ("rating distributions... highlights outliers") · priority:
  differentiator · spine: a **read-only aggregate view/report** over `PerformanceReview.calibrated_rating` grouped
  by cycle+org-unit (a Python `Count`/`aggregate`, not a stored distribution table) — buildable now as a report,
  no new model
- **Stack Ranker — side-by-side team ranking on one screen** · seen in: SAP SuccessFactors (named feature) ·
  priority: differentiator · spine: a report/view sorted by `calibrated_rating` within a manager's direct reports —
  no new table · buildable now (as a view, not a model)
- **9-box talent grid (performance × potential)** · seen in: 15Five ("Talent Matrix"), Workday (their flagship
  calibration mechanic), SAP SuccessFactors (Matrix Grid View) · priority: differentiator · spine: needs a second
  axis ("potential") that none of the researched HRM models currently carry — would need either a new field
  (`PerformanceReview.potential_rating`) or a dedicated talent-review model; **defer the full 9-box visualization**,
  but the `potential_rating` field is cheap to add now for future use · integration/later (visualization); field
  buildable now
- **Calibration roll-up / multi-level submission chain** (a manager's calibrated grid rolls up to their manager,
  ultimately to a top-org sign-off) · seen in: Workday (explicit named mechanic) · priority: differentiator ·
  spine: would reuse the `EmployeeProfile.manager` chain recursively; deferred as a workflow-automation feature ·
  integration/later
- **AI-assisted calibration / bias detection** (AI flags outlier ratings, suggests adjustments, detects blind
  spots) · seen in: Betterworks ("AI surfaces feedback suggestions and detects blind spots"), Engagedly
  ("AI-calibrated feedback") · priority: differentiator · spine: N/A (needs an LLM integration) · integration/later

## Recommended build scope (this pass — 4 models)

- **`ReviewCycle`** [no numbered prefix — follows `GoalPeriod`'s `TenantOwned` catalog pattern, named not numbered]
  — `name` (e.g. "H1 2026 Performance Review"), `cycle_type` (`annual`/`half_yearly`/`quarterly`/`custom` —
  mirrors `GoalPeriod.PERIOD_TYPE_CHOICES`), `status` (`draft`/`active`/`closed`/`archived` — mirrors
  `GoalPeriod.STATUS_CHOICES`), `self_assessment_start`/`self_assessment_end`,
  `manager_review_start`/`manager_review_end`, `calibration_start`/`calibration_end`, `results_release_date`,
  `goal_period` (nullable FK → **reuse `hrm.GoalPeriod`**), `description`. Justified by: Review Cycles
  (15Five's "cycle = participants + review types + timeline", Culture Amp's phased unified cycle, BambooHR/Lattice
  goal-integration).

- **`ReviewTemplate`** [`RVT-` prefix] — `name`, `review_type` (`self`/`manager`/`peer`/`upward`/`skip_level` —
  scopes which participant type this form is for, per PerformYard's "form differs by review type"), `rating_scale`
  (`3_point`/`5_point`/`7_point` choice — the 5-point standard confirmed across all 10 products), `is_anonymous`
  default (per Trakstar's per-relationship anonymity), `include_goal_section` boolean (whether this template pulls
  the subject's `Objective`/`KeyResult` progress into the form, per BambooHR/Lattice/PerformYard goal-integration),
  `instructions` text, `is_active`. Its `ReviewCriterion`-equivalent (competency/question list) is expressed via
  `ReviewRating` rows being pre-seeded from a lightweight JSON/text competency list on the template for this pass
  (avoiding a 5th model) — **if a full competency catalog is wanted later, `ReviewCriterion` is the natural
  extraction**, flagged under Deferred. Justified by: Leapsome's competency-framework-drives-questions pattern,
  15Five's "Question Templates" with optional competency/manager-effectiveness/private sections, BambooHR's "up to
  10 custom assessment questions."

- **`PerformanceReview`** [`RVW-` prefix] — `cycle` (FK → `ReviewCycle`), `template` (FK → `ReviewTemplate`),
  `subject` (FK → `EmployeeProfile`, the person being reviewed), `reviewer` (FK → `EmployeeProfile`, the person
  writing this instance — equals `subject` for self-review), `review_type` (same choices as `ReviewTemplate`,
  copied at creation for query convenience — mirrors how `Objective.scope` is a denormalized-for-query field),
  `status` (`draft`/`submitted`/`shared`/`acknowledged`/`cancelled`), `overall_rating` (decimal, the reviewer's
  submitted score), `manager_rating` (decimal, nullable — the pre-calibration snapshot when `review_type="manager"`,
  distinct from `overall_rating` for audit per Workday's two-field pattern), `calibrated_rating` (decimal, nullable
  — set during calibration, per Workday/SAP SuccessFactors), `potential_rating` (decimal, nullable — cheap 9-box
  groundwork per 15Five/Workday, visualization deferred), `calibration_notes` (text), `manager_private_notes`
  (text — per 15Five's Private Manager Assessment, hidden from the employee-facing view), `is_anonymous` (boolean,
  overridable from the template default), `strengths`/`areas_for_improvement` (text — near-universal
  free-text sections across every product surveyed), `submitted_at`, `acknowledged_at`, `acknowledged_by` (FK →
  `EmployeeProfile`, nullable). `goal_period` is resolved via `cycle.goal_period`, not duplicated. Justified by:
  Self-Assessment + Manager Review + 360° Feedback (this is the per-instance review row for every participant
  type — self/manager/peer/upward all become rows of this one table, exactly as PerformYard/Culture Amp/15Five
  structure it) + Calibration (manager_rating/calibrated_rating/potential_rating fields, per Workday/SAP
  SuccessFactors).

- **`ReviewRating`** [`RVR-` prefix] — `review` (FK → `PerformanceReview`, `related_name="ratings"`),
  `criterion_label` (CharField — the competency/question text; kept as a label rather than a 5th
  `ReviewCriterion` FK model for this pass, per the Deferred note above), `criterion_category`
  (`competency`/`goal`/`value`/`custom` choice — folds 15Five's "Competency ratings / Company Values ratings /
  Objectives ratings" distinction into one field, same pattern as `KeyResult.metric_type` folding several KR types
  into one CharField), `rating_value` (decimal — the per-criterion score on the template's scale),
  `weight` (decimal, default equal-split — **directly mirrors the already-built
  `Objective.weight`/`KeyResult.weight` pattern** so `PerformanceReview.overall_rating` can be derived as a
  weighted mean instead of a manually-typed duplicate), `comments` (text). Justified by: Manager Review's
  per-competency ratings (15Five, Leapsome, Culture Amp, BambooHR's custom questions) + the weighted-formula
  differentiator noted in Manager Review + 360° Feedback's competency-framework-drives-questions pattern (Leapsome)
  since the same `ReviewRating` shape is reused regardless of `review.review_type`.

## Deferred (later passes / integrations)
- **Continuous feedback / kudos / praise / recognition** — belongs to 3.20 Continuous Feedback, not 3.19.
- **1:1 meeting scheduling/notes/action items** — belongs to 3.20 Continuous Feedback.
- **PIP / warning letters / coaching logs** — belongs to 3.21 Performance Improvement.
- **The goal/OKR mechanics themselves (Objective/KeyResult/GoalCheckIn creation, weighting, cascading)** — already
  built in 3.18; 3.19 only *references* `GoalPeriod`/`Objective`/`KeyResult` for the goal-review section, never
  duplicates their fields.
- **Dedicated `ReviewCriterion` / competency-catalog model** — for this pass, competencies are a label + category on
  `ReviewRating` (denormalized per review, no shared catalog). If a tenant wants a reusable, editable
  company-wide competency library (Leapsome's differentiator), extract `ReviewCriterion` as a 5th model in a later
  pass and FK `ReviewRating.criterion` to it instead of a free-text label.
  A `ReviewTemplate` competency section rendered as pre-populated question text is sufficient for v1.
- **Dedicated `CalibrationSession` grouping table** — v1 keeps calibration as fields
  (`manager_rating`/`calibrated_rating`/`calibration_notes`) on `PerformanceReview` plus a report/view that groups
  by cycle + org-unit. A later pass can add `CalibrationSession` (facilitator, group, meeting date, participants)
  if formal session tracking/minutes are needed.
- **Rating-distribution / bell-curve enforcement, Stack Ranker view, 9-box visualization** — all buildable as
  reports/aggregations over the fields already captured (`calibrated_rating`, `potential_rating`) once the core
  4 models exist; no new model required, but no report code is written in this research-only pass.
- **Multi-level calibration roll-up / top-org sign-off chain** (Workday's mechanic) — a workflow-automation feature
  layered on top of the manager chain; deferred as an integration-later item.
- **External/non-employee 360 reviewer** (Leapsome's "external reviews") — would require relaxing `reviewer` to
  accept a `core.Party` outside `EmployeeProfile`; deferred, not needed for internal-360 scope.
- **AI-drafted reviews, AI bias detection, AI auto-assignment to cycles, sentiment scoring** (Lattice, Betterworks,
  Engagedly, Synergita) — all require an LLM integration; out of a single Django pass.
- **Skip-level review as a distinct table** — not deferred as a *feature* (it's cheap — just another
  `review_type` choice value: `skip_level`), but noted here so the build doesn't over-scope trying to model it
  specially.
