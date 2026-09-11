---
name: projects
description: >-
  Work on the Project Management module (Module 7 — as-built: 7.1 Project Initiation & Charter:
  project requests/intake with a business case and risk-adjusted ROI, the go/no-go decision verbs,
  request→project conversion, charter authoring with a submit/approve gate, the RACI stakeholder
  register with influence/interest engagement strategy, and kickoff ceremonies with baseline
  acknowledgement; and 7.2 Project Planning & Scheduling: the WBS tree with computed WBS codes and
  deliverable rollups, the task register with duration/effort estimation, the dependency network
  with a computed critical chain, milestones and phase gates with a one-shot achieved stamp, and
  frozen schedule baselines with what-if scenarios and promote/activate verbs). Use when the user
  asks to add/change/debug anything under apps/projects or templates/projects, extend the
  seed_projects seeder, touch project sidebar wiring (LIVE_LINKS 7.1/7.2), work on
  ProjectRequest/Project/ProjectStakeholder/ProjectKickoff/ProjectTask/TaskDependency/
  ProjectMilestone/ScheduleBaseline, or invokes /projects.
---

# Module 7 — Project Management (`apps/projects`)

**As-built: 7.1 + 7.2.** 7.3–7.19 are roadmap (a parallel build may be landing them — always
check `apps/projects/models/` first). Do not assume a model exists because NavERP.md lists the
feature — check first.

App path `apps/projects/`, templates `templates/projects/`, `app_name = "projects"`, mounted at
`/projects/`. Migrations `0001_initial`, `0002_ordering_indexes_and_nonnegative_estimates`,
`0003_projecttask_projectmilestone_schedulebaseline_and_more`.

## ⚠️ Three different models are called "Project"

| Model | Path | What it is |
|---|---|---|
| `projects.Project` | `apps/projects/models/ProjectInitiation/Projects.py` | **this module's** — the chartered project |
| `accounting.Project` | `apps/accounting/models/ProjectCosting/Projects.py` | pre-spine stand-in for job costing |
| `crm.CrmProject` | `apps/crm/models/ProjectDelivery/Projects.py` | pre-spine stand-in for delivery |

All three use `NUMBER_PREFIX = "PRJ"`. **This is deliberate and is not a bug to "fix".** Numbers are
unique per `(tenant, number)` *within a model*, so there is no key collision. Always import
explicitly (`from apps.projects.models import Project`) and say which "project" a page means.

## Models

All four subclass `TenantNumbered` (`apps/projects/models/_base.py`): tenant FK, `number` allocated
in `save()` via `apps.core.utils.next_number`, timestamps, `ordering = ["-created_at", "-id"]`,
`unique_together ("tenant", "number")`.

### `ProjectRequest` [PRQ-] — intake + business case
Choices: `REQUEST_TYPE_CHOICES` (new_project/enhancement/change_request/defect/idea) ·
`SOURCE_CHOICES` (portal/internal/idea/opportunity/email) · `PRIORITY_CHOICES` ·
`RISK_RATING_CHOICES` (low/medium/high/critical) · `FEASIBILITY_CHOICES` (not_assessed/feasible/
**feasible_with_constraints**/not_feasible — 25 chars, hence `max_length=32`) ·
`STATUS_CHOICES` (draft/submitted/screening/assessment/needs_information/approved/rejected/
deferred/converted) · `DECISION_CHOICES` (go/no_go/hold/deferred).

Money: `estimated_cost`, `estimated_benefit` — `DecimalField(14,2)` with `MinValueValidator(0)`.
Derived, never stored: `roi_pct`, `risk_adjusted_benefit`, `risk_adjusted_roi_pct` using
`RISK_DISCOUNT = {low: 1.00, medium: 0.85, high: 0.70, critical: 0.50}` — a **documented flat
factor, deliberately not Monte Carlo** (that is 7.5's). All arithmetic is `Decimal`; `q2()` clamps
at `9999999999.99`.

`convert_to_project()` — one `transaction.atomic()` with a **row-level compare-and-swap**
(`select_for_update` / `filter(converted_project__isnull=True)`); maps `title→name`, `description`,
`org_unit`, `requester_party→client`, `assigned_approver→executive_sponsor`,
`target_start_date→start_date`, `target_end_date→end_date`, sets both FK directions and
`created_by`. It deliberately does **not** gate on `status` — that rule belongs to the `prq_convert`
view.

### `Project` [PRJ-] — the charter
`name`, `code`, `description`, `request` (back-pointer), `methodology`, and the charter body:
`in_scope`, `out_of_scope`, `objectives`, `success_criteria`, `assumptions`, `constraints`,
`risk_summary`. People: `executive_sponsor`, `project_manager` (Users), `org_unit`, `client`
(`core.Party`). `charter_status` (draft/submitted/approved/rejected) + `charter_approved_by/_at`
(`editable=False`) + `charter_document` (`core.Document`). `status` (draft/chartered/kickoff/
active/on_hold/completed/cancelled).

### `ProjectStakeholder` [PST-] — RACI register
A stakeholder is a **`core.Party` OR a User** — at least one required (`clean()`).
`STAKEHOLDER_TYPE_CHOICES`, `RACI_ROLE_CHOICES` (r/a/c/i), `INFLUENCE_CHOICES` /
`INTEREST_CHOICES` (high/medium/low), `COMMS_PREFERENCE_CHOICES`, `COMMS_FREQUENCY_CHOICES`,
`attending_kickoff`. `unique_together ("tenant","project","party","raci_scope")`.
**`get_engagement_strategy_display()` is hand-written** — Django does *not* generate
`get_FOO_display` for a property. It derives manage_closely / keep_satisfied / keep_informed /
monitor from the influence×interest grid.

### `ProjectKickoff` [PKO-] — the ceremony
`unique_together ("tenant","project")` — one kickoff per project. `AGENDA_TEMPLATE_CHOICES`,
`STATUS_CHOICES` (planned/scheduled/held/completed), `meeting_date`, `completed_at`,
`baseline_acknowledged_by/_at`. `attendee_count` is a **property**; `is_locked` is the attested
predicate (`completed`, or either stamp set), mirroring `accounting.JournalEntry.is_locked`.

## 7.2 Project Planning & Scheduling — `ProjectPlanningScheduling/`, template slug `planning`

Contract: `.claude/tasks/contract-projects-7.2.md`. Scope: the PLAN only — no money columns (7.4's),
no execution actuals/assignments (7.8 extends `ProjectTask` in place), no risk rows (7.5's).

### `ProjectTask` [TSK-] — the WBS node AND the schedulable activity in one row
`project` FK CASCADE `related_name="tasks"` · `parent` self-FK SET_NULL `related_name="children"`
(plain self-FK, no MPTT) · `node_type` (`deliverable` = summary rollup / `work_package` = schedulable
leaf) · `status` (planned/in_progress/done/cancelled — planning only, NOT gated) ·
`planned_start`/`planned_end` (clean(): end ≥ start) · `duration_days` derived property ·
`effort_hours` + `estimation_method` (bottom_up/top_down/analogous/parametric) + `confidence` ·
`sequence` (sibling order). `clean()` also rejects a **cross-project parent**. The hierarchical
`1.2.3` WBS code and every deliverable rollup are computed in the tree view — NEVER stored.

### `TaskDependency` [DEP-] — the sequencing network
`predecessor`/`successor` FKs (`related_name="successor_links"` / `"predecessor_links"`) ·
`link_type` (finish_to_start/start_to_start/finish_to_finish/start_to_finish) · `lag_days`
SmallIntegerField — positive = lag, negative = lead. `clean()`: no self-link, both endpoints in the
same project (and tenant).

### `ProjectMilestone` [MST-] — milestones and phase gates
`is_phase_gate` + `entry_criteria`/`exit_criteria` · `status` (planned/in_review/achieved/missed/
cancelled) · `actual_date` is a stamp: `save()` writes it the first time status is `achieved` and
clears it on reopen — never a form field. Ordering `["target_date", "id"]` (timeline) — a deliberate
exception to newest-first. `status` is NOT on `MilestoneForm`: the only path to `achieved` is the
tenant-admin verb `mst_achieve`.

### `ScheduleBaseline` [BSL-] — frozen baselines and what-if scenarios
`baseline_type` (`baseline` frozen / `what_if` scenario) · snapshot columns `planned_finish`/
`task_count`/`total_effort_hours` + `frozen_on` (editable=False — freeze-time evidence written by
`freeze_snapshot()`, one aggregate; NOT live aggregates). Frozen rows refuse edit/delete (state
guard, not role gate); type is LOCKED on edit (only `bsl_promote` moves what_if→baseline);
`bsl_activate`/`bsl_promote` keep exactly one active baseline per project inside
`transaction.atomic()` — deliberately NO conditional unique constraint (MariaDB can't enforce one).

### 7.2 views and the WBS tree
`views/ProjectPlanningScheduling/ProjectTasks.py::_decorate_wbs` prefetches the whole tree in ONE
query, then decorates each node in Python: `wbs_code`, `is_critical`, `kids` (the decorated child
instances) and the `rollup_*` attrs. The template walks `node.kids` — NEVER `node.children.all`
(see gotcha 8). `views/_helpers.py::critical_path_ids` = the longest dependency chain, computed on
read (iterative Kahn pass, hop-capped, `(sequence, id)` tie-breaks; full CPM float is 7.16's).

## Routes (`app_name = "projects"`, 56 names)

`overview` · `prq_{list,create,detail,edit,delete}` · `prj_…` · `pst_…` · `pko_…` plus the verbs ·
7.2: `tsk_{list,create,detail,edit,delete}` + `tsk_tree` (literal route `tasks/tree/`) ·
`dep_…` · `mst_…` · `bsl_…` (path prefixes `tasks/ dependencies/ milestones/ baselines/` — first
segments disjoint from 7.1's, so the url concatenation cannot shadow).

**The 15 POST-only 7.1 verbs are `@require_POST`, so a GET returns 405, not 302** — that is the house
pattern, not a bug. 7.2 adds three more, all `@require_POST` + `@tenant_admin_required`:

| Verb | Requires |
|---|---|
| `mst_achieve` | not achieved/cancelled — stamps `actual_date` exactly once |
| `bsl_activate` | type `baseline`, not already active |
| `bsl_promote` | type `what_if` — snapshots, freezes, activates |

7.2's plain CRUD is login-only, but **frozen baselines refuse `bsl_edit`/`bsl_delete` with a
redirect + message** — and `BaselineForm` locks `baseline_type` on edit, so the promote verb is the
only what_if→baseline path.

| Verb | Gate | Requires |
|---|---|---|
| `prq_submit` | login | draft / needs_information |
| `prq_approve` | **tenant_admin** | `DECISION_STATUSES` |
| `prq_reject` | **tenant_admin** | `DECISION_STATUSES` |
| `prq_return_for_information` | **tenant_admin** | not draft/converted; **voids the decision stamps** |
| `prq_convert` | **tenant_admin** | `approved`, not already converted |
| `prj_submit_charter` | login | charter draft/rejected, project not terminal |
| `prj_approve_charter` | **tenant_admin** | charter `submitted`, project not terminal |
| `prj_delete` | login | **refused while `charter_status == "approved"`**; reopens the source request |
| `pko_schedule` | login | needs a `meeting_date` |
| `pko_mark_held` | **tenant_admin** | `scheduled` |
| `pko_complete` | **tenant_admin** | `held` **and** an approved charter |
| `pko_mark_baseline_set` | **tenant_admin** | not planned/scheduled |

`prq_edit` and `prj_edit` and `pko_edit` carry **post-attestation edit locks** — once decided /
charter-approved / ceremony-attested, the row is not editable. This is the module's evidence model:
*you cannot forge the signature, so you must not be able to change what it signs.*

## Templates — `templates/projects/<submodule>/<entity>/{list,detail,form}.html`

Entity folders `initiation/{projectrequest, project, projectstakeholder, projectkickoff}/` and
`planning/{task, taskdependency, milestone, schedulebaseline}/`, plus
`templates/projects/overview.html` at the app root and the recursive
`planning/task/{tree.html,_tree_node.html}` WBS pair (depth-capped, walks `node.kids`). Extend `base.html`; colour-named theme.css
badges only (`badge-green/-red/-amber/-info/-muted/-slate` — the semantic `-success/-warning/
-danger` variants **do not exist** and render unstyled).

## Seeder — `seed_projects`

Idempotent, per-tenant guarded, and the 7.2 block has its OWN guard (an already-seeded 7.1
workspace still gets its planning rows). Creates **9 ProjectRequests / 3 Projects /
6 ProjectStakeholders / 2 ProjectKickoffs per tenant** (Acme + Globex) plus `core.Activity` rows,
and — 7.2 — a stage-sized plan per project: the ACTIVE project gets an 11-node WBS, a 9-link
dependency network whose longest chain is the critical path, 3 milestones (one achieved gate) and a
frozen baseline + what-if; the chartered project a 5-node WBS, 2 links, an in-review gate and a
what-if; the draft 3 sketch nodes and 3 planned milestones (no commitments). Log in as
`admin_acme` / `admin_globex`, password `password`. Run it twice to prove idempotency.

Do **not** "optimize" it with `bulk_create` — `TenantNumbered.save()` allocates `number`, and
`bulk_create` bypasses `save()`, shipping rows with empty numbers.

## Tests — `apps/projects/tests/` (green unfiltered)

`conftest.py` (7.1 `projectinitiation_*` + 7.2 `planning_*` fixture blocks — **owned by itself;
edit it only with a full unfiltered re-run**) plus `test_initiation_{models,forms,views,security}.py`
and `test_planning_{models,forms,views,security}.py` (16/15/21/12 — the security file expands to 35
cases via route parametrization). Naming: every test `test_<subslug>_*`, every helper
`_<subslug>_*`, so the next sub-module cannot shadow them.

```bash
venv\Scripts\python.exe -m pytest apps/projects/ --nomigrations
```

**Iterate with `--nomigrations` (~90 s). The full migration path takes ~23 minutes** of DB setup and
`--reuse-db` is inert against SQLite `:memory:`. Never use `-k` for the final run (L47).

## Gotchas that have already bitten this module

1. **A nullable FK inside a `|default:` filter argument 500s the page.** Django resolves filter
   *arguments* eagerly and `string_if_invalid` only swallows `VariableDoesNotExist` for the *main*
   variable. `{{ obj.user.get_full_name|default:obj.user.username }}` is a hard 500 the instant the
   FK is NULL. Use `{% if obj.user %}…{% else %}—{% endif %}`. This cost four 500-ing pages here.
2. **`attendee_total`, not `attendee_count`, in the registers.** `attendee_count` is a `property`
   (a data descriptor) and shadows an annotation — `annotate(attendee_count=…)` raises
   `AttributeError: can't set attribute`.
3. **An aggregate over a multi-valued relation drops `Meta.ordering`.** `pko_list` and `prj_detail`
   annotate `attendee_total`, so the explicit `.order_by("-created_at", "-id")` is **load-bearing** —
   remove it and the register silently stops being newest-first.
4. **403 vs 404 depends on the actor.** `apps/core/decorators.py:16` runs before
   `get_object_or_404`, so on an admin-gated verb with a cross-tenant pk a *member* gets 403 and an
   *admin* gets 404. Write IDOR-404 assertions with the admin client.
5. **`_reject_foreign`'s message is unreachable via a normal crafted POST** — `TenantModelForm`
   narrows the queryset first, so Django's "Select a valid choice" wins. Assert *that the field has
   an error*, never the wording.
6. **`accounting.Currency` is a deliberate GLOBAL table with no `tenant` column (L29)** — it is the
   one FK that must stay unscoped.
7. **`core.AuditLog.action` is `varchar(10)`.** The verb goes in `changes` (`{"verb":…, "from":…,
   "to":…}`), never in `action`. Capture `previous = obj.status` *before* mutating — a hard-coded
   `from` makes the trail assert a gate held precisely when it was skipped.
8. **`prefetch_related("children")` returns DIFFERENT Python objects than the parent queryset.**
   7.2's first tree build decorated one set and the template read the other — rows rendered with no
   wbs_code/critical/rollup. That is why `_decorate_wbs` hangs the DECORATED instances on
   `node.kids` and the include walks `node.kids`, never `node.children.all`.
9. **Recursion depth is a member-triggerable 500.** The tree walk and the critical-path pass are
   ITERATIVE with hard caps (template depth 5, walk depth 20, Kahn hop cap) — a ~1000-node chain
   must skip nodes, never RecursionError. Don't "simplify" them back to recursion.
10. **A verb-gated field must not also be POST-settable through the ungated edit form.** 7.2 shipped
   `status` on `MilestoneForm` and `baseline_type` on `BaselineForm` — both let a member bypass the
   tenant-admin verbs (achieve without the stamp gate; "freeze" without a snapshot). Verbs write
   state; forms must not.

## Sidebar wiring — `apps/core/navigation.py`

```python
"7.1": {
    "Project Request & Intake":              "projects:prq_list",
    "Business Case & Feasibility":           "projects:prq_list?status=submitted",
    "Project Charter Authoring":             "projects:prj_list",
    "Stakeholder Identification & Analysis": "projects:pst_list",
    "Project Kickoff & Launch":              "projects:pko_list",
}
```
The business case has no register of its own — cost/benefit, ROI and the go/no-go verbs all live
**on `ProjectRequest`**, so that bullet deep-links the same register filtered to the gate where
those numbers are weighed (the 2.15 `?category=` precedent).

```python
"7.2": {
    "Work Breakdown Structure (WBS)":        "projects:tsk_tree",
    "Task Sequencing & Dependency Mapping":  "projects:dep_list",
    "Duration & Effort Estimation":          "projects:tsk_list?node_type=work_package",
    "Milestone & Phase-Gate Definition":     "projects:mst_list",
    "Schedule Baseline & Version Control":   "projects:bsl_list",
    "Task Register":                         "projects:tsk_list",  # extra live leaf
}
```
Estimation deep-links the task register filtered to work packages (the rows that carry the
estimate); "Task Register" is an extra leaf — the parser appends labels that don't match a
NavERP.md bullet.

## Common tasks

- **Add a field** — edit the entity file under `models/ProjectInitiation/`, add it to the form's
  `Meta` (or its `exclude` if it is system/evidence — see the evidence model above), render it in
  the templates, `makemigrations projects`, `migrate`, extend `seed_projects`, add tests.
- **Add a model + CRUD** — new `<Entity>.py` in **all four** layers under `ProjectInitiation/`,
  **add it to every package `__init__.py` re-export block** (a missing re-export is a runtime
  `ImportError`), templates at `templates/projects/initiation/<entity>/`, then the seeder and tests.
- **Add a filter** — parse it in the view *before* pagination, pass the choices/queryset into the
  context, and in the template compare pk filters with `|stringformat:"d"` (never `|slugify`).
- **Build 7.3+** — use `/next-module`. New sub-module = a new `<SubModule>/` folder in each of
  the four layers, a new `templates/projects/<submodule>/` tree, and one new `LIVE_LINKS` entry.
