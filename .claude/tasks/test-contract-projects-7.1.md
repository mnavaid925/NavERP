# Test contract — Projects 7.1 Project Initiation & Charter (`apps/projects`)

**Phase 6, step 1.** Everything below is pinned from the **as-built source after the 41-finding fix
pass** (`.claude/tasks/review-projects-7.1.md`), not from `.claude/tasks/contract-projects-7.1.md`
(the *build* contract, now stale in several places). Where the two disagree, **this file wins** —
it was read out of the code and, for every status code and context key, verified by running it.

Steps 2–5 (`test_projectinitiation_models.py` → `_forms.py` → `_views.py` → `_security.py`) write
their tests against these names. A wrong name here becomes four wrong test files.

---

## 0. How the suite runs

| | |
|---|---|
| Settings | `config.settings_test` (SQLite `:memory:`) — set by `pytest.ini`; **env `DJANGO_SETTINGS_MODULE` beats it** (L19), and it is currently unset in this shell |
| Command | `venv\Scripts\python.exe -m pytest apps/projects -q` |
| Iterating | add `--nomigrations` (**L49**: `--reuse-db` is inert against `:memory:`; a full-migration run costs ~25 min of setup before the first assertion, `--nomigrations` ~15 s) |
| Final proof run | **migrations ON and unfiltered** — never `-k` (L47), never `--nomigrations` (L49 rule 4) |
| App mount | `path("projects/", include("apps.projects.urls"))` → every url below is under `/projects/` |
| Namespace | `app_name = "projects"` → `reverse("projects:<name>")` |

### Naming rule (mandatory)

* test functions: `test_projectinitiation_*`
* module-level helpers: `_projectinitiation_*`
* conftest fixtures: `projectinitiation_*` (root-conftest names excepted)

Module 7 keeps appending sub-modules to this same package; the prefix is what stops 7.2 shadowing
7.1.

### conftest ownership

`apps/projects/tests/conftest.py` is owned by step 1 **alone**. Steps 2–5 must not edit it. If it
ever must change, the whole app suite is re-run unfiltered afterwards.

---

## 1. Models — `apps/projects/models/ProjectInitiation/`

All four inherit `TenantNumbered` → `TenantOwned` (`apps/projects/models/_base.py`), giving
`tenant` (FK `core.Tenant`, `related_name="+"`), `created_at`, `updated_at`, and
`number` (`CharField(max_length=20, editable=False)`) minted in `save()` via
`apps.core.utils.next_number` with a 5-retry IntegrityError guard.
**All four use `ordering = ["-created_at", "-id"]`.**

Also exported from `apps.projects.models`: `TenantOwned`, `TenantNumbered`, `q2`, `MAX_Q2`
(`Decimal("9999999999.99")`), `ZERO`, `next_number`.

### 1.1 `ProjectRequest` — prefix `PRQ`, `PRQ-00001`

Concrete fields, in declaration order:

```
id tenant created_at updated_at number
title description request_type requested_by requester_party org_unit source source_opportunity
assigned_reviewer assigned_approver priority strategic_alignment
estimated_cost estimated_benefit currency risk_rating
feasibility feasibility_notes alternatives_considered required_resources
target_start_date target_end_date
status decision decided_by decided_at decision_notes rejection_reason information_requested
submitted_at converted_project created_by
```

* `editable=False`: `number`, `decided_by`, `decided_at`, `submitted_at`, `created_by`
  (+ `created_at`/`updated_at`).
* `Meta`: `unique_together = ("tenant", "number")`; indexes `prq_tnt_status_idx`,
  `prq_tnt_type_idx`, `prq_tnt_ou_idx`, `prq_tnt_created_idx` (`["tenant", "-created_at"]`, added
  by migration `0002`).
* `__str__` → `f"{number} — {title}"` (em dash U+2014).

CHOICES (assert the exact value strings):

| constant | values |
|---|---|
| `REQUEST_TYPE_CHOICES` | `new_project` `enhancement` `change_request` `defect` `idea` |
| `SOURCE_CHOICES` | `portal` `internal` `idea` `opportunity` `email` |
| `PRIORITY_CHOICES` | `low` `medium` `high` `critical` |
| `RISK_RATING_CHOICES` | `low` `medium` `high` `critical` |
| `FEASIBILITY_CHOICES` | `not_assessed` `feasible` `feasible_with_constraints` `not_feasible` |
| `STATUS_CHOICES` | `draft` `submitted` `screening` `assessment` `needs_information` `approved` `rejected` `deferred` `converted` |
| `DECISION_CHOICES` | `go` `no_go` `hold` `deferred` |

Constants: `RISK_DISCOUNT = {low: 1.00, medium: 0.85, high: 0.70, critical: 0.50}`;
**`DECISION_STATUSES = ("submitted", "screening", "assessment")`**.

Defaults: `request_type="new_project"`, `source="internal"`, `priority="medium"`,
`strategic_alignment=0` (`MaxValueValidator(5)`), `estimated_cost=0`, `estimated_benefit=0`
(both `max_digits=14, decimal_places=2`, **`MinValueValidator(Decimal("0"))` added by migration
`0002`**), `risk_rating="low"`, `feasibility="not_assessed"` (`max_length=32` — 24 was too short
for `feasible_with_constraints`), `status="draft"`, `decision=""` (blank).

DERIVED, properties not columns — assert no such column exists:

* `roi_pct` → `q2((benefit - cost) / cost * 100)`, **`None` when `cost == 0`** (not 0, not ∞).
* `risk_adjusted_benefit` → `q2(benefit * RISK_DISCOUNT[risk_rating])`.
* `risk_adjusted_roi_pct` → same shape, **`None` when `cost == 0`**.

`convert_to_project(user=None)`:
fast-path returns `None` if `self.converted_project_id`; otherwise opens `transaction.atomic()`
and does a **compare-and-swap** —
`type(self).objects.select_for_update().filter(pk=self.pk, converted_project__isnull=True).exists()`
— returning `None` when it matches nothing. On success builds `Project(tenant, name=title,
description, request=self, org_unit, client=requester_party, executive_sponsor=assigned_approver,
start_date=target_start_date, end_date=target_end_date, created_by=user)`, saves it, then
`self.converted_project = project; self.status = "converted"` saved with
`update_fields=["converted_project", "status", "updated_at"]`.
**It does NOT check `status`** — the "only an approved request" gate lives in the view.

### 1.2 `Project` — prefix `PRJ`, `PRJ-00001`

```
id tenant created_at updated_at number
name code description request methodology
in_scope out_of_scope objectives success_criteria assumptions constraints risk_summary
executive_sponsor project_manager org_unit client start_date end_date
charter_status charter_approved_by charter_approved_at charter_document
status created_by
```

* `editable=False`: `number`, `charter_approved_by`, `charter_approved_at`, `created_by`.
* `Meta`: `unique_together = ("tenant", "number")`; indexes `prj_tnt_status_idx`,
  `prj_tnt_charter_idx`, `prj_tnt_client_idx`, `prj_tnt_ou_idx`, `prj_tnt_created_idx` (`0002`).
* `__str__` → `f"{number} — {name}"`.
* `METHODOLOGY_CHOICES`: `waterfall` `agile` `hybrid` (default `hybrid`).
* `CHARTER_STATUS_CHOICES`: `draft` `submitted` `approved` `rejected` (default `draft`).
  **`rejected` is RESERVED** — no 7.1 verb sets it, but `prj_submit_charter` accepts it as a
  source, so a rejected charter can be resubmitted.
* `STATUS_CHOICES`: `draft` `chartered` `kickoff` `active` `on_hold` `completed` `cancelled`
  (default `draft`).
* `is_overdue` property: `False` when `end_date` is None **or** `status in ("completed",
  "cancelled")`; else `end_date < timezone.localdate()`. **Test it against `timezone.localdate()`,
  never `datetime.date.today()`** (L16).

**Three `PRJ-` models coexist** (`accounting.Project`, `crm.CrmProject`, `projects.Project`).
`unique_together` is per-model, so all three can read `PRJ-00001` in one tenant — never assert a
number is globally unique, and always import `Project` from `apps.projects.models`.

### 1.3 `ProjectStakeholder` — prefix `PST`, `PST-00001`

```
id tenant created_at updated_at number project party user
stakeholder_type raci_role raci_scope influence interest
comms_preference comms_frequency attending_kickoff notes created_by
```

* `project` → `projects.Project`, `on_delete=CASCADE`, `related_name="stakeholders"`.
* `party` → `core.Party` (SET_NULL), `user` → AUTH_USER_MODEL (SET_NULL); **at least one required
  by `clean()`**.
* `Meta.unique_together = (("tenant","number"), ("tenant","project","party","raci_scope"))` — the
  second is **partial** in SQL (NULL `party` is always distinct), which is why `clean()` re-checks.
* Indexes: `pst_tnt_type_idx`, `pst_tnt_created_idx` (`0002`).
  **`pst_tnt_project_idx` was REMOVED by `0002`** (leftmost prefix of the unique_together index).
* `__str__` → `f"{number} — {party or user or '—'} ({get_raci_role_display()})"`.
* CHOICES: `STAKEHOLDER_TYPE_CHOICES` = `sponsor` `approver` `resource_provider`
  `subject_matter_expert` `affected` `team_member` `other` (default `other`);
  `RACI_ROLE_CHOICES` = `r` `a` `c` `i` (default `i`, `max_length=1`);
  `INFLUENCE_CHOICES` / `INTEREST_CHOICES` = `high` `medium` `low` (default `medium`);
  `COMMS_PREFERENCE_CHOICES` = `email` `meeting` `written_report` `portal` `none` (default
  `email`); `COMMS_FREQUENCY_CHOICES` = `daily` `weekly` `monthly` `at_milestone` `ad_hoc`
  (default `weekly`);
  **`ENGAGEMENT_STRATEGY_CHOICES` is a LABEL SET, not a column** = `manage_closely`
  `keep_satisfied` `keep_informed` `monitor`.
* `engagement_strategy` property: high+high → `manage_closely`; high influence only →
  `keep_satisfied`; high interest only → `keep_informed`; else `monitor`.
  **`medium` maps to the LOW side of both axes.**
* `get_engagement_strategy_display()` is a **hand-written method** (Django does not generate
  `get_FOO_display` for a property) returning the label, `"—"` on miss.
* `clean()` raises `ValidationError` (a **non-field / `__all__`** error) for: neither party nor
  user; and a duplicate `(tenant, project, party, raci_scope)` excluding `self.pk`.

### 1.4 `ProjectKickoff` — prefix `PKO`, `PKO-00001`

```
id tenant created_at updated_at number project meeting_date location_or_link
agenda_template agenda attendee_summary onboarding_notes status
baseline_acknowledged_at baseline_acknowledged_by completed_at notes created_by
```

* `project` → CASCADE, `related_name="kickoffs"`.
* `Meta.unique_together = (("tenant","number"), ("tenant","project"))` — **one kickoff per
  project** (a plain FK + unique_together, deliberately NOT a OneToOneField).
* Indexes: `pko_tnt_status_idx`, `pko_tnt_created_idx` (`0002`).
  **`pko_tnt_project_idx` was REMOVED by `0002`.**
* `editable=False`: `number`, `baseline_acknowledged_at`, `baseline_acknowledged_by`,
  `completed_at`, `created_by`.
* `AGENDA_TEMPLATE_CHOICES` = `standard` `agile` `client_facing` `custom` (default `standard`);
  `STATUS_CHOICES` = `planned` `scheduled` `held` `completed` (default `planned`).
* `__str__` → `f"{number} — {project} ({get_status_display()})"` — chains through
  `Project.__str__`, so a list `__str__` loop is an N+1 unless `select_related("project")`.
* **`attendee_count` is a PROPERTY** — `project.stakeholders.filter(attending_kickoff=True).count()`,
  `0` when `project_id` is None. It is a data descriptor, so **the views annotate
  `attendee_total`, not `attendee_count`** (annotating over the property raises
  `AttributeError: can't set attribute`). Both must agree in value.

### 1.5 Migration `0002_ordering_indexes_and_nonnegative_estimates`

Removes `pko_tnt_project_idx` + `pst_tnt_project_idx`; adds `MinValueValidator(Decimal("0"))` to
`estimated_cost` and `estimated_benefit`; adds `(tenant, -created_at)` to **all four** models
(`prj_tnt_created_idx`, `pko_tnt_created_idx`, `prq_tnt_created_idx`, `pst_tnt_created_idx`).
`makemigrations --check` must stay clean.

---

## 2. Forms — `apps/projects/forms/ProjectInitiation/`

Import through the package root: `from apps.projects.forms import ProjectRequestForm,
ProjectRequestDecisionForm, ProjectForm, ProjectStakeholderForm, ProjectKickoffForm`
(the root also re-exports `TenantModelForm`, `TenantUniqueMixin`, `_reject_foreign`).

Every ModelForm is `class X(TenantUniqueMixin, TenantModelForm)` — **mixin first**, so
`instance.tenant` is stamped before `full_clean()`. Constructor: `Form(data=None, *, tenant=...)`.

### 2.1 `ProjectRequestForm`

`Meta.exclude` (**verify this list verbatim — it grew during the fix pass**):

```python
exclude = [
    "tenant", "number",                                  # auto
    "status", "decision",                                # verb-driven
    "decided_by", "decided_at", "submitted_at",          # stamps
    "converted_project",                                 # set by the convert verb
    "created_by",                                        # set in the view
    "rejection_reason", "information_requested", "decision_notes",   # ADDED IN THE FIX PASS
]
```

The last line is the L20/L22 test: `rejection_reason` / `information_requested` /
`decision_notes` are written only by the `@tenant_admin_required` verbs, so a field a gated verb
writes must not also be POST-settable through the ungated edit form.

Resulting **22 fields**: `title description request_type requested_by requester_party org_unit
source source_opportunity assigned_reviewer assigned_approver priority strategic_alignment
estimated_cost estimated_benefit currency risk_rating feasibility feasibility_notes
alternatives_considered required_resources target_start_date target_end_date`.

**Required (10)**: `title description request_type source priority strategic_alignment
estimated_cost estimated_benefit risk_rating feasibility` — the last five are required *because
they carry a model default without `blank=True`*, which is the trap in every create POST.

`clean()` → `_reject_foreign(self, cleaned, ["org_unit", "source_opportunity"])`.
**`currency` is deliberately absent** — `accounting.Currency` is GLOBAL with no `tenant` column
(L29); passing it would raise `AttributeError`.

### 2.2 `ProjectRequestDecisionForm(forms.Form)`

One field: `reason` (`CharField`, Textarea, **`required=True`**, label `"Reason"`). Shared by
`prq_reject` and `prq_return_for_information`.

### 2.3 `ProjectForm`

```python
exclude = ["tenant", "number", "request", "charter_status",
           "charter_approved_by", "charter_approved_at", "status", "created_by"]
```

**18 fields**: `name code description methodology in_scope out_of_scope objectives
success_criteria assumptions constraints risk_summary executive_sponsor project_manager org_unit
client start_date end_date charter_document`. **Required: `name`, `methodology` only.**

`clean()` → `_reject_foreign(self, cleaned, ["org_unit", "client", "charter_document"])`.

### 2.4 `ProjectStakeholderForm`

`exclude = ["tenant", "number", "created_by"]` → **12 fields**: `project party user
stakeholder_type raci_role raci_scope influence interest comms_preference comms_frequency
attending_kickoff notes`. Required: `project stakeholder_type raci_role influence interest
comms_preference comms_frequency`.

`project` is an explicit `forms.ModelChoiceField(queryset=Project.objects.none())` — the
class-level `.none()` is the fail-closed fallback; `__init__` sets
`Project.objects.filter(tenant=self.tenant)`, or `.none()` when `tenant is None`.
`clean()` → `_reject_foreign(self, cleaned, ["project", "party"])`.
The party-or-user rule and the duplicate rule come from **`ProjectStakeholder.clean()`** and land
as `__all__` (non-field) errors.

### 2.5 `ProjectKickoffForm`

```python
exclude = ["tenant", "number", "status",
           "baseline_acknowledged_at", "baseline_acknowledged_by", "completed_at", "created_by"]
```

**8 fields**: `project meeting_date location_or_link agenda_template agenda attendee_summary
onboarding_notes notes`. Required: `project`, `agenda_template`.

`project` queryset **excludes projects that already have a kickoff** (`unique_together`), and on
edit re-adds the instance's own project:
`qs.filter(pk=instance.project_id) | qs.exclude(pk__in=taken)`. Verified.
`clean()` → `_reject_foreign(self, cleaned, ["project"])`.

### 2.6 What a cross-tenant FK POST actually returns (verified)

`TenantModelForm.__init__` narrows every `ModelChoiceField` whose target model has a `tenant`
field, so the **queryset validation fires first** and the message is Django's:

```
'org_unit': ['Select a valid choice. That choice is not one of the available choices.']
```

`_reject_foreign`'s own `"That record belongs to another workspace."` is defence-in-depth for a
field the scoping missed (or a `tenant=None` form) and is **not** what a normal crafted POST
produces. **Assert that the field has an error, not the wording.** Confirmed for
`ProjectRequestForm` (`org_unit`, `requester_party`, `source_opportunity`, `assigned_approver`),
`ProjectForm` (`org_unit`, `client`, `charter_document`), `ProjectStakeholderForm`
(`project`, `party`), `ProjectKickoffForm` (`project`).

### 2.7 Numeric hardening on `ProjectRequestForm` (verified, all field-level, never a 500)

| POSTed `estimated_cost` | result |
|---|---|
| `"-5"` | `Ensure this value is greater than or equal to 0.` (the `0002` validator) |
| `"NaN"` / `"Infinity"` / `"abc"` | `Enter a number.` |
| `"999999999999999.99"` | `Ensure that there are no more than 14 digits in total.` |
| `strategic_alignment="9"` | `Ensure this value is less than or equal to 5.` |

---

## 3. URLs — all 32 names (`app_name = "projects"`)

Order inside each module is literal-before-`<int:pk>`; no route uses a converter in its first path
component, so no module shadows another.

| # | name | path | args |
|---|---|---|---|
| 1 | `overview` | `/projects/` | — |
| 2 | `prq_list` | `/projects/project-requests/` | — |
| 3 | `prq_create` | `/projects/project-requests/add/` | — |
| 4 | `prq_detail` | `/projects/project-requests/<pk>/` | pk |
| 5 | `prq_edit` | `/projects/project-requests/<pk>/edit/` | pk |
| 6 | `prq_delete` | `/projects/project-requests/<pk>/delete/` | pk |
| 7 | `prq_submit` | `/projects/project-requests/<pk>/submit/` | pk |
| 8 | `prq_approve` | `/projects/project-requests/<pk>/approve/` | pk |
| 9 | `prq_reject` | `/projects/project-requests/<pk>/reject/` | pk |
| 10 | `prq_return_for_information` | `/projects/project-requests/<pk>/return/` | pk |
| 11 | `prq_convert` | `/projects/project-requests/<pk>/convert/` | pk |
| 12 | `prj_list` | `/projects/projects/` | — |
| 13 | `prj_create` | `/projects/projects/add/` | — |
| 14 | `prj_detail` | `/projects/projects/<pk>/` | pk |
| 15 | `prj_edit` | `/projects/projects/<pk>/edit/` | pk |
| 16 | `prj_delete` | `/projects/projects/<pk>/delete/` | pk |
| 17 | `prj_submit_charter` | `/projects/projects/<pk>/submit-charter/` | pk |
| 18 | `prj_approve_charter` | `/projects/projects/<pk>/approve-charter/` | pk |
| 19 | `pst_list` | `/projects/stakeholders/` | — |
| 20 | `pst_create` | `/projects/stakeholders/add/` | — |
| 21 | `pst_detail` | `/projects/stakeholders/<pk>/` | pk |
| 22 | `pst_edit` | `/projects/stakeholders/<pk>/edit/` | pk |
| 23 | `pst_delete` | `/projects/stakeholders/<pk>/delete/` | pk |
| 24 | `pko_list` | `/projects/kickoffs/` | — |
| 25 | `pko_create` | `/projects/kickoffs/add/` | — |
| 26 | `pko_detail` | `/projects/kickoffs/<pk>/` | pk |
| 27 | `pko_edit` | `/projects/kickoffs/<pk>/edit/` | pk |
| 28 | `pko_delete` | `/projects/kickoffs/<pk>/delete/` | pk |
| 29 | `pko_schedule` | `/projects/kickoffs/<pk>/schedule/` | pk |
| 30 | `pko_mark_held` | `/projects/kickoffs/<pk>/mark-held/` | pk |
| 31 | `pko_complete` | `/projects/kickoffs/<pk>/complete/` | pk |
| 32 | `pko_mark_baseline_set` | `/projects/kickoffs/<pk>/baseline/` | pk |

All 32 verified to reverse.

---

## 4. View context keys (L7 — an unpinned name renders blank at 200)

Base contract from `apps.core.crud`: list → `object_list` + `page_obj` + `q`; detail/edit object →
`obj`; form → `form` + `is_edit`. **`per_page = 15` on every register** (the `crud_list` default;
the conftest exposes it as `PROJECTINITIATION_PAGE_SIZE`).

Verified by rendering each page as a tenant admin. (`forloop` / `option` / `widget` / `group_*`
also appear in `response.context` — those are Django's widget-render internals, not view context.)

| view | template | context keys beyond the base |
|---|---|---|
| `overview` | `projects/overview.html` | `request_count` `awaiting_decision` `approved_unconverted` `project_count` `active_projects` `stakeholder_count` `kickoff_count` — **no pagination, no filters** |
| `prq_list` | `projects/initiation/projectrequest/list.html` | `status_choices` `request_type_choices` `priority_choices` `risk_rating_choices` `feasibility_choices` `decision_choices` `org_units` |
| `prq_create` | `projects/initiation/projectrequest/form.html` | `form`, `is_edit=False` (**no `obj`**) |
| `prq_detail` | `projects/initiation/projectrequest/detail.html` | `obj` `decision_form` |
| `prq_edit` | `projects/initiation/projectrequest/form.html` | `form` `obj` `is_edit=True` |
| `prj_list` | `projects/initiation/project/list.html` | `status_choices` `charter_status_choices` `methodology_choices` `org_units` `clients` |
| `prj_create` | `projects/initiation/project/form.html` | `form`, `is_edit=False` |
| `prj_detail` | `projects/initiation/project/detail.html` | `obj` `stakeholders` (capped `[:50]`) `kickoffs` (**annotated `attendee_total`**, `.order_by("-created_at","-id")`) `source_request` (`= obj.request`) |
| `prj_edit` | `projects/initiation/project/form.html` | `form` `obj` `is_edit=True` |
| `pst_list` | `projects/initiation/projectstakeholder/list.html` | `projects` `stakeholder_type_choices` `raci_role_choices` `influence_choices` `interest_choices` |
| `pst_create` | `projects/initiation/projectstakeholder/form.html` | `form`, `is_edit=False`; GET `?project=<pk>` pre-selects |
| `pst_detail` | `projects/initiation/projectstakeholder/detail.html` | `obj` |
| `pst_edit` | `projects/initiation/projectstakeholder/form.html` | `form` `obj` `is_edit=True` |
| `pko_list` | `projects/initiation/projectkickoff/list.html` | `projects` `status_choices` `agenda_template_choices`; rows carry **`attendee_total`** |
| `pko_create` | `projects/initiation/projectkickoff/form.html` | `form`, `is_edit=False`; GET `?project=<pk>` pre-selects |
| `pko_detail` | `projects/initiation/projectkickoff/detail.html` | `obj` `attending` `activities` |
| `pko_edit` | `projects/initiation/projectkickoff/form.html` | `form` `obj` `is_edit=True` |

### `attendee_total` vs `attendee_count`

`pko_list` and `prj_detail` annotate
`Count("project__stakeholders", filter=Q(project__stakeholders__attending_kickoff=True))` as
**`attendee_total`**, and both add an explicit `.order_by("-created_at", "-id")` because an
aggregate over a multi-valued relation makes Django drop `Meta.ordering` entirely. The property
`attendee_count` still exists on the model and shadows the name — annotating over it raises
`AttributeError: can't set attribute`. Assert **both** names where both apply, and assert the
ordering did not flip.

### List filters (`crud_list` `(get_param, orm_lookup, is_int)`)

| view | search fields | filters |
|---|---|---|
| `prq_list` | `title description number` | `status`, `request_type`, `priority`, `risk_rating`, `feasibility`, `decision` (enum) · `org_unit`→`org_unit_id` (**int**) |
| `prj_list` | `name code number` | `status`, `charter_status`, `methodology` (enum) · `org_unit`→`org_unit_id`, `client`→`client_id` (**int**) |
| `pst_list` | `number raci_scope notes` | `project`→`project_id` (**int**) · `stakeholder_type`, `raci_role`, `influence`, `interest` (enum) |
| `pko_list` | `number location_or_link agenda` | `project`→`project_id` (**int**) · `status`, `agenda_template` (enum) |

Verified negative-input behaviour on `prq_list` with 16 rows (**200 every time, filter SKIPPED not
applied — the register must not silently empty**):

| query | status | rows on page |
|---|---|---|
| `?org_unit=abc` | 200 | 15 |
| `?org_unit=0` | 200 | 15 |
| `?org_unit=999999999999999999999` | 200 | 15 |
| `?status=nope` | 200 | 15 |
| `?decision=²` (U+00B2) | 200 | 15 |
| `?page=abc` | 200 | 15 (page 1) |
| `?page=2` | 200 | 1 |
| `?page=99` | 200 | 1 (last page) |

### Query budgets (`django_assert_max_num_queries`)

* `prq_list` has **NO `select_related`** — deliberate (the register renders no joined column; the
  three joins were 88 columns/row for nothing). Do not "fix" this in a test.
* `prj_list` → `select_related("client", "project_manager")` only.
* `pst_list` → `select_related("project", "party", "user")` + `annotate(influence_rank=Case(high→3,
  medium→2, default 1))` + `.order_by("-influence_rank", "id")`. **`Meta.ordering` is NOT the power
  ranking** — `"-influence"` on a CharField sorts alphabetically (medium, low, high), the exact
  inverse.
* `pko_list` → `select_related("project")` + the `attendee_total` annotation. The annotation is
  what keeps `__str__`/Attending off a per-row COUNT.

---

## 5. The 15 POST verbs — decorator + exact allowed source states

All 15 are `@require_POST`. Decorator application is **`login_required(tenant_admin_required(
require_POST(view)))`**, so the order of refusals is: anonymous → login redirect → role → method.

### Verified status codes

| actor / method | tenant-admin verb | login-only verb |
|---|---|---|
| anonymous, POST | **302** → login | **302** → login |
| tenant admin, GET | **405** | **405** |
| non-admin member, GET | **403** (role beats method) | **405** |
| non-admin member, POST | **403** | runs |
| tenant A admin, POST on a tenant B pk | **404** | **404** |
| tenant A member, POST on a tenant B pk | **403** (never reaches the 404) | **404** |
| any actor, POST with no CSRF token (`Client(enforce_csrf_checks=True)`) | **403** | **403** |

That member-vs-admin split on a cross-tenant pk is a real contract: the role gate runs *before*
`get_object_or_404`, so `test_..._security.py` must use `client_a` (an admin) to assert the 404 on
an admin-gated verb.

### The table

| # | verb | decorators | allowed SOURCE state → result | refusal |
|---|---|---|---|---|
| 1 | `prq_submit` | `login_required`, `require_POST` | `status in ("draft","needs_information")` → `submitted`, stamps `submitted_at` | `messages.info` "already {status}" → redirect `prq_detail` |
| 2 | `prq_approve` | `login_required`, **`tenant_admin_required`**, `require_POST` | `status in DECISION_STATUSES` (`submitted`/`screening`/`assessment`) → `approved` + `decision="go"` + `decided_by`/`decided_at` | `messages.error` "Only a request under review can be approved" |
| 3 | `prq_reject` | `login_required`, **`tenant_admin_required`**, `require_POST` | POST **must carry `reason`** (`ProjectRequestDecisionForm`); then `status in DECISION_STATUSES` → `rejected` + `decision="no_go"` + `rejection_reason` + stamps | no reason → "A rejection needs a stated reason."; already `rejected` → info; `converted` → "reject the project"; otherwise → "Only a request under review can be rejected" |
| 4 | `prq_return_for_information` | `login_required`, **`tenant_admin_required`**, `require_POST` | POST **must carry `reason`**; `status NOT in ("draft","converted")` and not already `needs_information` → `needs_information` + `information_requested`, **and VOIDS any decision** (`decision=""`, `decided_by=None`, `decided_at=None`, `rejection_reason=""`, the voided values written into the audit `changes`) | no reason → "Say what information is needed."; already → info; draft/converted → error |
| 5 | `prq_convert` | `login_required`, **`tenant_admin_required`**, `require_POST` | `status == "approved"` **and** `converted_project_id` is None → `convert_to_project(user)`; redirects to **`projects:prj_detail`** of the new project | not approved → "Only an approved request can be converted to a project."; already/CAS-loser → info "already been converted" |
| 6 | `prq_delete` | `login_required`, `require_POST` | any → `crud_delete`, redirect `prq_list` | — |
| 7 | `prj_submit_charter` | `login_required`, `require_POST` | `status NOT in ("completed","cancelled")` **and** `charter_status in ("draft","rejected")` → `submitted` | terminal status → error; else info "already submitted or approved" |
| 8 | `prj_approve_charter` | `login_required`, **`tenant_admin_required`**, `require_POST` | `status NOT in ("completed","cancelled")` **and** `charter_status == "submitted"` → `approved` + `charter_approved_by`/`_at`, **and `status` draft → `chartered`** | terminal → error; already `approved` → info (must NOT re-stamp); else "Submit the charter before approving it." |
| 9 | `prj_delete` | `login_required`, `require_POST` | any → deletes, and **REOPENS the source request** (`status="approved"`, `converted_project=None`) inside `transaction.atomic()` when `obj.request.status == "converted"` | — |
| 10 | `pst_delete` | `login_required`, `require_POST` | any → `crud_delete`, redirect `pst_list` | — |
| 11 | `pko_schedule` | `login_required`, `require_POST` **(login-only on purpose — it books a meeting, it does not advance the project)** | `status == "planned"` **and `meeting_date` is set** → `scheduled` | not planned → info; no date → "Set a meeting date before scheduling the kickoff." |
| 12 | `pko_mark_held` | `login_required`, **`tenant_admin_required`**, `require_POST` | **`status == "scheduled"` only** (`planned` is deliberately NOT allowed) → `held`, and project `draft`/`chartered` → `kickoff` | held/completed → info; else "Schedule the kickoff before marking it held." |
| 13 | `pko_complete` | `login_required`, **`tenant_admin_required`**, `require_POST` | `status == "held"` **AND `project.charter_status == "approved"`** → `completed` + `completed_at`, and project `draft`/`chartered`/`kickoff` → `active` | completed → info; not held → "Hold the kickoff before completing it."; unapproved charter → "Approve the charter before completing the kickoff…" — **the L35 case: without it a member routes around `prj_approve_charter`'s admin gate** |
| 14 | `pko_mark_baseline_set` | `login_required`, **`tenant_admin_required`**, `require_POST` | `baseline_acknowledged_at` is None **and `status NOT in ("planned","scheduled")`** → stamps `baseline_acknowledged_at`/`_by` | already stamped → info (**no re-stamp**); planned/scheduled → "Hold the kickoff before acknowledging the baseline." |
| 15 | `pko_delete` | `login_required`, `require_POST` | any → `crud_delete`, redirect `pko_list` | — |

**Eight verbs are `@tenant_admin_required`**: `prq_approve`, `prq_reject`,
`prq_return_for_information`, `prq_convert`, `prj_approve_charter`, `pko_mark_held`,
`pko_complete`, `pko_mark_baseline_set`.
**Seven are login-only**: `prq_submit`, `prq_delete`, `prj_submit_charter`, `prj_delete`,
`pst_delete`, `pko_schedule`, `pko_delete`.

Every refusal is a `messages` call + `redirect` to the object's detail page — **never a 500 and
never a silent no-op**. Assert the redirect *and* that the row is unchanged.

### Audit actions (`core.AuditLog.action` is `varchar(10)` — every string ≤ 10 chars)

`create` `update` `delete` `submit` `approve` `reject` `convert` `return` `schedule` `held`
`complete` `baseline`. The human verb goes in `changes["verb"]`, alongside `from`/`to` captured
**before** the mutation (`prq_*` verbs log `previous = obj.status`, not a hard-coded `"draft"`).
`prj_submit_charter` logs action `update` with `verb="submit_charter"`;
`prj_approve_charter` logs `approve` with `verb="approve_charter"`;
`prj_delete`'s reopen logs `update` with `verb="reopen_on_project_delete"`.

---

## 6. Edit locks and the tenant-less guard

* **`prq_edit`**: refuses when `obj.decided_at` **or** `obj.status == "converted"` →
  `messages.error` + **302 to `projects:prq_detail`** (verified). The lock follows the *evidence
  stamp*, not a status list, so `prq_return_for_information` (which clears the stamps) reopens the
  row for editing. That is the reopen path.
* **`prj_edit`**: refuses when `obj.charter_status == "approved"` → `messages.error` + **302 to
  `projects:prj_detail`** (verified).
* `pst_edit` / `pko_edit` have **no lock** — straight `crud_edit`.
* All four create views (`prq_create`, `prj_create`, `pst_create`, `pko_create`) guard
  `request.tenant is None` on their **first line** and `redirect("dashboard:home")` with an error
  message — before the form is built, because `TenantModelForm` only scopes its FK dropdowns when
  `tenant is not None`.
* Cross-tenant `detail` / `edit` / `delete` on all four models → **404** (verified for a tenant A
  admin against every tenant B fixture).

---

## 7. Fixtures the four test modules use (`apps/projects/tests/conftest.py`)

### From the ROOT conftest (`C:\xampp\htdocs\NavERP\conftest.py`) — reuse, never redefine

`tenant_a` (Acme/`acme`) · `tenant_b` (Globex/`globex`) · `admin_user` (tenant A,
`is_tenant_admin=True`) · `member_user` (tenant A, `is_tenant_admin=False`) · `admin_b` (tenant B
admin) · `client_a` · `client_b` · `member_client`.

### Module-level factories — import them directly

```python
from apps.projects.tests.conftest import (
    PROJECTINITIATION_PAGE_SIZE,           # 15
    _projectinitiation_today,              # timezone.localdate()  (L16)
    _projectinitiation_request,            # (tenant, **overrides) -> ProjectRequest
    _projectinitiation_project,            # (tenant, **overrides) -> Project
    _projectinitiation_stakeholder,        # (project, party=None, user=None, **overrides)
    _projectinitiation_kickoff,            # (project, **overrides)
    _projectinitiation_activity,           # (project, **overrides) -> core.Activity GFK'd
    _projectinitiation_fill_requests,      # (tenant, count, **overrides) -> list
    _projectinitiation_fill_projects,      # (tenant, count, **overrides) -> list
    _projectinitiation_fill_stakeholders,  # (project, count, **overrides) -> list
    _projectinitiation_fill_kickoffs,      # (tenant, count, **overrides) -> list (+ one project each)
)
```

Every factory constructs and calls `.save()` — that is where `TenantNumbered` mints `number`.
**Never `bulk_create`** (it skips `save()` and ships empty numbers).
`_projectinitiation_stakeholder` auto-mints a `core.Party` when given neither `party` nor `user`.
`_projectinitiation_fill_kickoffs` also creates one project per kickoff, because
`(tenant, project)` is unique.

### Fixtures

Core spine / actors:
`projectinitiation_org_unit_a` · `projectinitiation_org_unit_b` · `projectinitiation_party_a`
(organization) · `projectinitiation_person_a` (person) · `projectinitiation_party_b` ·
`projectinitiation_document_a` · `projectinitiation_document_b` · `projectinitiation_currency`
(USD, **global — no tenant**) · `projectinitiation_opportunity_a` ·
`projectinitiation_opportunity_b` · `projectinitiation_member_b` (non-admin, tenant B) ·
`projectinitiation_tenantless_user` / `projectinitiation_tenantless_client` (`request.tenant is
None`) · `projectinitiation_anon_client` · `projectinitiation_csrf_client`
(`Client(enforce_csrf_checks=True)`, logged in as `admin_user`).

`ProjectRequest`:
`projectinitiation_request_draft` · `_submitted` · `_screening` · `_needs_information` ·
`_approved` (decided, convertible, **edit-locked**) · `_rejected` · `_deferred` · `_converted`
(runs the real `convert_to_project()`; depends on `_approved` and is the SAME row) · `_b`
(tenant B).

`Project`:
`projectinitiation_project_draft` (charter draft; hosts `stakeholder_*` and `kickoff_planned`) ·
`_charter_submitted` · `_charter_approved` (**edit-locked**; the only shape `pko_complete`
accepts) · `_charter_rejected` (the reserved choice) · `_cancelled` (terminal) · `_overdue`
(`end_date` 5 days past, `status="active"` → `is_overdue` True) · `_b`.

`ProjectStakeholder`:
`projectinitiation_stakeholder_a` (high/high → `manage_closely`, `attending_kickoff=True`) ·
`_monitor` (medium/low → `monitor`) · `_user_only` (`user` set, `party` NULL) · `_b`.

`ProjectKickoff` — **each builds its own project** (`(tenant, project)` is unique):
`projectinitiation_kickoff_planned` (planned, dated; on `project_draft`) · `_undated`
(`meeting_date=None`) · `_scheduled` · `_held` (project charter **draft** → `pko_complete` must
refuse) · `_ready_to_complete` (held + charter approved → `pko_complete` succeeds) · `_completed`
· `_baselined` (already acknowledged) · `_with_attendees` (3 stakeholders, **exactly 2 attending
→ `attendee_total == attendee_count == 2`**) · `_b`.

Plus `projectinitiation_activity_a` (a `core.Activity` GFK'd to `project_draft`).

---

## 8. Reminders that have bitten this repo

* **L16** — `USE_TZ=True`. Derive dates from `timezone.localdate()` / `timezone.now()`, the same
  basis `Project.is_overdue` uses. `datetime.date.today()` flakes around local midnight.
* **L11** — junk FK filter params must 200 with the filter skipped, never 500 and never an empty
  register.
* **L9** — page past the end and page 2 with `PAGE_SIZE + 1` rows.
* **L35** — an absent prerequisite must be REJECTED, not fall through to approval:
  `pko_complete` on an unapproved charter, `prq_approve`/`prq_reject` on a never-submitted draft,
  `pko_mark_held` on a `planned` kickoff, `pko_mark_baseline_set` on a `scheduled` one.
* **L20/L22** — `rejection_reason`, `information_requested`, `decision_notes` must NOT be in
  `ProjectRequestForm`; `status`/`decision`/`charter_status`/the `*_at`/`*_by` stamps/`number`/
  `tenant`/`created_by`/`converted_project`/`request` must not be form fields anywhere.
* **L47** — the closing run is unfiltered. **L49** — and keeps migrations on.
