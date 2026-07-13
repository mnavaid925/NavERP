# Research — Module 3: HRM Sub-module 3.41 Employee Engagement & Wellbeing (engagement-wellbeing)

Scope per `NavERP.md` §3.41: **Engagement Surveys** (pulse, eNPS, action planning) · **Wellbeing Programs**
(mental health resources, wellness challenges) · **Work-Life Balance** (flexible work arrangements, remote work
policies) · **Employee Assistance** (EAP programs, counseling services) · **Culture & Values** (mission alignment,
culture assessments) · **Social Connect** (team events, interest groups, volunteering).

`apps/hrm` already exists (~100 models). This is an **extension pass** — the priority is reusing what 3.18–3.27
already built, not re-inventing it.

## Existing HRM infrastructure to reuse (grepped `apps/hrm/models.py`)
- **`EmployeeProfile`** (3.1, `EMP-…`) — the anchor every new model below FKs to (never `core.Party` directly).
- **`core.OrgUnit`** (kind="department") — department/team scoping, exactly as `Announcement.target_department` and
  `Objective.department` already do (`limit_choices_to={"kind": "department"}`).
- **`Survey` / `SurveyResponse`** (3.27, `SUR-…`) — **already implements pulse surveys, eNPS, and custom
  questions**: `questions` is a JSON list of `{text, type: rating|text|single_choice, options}` — a 0–10 `rating`
  question IS the eNPS pattern, no new schema needed. `is_anonymous`, draft→open→closed lifecycle, respond-once
  (`unique_together (survey, employee)`) are all built. **The only 3.41 "Engagement Surveys" gap is action
  planning** (Culture Amp/Qualtrics/Lattice's differentiator) — nothing today turns a closed Survey's low scores
  into assigned, tracked follow-up work.
- **`Suggestion`** (3.27, `SUG-…`) — already has a `wellbeing` category choice; general idea-box, not wellness
  programs/challenges. Leave as-is; do not fold wellbeing content into it.
- **`Announcement`** (3.27, `ANN-…`) — news/policy/event feed with audience targeting; no RSVP/attendance/points,
  so it doesn't cover Social Connect's "team events" participation tracking.
- **`KudosBadge` / `Feedback`** (3.20, `FBK-…`) — peer recognition/kudos (Bonusly-shaped) already exists. Do not
  duplicate; 3.41 Social Connect is about **events/groups/volunteering**, not recognition.
- **`Objective` / `KeyResult` / `GoalCheckIn`** (3.18, `OBJ-…`/`KR-…`) — OKR machinery a survey Action Plan can
  optionally point at (`related_objective`), mirroring how `Feedback.related_objective` already links back to it.
- **`MeetingActionItem`** (3.20, `MAI-…`) — proves the "open/in_progress/done task off a parent record" shape this
  sub-module's new action-plan model should mirror.
- **`HRDashboard` / `HRDashboardWidget`** (3.32) — later pass can add engagement KPI widgets (eNPS trend, wellbeing
  participation) here; not part of this build.
- **`_hr_request_submit/_cancel/_approve/_reject/_edit/_delete`** (`apps/hrm/views.py`) — the shared single-approver
  workflow helpers used verbatim by `Suggestion`, `DocumentRequest`, `IdCardRequest`, `AssetRequest`, and 3.35
  `TravelRequest`. The new Work-Life Balance request model reuses these directly.
- **3.35 `TravelPolicy` / `TravelRequest` / `TravelBooking`** (catalog + numbered request + `TenantOwned` nested
  child, only `TravelBooking` has a `form.html` — no standalone list) is the **template shape** this sub-module
  copies: one catalog/program table, one numbered request/participation table, everything tenant-scoped off
  `TenantOwned`/`TenantNumbered`.

## Leaders surveyed (10, with source links)
1. **Culture Amp** — engagement-survey category leader; strongest **action-planning** workflow (assign owners,
   track progress against low-scoring focus areas) — [Product updates](https://support.cultureamp.com/en/articles/10368642-employee-engagement-product-updates-2025), [eNPS guide](https://support.cultureamp.com/en/articles/7048397-employee-net-promoter-scores-enps)
2. **Officevibe (Workleap)** — SMB pulse-survey leader; validated question bank across 10 engagement drivers +
   AI-summarized results — [Pulse survey feature](https://workleap.com/features/pulse-survey/), [Survey breakdown](https://help.workleap.com/en/articles/10281707-workleap-officevibe-survey-breakdown)
3. **Qualtrics Employee Experience (EX)** — enterprise listening platform; **Guided Action Planning** with
   AI-recommended actions per focus area — [EX capabilities](https://www.qualtrics.com/employee-experience/capabilities/), [Action planning](https://www.qualtrics.com/support/employee-experience/creating-ee-project/dashboards-tab/action-planning-ex/action-planning-ee/)
4. **Glint / Microsoft Viva Glint** — pulse + lifecycle surveys with NLP comment analysis and attrition-risk heat
   maps — [Viva Glint](https://www.microsoft.com/en-us/microsoft-viva/glint)
5. **Lattice Engagement** — eNPS + pulse with a heatmap (delta scoring across cycles, manager-of-manager rollups)
   — [Engagement platform](https://lattice.com/platform/engagement), [eNPS](https://lattice.com/platform/engagement/enps)
6. **Wellable** — wellness-challenge leader: turnkey challenge library, individual/team leaderboards, a
   points-as-common-currency reward model, wearable sync — [Wellness platform](https://www.wellable.co/wellness-platform/), [Wellness challenges](https://www.wellable.co/wellness-challenges)
7. **Virgin Pulse / Personify Health** — wellbeing + EAP-adjacent mental-health coaching, points/rewards, ROI
   analytics — [Employee wellbeing platform](https://personifyhealth.com/employee-wellbeing-platform/), [Mental health](https://engage.personifyhealth.com/employee-mental-health)
8. **Limeade (WebMD Health Services)** — holistic wellbeing + inclusion + communications in one mobile-first
   platform — [Limeade/WebMD](https://www.limeade.com/limeade-webmd-health-services/)
9. **Bonusly** — peer recognition + points/rewards catalog (gift cards, donations, cash) — boundary case, see
   Deferred — [Product overview](https://bonusly.com/features/product-overview), [Peer recognition](https://bonusly.com/solutions/peer-to-peer-recognition)
10. **Zoho People (Engagement)** — eNPS/engagement surveys with applicability rules + AI sentiment (Zia), wellness
    + rewards modules bundled into the HRIS — [Employee engagement](https://www.zoho.com/people/employee-engagement.html), [Create engagement survey](https://help.zoho.com/portal/en/kb/people/administrator-guide/employee-engagement/articles/engagement-survey-zoho-people)

Supplementary domain checks (Social Connect / EAP / Culture & Values are thin in the core-10, so 3 more were
pulled to validate feature shape, not full "leader" profiles):
- **WeSpire / Deed / Alaya** (corporate volunteering + ERG/interest-group platforms) — confirm the "events +
  RSVP/participation + points + volunteering log" shape — [WeSpire](https://blog.betterimpact.com/en/best-csr-software), [Deed communities](https://www.joindeed.com/product/communities), [Alaya](https://www.gartner.com/reviews/market/corporate-volunteering-platform/vendor/benevity/product/alaya)
- **EAP software category** (SHRM/Bonterra buyer guides) — confirms **confidentiality-by-design**: aggregate
  reporting only, individual session detail never exposed without consent — [EAP software guide](https://www.bonterratech.com/blog/eap-software)
- **Culture-assessment tooling** (Denison Model, Barrett Values Centre, MyCulture.ai) — confirms culture/mission
  assessments are just another survey instrument (values-alignment questions), not a distinct engine —
  [Culture assessment tools](https://www.myculture.ai/blog/organizational-culture-assessment-tools)

## Feature catalog by NavERP.md bullet (3.41)

### Engagement Surveys — pulse surveys, eNPS, action planning
- **Pulse / eNPS survey delivery** — short recurring surveys, 0–10 recommend-score question · seen in: Culture
  Amp, Officevibe, Qualtrics, Glint, Lattice, Zoho People · priority: table-stakes · spine: **reuse `hrm.Survey` /
  `SurveyResponse` (3.27) — already built**, no new table · buildable now (already shipped).
- **Heatmap / trend-over-time scoring** — compare scores across cycles, by department/manager · seen in: Lattice,
  Glint, Qualtrics · priority: common · spine: computed live over `SurveyResponse.answers` — later analytics-pass
  widget on `HRDashboard`, not a stored table · integration/later (reporting, not this pass).
- **AI sentiment / NLP comment analysis** — auto-summarize open-text answers, classify tone · seen in: Glint,
  Officevibe, Zoho People (Zia) · priority: differentiator · spine: n/a (external AI call) · integration/later.
- **Action planning** — turn a survey's low-scoring focus area into an assigned, tracked follow-up initiative with
  an owner, target date, and status; optionally guided/AI-recommended · seen in: **Culture Amp, Qualtrics, Lattice**
  · priority: differentiator (the feature that separates a "survey tool" from an "engagement platform") · spine:
  **new table**, FKs `hrm.Survey` + `hrm.EmployeeProfile` (owner) + optionally `hrm.Objective` for goal tracking ·
  buildable now — **this is the one real gap in 3.27's survey coverage and the highest-value model for this pass.**

### Wellbeing Programs — mental health resources, wellness challenges
- **Wellness-challenge catalog** — turnkey themed challenges (steps, hydration, mindfulness), individual/team
  leaderboards, a start/end window · seen in: Wellable, Virgin Pulse/Personify, Limeade · priority: table-stakes ·
  spine: new table (catalog) · buildable now.
- **Points-as-common-currency gamification** — every activity (challenge completion, session attended, resource
  used) earns points on one shared ledger · seen in: Wellable, Virgin Pulse, Bonusly · priority: common · spine:
  a field on the participation/enrollment row, not a separate ledger this pass · buildable now (a simple integer
  field; a full points-ledger/redemption engine is deferred).
- **Mental-health resource library** — curated articles/coaching links, on-demand content · seen in: Virgin
  Pulse, Limeade, Wellable · priority: common · spine: a catalog entry (type=resource) with an external link, not
  hosted content · buildable now (link-out, no CMS this pass).
- **Wearable / consumer-app sync** (Fitbit, Apple Health, Garmin) · seen in: Wellable, Virgin Pulse · priority:
  differentiator · spine: n/a · integration/later (external device APIs).
- **Predictive/ROI analytics** (health-cost savings, engagement-to-outcome correlation) · seen in: Virgin
  Pulse/Personify · priority: differentiator · spine: n/a this pass · integration/later.

### Work-Life Balance — flexible work arrangements, remote work policies
- **Flexible/remote work arrangement requests** — employee requests a schedule type (remote/hybrid/compressed/
  flextime) for a date range, manager/HR approves against policy · seen in: general hybrid-workforce-management
  category (Workstatus, Softworks-style HRIS request flows) — same shape as any HR self-service request · priority:
  table-stakes · spine: **new table**, single-approver workflow reusing `_hr_request_*` verbatim (same shape as
  3.35 `TravelRequest`) · buildable now.
- **Desk/room booking, occupancy analytics** · seen in: hybrid-workplace-management category · priority: common
  (facilities-adjacent, not core HR) · spine: n/a · deferred (belongs nearer Module 11 Assets/Facilities, not HRM).

### Employee Assistance — EAP programs, counseling services
- **EAP program/provider catalog** — what counseling/assistance benefits are available, how to access them ·
  seen in: Virgin Pulse/Personify (mental-health coach hand-off to EAP), SHRM/Bonterra EAP-software category ·
  priority: table-stakes · spine: a `WellbeingProgram` catalog row (type=eap_counseling) · buildable now.
- **Confidential referral/usage tracking** — individual session detail is never exposed to managers; only
  **aggregate** usage is reportable, consent-gated · seen in: EAP-software category (SHRM/Bonterra) — universal
  compliance requirement, not a vendor differentiator · priority: table-stakes (compliance-driven) · spine: an
  `is_confidential` flag on the program + a confidentiality-respecting participation row (status only, no clinical
  notes field) · buildable now — **flag this loudly in the model docstring and in any admin list/report.**
- **Session billing / coverage-limit tracking** (per-employee session caps, contracted rates) · seen in: EAP
  software category · priority: differentiator · spine: n/a this pass · integration/later (usually the EAP
  vendor's own system of record).

### Culture & Values — mission alignment, culture assessments
- **Culture/values-alignment assessment** — a survey instrument measuring mission alignment, values fit, team
  cohesion (Denison/Barrett-style dimensions) · seen in: MyCulture.ai, Denison Model, Barrett Values Centre, and
  folded into Glint/Culture Amp's survey template library · priority: common · spine: **reuse `hrm.Survey`**
  (a `survey_purpose`/category distinguishes it from an engagement pulse) OR a `WellbeingProgram` entry
  (type=culture_assessment) that links out to/schedules a `Survey` — no new survey engine needed · buildable now.
- **Values/mission content & acknowledgment** (publish company values, track read/acknowledge) · seen in: general
  culture-tooling category · priority: common · spine: could reuse `Announcement` (category=policy) · buildable
  now, but out of scope for this pass's 4 models (already covered by 3.27 `Announcement`).

### Social Connect — team events, interest groups, volunteering
- **Event/interest-group/volunteering catalog** — plan a team event, stand up an interest group (ERG-style), or
  post a volunteering opportunity in one unified feed · seen in: WeSpire, Deed, Alaya (all three unify
  events+groups+volunteering rather than separate tools) · priority: common · spine: **new table** — same
  `WellbeingProgram` catalog as Wellbeing Programs/EAP, discriminated by `program_type` · buildable now.
- **RSVP / participation / attendance + points** — who signed up, who showed up, points/impact earned (hours
  volunteered, event attended) · seen in: WeSpire, Deed, Alaya, Wellable · priority: common · spine: new
  `TenantOwned` child row (mirrors `TravelBooking`/`TrainingAttendance`) · buildable now.
- **Donation matching / grants** · seen in: Deed · priority: differentiator · spine: n/a · integration/later
  (payment processing).

## Recommended build scope (this pass — 4 models)

Mirrors the proven 3.35 shape (catalog → numbered request/action → `TenantOwned` nested participation) so the
build is low-risk and consistent with the rest of the app.

1. **`SurveyActionPlan`** (`TenantNumbered`, prefix **`ACTP`**) — closes the one real gap in 3.27's survey
   coverage (Culture Amp/Qualtrics/Lattice's action-planning differentiator).
   - `survey` FK `hrm.Survey` (`related_name="action_plans"`) — the closed survey this plan responds to.
   - `title`, `focus_area` (CharField — the low-scoring driver/theme this plan addresses, free text since
     `Survey.questions` is schema-less JSON).
   - `owner` FK `hrm.EmployeeProfile` (`PROTECT`) — accountable owner (usually a manager), mirrors
     `Objective.owner`.
   - `department` FK `core.OrgUnit` (`SET_NULL`, null/blank, `limit_choices_to={"kind": "department"}`) — scope,
     mirrors `Announcement.target_department` / `Objective.department`.
   - `description` (TextField) — the plan itself.
   - `related_objective` FK `hrm.Objective` (`SET_NULL`, null/blank) — optional tie-in to 3.18 OKR tracking,
     mirrors `Feedback.related_objective`.
   - `target_date` (DateField), `status` (`open`/`in_progress`/`completed`/`cancelled`), `completed_at`
     (DateTimeField, null/blank, editable=False).
   - Full CRUD + list page (Culture Amp/Qualtrics treat action plans as first-class tracked records, not a
     survey sub-field).

2. **`WellbeingProgram`** (`TenantNumbered`, prefix **`WBP`**) — the unified catalog for Wellbeing Programs,
   Employee Assistance, Culture & Values, and Social Connect (Wellable/WeSpire/Deed/Alaya precedent: one
   platform, one catalog, a type discriminator — same pattern `Feedback.feedback_type` already uses in this app).
   - `title`, `description` (TextField).
   - `program_type` (CharField choices: `wellness_challenge`, `mental_health_resource`, `eap_counseling`,
     `culture_assessment`, `team_event`, `interest_group`, `volunteering`, `work_life_policy`) — one field covers
     4 of the 6 NavERP.md bullets, matching how the leaders bundle these.
   - `owner` FK `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank) — the HR/wellness admin, mirrors
     `Announcement.author`.
   - `target_department` FK `core.OrgUnit` (`SET_NULL`, null/blank, `limit_choices_to={"kind": "department"}`) —
     blank = company-wide.
   - `start_date` / `end_date` (DateField, null/blank — ongoing resources like an EAP hotline have neither).
   - `points_value` (PositiveIntegerField, null/blank) — Wellable's points-as-common-currency gamification.
   - `external_resource_url` (URLField, blank) — link out to the EAP provider portal, wearable-challenge page, or
     ERG sign-up (no live vendor integration this pass — WARNING: do not build a fake "connect" button; a plain
     link is honest about scope).
   - `is_confidential` (BooleanField, default=False) — **must default True-aware behavior for `eap_counseling`**:
     when set, any admin list/report shows aggregate counts only, never per-employee rows (compliance-driven,
     confirmed universal across the EAP-software category).
   - `status` (`draft`/`active`/`completed`/`archived`) — mirrors `Survey.status` shape.

3. **`WellbeingParticipation`** (`TenantOwned` — nested child, no `NUMBER_PREFIX`, mirrors `TravelBooking`) —
   RSVP/enrollment/attendance for a `WellbeingProgram`, added/edited from the program's detail page (a
   `form.html` only, no standalone top-nav list — same shape as `TravelBooking`).
   - `program` FK `WellbeingProgram` (`CASCADE`, `related_name="participations"`).
   - `employee` FK `hrm.EmployeeProfile` (`PROTECT`, `related_name="wellbeing_participations"`).
   - `status` (CharField choices: `registered`, `attended`, `completed`, `no_show`, `withdrawn`) — mirrors
     `TrainingAttendance.attendance_status` shape.
   - `points_earned` (PositiveIntegerField, null/blank).
   - `completed_at` (DateTimeField, null/blank, editable=False).
   - `notes` (TextField, blank) — **WARNING: for `program.is_confidential=True` rows (EAP), this must stay to
     scheduling/status notes only — never store clinical/counseling content here.** Enforce in `clean()`/the form
     with a help_text warning, and mask this field's value on any non-admin/non-self view.
   - `unique_together (tenant, program, employee)` — one participation row per employee per program (re-enroll =
     new program instance, mirrors `TrainingNomination`'s `unique_together`).

4. **`FlexibleWorkArrangement`** (`TenantNumbered`, prefix **`FWA`**) — the Work-Life Balance request, a direct
   structural clone of 3.35 `TravelRequest` (same lifecycle, same shared view helpers).
   - `employee` FK `hrm.EmployeeProfile` (`CASCADE`, `related_name="flexible_work_arrangements"`).
   - `arrangement_type` (CharField choices: `remote`, `hybrid`, `compressed_week`, `flextime`, `part_time`).
   - `start_date`, `end_date` (DateField; `end_date` null/blank = open-ended/permanent).
   - `days_per_week_remote` (PositiveSmallIntegerField, null/blank) — only meaningful for `remote`/`hybrid`.
   - `reason` (TextField).
   - `status` (`draft`/`pending`/`approved`/`rejected`/`cancelled`/`expired`), `OPEN_STATUSES = ("draft",
     "pending")` — **reuses `_hr_request_submit/_cancel/_approve/_reject/_edit/_delete` verbatim**, same as
     `Suggestion`/`TravelRequest`.
   - `approver` FK `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank), `approved_at` (DateTimeField, null/blank),
     `decision_note` (TextField, blank).
   - Full CRUD + list page (employee self-service "My Flexible Work Requests" + admin "All Requests" filtered
     list, same pattern as `TravelRequest`/`Suggestion`).

## Deferred (later passes / integrations)
- **AI sentiment/NLP comment analysis, AI-recommended action plans** (Glint, Officevibe, Qualtrics) — external AI
  call; the plain `SurveyActionPlan` model is the buildable substrate for this later.
- **Heatmap / cycle-over-cycle trend dashboards, eNPS benchmarking** — an `HRDashboard`/`HRDashboardWidget`
  analytics-pass item (3.32), not a new table.
- **Wearable/consumer-app sync** (Fitbit, Apple Health, Garmin) — external device API integration.
- **Predictive/ROI wellbeing analytics, health-cost correlation** (Virgin Pulse/Personify) — needs claims/cost
  data this ERP doesn't hold.
- **EAP session billing / coverage-limit tracking** — normally owned by the EAP vendor's own system; NavERP only
  needs the confidentiality-respecting participation status, not clinical/billing detail.
- **Donation matching / volunteering-hours-to-grant conversion** (Deed) — payment/grant processing, a Module 2
  (Accounting) integration if ever built.
- **Points redemption / gift-card catalog** (Wellable, Bonusly, Virgin Pulse) — this pass stores `points_earned`
  only; a redeemable-rewards catalog overlaps 3.37 Compensation & Benefits' "Rewards & Recognition" (not yet
  built) and should live there, not be duplicated in 3.41.
- **Desk/room booking & office-occupancy analytics** (hybrid-workplace-management category) — facilities-adjacent,
  nearer Module 11 (Assets) if built at all.
- **Values/mission content publishing** — already covered by existing `Announcement` (category=policy); no new
  table needed.
- **Splitting `WellbeingParticipation` into separate nomination/attendance/feedback tables** (the 3.24
  `TrainingNomination`/`TrainingAttendance`/`TrainingFeedback` 3-table pattern) — deferred until usage shows the
  unified row is too coarse; the lean 4-model budget for this pass keeps it as one child table.
