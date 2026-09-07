# 7.1 Project Initiation & Charter — contract (`apps/projects`)

> **BRAND-NEW-APP RUN.** `apps/projects/` is created by this pass; `apps.projects` joins
> `INSTALLED_APPS` and `config/urls.py` at Integrate (the check-after-edit hook blocks adding it
> before the app files exist — L12).
>
> Source of truth for *why* each field exists: `.claude/tasks/research-projects-7.1.md`.
> Build plan: `.claude/tasks/todo.md` §7.1. **This file only pins names** — the thing a wrong
> guess turns into a blank region at 200 (L7) or a `NoReverseMatch` (L8).

## Namespaces

| Thing | Value |
|---|---|
| app slug / `app_name` | `projects` |
| backend sub-module folder | `ProjectInitiation/` (all four layers) |
| template sub-module slug | `initiation` |
| entity files | `ProjectRequests.py`, `Projects.py`, `ProjectStakeholders.py`, `ProjectKickoffs.py` |
| template entity folders | `initiation/projectrequest/`, `initiation/project/`, `initiation/projectstakeholder/`, `initiation/projectkickoff/` |
| url stems | `prq_` / `prj_` / `pst_` / `pko_` |
| number prefixes | `PRQ` / `PRJ` / `PST` / `PKO` |
| migration | `projects/0001_initial.py` |

## ⚠️ The three `PRJ-` models — do not "fix"

`accounting.Project` (`apps/accounting/models/ProjectCosting/Projects.py`) and
`crm.CrmProject` (`apps/crm/models/ProjectDelivery/Projects.py`) both already use
`NUMBER_PREFIX = "PRJ"`. They are pre-spine stand-ins and are **untouched this pass** — no
migration for either app. Numbers are unique per `(tenant, number)` *within a model*, so there is
no key collision; `projects.Project`'s docstring names both stand-ins and every page title says
which "project" the user is looking at.

## 🚨 `core.AuditLog.action` is `varchar(10)`

Every 7.1 action string is **≤ 10 characters**: `create` / `update` / `delete` (the `crud_*`
helpers), `submit`, `approve`, `reject`, `convert`, `return`, `schedule`, `held`, `complete`,
`baseline` (8). The verb itself goes in `changes` (`{"verb": "...", "from": ..., "to": ...}`),
never in `action`. (Upstream `core` migration noted in the review file, not done here.)

---

## Model 1 — `ProjectRequest` [PRQ-]

Base `TenantNumbered`, `NUMBER_PREFIX = "PRQ"`. `ordering = ["-created_at", "-id"]`,
`unique_together = ("tenant", "number")`.
Indexes: `prq_tnt_status_idx (tenant,status)`, `prq_tnt_type_idx (tenant,request_type)`,
`prq_tnt_ou_idx (tenant,org_unit)`.

### CHOICES (exact machine values — templates compare against these)

| Constant | Values |
|---|---|
| `REQUEST_TYPE_CHOICES` | `new_project`, `enhancement`, `change_request`, `defect`, `idea` |
| `SOURCE_CHOICES` | `portal`, `internal`, `idea`, `opportunity`, `email` |
| `PRIORITY_CHOICES` | `low`, `medium`, `high`, `critical` |
| `RISK_RATING_CHOICES` | `low`, `medium`, `high`, `critical` |
| `FEASIBILITY_CHOICES` | `not_assessed`, `feasible`, `feasible_with_constraints`, `not_feasible` |
| `STATUS_CHOICES` | `draft`, `submitted`, `screening`, `assessment`, `needs_information`, `approved`, `rejected`, `deferred`, `converted` |
| `DECISION_CHOICES` | `go`, `no_go`, `hold`, `deferred` |

`RISK_DISCOUNT = {"low": Decimal("1.00"), "medium": Decimal("0.85"), "high": Decimal("0.70"),
"critical": Decimal("0.50")}` — a documented flat factor, explicitly **not** Monte Carlo (7.5's).

### Fields

`title`(200), `description`(Text), `request_type`(20, default `new_project`),
`requested_by`(FK User SET_NULL `prq_filed`), `requester_party`(FK `core.Party` SET_NULL
`project_requests`), `org_unit`(FK `core.OrgUnit` SET_NULL `project_requests`),
`source`(20, default `internal`), `source_opportunity`(FK `crm.Opportunity` SET_NULL
`project_requests`), `assigned_reviewer`(FK User SET_NULL `prq_to_review`),
`assigned_approver`(FK User SET_NULL `prq_to_approve`), `priority`(10, default `medium`),
`strategic_alignment`(PosSmallInt 0–5 default 0), `estimated_cost`(Dec 14,2 default 0),
`estimated_benefit`(Dec 14,2 default 0), `currency`(FK `accounting.Currency` SET_NULL
`project_requests` — **global table, no `tenant` column**, L29), `risk_rating`(10 default `low`),
`feasibility`(24 default `not_assessed`), `feasibility_notes`(Text blank),
`alternatives_considered`(Text blank), `required_resources`(Text blank),
`target_start_date`(Date null), `target_end_date`(Date null), `status`(20 default `draft`),
`decision`(10 default `""` blank), `decided_by`(FK User SET_NULL `+` editable=False),
`decided_at`(DateTime null editable=False), `decision_notes`(Text blank),
`rejection_reason`(Text blank), `information_requested`(Text blank),
`submitted_at`(DateTime null editable=False), `converted_project`(FK `projects.Project`
SET_NULL `source_requests`), `created_by`(FK User SET_NULL `+` editable=False).

Derived **properties, never columns**: `roi_pct` (None when cost == 0), `risk_adjusted_benefit`,
`risk_adjusted_roi_pct`.

Service method: `convert_to_project(user)` — one `transaction.atomic()`; copies
`title`→`name`, `description`, `target_start_date`→`start_date`, `target_end_date`→`end_date`,
`org_unit`, `requester_party`→`client`, `assigned_approver`→`executive_sponsor`; sets
`Project.request = self`, `self.converted_project = project`, `self.status = "converted"`;
refuses when `converted_project_id` is already set.

### Form

`ProjectRequestForm` — `TenantUniqueMixin, TenantModelForm`.
**Excludes:** `tenant`, `number`, `status`, `decision`, `decided_by`, `decided_at`,
`submitted_at`, `converted_project`, `created_by`.
Tenant-scoped FK re-check via `_reject_foreign`: `org_unit`, `source_opportunity` — **not**
`currency` (global, no tenant).

`ProjectRequestDecisionForm` — `reason = CharField(widget=Textarea, required=True)`, shared by
the reject and return-for-information verbs.

### Routes (`project-requests/`) + context keys

| url name | view | template | context |
|---|---|---|---|
| `prq_list` | `prq_list` | `projects/initiation/projectrequest/list.html` | `object_list`, `page_obj`, `q`, `status_choices`, `request_type_choices`, `priority_choices`, `risk_rating_choices`, `feasibility_choices`, `decision_choices`, `org_units` |
| `prq_create` | `prq_create` | `…/form.html` | `form`, `is_edit`=False |
| `prq_detail` | `prq_detail` | `…/detail.html` | `obj`, `decision_form` |
| `prq_edit` | `prq_edit` | `…/form.html` | `form`, `obj`, `is_edit`=True |
| `prq_delete` | `prq_delete` (POST) | — | — |
| `prq_submit` | POST `submit/` | — | — |
| `prq_approve` | POST `approve/` — `@tenant_admin_required` | — | — |
| `prq_reject` | POST `reject/` — `@tenant_admin_required` | — | — |
| `prq_return_for_information` | POST `return/` | — | — |
| `prq_convert` | POST `convert/` — `@tenant_admin_required` | — | — |

List filters: `q` over `title`/`description`/`number`; `status`, `request_type`, `priority`,
`risk_rating`, `feasibility`, `decision` (enum-allow-listed by `crud_list`), `org_unit` (int pk).

---

## Model 2 — `Project` [PRJ-]

Base `TenantNumbered`, `NUMBER_PREFIX = "PRJ"`. `ordering = ["-created_at", "-id"]`,
`unique_together = ("tenant", "number")`.
Indexes: `prj_tnt_status_idx (tenant,status)`, `prj_tnt_charter_idx (tenant,charter_status)`,
`prj_tnt_client_idx (tenant,client)`, `prj_tnt_ou_idx (tenant,org_unit)`.

| Constant | Values |
|---|---|
| `METHODOLOGY_CHOICES` | `waterfall`, `agile`, `hybrid` |
| `CHARTER_STATUS_CHOICES` | `draft`, `submitted`, `approved`, `rejected` |
| `STATUS_CHOICES` | `draft`, `chartered`, `kickoff`, `active`, `on_hold`, `completed`, `cancelled` |

### Fields

`name`(255), `code`(30 blank), `request`(FK `projects.ProjectRequest` SET_NULL `projects` — set
by the convert verb only), `methodology`(12 default `hybrid`), `in_scope`(Text blank),
`out_of_scope`(Text blank), `objectives`(Text blank), `success_criteria`(Text blank),
`assumptions`(Text blank), `constraints`(Text blank), `risk_summary`(Text blank),
`executive_sponsor`(FK User SET_NULL `sponsored_projects`), `project_manager`(FK User SET_NULL
`managed_projects`), `org_unit`(FK `core.OrgUnit` SET_NULL `projects`), `client`(FK `core.Party`
SET_NULL `delivery_projects`), `start_date`(Date null), `end_date`(Date null),
`charter_status`(12 default `draft`), `charter_approved_by`(FK User SET_NULL `+` editable=False),
`charter_approved_at`(DateTime null editable=False), `charter_document`(FK `core.Document`
SET_NULL `project_charters`), `status`(12 default `draft`),
`created_by`(FK User SET_NULL `+` editable=False).

**No money columns** — budget/actuals are 7.4's. Derived: `is_overdue` property.

### Form

`ProjectForm` — **excludes** `tenant`, `number`, `request`, `charter_status`,
`charter_approved_by`, `charter_approved_at`, `status`, `created_by`.
`_reject_foreign`: `org_unit`, `client`, `charter_document`.

### Routes (`projects/`) + context keys

| url name | view | context |
|---|---|---|
| `prj_list` | `prj_list` | `object_list`, `page_obj`, `q`, `status_choices`, `charter_status_choices`, `methodology_choices`, `org_units`, `clients` |
| `prj_create` / `prj_edit` | | `form`, `obj`, `is_edit` |
| `prj_detail` | | `obj`, `stakeholders` (reverse, capped 50), `kickoffs` (reverse), `source_request` |
| `prj_delete` | POST | — |
| `prj_submit_charter` | POST `submit-charter/` | — |
| `prj_approve_charter` | POST `approve-charter/` — `@tenant_admin_required` | — |

Filters: `q` over `name`/`code`/`number`; `status`, `charter_status`, `methodology`, `org_unit`
(int), `client` (int).

---

## Model 3 — `ProjectStakeholder` [PST-]

Base `TenantNumbered`, `NUMBER_PREFIX = "PST"`.
`ordering = ["-created_at", "-id"]` — **override #1**: the research's
`["-influence", "party__name"]` is wrong (`influence` is a CharField, so descending sorts
`medium > low > high` alphabetically, and `party__name` sorts NULLs inconsistently across
backends). The list view keeps the intent by annotating `influence_rank`
(`Case(When(influence="high", then=3), When(influence="medium", then=2), default=1)`) and
ordering `("-influence_rank", "id")`.

`unique_together = ("tenant","number")` **and** `("tenant","project","party","raci_scope")`.
**Override #2:** that second constraint is *partial* — `party` is nullable and SQL treats every
NULL as distinct, so a form-level `clean()` also raises on a duplicate
`(project, party, raci_scope)` and enforces "at least one of `party` / `user`".

Indexes: `pst_tnt_project_idx (tenant,project)`, `pst_tnt_type_idx (tenant,stakeholder_type)`.

| Constant | Values |
|---|---|
| `STAKEHOLDER_TYPE_CHOICES` | `sponsor`, `approver`, `resource_provider`, `subject_matter_expert`, `affected`, `team_member`, `other` |
| `RACI_ROLE_CHOICES` | `r`, `a`, `c`, `i` |
| `INFLUENCE_CHOICES` | `high`, `medium`, `low` |
| `INTEREST_CHOICES` | `high`, `medium`, `low` |
| `COMMS_PREFERENCE_CHOICES` | `email`, `meeting`, `written_report`, `portal`, `none` |
| `COMMS_FREQUENCY_CHOICES` | `daily`, `weekly`, `monthly`, `at_milestone`, `ad_hoc` |
| `ENGAGEMENT_STRATEGY_CHOICES` | `manage_closely`, `keep_satisfied`, `keep_informed`, `monitor` — **a label set, not a column** |

### Fields

`project`(FK `projects.Project` CASCADE `stakeholders`), `party`(FK `core.Party` SET_NULL
`project_stakeholders`), `user`(FK User SET_NULL `project_stakeholders`),
`stakeholder_type`(24 default `other`), `raci_role`(1 default `i`), `raci_scope`(120 blank),
`influence`(8 default `medium`), `interest`(8 default `medium`), `comms_preference`(16 default
`email`), `comms_frequency`(16 default `weekly`), `attending_kickoff`(Bool default False),
`notes`(Text blank), `created_by`(FK User SET_NULL `+` editable=False).

Derived: `engagement_strategy` — high/high→`manage_closely`, high/low→`keep_satisfied`,
low/high→`keep_informed`, else `monitor`. **`medium` maps to the low side** (documented).
`org_unit` is deliberately NOT added.

### Form

`ProjectStakeholderForm` — excludes `tenant`, `number`, `created_by`; `project` is an explicit
tenant-scoped `ModelChoiceField`. `clean()` carries override #2. `_reject_foreign`: `project`,
`party`.

### Routes (`stakeholders/`) + context keys

| url name | context |
|---|---|
| `pst_list` | `object_list`, `page_obj`, `q`, `projects`, `stakeholder_type_choices`, `raci_role_choices`, `influence_choices`, `interest_choices` |
| `pst_detail` / `pst_edit` | `obj` / `form`+`obj`+`is_edit` |
| `pst_create` / `pst_delete` | `form`+`is_edit` / POST |

Filters: `q` over `number`/`raci_scope`/`notes`; `project` (int), `stakeholder_type`, `raci_role`,
`influence`, `interest`.

---

## Model 4 — `ProjectKickoff` [PKO-]

Base `TenantNumbered`, `NUMBER_PREFIX = "PKO"`. `ordering = ["-created_at", "-id"]`,
`unique_together = ("tenant","number")` and `("tenant","project")`.
Indexes: `pko_tnt_project_idx (tenant,project)`, `pko_tnt_status_idx (tenant,status)`.

| Constant | Values |
|---|---|
| `AGENDA_TEMPLATE_CHOICES` | `standard`, `agile`, `client_facing`, `custom` |
| `STATUS_CHOICES` | `planned`, `scheduled`, `held`, `completed` |

### Fields

`project`(FK `projects.Project` CASCADE `kickoffs` — plain FK + `unique_together`, **not**
OneToOne), `meeting_date`(DateTime null), `location_or_link`(255 blank),
`agenda_template`(16 default `standard`), `agenda`(Text blank), `attendee_summary`(Text blank),
`onboarding_notes`(Text blank), `status`(12 default `planned`),
`baseline_acknowledged_at`(DateTime null editable=False),
`baseline_acknowledged_by`(FK User SET_NULL `+` editable=False),
`completed_at`(DateTime null editable=False), `notes`(Text blank), `created_by`(FK User SET_NULL
`+` editable=False).

Derived: `attendee_count` = `project.stakeholders.filter(attending_kickoff=True).count()`.
Docstring states the baseline **record** is 7.2's — this row attests the ceremony happened.

### Form

`ProjectKickoffForm` — excludes `tenant`, `number`, `status`, `baseline_acknowledged_at`,
`baseline_acknowledged_by`, `completed_at`, `created_by`. `_reject_foreign`: `project`.

### Routes (`kickoffs/`) + context keys

| url name | context |
|---|---|
| `pko_list` | `object_list`, `page_obj`, `q`, `projects`, `status_choices`, `agenda_template_choices` |
| `pko_detail` | `obj`, `attending` (project stakeholders with `attending_kickoff=True`), `activities` (`core.Activity` rows GFK'd to the project, read-only) |
| `pko_create` / `pko_edit` | `form` (+`obj`) + `is_edit` |
| `pko_delete` | POST |
| `pko_schedule` | POST `schedule/` |
| `pko_mark_held` | POST `mark-held/` — sets `Project.status = "kickoff"` |
| `pko_complete` | POST `complete/` — sets `completed_at` **and** `Project.status = "active"` |
| `pko_mark_baseline_set` | POST `baseline/` — stamps `baseline_acknowledged_at/by` |

Filters: `q` over `number`/`location_or_link`/`agenda`; `project` (int), `status`,
`agenda_template`.

---

## Cross-cutting invariants

- Every queryset is `filter(tenant=request.tenant)` — never `.all()`.
- Every verb refuses a disallowed transition with `messages.*` + redirect — never a 500, never a
  silent no-op; an action already in its target state says so and writes nothing.
- Every `?enum=` value is allow-listed against the model's CHOICES before filtering (`crud_list`
  does this for the `filters=` tuples — L11).
- Badges: colour-named theme.css classes only (`badge-green` / `badge-red` / `badge-amber` /
  `badge-info` / `badge-muted` / `badge-slate`). `badge-success` / `badge-danger` **do not
  exist** (L33). Every badge block ends with an `{% else %}{{ obj.get_x_display }}{% endif %}`.
- FK `<select>` pk comparisons use `|stringformat:"d"` — never `|slugify`.
- `{% extends "base.html" %}`; partials stay at the templates root.

## Seeded shape (for the smoke assertions)

9 `ProjectRequest` rows (one per status; **`approved` #1 converted through the real
`convert_to_project()`**, **`approved` #2 left unconverted** so the verb is exercisable),
3 `Project` rows, 6 `ProjectStakeholder` rows (all four RACI values, all four
influence×interest quadrants, 3 attending), 2 `ProjectKickoff` rows, 4 `core.Activity` rows
(1 `kind="meeting"` + 3 `kind="task"`) GFK'd to the active project.
9 requests / 15 per page → **2 pages**.

## NavERP 7.1 bullets → routes (`LIVE_LINKS["7.1"]`)

| Bullet | Route |
|---|---|
| Project Request & Intake | `projects:prq_list` |
| Business Case & Feasibility | `projects:prq_list?status=assessment` |
| Project Charter Authoring | `projects:prj_list` |
| Stakeholder Identification & Analysis | `projects:pst_list` |
| Project Kickoff & Launch | `projects:pko_list` |

No bullet for `Project` (the container), none for `ProjectRequest`'s economics (bullet 2's field
set), and none pointing at a login-gated portal view (L32).
