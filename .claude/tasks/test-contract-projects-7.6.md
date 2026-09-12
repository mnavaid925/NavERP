# Test contract — Projects 7.6 Quality Management (`apps/projects`)

**Phase 6, step 1 (fixture layer).** The four test modules (`test_quality_models.py` →
`test_quality_forms.py` → `test_quality_views.py` → `test_quality_security.py`, written by steps
2–5) import the `quality_*` block appended to `apps/projects/tests/conftest.py`. Model/form/view
behaviour is pinned by the build contract `.claude/tasks/contract-projects-7.6.md` (§2–§6, as
amended by the close-out: `qrv_report` accepts `planned`+`in_progress`; `QualityDefect.is_locked`
includes `cancelled`; the §4.5 `maturity` dict carries `has_score`; §4.3 has no `parties` key) —
**this file pins the fixture names and the computed board figures**; where a number below
disagrees with a re-derivation, this file wins (it was computed from the as-built properties in
`apps/projects/models/QualityManagement/` and the two computed views).

### Naming rule (mandatory — same as 7.1–7.5)

* test functions `test_quality_*`; module-level helpers `_quality_*` / `_QUALITY_*`
* conftest fixtures `quality_*` (root-conftest names excepted); never import another lane's
  *fixtures* (`projectinitiation_*` / `planning_*` / `resource_*` / `cost_*` / `risk_*`); DO
  import their factory functions where they fit (`_projectinitiation_project`, `_planning_task`,
  `_planning_milestone` are already inside the conftest factories; `_risk_issue` is the bridge
  builder — pull it the same way)
* conftest is owned by step 1 alone — steps 2–5 must not edit it. Pull factories directly:

```python
from apps.projects.tests.conftest import (
    QUALITY_PAGE_SIZE,
    _quality_today, _quality_project, _quality_wbs_node,
    _quality_plan, _quality_review, _quality_inspection, _quality_defect,
    _quality_fill_plans, _quality_fill_reviews, _quality_fill_inspections, _quality_fill_defects,
    _risk_issue,  # 7.5 factory — the ONLY sanctioned way to build a bridge row's ProjectIssue
)
```

`QUALITY_PAGE_SIZE = 15` (`crud_list` default) — a pagination test needs 16 rows.

---

## 1. Factories (construct + `.save()` → QPL-/QRV-/QCI-/QDF- numbers mint; NEVER `bulk_create`)

| helper | signature | notes |
|---|---|---|
| `_quality_project` | `(tenant, **overrides)` | ACTIVE host via the 7.1 factory (charter approved, window today−30..today+150, "Quality host NN"/"QHP-NN"). The computed boards lens per project — a test that wants an isolated register builds a throwaway host here |
| `_quality_wbs_node` | `(tenant, project, **overrides)` | a `ProjectTask` **`node_type="deliverable"`** node under the project (the inspected node; the acceptance board's row key). Built through the 7.2 factory, undated/effort-less like `_planning_wbs_tree`'s deliverables; pass `name=`/`sequence=` where sibling order matters |
| `_quality_plan` | `(tenant, project, **overrides)` | defaults: `status="draft"`, `verification_method="inspection"`, `acceptance_criteria` filled (REQUIRED column), `planned_review_date=None` (never review-overdue), no wbs/risk/owner. `clean()` runs before `save()` (the `_risk` precedent) — a cross-project `wbs_node`/`source_risk` raises at build time |
| `_quality_review` | `(tenant, project, **overrides)` | defaults: `status="planned"`, `review_type="methodology_review"`, `review_date=today`, `maturity_score=None` (never in the maturity aggregate), `improvement_status="n_a"`, `improvement_due_date=None` (never overdue). `clean()` before `save()` |
| `_quality_inspection` | `(tenant, project, **overrides)` | defaults: `status="planned"`, `inspection_type="review"` (NOT acceptance — never in the queue), `result="pending"`, `usage_decision="pending"`, no dates (never overdue), no acceptor stamps. `clean()` before `save()` (guards `wbs_node`/`quality_plan`/`milestone`) |
| `_quality_defect` | `(tenant, project, **overrides)` | defaults: `status="open"`, `severity="minor"`, `disposition="open"`, `defect_category="other"`, `identified_date=today`, `due_date=None` (never overdue), `description` filled (REQUIRED), no resolution stamps, `project_issue=None`. `clean()` before `save()` |
| `_quality_fill_plans` | `(tenant, project, count, **overrides)` | DRAFT rows, `planned_review_date=None`, distinct titles ("Backlog plan NN") |
| `_quality_fill_reviews` | `(tenant, project, count, **overrides)` | planned methodology rows — `maturity_score=None`, `improvement_status="n_a"`, no due date (board-safe) |
| `_quality_fill_inspections` | `(tenant, project, count, **overrides)` | planned/pending `review`-typed rows, `planned_date=None` (never overdue, never in the queue) |
| `_quality_fill_defects` | `(tenant, project, count, **overrides)` | OPEN rows, `due_date=None`, `identified_date=today` (deliberate: fills DO land in the trend's current-month bucket) |

To test a `clean()` refusal (cross-project wbs_node/plan/milestone/inspection), build the
malformed row with the model directly — the factories deliberately raise on it instead of seeding
bad data. To test a 7.5 `source_risk` on a plan, build the risk inline:
`_risk(quality_project_a.tenant, quality_project_a)` (7.5 factory import — no 7.6 risk fixture
exists on purpose; lanes never depend on each other's fixture rows).

---

## 2. Fixture inventory (all function-scoped)

**Root conftest reuse (never redefine):** `tenant_a` `tenant_b` `admin_user` `member_user`
`admin_b` `client_a` `client_b` `member_client`.

**Actors/clients:** `quality_member` (= `member_user`; runs every login-gated verb and all CRUD —
only `qpl_supersede` is admin-gated) · `quality_member_b` (tenant B non-admin — tenant-A pk → 404
on scope; log in with a fresh `Client()` in-test) · `quality_tenantless_user`/
`quality_tenantless_client` (create redirects `dashboard:home`; registers and both computed pages
render empty — the boards are 0-safe) · `quality_anon_client` (302 → login) ·
`quality_admin_client` (= `client_a`; admin happy paths AND every IDOR-404) ·
`quality_member_client` (= `member_client`) · `quality_csrf_client` (POST without token → 403).
Tenant-B ADMIN requests: root `client_b`.

**Spine:** `quality_project_a` (ACTIVE host)/`quality_project_b` ·
`quality_wbs_node_a` (deliverable node on project_a — the acceptance board's ONE default row)/
`quality_wbs_node_b` · `quality_milestone_a`/`quality_milestone_b` (7.2 `_planning_milestone`
factory — the inspection form's `milestone` FK and its crafted value) ·
`quality_client_party_a` (tenant A organization Party — the `qci_accept` acceptor;
`clients(tenant)` is ALL tenant parties, any kind passes)/`quality_client_party_b` (crafted POST
value — the form queryset refuses it first, assert the FIELD error).

**QualityPlan (project_a):** `quality_plan_draft` (edit/delete OPEN; the `qpl_approve` happy
path; approve on anything else refuses "Only a draft plan can be approved") ·
`quality_plan_active` (approved stamps now−1d, **anchored to `quality_wbs_node_a`** — the
acceptance board's plan row; the `qpl_supersede` happy path; NOT locked) ·
`quality_plan_superseded` / `quality_plan_closed` (the two `is_locked` statuses — edit/delete
refuse; supersede answers "Only an active plan…") · `quality_plan_review_overdue`
(`planned_review_date=today−3`, still draft → `is_review_overdue` True; the
`?review_due=1`/`?overdue=1` lens row) · `quality_plan_b`.

**QualityReview (project_a) — one per status + the family/lens rows:** `quality_review_planned`
(`methodology_review`, review_date today — report happy path AND the `?kind=assurance` row) ·
`quality_review_in_progress` (`compliance_check` — report happy path: **`qrv_report` accepts
`planned`+`in_progress`**, the close-out amendment) · `quality_review_reported`
(`gate_review` — the ONLY `qrv_close` happy path) · `quality_review_closed` (`closed_at` now−1d —
locked) · `quality_review_cancelled` (locked) · `quality_review_improvement`
(`retrospective`, `improvement_action` set, `improvement_owner`=admin_user,
`improvement_due_date=today+7`, `improvement_status="planned"` — the `?kind=improvement` row and
an improvement-board row) · `quality_review_improvement_overdue` (`kaizen_event`,
`improvement_due_date=today−3`, `improvement_status="in_progress"` → `is_improvement_overdue`
True; the register's `?overdue=1` lens row) · `quality_review_improvement_done`
(`retrospective`, `improvement_status="done"` with `improvement_due_date=today−7` — finished on
time: `is_improvement_overdue` False, OUT of `improvement_open_count`, IN `improvement_rows`) ·
`quality_review_maturity`
(`maturity_assessment`, **`maturity_score=4`** — the default set's ONLY scored review: it alone
feeds `reviews_scored`/`avg`) · `quality_review_b`.

**DeliverableInspection (project_a) — one per status and per result, every row an honest
verb-output shape:** `quality_inspection_planned` (planned/pending, `planned_date=today+7` —
`qci_record` happy path; edit/delete OPEN) · `quality_inspection_in_progress` (result `pass`,
`inspected_date=today−1`, decision still pending — the exact shape `qci_record` leaves; the
decide-later happy path for a NON-acceptance row) · `quality_inspection_on_hold` (hand-built —
no verb writes `on_hold`; still unlockable, `qci_record` accepts it as a source) ·
`quality_inspection_conditional` (result `conditional`, recorded, undecided) ·
`quality_inspection_not_applicable` (result `not_applicable`, recorded, undecided) ·
`quality_inspection_cancelled` (locked before execution) · `quality_inspection_accepted`
(status `passed`, result `pass`, `usage_decision="accept"`, accepted_by/admin_user,
accepted_by_party/`quality_client_party_a`, accepted_at now−1d, `acceptance_note` set,
**anchored to `quality_wbs_node_a`** — the board's latest inspection; locked) ·
`quality_inspection_rejected` (status `failed`, result `fail`, `usage_decision="reject"` —
the shape `qci_reject` leaves; locked) · `quality_inspection_acceptance_pending`
(`inspection_type="acceptance"`, result `pass` recorded, `usage_decision="pending"`,
`planned_date=today+3` — the acceptance queue's default row AND the `qci_accept`/
`qci_reject` happy path) · `quality_inspection_overdue` (`planned_date=today−3`, never
executed, status planned → `is_overdue` True; the `?overdue=1` lens row) ·
`quality_inspection_b`.
NOTE: a `qci_accept` refusal row (acceptance row whose result is still `pending` → "Record the
inspection result before taking the acceptance decision") is built inline via the factory — the
default queue row must stay decision-ready. `usage_decision="accept_with_deviation"` /
`"rework"` rows are also factory-built inline (no verb writes them by default).

**QualityDefect (project_a) — one per status and per severity, plus the two lens rows:**
`quality_defect_open` (severity `major`, identified today−2 → `age_days` 2, **anchored to
`quality_wbs_node_a`** — the board's open-defects 1; the `qdf_resolve` AND `qdf_raise_issue`
happy path) · `quality_defect_in_progress` (severity `critical`, identified today−5) ·
`quality_defect_resolved` (severity `minor`, root_cause/resolution_note/resolved_by/at now−1d —
the ONLY `qdf_close` happy path; locked) · `quality_defect_closed` (severity `minor`,
resolved_at now−3d, `lessons_learned` set — locked; the improvement page's ONLY default lessons
row) · `quality_defect_cancelled` (severity `observation` — locked like its QRV/QCI siblings,
the M1 amendment) · `quality_defect_overdue` (`due_date=today−2`, status open, severity minor,
identified today−20 → `age_days` 20 → `is_overdue` True; the `?overdue=1` lens row) ·
`quality_defect_bridged` (`project_issue` SET — built through the 7.5 factory
`_risk_issue(tenant_a, quality_project_a)`; severity major, still open; `qdf_raise_issue`
answers "already raised issue ISS-…" on it) · `quality_defect_b`.

---

## 3. THE BOARD TABLES — assert these, do not re-derive

Fixtures are independent (a test instantiates only what its signature requests), so the tables
hold for the FULL default set with everything scoped to `?project=quality_project_a` — the same
caveat as 7.4's EVM table: pull MORE rows and the figures move; recompute from the pulled rows.

### 3.1 `quality_improvement` (GET-only; context keys `projects`, `project`, `improvement_rows`,
`maturity`, `defect_trend_rows`, `defect_trend_max`, `lessons`, `lessons_count`,
`open_defect_count`, `improvement_open_count`)

| figure | full default set | why |
|---|---|---|
| `improvement_rows` | **3** (retrospective ×2 + kaizen_event — `_BOARD_IMPROVEMENT_TYPES`, NOT the register's 3-type `_IMPROVEMENT_TYPES`; `quality_review_maturity` is excluded) | cap 25 |
| `maturity["reviews_scored"]` | **1** | only `quality_review_maturity` (avg 4.0) |
| `maturity["defects_total"]` | **7** (open, in_progress, resolved, closed, cancelled, overdue, bridged) | |
| `maturity["defects_closed"]` | **2** (resolved + closed — `resolved` counts as dispositioned) | |
| `maturity["closure_pct"]` | **29** | round(2/7×100) |
| `maturity["score"]` | **3.0** | round(0.6×4.0 + 0.4×29/20, 1) = round(2.98, 1) |
| `maturity["band"]` / `["badge"]` | **"Defined" / "badge-info"** | 3.0 ≤ 3.9999 |
| `maturity["has_score"]` | **True** | the M9 amendment — a falsy 0.0 must still render |
| `open_defect_count` | **4** (open, in_progress, overdue, bridged) | statuses open/in_progress |
| `improvement_open_count` | **2** (improvement + improvement_overdue) | board types × planned/in_progress |
| `lessons_count` / `lessons` | **1** (`quality_defect_closed`, newest-first) | closed ∧ lessons non-empty |

**Maturity-band recipes** (build on a throwaway `_quality_project`): no rows → `has_score`
False, `score` None, `badge-muted` (no band computed from nothing) · one open defect, no scored
reviews → score **0.0**, `has_score` True, band **Initial/badge-red** (the M9 edge) · all
defects closed, no scored reviews → score = closure_pct/20 (100% → **5.0 Optimizing/badge-green**;
50% → 2.5 Managed/badge-amber) · bands: ≤1.9999 Initial/red, ≤2.9999 Managed/amber,
≤3.9999 Defined/info, ≤4.9999 Quantitatively Managed/green, ≤5.0 Optimizing/green.
**Trend recipe:** the default rows' identified/resolved offsets cross month boundaries depending
on the run date — pin trend assertions on dedicated rows (`_quality_fill_defects`, identified
today = current month; close some via `status="resolved"` + `resolved_at=now`) and re-derive
`opened`/`closed`/`bar_pct` from the pulled rows using the view's own bucketing
(`identified_date` month; `localdate(resolved_at)` month; `bar_pct` scaled by `defect_trend_max`).
**Scope trap:** `?project=<junk>` or a valid-but-FOREIGN pk → the view's `.filter(tenant=…,
pk=…).first()` yields None → the page falls back to **tenant-wide** figures (200, not 404, not
empty — unlike the crud registers).

### 3.2 `quality_acceptance` (GET-only; context keys `projects`, `project`, `deliverable_rows`,
`acceptance_queue`, `acceptance_queue_count`, `accepted_count`, `conditional_count`,
`rejected_count`, `pending_count`)

| figure | full default set, `?project=quality_project_a` | why |
|---|---|---|
| `deliverable_rows` | **1** row (`quality_wbs_node_a`) | one per `node_type="deliverable"` node |
| row `plan` / `plan_status` | `quality_plan_active` / "active" | latest plan anchored to the node |
| row `latest_inspection` / `result` / `usage_decision` | `quality_inspection_accepted` / "pass" / "accept" | latest inspection anchored to the node |
| row `open_defects` | **1** (`quality_defect_open`) | open punch items on the node |
| row `acceptance_state` / `badge` | **"accepted" / "badge-green"** | `_DECISION_STATES["accept"]` |
| `acceptance_queue` / `_count` | **1** (`quality_inspection_acceptance_pending`) | acceptance-type ∧ decision pending |
| `accepted_count` | **1** | usage_decision accept |
| `conditional_count` | **0** | counts `accept_with_deviation` decisions, not `result="conditional"` rows |
| `rejected_count` | **1** | usage_decision reject |
| `pending_count` | **8** | every undecided row incl. cancelled/on_hold ones (10 tenant-A inspections − accept − reject) |

`acceptance_state` map: accept→accepted/badge-green · accept_with_deviation→conditional/
badge-amber · reject→rejected/badge-red · rework→pending/badge-slate · pending→pending/
badge-slate. Without `?project=` the board is **empty by design** (`deliverable_rows == []`)
while the queue stays tenant-wide; the queue renders ≤100 rows with a DB-count header. Same
scope trap as §3.1: a foreign `?project=` pk unscopes to tenant-wide. Anchor exactly ONE default
inspection to `quality_wbs_node_a` — a factory-built row on that node becomes the "latest" and
moves the row's state.

---

## 4. Mutation matrix — a verb on a shared fixture moves the pinned figures

| verb on fixture | effect |
|---|---|
| `qpl_approve(quality_plan_draft)` | → active + `approved_by`/`approved_at`; audit `update`; figures unchanged (draft left the `?overdue=1` lens — recompute if `quality_plan_review_overdue` was the target) |
| `qpl_supersede(quality_plan_active)` | → superseded (admin-only). **Decorator order (M2): `@require_POST` ABOVE `@tenant_admin_required` — a member GET gets 405, a member POST 403.** Moves the acceptance board's `plan_status` if that test pulled the node row |
| `qrv_report(quality_review_planned)` or `(…_in_progress)` | → reported; audit `update` (planned+in_progress both legal) |
| `qrv_close(quality_review_reported)` | → closed + `closed_at`; audit `close` |
| `qci_record(quality_inspection_planned)` | POST `result` ∈ {pass, fail, conditional, not_applicable} (`pending` refused) + optional `inspected_date` (default today); status planned/on_hold → in_progress, NEVER terminal; audit `update` |
| `qci_accept(quality_inspection_acceptance_pending)` | `InspectionAcceptanceForm`: `usage_decision` ∈ {accept, accept_with_deviation}, optional `accepted_by_party`, `acceptance_note`; stamps accepted_by/at + status `passed`; audit `accept`. PRECONDITION: result recorded — a pending-result acceptance row refuses first |
| `qci_reject(quality_inspection_acceptance_pending)` | → `usage_decision="reject"` + status `failed`; audit `reject`; same recorded-result precondition |
| `qdf_resolve(quality_defect_open)` | `DefectResolutionForm` (`resolution_note` REQUIRED, `root_cause` optional) + resolved_by/at + status `resolved`; audit `resolve`; legal from open AND in_progress |
| `qdf_close(quality_defect_resolved)` | → closed; audit `close` (no new stamps) |
| `qdf_raise_issue(quality_defect_open)` | mints a `ProjectIssue` (severity mapped critical→critical / major→high / minor→medium / observation→low; owner copied; raised_by/created_by = user; identified today) + `project_issue` set; audit `create` on the issue AND `update` on the defect; the success message names BOTH numbers; `quality_defect_bridged` answers "already raised issue ISS-…" (info) |

**Edit-lock rows** (`is_locked` → edit/delete refuse): plan superseded/closed · review
closed/cancelled · inspection passed/failed/cancelled **or `usage_decision != "pending"`** ·
defect resolved/closed/**cancelled** (the M1 amendment). GET on every verb and delete route →
405. Audit verbs used: create/update/delete/accept/reject/resolve/close (`AuditLog.action` is
varchar(10); choices are not DB-enforced — the D2 convention).

---

## 5. Reminders that have bitten this repo

* **Numbers are creation-order dependent** — assert prefix + shape (`^QPL-\d{5}$`, `^QRV-`,
  `^QCI-`, `^QDF-`), never a hardcoded number. Per tenant, per model (tenant B reads QPL-00001 too).
* **L16** — every date from `timezone.localdate()` / `timezone.now()` (`_quality_today()`); the
  overdue/age fixtures' offsets are what make `is_review_overdue` / `is_improvement_overdue` /
  `is_overdue` / `age_days` exact.
* **L11/L9** — junk enum/int GET params → 200 default page; a valid-but-FOREIGN pk FILTER
  (`?project=<B pk>`) → 200 EMPTY on the four registers; `?page=abc` → page 1; page 2 needs
  `QUALITY_PAGE_SIZE + 1` rows (use the `_quality_fill_*` helpers — but remember fills move the
  project-scoped board figures of §3).
* **L35** — absent prerequisites are REFUSED, not fallen through: approve a non-draft, supersede
  a non-active, report a reported/closed/cancelled review, close a non-reported review, record on
  a locked inspection, decide on a pending-result inspection, close a non-resolved defect,
  resolve a locked defect, raise a second issue.
* **403 vs 404 by actor**: `qpl_supersede` is the ONLY admin-gated verb — a tenant-A member's
  POST must 403 before any lookup (and its GET must 405, decorator order). Everything else is
  login-gated: `quality_member` runs the happy paths. IDOR-404s via `quality_admin_client`;
  `quality_member_b` on a tenant-A pk → 404 (scope, not role).
* **Cross-tenant FK POSTs**: the narrowed queryset refuses first — assert the FIELD has an
  error, never `_reject_foreign`'s wording. Crafted values: `quality_project_b`,
  `quality_wbs_node_b`, `quality_plan_b`, `quality_milestone_b`, `quality_inspection_b`,
  `quality_defect_b`, `quality_client_party_b`, plus an inline `_risk(tenant_b, …)` for
  `source_risk`. `accepted_by_party` is a `core.Party` FK — NEVER hand it to `_reject_foreign`
  (a Party has no `tenant`-comparable in the form mixin; the form scopes the queryset and the
  view re-checks `party.tenant_id`).
* **L20/L22** — `status` (all four models), `approved_by`/`approved_at`, `closed_at`,
  `usage_decision`/`accepted_by`/`accepted_by_party`/`accepted_at`/`acceptance_note`,
  `project_issue`, `root_cause`/`resolution_note`/`resolved_by`/`resolved_at`, `created_by`
  must not be form fields; assert a smuggled POST value changes nothing. The ONLY writers are
  the verbs + `InspectionAcceptanceForm` / `DefectResolutionForm` (the two plain `forms.Form`s).
* Form field lists (§3 of the build contract): `QualityPlanForm`, `QualityReviewForm`,
  `DeliverableInspectionForm`, `QualityDefectForm` are `TenantUniqueMixin, TenantModelForm`
  (mixin FIRST); `InspectionAcceptanceForm` (usage_decision/accepted_by_party/acceptance_note)
  and `DefectResolutionForm` (root_cause/resolution_note) are plain `forms.Form`. `status` is
  excluded from all four ModelForms.
* URL names (all disjoint first segments `quality-plans/` `quality-reviews/` `inspections/`
  `defects/` `quality-improvement/` `quality-acceptance/`): CRUD sets `qpl_*` (7 routes),
  `qrv_*` (7), `qci_*` (8), `qdf_*` (8), plus `quality_improvement` and `quality_acceptance`.
  Detail-page extra context: `qpl_detail` → `linked_reviews`/`linked_inspections`/
  `linked_defects`; `qci_detail` → `defects`/`accept_form`; `qdf_detail` → `resolution_form`.
* Search fields per register: qpl number/title/description/acceptance_criteria/standard_reference ·
  qrv number/title/scope/findings/improvement_action · qci number/title/description/findings ·
  qdf number/title/description/root_cause/resolution_note.
* Tests never touch `management/commands/seed_projects.py`; peers own `test_risk_*` etc. — 7.6
  imports nothing from other lanes' TEST modules, only factory functions from the shared conftest.
