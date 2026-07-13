# Research — Module 3: HRM Sub-module 3.38 Talent Management & Succession Planning (talent-succession)

## Existing HRM reuse surface (grepped `apps/hrm/models.py`, ~100 models)
- **`hrm.EmployeeProfile`** (`TenantNumbered`, prefix `EMP`) — the anchor every new model FKs to (never `core.Party` directly).
- **`hrm.Designation`** / **`hrm.JobGrade`** — the "critical role" / seniority-level catalog for succession mapping.
- **`core.OrgUnit`** (`kind="department"`) — org hierarchy; **`core.Employment.manager`** — the reporting line.
- **`hrm.PerformanceReview`** (prefix `RVW`) already stores `manager_rating`, `calibrated_rating`, **`potential_rating`**
  (docstring: *"9-box potential axis (visualization deferred)"*) and `calibration_notes` — i.e. **the 9-box performance
  axis and the calibration workflow already exist**; this pass should plot the grid, not re-store ratings.
  `PerformanceReview.effective_rating` is the calibrated-else-derived performance score to read.
- **`hrm.ReviewCycle`** — the periodic cadence a calibration/talent-review session hangs off.
- **`hrm.Objective`/`KeyResult`** (OKR) and **`hrm.Feedback`**/`KudosBadge` — inputs a talent-pool card can surface, not
  new tables.
- **`hrm.TrainingCourse`/`LearningPath`/`TrainingNomination`** — the development-action catalog a succession/career gap
  points into.
- **`hrm.JobRequisition`** already has **`posting_type` choices `internal|external|both`** and **`hrm.JobApplication`**
  — i.e. an "internal job posting" and its "transfer application" are **already modeled** as a `JobRequisition`
  posted `internal` + a `JobApplication` against it. Internal Mobility needs a thin workflow layer, not new core
  entities.
- **`hrm.CandidateSkill`** — precedent for a structured, freeform-named skill child table (candidate side); no
  equivalent exists yet on the employee side.
- **`hrm.SeparationCase`** / **`ExitInterview`** — the attrition-outcome side that a flight-risk flag should feed into
  later (not reused directly this pass).
- Conventions confirmed from the 3.35 Travel Management tail (`TenantOwned`/`TenantNumbered` base classes,
  `unique_together=("tenant","number")`, `models.Index(fields=["tenant", ...])`, derived `@property` values never
  stored — e.g. `Objective.health_status`, `TravelBooking.out_of_policy`).
- Unused `NUMBER_PREFIX`es confirmed via full grep (avoid collision): `SPL`, `TP`, `SC` are free (`SCR`/`SST`/`SUR`/`SUG`
  are already taken by other models).

## Leaders surveyed (with source links)
1. **Workday Talent Management** — enterprise HCM suite's succession/talent module (N-box, succession pools/plans owned by leaders) — [Workday Talent Management datasheet](https://www.workday.com/content/dam/web/uk/documents/datasheets/datasheet-workday-talent-management-uk.pdf)
2. **SAP SuccessFactors Succession & Development** — succession org charts, AI-assisted successor recommendations, matrix-grid (9-box) rating scales — [SAP Succession & Development](https://www.sap.com/products/hcm/successfactors-succession-development-successor-insights.html), [2H 2025 release highlights](https://community.sap.com/t5/human-capital-management-blog-posts-by-members/2h-2025-release-highlights-of-successfactors-succession-management/ba-p/14240017)
3. **Cornerstone OnDemand (Cornerstone Galaxy)** — configurable 9-box grid, succession plans with skill-gap benchmarking, Career Center for internal job search — [Cornerstone Succession Planning](https://www.cornerstoneondemand.com/platform/succession-planning/), [Career Management](https://www.cornerstoneondemand.com/employee-performance-management/career-management-goals-development-plans-and-certification-software)
4. **Gloat** — AI internal talent marketplace: career pathing, gigs/projects/mentorships/full-time roles, skills-based matching — [Gloat Talent Marketplace](https://gloat.com/platform/the-talent-marketplace/), [G2 feature list](https://www.g2.com/products/gloat/features)
5. **Fuel50** — skills-ontology-driven career pathing (multi-path, non-linear), talent marketplace, AI career agent — [Fuel50 Talent Marketplace](https://fuel50.com/products/talent-marketplace), [What is Career Pathing](https://fuel50.com/learn/what-is-career-pathing-and-how-does-it-work/)
6. **Eightfold AI Talent Management** — skills-based (not title-based) succession readiness scoring, internal mobility matching, workforce planning — [Eightfold Talent Management](https://eightfold.ai/products/talent-management/), [Succession planning & internal mobility](https://eightfold.ai/learn/succession-planning-and-internal-mobility/)
7. **Lattice Grow** — Career Tracks (role/level progression + expected competencies), Individual Development Plans, upcoming Succession Planning with readiness/attrition-risk filters — [Lattice Grow](https://lattice.com/platform/grow), [HR's Guide to Succession Planning](https://lattice.com/articles/hrs-essential-guide-to-succession-planning)
8. **15Five (Growth Studio)** — 9-box Talent Matrix from performance + Private Manager Assessment signals, launches IDP/PIP/succession plans directly from the grid — [15Five Talent Matrix](https://success.15five.com/hc/en-us/articles/360057179491-Analyze-Review-Results-Talent-Matrix)
9. **Zoho People Plus** — 9-box talent matrix, skill-set matrix (skills tagged to roles + employee proficiency), succession planning (Professional tier) — [Zoho People Talent Management](https://www.zoho.com/peopleplus/talent-management.html)
10. **PeopleFluent Succession & Development** — succession slates/pools, drag-and-drop calibration + 9-box, gap/scenario analytics, predictive flight-risk analysis — [PeopleFluent Succession & Development](https://www.peoplefluent.com/products/talent-management-software/succession-and-development/)

Supplementary domain searches (cross-vendor patterns, not single-product pages): 9-box/flight-risk/calibration-session
mechanics — [AIHR 9-box grid guide](https://www.aihr.com/blog/9-box-grid/), [Betterworks succession for critical roles](https://www.betterworks.com/magazine/succession-planning-for-a-world-where-key-roles-dont-wait-for-q4), [SHRM flight-risk identification](https://www.shrm.org/topics-tools/news/technology/how-to-identify-companys-flight-risks), [Sprad talent calibration guide](https://sprad.io/blog/talent-calibration-guide-how-to-run-fair-evidence-based-rating-sessions-templates-inside), [Betterworks calibration](https://www.betterworks.com/product/succession).

## Feature catalog by sub-module bullet (all under NavERP.md 3.38)

### Talent Pool (high-potential identification, 9-box grid)
- **9-box grid (performance × potential)** — plots employees on a 3×3 performance/potential matrix — seen in: Workday, SAP SuccessFactors, Cornerstone, 15Five, Zoho People, PeopleFluent · priority: table-stakes · spine: reuse `PerformanceReview.effective_rating` (performance axis) + `PerformanceReview.potential_rating` (potential axis, already exists) — new table only needs to bucket/derive the quadrant, never re-store the score · buildable now
- **Named talent pools/segments** (e.g. "High Potential", "Future Leaders", "Critical Talent") — curated groups an employee is nominated into — seen in: Workday (succession pools), Cornerstone (talent pools), SAP SuccessFactors (talent pool nominations) · priority: table-stakes · spine: new table `TalentPool` (catalog, mirrors `hrm.TravelPolicy`/`LeaveType` pattern) · buildable now
- **Pool membership with join history + status** — nominate/graduate/remove an employee from a pool over time — seen in: Workday, SAP SuccessFactors, Cornerstone · priority: common · spine: new child table `TalentPoolMembership` FK `TalentPool` + `EmployeeProfile` · buildable now
- **AI-suggested pool candidates from skills/competency data** — auto-recommends who belongs in a pool — seen in: SAP SuccessFactors (AI-Assisted Successor Recommendation), Eightfold, Gloat · priority: differentiator · spine: n/a (no model, algorithmic) · integration/later
- **Skill/competency inventory feeding the pool score** — structured proficiency tags per employee — seen in: Zoho People (skill-set matrix), Fuel50 (skills ontology), Eightfold · priority: common · spine: would need a new `EmployeeSkill` table (no employee-side equivalent to `CandidateSkill` exists yet) · buildable later (deferred this pass — see below)

### Succession Planning (critical role mapping, successor identification)
- **Critical-role register** — flags which positions are business-critical and need a succession plan — seen in: Workday, SAP SuccessFactors, Cornerstone, PeopleFluent, Eightfold · priority: table-stakes · spine: new table `SuccessionPlan`, `critical_role` FK to `hrm.Designation` (reuses the existing role/title catalog instead of a new "Position" table) · buildable now
- **Successor slate with readiness tiers** — multiple candidates per role ranked "ready now / ready 1–2 yrs / ready 3–5 yrs / development needed" — seen in: PeopleFluent (succession slates), SAP SuccessFactors (Suggested Successors + role-readiness explanation), Eightfold, Betterworks/industry-standard readiness bands · priority: table-stakes · spine: new child table `SuccessionCandidate` FK `SuccessionPlan` + `EmployeeProfile` (successor) · buildable now
- **Bench-strength / vacancy-risk indicator** — how many ready successors exist per critical role, risk of an unplanned vacancy — seen in: PeopleFluent, Visier, industry benchmark (target ≥3 successors/role) · priority: common · spine: derived `@property` on `SuccessionPlan` (count of `SuccessionCandidate` by readiness tier), never stored — mirrors `Objective.progress_pct` pattern · buildable now
- **Drag-and-drop org-chart succession view / scenario planning** — visual what-if reorg simulation — seen in: Cornerstone, PeopleFluent, SAP SuccessFactors (Position Tile view) · priority: differentiator · spine: n/a — UI/JS visualization on top of `SuccessionPlan`/`SuccessionCandidate` data · buildable later (template/UI polish, not a data-model gap)
- **Multi-employment / concurrent-position nominations** — an employee nominated as successor for >1 role simultaneously — seen in: SAP SuccessFactors (2H 2025) · priority: differentiator · spine: already possible — `SuccessionCandidate` is a normal FK join, no uniqueness constraint needed beyond `(plan, candidate)` · buildable now

### Career Pathing (role progression maps, skill requirements)
- **Role-to-role progression maps** (linear and lateral/non-traditional paths) — shows "from role X you can move to Y/Z" — seen in: Lattice (Career Tracks), Cornerstone (Career Center related-jobs), Fuel50 (multi-path career journeys), Gloat · priority: common · spine: would reuse `hrm.Designation` as both endpoints of a path edge (new table `CareerPath: from_designation -> to_designation`) · buildable later (deferred this pass)
- **Skill/competency requirements per role level** — what's expected to move up a level — seen in: Lattice (Competency Matrices), Zoho People (skill-set matrix), Fuel50 (skills ontology) · priority: common · spine: needs the same `EmployeeSkill`/role-requirement structure deferred under Talent Pool above · integration/later (skills taxonomy is a bigger investment better suited to a dedicated Skills sub-pass)
- **AI career agent / personalized path + gap recommendations** — seen in: Fuel50, Gloat, Eightfold · priority: differentiator · spine: n/a · integration/later (external AI)

### Internal Mobility (internal job postings, transfer applications)
- **Internal-only job posting** — a requisition visible only to current employees — seen in: Workday/SAP native modules, Gloat, Fuel50, Eightfold, item.com/Eploy internal-mobility ATS features · priority: table-stakes · spine: **already modeled** — `hrm.JobRequisition.posting_type = "internal"` — no new table needed · reuse existing (no build needed)
- **Employee applies via existing profile (no re-entry)** — seen in: Gloat, item.com, Eploy · priority: table-stakes · spine: **already modeled** — `hrm.JobApplication` against a `JobRequisition`; would need the applicant path to accept an internal `EmployeeProfile` instead of only an external `CandidateProfile` · buildable later (small workflow addition, not a new model)
- **Transfer approval workflow** (releasing manager + receiving manager + HR sign-off, auto-update Employment record, optional backfill req) — seen in: item.com/Eploy pattern description, Workday, SAP SuccessFactors · priority: common · spine: extend `RequisitionApproval` pattern or a small new join — **deferred**, not core to the 9-box/succession theme of this pass
- **Gig/project/mentorship marketplace (non-role opportunities)** — stretch projects, shadowing, mentoring matched by skill — seen in: Gloat, Fuel50 · priority: differentiator · spine: n/a, new marketplace concept entirely · integration/later

### Talent Reviews (calibration sessions, talent discussions)
- **Calibration session with rating adjustment + rationale log** — managers/HR align ratings against a shared yardstick — seen in: PeopleFluent, Betterworks, Cornerstone, SAP SuccessFactors, Sprad/industry pattern · priority: table-stakes · spine: **already modeled** — `PerformanceReview.calibrated_rating` + `calibration_notes` + `ReviewCycle` cover the data; only a session-scheduling/attendee shell is missing · reuse existing (mostly)
- **Rating-distribution / bias-detection view during calibration** — flags a manager rating everyone the same — seen in: Betterworks, Confirm · priority: differentiator · spine: n/a — an aggregate query/report over existing `PerformanceReview` rows, not a new table · buildable later (report, not a model)
- **9-box view launched directly from the calibration session** — seen in: 15Five (Growth Studio Explore), Cornerstone · priority: common · spine: same `TalentPool`/9-box derivation reused here — no separate table · buildable now (via the Talent Pool grid, once built)

### Retention Strategies (flight-risk analysis, retention action plans)
- **Flight-risk flag per employee** (manual tier: low/medium/high, or reason codes) — seen in: PeopleFluent (predictive flight-risk), Effectory (Flight Risk Screening), SHRM guidance, industry-wide · priority: table-stakes (as a manual field; **AI-predicted** scoring is differentiator/integration) · spine: new field on the talent-pool membership row (`TalentPoolMembership.flight_risk`) rather than a whole new table — flight risk is meaningful precisely for the people already being tracked as key talent · buildable now (manual); predictive scoring → integration/later
- **Retention action plan** (notes/next steps tied to the at-risk employee) — seen in: PeopleFluent, Effectory, culturemonkey/SHRM pattern · priority: common · spine: `TalentPoolMembership.retention_action_plan` (text) · buildable now
- **Predictive attrition scoring from behavioral/engagement signals** — seen in: PeopleFluent, Visier, Workday, SAP SuccessFactors · priority: differentiator · spine: n/a — needs an analytics/ML pipeline over attendance/survey/performance data · integration/later
- **Retention linked to compensation/promotion action** — seen in: PeopleFluent, Betterworks (comp signals) · priority: common · spine: cross-reference existing `hrm.PayComponent`/comp-planning models (3.37) — no new table this pass · deferred (cross-sub-module, out of scope here)

## Recommended build scope (this pass — 4 models)

- **`TalentPool`** [no numbering — `TenantOwned`, catalog like `TravelPolicy`] — `name`, `pool_type` (choices:
  `high_potential`, `critical_talent`, `emerging_leader`, `successor_ready`, `custom`), `description`, `owner`
  (FK `EmployeeProfile`, the pool sponsor), `is_active`. Justified by: **Talent Pool** — named pool/segment
  (Workday succession pools, Cornerstone talent pools, SAP SuccessFactors talent pool nominations).

- **`TalentPoolMembership`** [`TenantOwned` child of `TalentPool`, mirrors `CandidateSkill`/`RequisitionApproval`
  inline-child pattern] — `pool` FK `TalentPool`, `employee` FK `EmployeeProfile`, `joined_on` (date),
  `status` (choices: `active`, `graduated`, `removed`), `performance_review` (optional FK
  `hrm.PerformanceReview`, the review row this membership's grid position is sourced from — nullable so a
  membership can exist before a review does), `potential_override`/`performance_override` (nullable decimals,
  manual override when no linked review exists yet), `flight_risk` (choices: `low`, `medium`, `high`),
  `retention_action_plan` (text), `notes` (text). A derived `@property nine_box_quadrant` computes the
  performance/potential bucket from the linked review's `effective_rating`/`potential_rating` (falling back to
  the override fields) — never stored, mirrors `Objective.health_status`. Justified by: **Talent Pool** (9-box
  grid, high-potential ID) + **Retention Strategies** (flight-risk flag, retention action plan) — both bullets
  collapse cleanly onto "who's in the pool and how are we protecting them."

- **`SuccessionPlan`** [`TenantNumbered`, prefix `SPL`] — `critical_role` FK `hrm.Designation` (the role being
  planned for — reuses the existing title catalog instead of inventing a Position model), `department` FK
  `core.OrgUnit` (optional, narrows scope), `incumbent` FK `EmployeeProfile` (nullable — a plan can exist for a
  currently-vacant/at-risk role), `vacancy_risk` (choices: `low`, `medium`, `high`, `imminent`), `status`
  (choices: `draft`, `active`, `under_review`, `closed`), `review_date` (next scheduled review), `notes`. A
  derived `@property bench_strength` returns `(ready_now_count, total_candidate_count)` from its
  `SuccessionCandidate` rows (mirrors `JobRequisition.approval_progress`). Justified by: **Succession Planning**
  — critical role mapping (PeopleFluent succession slates, Workday/SAP succession pools per role, Eightfold
  role-readiness).

- **`SuccessionCandidate`** [`TenantOwned` child of `SuccessionPlan`, mirrors `RequisitionApproval`/
  `CandidateSkill`] — `plan` FK `SuccessionPlan`, `candidate` FK `EmployeeProfile` (the successor), `readiness`
  (choices: `ready_now`, `ready_1_2_years`, `ready_3_5_years`, `development_needed` — the industry-standard A/B/C
  bands cited by PeopleFluent/Betterworks/SHRM), `rank_order` (small int, for ordering the slate), `development_notes`
  (text — the gap-closing plan, can reference an `hrm.TrainingCourse`/`LearningPath` by name in free text this
  pass), `identified_on` (date). Justified by: **Succession Planning** — successor identification + readiness
  tiering (PeopleFluent, SAP SuccessFactors Suggested Successors, Eightfold role-readiness, Betterworks bench
  strength).

Auto-number prefixes: `SPL` (SuccessionPlan) — confirmed free against the full `NUMBER_PREFIX` grep of
`apps/hrm/models.py`. `TalentPool`/`TalentPoolMembership`/`SuccessionCandidate` are `TenantOwned` (no numbering),
matching the catalog/child-row convention used by `TravelPolicy`/`TravelBooking`, `JobGrade`/`Designation`, and
`CandidateSkill`/`RequisitionApproval`.

## Deferred (later passes / integrations)
- **Internal Mobility (internal job postings + transfer applications)** — largely **already built**:
  `hrm.JobRequisition.posting_type="internal"` + `hrm.JobApplication` cover the posting/apply mechanics. Deferred
  work is a thin *transfer-approval* workflow (releasing manager + receiving manager + HR sign-off + auto-update
  `core.Employment`) and letting an internal `EmployeeProfile` apply without re-entering a `CandidateProfile` —
  neither needs a brand-new model, so it doesn't compete for one of this pass's 4 slots.
- **Talent Reviews / calibration sessions** — the rating data already lives on `PerformanceReview`
  (`calibrated_rating`, `calibration_notes`) + `ReviewCycle`. Only a session-scheduling shell (attendees, date,
  linked cycle, minutes) is missing — a natural `TalentReviewSession` model for a follow-up pass, or fold into
  3.19's calibration UI instead of a new 3.38 table.
- **Career Pathing (role progression maps + skill requirements)** — needs a `CareerPath` (from-`Designation` →
  to-`Designation`) edge table plus a proper `EmployeeSkill`/role-skill-requirement structure. The skills
  taxonomy is shared infrastructure that Talent Pool's "skill-set matrix" (Zoho People) and Career Pathing's
  "skill requirements" both want — worth building once, deliberately, as its own follow-up pass rather than
  half-building it here.
- **AI-driven matching/recommendations** (SAP SuccessFactors AI-Assisted Successor Recommendation, Eightfold
  skills-based matching, Gloat/Fuel50 career agents, predictive flight-risk scoring) — all external-model/ML
  territory; out of a single Django pass by nature. The manual fields built this pass (`flight_risk`, `readiness`,
  `nine_box_quadrant`) are the data surface a future scoring job would populate.
- **Drag-and-drop succession org chart / scenario planning UI** — a visualization layer over `SuccessionPlan`/
  `SuccessionCandidate`, not a data-model gap; revisit once the base CRUD is live.
- **Retention ↔ compensation/promotion linkage** — cross-references 3.37 Compensation & Benefits comp-planning
  models; out of scope for this sub-module pass.

