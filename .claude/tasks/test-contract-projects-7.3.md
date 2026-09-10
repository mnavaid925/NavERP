# Test contract — Projects 7.3 Resource Management (`apps/projects`)

**Phase 6, step 1.** Everything below is pinned from the **as-built source** (`models/ forms/ views/
urls` under `ResourceManagement/`, after the review pass `.claude/tasks/review-projects-7.3.md`),
not from `.claude/tasks/contract-projects-7.3.md` (the *build* contract). Where the two disagree,
**this file wins** — it was read out of the code. As-built deltas vs the build contract are called
out inline (§5: the `ral_commit` soft-placeholder refusal, the `ral_substitute` in-transaction
re-check, `rte_approve_week`'s real-ISO-week check; §4: `actuals_year`/`actuals_week` context keys,
the `ral_create` `?resource=` initial).

The four files, in build order: `test_resource_models.py` → `test_resource_forms.py` →
`test_resource_views.py` → `test_resource_security.py`. Steps 2–5 write their tests against these
names — a wrong name here becomes four wrong test files.

---

## 0. How the suite runs

| | |
|---|---|
| Settings | `config.settings_test` (SQLite `:memory:`) via `pytest.ini`; add `--nomigrations` while iterating, never for the final run |
| Command | `venv\Scripts\python.exe -m pytest apps/projects -q` |
| App mount | `path("projects/", include("apps.projects.urls"))` → every route below is under `/projects/` |
| Namespace | `app_name = "projects"` → `reverse("projects:<name>")` |
| Pagination | every 7.3 register uses `crud_list`'s default `per_page=15`, exposed as **`RESOURCE_PAGE_SIZE = 15`** in `apps/projects/tests/conftest.py` |

### Naming rule (mandatory — same as 7.1/7.2)

* test functions: `test_resource_*`
* module-level helpers (incl. constants): `_resource_*` / `_RESOURCE_*`
* conftest fixtures: `resource_*` (root-conftest names excepted)
* 7.1's lane uses `projectinitiation_*`, 7.2's `planning_*` — never collide, never import another
  lane's *fixture*; DO import 7.1's factory functions where they fit (see §7).

### conftest ownership

`apps/projects/tests/conftest.py` is owned by step 1 **alone**. Steps 2–5 must not edit it. Test
modules pull the factories in directly (peer pattern):

```python
from apps.projects.tests.conftest import (
    RESOURCE_PAGE_SIZE,
    _resource_today, _resource_profile, _resource_allocation, _resource_entry,
    _resource_fill_profiles, _resource_fill_allocations, _resource_fill_entries,
)
```

---

## 1. Models — `apps/projects/models/ResourceManagement/`

All three inherit `TenantNumbered` → `TenantOwned`: `tenant` (FK `core.Tenant`,
`related_name="+"`), `created_at`, `updated_at`, and `number` minted in `save()` via
`apps.core.utils.next_number`. **Every factory/fill path must construct + `.save()` — never
`bulk_create`** (numbering lives in `save()`). Also exported from `apps.projects.models`:
`q2` (quantize 2dp, clamp to `±MAX_Q2 = Decimal("9999999999.99")`, `q2(None) == 0.00`), `ZERO`.

Number prefixes are per tenant, per model: tenant A and tenant B both read `RSP-00001` with no
collision; a second `save()` never renumbers. **Two `ResourceAllocation` models coexist** —
`crm.ResourceAllocation` [RA-] is the 1.8 stand-in; always import from `apps.projects.models`,
never assert a number is globally unique.

### 1.1 `ResourceProfile` — `RSP-`, one bookable person

* `Meta.ordering = ["employee__party__name", "party__name", "id"]` (people-list order;
  NULL-`employee` rows sort first on SQLite/MariaDB ASC — **do not pin cross-DB NULL position**,
  pin order only within same-kind rows); `unique_together = ("tenant", "number")`.
* Indexes (exact names): `rsp_tnt_rtype_idx` `(tenant, resource_type)` · `rsp_tnt_status_idx`
  `(tenant, status)` · `rsp_tnt_employee_idx` `(tenant, employee)` · `rsp_tnt_party_idx`
  `(tenant, party)`.
* `__str__` → `f"{number} · {name}"` (middle dot U+00B7).
* FKs: `employee` → `hrm.EmployeeProfile` SET_NULL null+blank `related_name="resource_profiles"`;
  `party` → `core.Party` SET_NULL null+blank `related_name="resource_profiles"`; `org_unit` →
  `core.OrgUnit` SET_NULL null+blank `related_name="resource_profiles"`.
* Fields: `resource_type` CharField(12) default `internal`; `default_role` CharField(80)
  (**required**); `skill_summary` CharField(255) blank; `weekly_capacity_hours` DecimalField(6,2)
  default `Decimal("40.00")` MinValueValidator(0); `utilization_target_pct` PositiveSmallInteger
  default 80, validators 1..100; `available_from` / `available_to` DateField null+blank; `status`
  CharField(8) default `active` (a lens toggle, ON the form); `notes` TextField blank.
* `name` is a **property** (never a column): `employee.party.name` when `employee_id` set → else
  `party.name` when `party_id` set → else `self.number`.
* `clean()` (runs on `full_clean()`, NOT on `save()`):
  * exactly one of `employee`/`party` → **non-field** error
    `"Choose an employee or an external party — exactly one of the two."`
  * duplicate pool row: `employee_id` set and another row with same `(tenant, employee)` exists
    (excluding `self.pk`) → error **keyed `"employee"`**: "This employee is already in this
    tenant's resource pool." (deliberately a clean-guard, not a conditional unique constraint).
* CHOICES (assert exact value + label): `RESOURCE_TYPE_CHOICES` = `internal` (Internal),
  `contractor` (Contractor), `freelancer` (Freelancer), `consultant` (Consultant);
  `STATUS_CHOICES` = `active` (Active), `inactive` (Inactive).

### 1.2 `ResourceAllocation` — `RAL-`, one booking

* `Meta.ordering = ["-start_date", "-id"]`; `unique_together = ("tenant", "number")`.
* Indexes: `ral_tnt_resource_idx` `(tenant, resource)` · `ral_tnt_project_idx` `(tenant, project)`
  · `ral_tnt_request_idx` `(tenant, project_request)` · `ral_tnt_status_idx` `(tenant,
  booking_status)` · `ral_tnt_start_idx` `(tenant, start_date)`.
* `__str__` → `f"{number} · {role_name}"`.
* FKs: `project` → `projects.Project` CASCADE null+blank `related_name="allocations"`;
  `project_request` → `projects.ProjectRequest` SET_NULL null+blank `related_name="allocations"`;
  `project_task` → `projects.ProjectTask` SET_NULL null+blank `related_name="allocations"`;
  `resource` → `projects.ResourceProfile` SET_NULL null+blank `related_name="allocations"`
  (**NULL = placeholder**); `substitute_of` → `"self"` SET_NULL null+blank
  `related_name="substituted_by"`; `requested_by` → AUTH_USER_MODEL SET_NULL null+blank
  **editable=False** `related_name="requested_allocations"` (stamped by `ral_create` only).
* Fields: `role_name` CharField(80) (**required**); `skill_requirements` CharField(255) blank;
  `allocation_unit` CharField(14) default `hours_per_week`; `hours_per_week` DecimalField(6,2)
  null+blank Min(0); `pct_capacity` PositiveSmallInteger null+blank validators 1..100;
  `total_hours` DecimalField(8,2) null+blank Min(0); `start_date` DateField **required**;
  `end_date` DateField null+blank (**null = ongoing**); `booking_status` CharField(12) default
  `requested` (verb-driven, never on the form); `notes` TextField blank.
* `is_live` property: `booking_status in ("soft", "firm")` AND `start_date <= timezone.localdate()`
  AND (`end_date is None or end_date >= today`). A **placeholder can be live** (a soft placeholder
  whose window covers today is live) — test that shape, it is load-bearing for the register lens.
* `planned_hours(win_start, win_end)` — pin the math exactly (all expectations computed in tests
  from these formulas, never hardcoded):
  * `booking_status in ("cancelled", "released")` → `ZERO` (a released row's successor already
    carries the demand; `completed` rows do NOT short-circuit here — the *board queries* exclude
    them, this method does not).
  * `a_end = end_date or win_end`; overlap `[max(start, win_start), min(a_end, win_end)]`;
    empty overlap → `ZERO`; `days = (ov_end - ov_start).days + 1`.
  * `hours_per_week` → `q2(hours_per_week * days / 7)`.
  * `pct_capacity` → `ZERO` when `resource_id is None` (a % of an unknown person is unknowable);
    else `q2(pct / 100 * resource.weekly_capacity_hours * days / 7)`.
  * `total_hours` → spread over the booking's OWN window: `window_days = (a_end -
    start_date).days + 1` (`<= 0` → `ZERO`), then `q2(total_hours * days / window_days)`.
  * Worked example to assert: 16h/wk booking whose window fully covers a 7-day window → 16.00;
    50% of a 24.00h resource over a full week → 12.00; 40 total hours over a 15-day own window
    fully inside the query window → 40.00.
* `clean()` (surfaces on the FORM too, via `_post_clean`):
  * both `project` and `project_request` null → **non-field** "Attach the allocation to a project
    or a project request."
  * `end_date < start_date` → keyed `"end_date"`: "End date cannot precede start date."
  * exactly one magnitude matching `allocation_unit`: own field None → keyed
    `{"hours_per_week"|"pct_capacity"|"total_hours"}`: "Required when the allocation unit is
    `<get_allocation_unit_display>`."; either other field set → keyed that field: "Leave blank —
    the allocation unit is `<label>`." Labels: `Hours per Week` / `% of Capacity` / `Total Hours`.
* CHOICES: `ALLOCATION_UNIT_CHOICES` = `hours_per_week` (Hours per Week), `pct_capacity`
  (% of Capacity), `total_hours` (Total Hours); `BOOKING_STATUS_CHOICES` = `requested` (Requested),
  `soft` (Soft Booked), `firm` (Firm Booked), `completed` (Completed), `cancelled` (Cancelled),
  `released` (Released).

### 1.3 `ResourceTimeEntry` — `RTE-`, one day's project time

* `Meta.ordering = ["resource_id", "-entry_date", "-id"]` (keeps person-week blocks contiguous for
  the template's regroup); `unique_together = ("tenant", "number")`.
* Indexes: `rte_tnt_res_date_idx` `(tenant, resource, entry_date)` · `rte_tnt_prj_date_idx`
  `(tenant, project, entry_date)` · `rte_tnt_status_idx` `(tenant, status)`.
* `__str__` → `f"{number} · {hours}h on {entry_date:%Y-%m-%d}"` — **no FK deref**.
* FKs: `resource` → `projects.ResourceProfile` **CASCADE** `related_name="time_entries"` (an entry
  dies with its person); `project` → `projects.Project` SET_NULL null+blank
  `related_name="time_entries"` (non-project time is loggable); `project_task` →
  `projects.ProjectTask` SET_NULL null+blank `related_name="time_entries"`; `approved_by` →
  AUTH_USER_MODEL SET_NULL null+blank **editable=False** `related_name="approved_time_entries"`.
* Fields: `entry_date` DateField **required**; `hours` DecimalField(5,2)
  MinValueValidator(`Decimal("0.01")`) — 0.01 is the smallest loggable unit; `task_description`
  CharField(255) blank; `status` CharField(12) default `draft` (verb-driven, never on the form);
  `submitted_at` / `approved_at` DateTimeField null+blank **editable=False**; `decision_note`
  TextField blank; `notes` TextField blank.
* Properties (all derived from `entry_date.isocalendar()`): `iso_year` (int), `iso_week` (int),
  `week_key` → `f"{resource_id}:{iso_year}-W{iso_week:02d}"` — the regroup key (one key = one
  person-week; two people in the same week never share a group).
* NO model `clean()` beyond the base — `hours > 0` is the validator; status moves only through the
  verbs. Guard semantics live at the VIEW layer (§5/§6): the approval stamps are written exactly
  once by the verbs and never rewound by edit (the form excludes them); approved/rejected rows
  refuse edit and delete.
* CHOICES: `STATUS_CHOICES` = `draft` (Draft), `submitted` (Submitted), `approved` (Approved),
  `rejected` (Rejected).

---

## 2. Forms — `apps/projects/forms/ResourceManagement/`

Import through the package root: `from apps.projects.forms import ResourceProfileForm,
ResourceAllocationForm, ResourceTimeEntryForm`. Every form is
`class X(TenantUniqueMixin, TenantModelForm)` — **mixin first** (tenant stamped before
`full_clean()`). Constructor: `Form(data=None, *, tenant=...)`.

**Cross-tenant FK POSTs:** `TenantModelForm` narrows every ModelChoiceField whose target has a
`tenant` column, so a crafted foreign pk fails queryset validation first — the message is Django's
`Select a valid choice…`, not `_reject_foreign`'s wording. **Assert that the field HAS an error,
never the wording.** (`_reject_foreign` is defence-in-depth for paths the scoping misses.)

### 2.1 `ResourceProfileForm` — fields (exact 12, in order)

`employee party resource_type default_role org_unit skill_summary weekly_capacity_hours
utilization_target_pct available_from available_to status notes`. `clean()` → `_reject_foreign`
on `["employee", "party", "org_unit"]`.

**Required (5)**: `resource_type default_role weekly_capacity_hours utilization_target_pct status`
— model defaults do NOT make a field optional when `blank=False` (the 7.1 trap). `employee` and
`party` are optional at field level; the exactly-one-of rule surfaces as a **non-field** error and
the pool-duplicate rule as an `"employee"` error (model clean, §1.1).

### 2.2 `ResourceAllocationForm` — fields (exact 13, in order)

`project project_request project_task resource role_name skill_requirements allocation_unit
hours_per_week pct_capacity total_hours start_date end_date notes`. **Deliberately NOT on the
form**: `tenant`, `number`, `booking_status` + `substitute_of` (verb-driven), `requested_by`
(provenance) — a smuggled `booking_status=firm` in a POST must be ignored (L20 shape: assert the
row's status is unchanged after an edit POST carrying it). `clean()` → `_reject_foreign` on
`["project", "project_request", "project_task", "resource"]`. The three model guards (§1.2)
surface through the form: attach → non-field; window → `"end_date"`; magnitude rules → keyed
magnitude field.

**Required (3)**: `role_name`, `allocation_unit`, `start_date`. As-built extras to be aware of
(not behaviour contracts, do not assert their internals): `Meta.help_texts` on
`allocation_unit`, and an `__init__` that `select_related`s the `resource` dropdown queryset.

### 2.3 `ResourceTimeEntryForm` — fields (exact 7, in order)

`resource project project_task entry_date hours task_description notes`. **Deliberately NOT on
the form**: `tenant`, `number`, `status`, `submitted_at`, `approved_at`, `approved_by`,
`decision_note` — the form can never rewind an approval because it cannot touch the stamps at all
(assert a POST carrying `status=approved` leaves the row's status unchanged). `clean()` →
`_reject_foreign` on `["resource", "project", "project_task"]`. **Required (3)**: `resource`,
`entry_date`, `hours`.

### 2.4 Numeric hardening (field-level, never a 500)

| POSTed value | result |
|---|---|
| `hours="0"` / `"-1"` | `Ensure this value is greater than or equal to 0.01.` |
| `hours="NaN"` / `"Infinity"` / `"abc"` | `Enter a number.` |
| `pct_capacity="0"` / `"101"` | `greater than or equal to 1` / `less than or equal to 100` |
| `utilization_target_pct="0"` / `"101"` | same 1..100 validators |
| `weekly_capacity_hours="123456"` | `Ensure that there are no more than 6 digits in total.` |

---

## 3. URLs — all 25 names (`app_name = "projects"`)

Route order inside each module is literal-before-`<int:pk>`; `time-entries/week/<int:resource>/<int:year>/w<int:week>/approve/` sits before the `<int:pk>/` routes.

| # | name | path | # | name | path |
|---|---|---|---|---|---|
| 1 | `rsp_list` | `/projects/resource-profiles/` | 14 | `ral_commit` | `/projects/allocations/<pk>/commit/` |
| 2 | `rsp_create` | `/projects/resource-profiles/add/` | 15 | `ral_complete` | `/projects/allocations/<pk>/complete/` |
| 3 | `rsp_detail` | `/projects/resource-profiles/<pk>/` | 16 | `ral_cancel` | `/projects/allocations/<pk>/cancel/` |
| 4 | `rsp_edit` | `/projects/resource-profiles/<pk>/edit/` | 17 | `rte_list` | `/projects/time-entries/` |
| 5 | `rsp_delete` | `/projects/resource-profiles/<pk>/delete/` | 18 | `rte_create` | `/projects/time-entries/add/` |
| 6 | `ral_list` | `/projects/allocations/` | 19 | `rte_approve_week` | `/projects/time-entries/week/<resource>/<year>/w<week>/approve/` |
| 7 | `ral_create` | `/projects/allocations/add/` | 20 | `rte_detail` | `/projects/time-entries/<pk>/` |
| 8 | `ral_detail` | `/projects/allocations/<pk>/` | 21 | `rte_edit` | `/projects/time-entries/<pk>/edit/` |
| 9 | `ral_edit` | `/projects/allocations/<pk>/edit/` | 22 | `rte_delete` | `/projects/time-entries/<pk>/delete/` |
| 10 | `ral_delete` | `/projects/allocations/<pk>/delete/` | 23 | `rte_submit` | `/projects/time-entries/<pk>/submit/` |
| 11 | `ral_assign` | `/projects/allocations/<pk>/assign/` | 24 | `rte_approve` | `/projects/time-entries/<pk>/approve/` |
| 12 | `ral_substitute` | `/projects/allocations/<pk>/substitute/` | 25 | `rte_reject` | `/projects/time-entries/<pk>/reject/` |
| 13 | — | — | + | `capacity_demand` | `/projects/capacity-demand/` |

Flat list for reverse() checks (authoritative): `rsp_list, rsp_create, rsp_detail, rsp_edit,
rsp_delete · ral_list, ral_create, ral_detail, ral_edit, ral_delete, ral_assign, ral_substitute,
ral_commit, ral_complete, ral_cancel · rte_list, rte_create, rte_approve_week, rte_detail,
rte_edit, rte_delete, rte_submit, rte_approve, rte_reject · capacity_demand` — **25 names**.

---

## 4. Views — context keys, filters, computed sections

Base contract from `apps.core.crud`: list → `object_list` + `page_obj` + `q`; detail/edit object →
`obj`; form → `form` + `is_edit`.

| view | template | context keys beyond the base |
|---|---|---|
| `rsp_list` | `projects/resource/resourceprofile/list.html` | `resource_type_choices` `status_choices` `org_units` |
| `rsp_create` | `.../resourceprofile/form.html` | `form`, `is_edit=False` (**no `obj`**) |
| `rsp_detail` | `.../resourceprofile/detail.html` | `obj` |
| `rsp_edit` | `.../resourceprofile/form.html` | `form` `obj` `is_edit=True` |
| `ral_list` | `projects/resource/resourceallocation/list.html` | `booking_status_choices` `projects` `project_requests` `resources` |
| `ral_create` | `.../resourceallocation/form.html` | `form`, `is_edit=False`; GET `?project=` **and `?resource=`** prefill initial (as-built — the build contract pinned `?project=` only) |
| `ral_detail` | `.../resourceallocation/detail.html` | `obj` `resources` (the assign/substitute dropdown queryset) `successor` (`obj.substituted_by.order_by("pk").first()`, may be None) |
| `ral_edit` | `.../resourceallocation/form.html` | `form` `obj` `is_edit=True` |
| `rte_list` | `projects/resource/resourcetimeentry/list.html` | `status_choices` `resources` `projects` `actuals_rows` **`actuals_year` `actuals_week`** (as-built additions — the resolved actuals window) |
| `rte_create` | `.../resourcetimeentry/form.html` | `form`, `is_edit=False`; GET `?resource=` prefill |
| `rte_detail` | `.../resourcetimeentry/detail.html` | `obj` |
| `capacity_demand` | `projects/resource/capacity_demand.html` | `weeks` `week_windows` `capacity_rows` `over_count` `demand_rows` `gap_count` |

`select_related` as built (do not "fix" N+1s these already cover): `rsp_list`/`rsp_detail`
`employee__party, party, org_unit`; `ral_list` `project, project_request, project_task,
resource__employee__party, resource__party`; `ral_detail` adds `substitute_of, requested_by`;
`rte_list`/`rte_detail` `resource__employee__party, resource__party, project, project_task`
(detail adds `approved_by`).

### List filters (`crud_list` `(get_param, orm_lookup, is_int)`, parsed before pagination)

| view | search fields (`?q=` icontains OR) | enum filters (junk SKIPPED, register never emptied) | int filters (junk/0/over-range skipped for pk lookups; valid-but-foreign pk FILTERS → empty register) |
|---|---|---|---|
| `rsp_list` | `employee__party__name party__name number default_role skill_summary` | `resource_type` `status` | `org_unit` → `org_unit_id` |
| `ral_list` | `role_name number skill_requirements project__name` | `booking_status` | `project` → `project_id`, `project_request` → `project_request_id`, `resource` → `resource_id` |
| `rte_list` | `number task_description resource__employee__party__name resource__party__name project__name` | `status` | `resource` → `resource_id`, `project` → `project_id`, `year` → `entry_date__iso_year`, `week` → `entry_date__week` |

`rte_list` int filters `year`/`week` are NOT pk lookups, so `?week=0` FILTERS on 0 → legitimately
empty register (200). **`?year=0` / `?year=9999` are special-cased in the view**: the year is
parsed with `as_db_int` before `crud_list` and anything outside `1..9998` empties the queryset via
`qs.none()` (Django's year-lookup bounds would otherwise RAISE inside `.count()`) AND the
actuals-window falls back to the current ISO week (`actuals_year`/`actuals_week` = current).
`?year=abc` is skipped as junk by both the view and `crud_list`.

### `ral_list` hand-parsed lenses (before `crud_list`)

`?placeholder=True` → `resource__isnull=True`; `?placeholder=False` → `resource__isnull=False`;
`?is_live=True` → soft/firm AND `start_date <= today` AND (`end_date__isnull=True` OR
`end_date >= today`); `?is_live=False` → the exact NEGATION of that Q. Any other value (junk,
`0`, `1`) is IGNORED — the lens never fires. Remember a soft **placeholder** with a current
window is `is_live=True` (§1.2).

### `rte_list` weekly lens + `actuals_rows`

The page is `crud_list`'s flat paginated rows; grouping is template-side
(`{% regroup object_list by week_key %}`) — a person-week may straddle pages (accepted; do not
test regroup continuity, test the `week_key`/`iso_week`/`iso_year` properties on the model).

`actuals_rows` — computed in the view over the window `?year=`+`?week=` when both parse (else the
current ISO week), ignoring `?q=`/`?status=`: per (resource, project) that logged **approved**
time in the window — `actual_hours` = SUM(hours); `planned_hours` = Σ `planned_hours(win_start,
win_end)` over LIVE (soft/firm) allocations of the SAME resource+project pair (a pair with no
approved time renders NO row, even if planned); `variance = actual − planned`; ordered by
variance DESC. Each row is a dict: `resource` (ResourceProfile), `project` (may be None → renders
"Non-project time"), `actual_hours`, `planned_hours`, `variance` (Decimals, quantized 0.01 —
"0h" never renders next to "2.00h").

### `capacity_demand` (computed board, no model)

* GET-only in spirit: **no method decorator** — a POST renders the same board (there is no verb to
  405). Do not assert a 405 here; assert GET behaviour only.
* `?weeks=<int>` horizon length: `as_db_int` then clamp 4..13, default 8. `?weeks=abc` / absent /
  `?weeks=0` (falsy → default) → 8; `?weeks=2` → 4; `?weeks=99` → 13. Windows start at the current
  ISO Monday; `week_windows` entries carry `year`, `week`, `start`, `end`, `label` (`"W37 · Sep 7"`).
* `capacity_rows`: ACTIVE profiles only, each decorated with `.cells` = one dict per window
  `{"planned": Decimal, "over": bool}` where planned = Σ `planned_hours` over that resource's
  **soft/firm** allocations (requested placeholders are demand, not supply; released counts zero
  via `planned_hours`). `over = planned > weekly_capacity_hours`; `over_count` = over cells total.
* `demand_rows`: `booking_status in ("requested", "soft")` overlapping the horizon — project-linked
  first (ordered `start_date`, then `-id`), then request-linked. Each decorated with
  `.demand_label` (project name / request title / `"—"`), `.demand_url_name`
  (`projects:prj_detail` / `projects:prq_detail` / None), `.demand_url_pk`, `.demand_hours`
  (Σ planned over the horizon), `.is_gap` (`resource_id is None`). `gap_count` = `is_gap` rows.
* **Pin shapes and deltas, never absolute board numbers**: compute every expectation in the test
  from the pulled fixture rows via the same `planned_hours` math. The demo seeder's figures
  (post-M4: its RAL-00001 is 48h/wk against a 40h capacity so `over_count >= 1` on the DEMO
  tenant) are seed data — tests never run `seed_projects` and never assert its numbers.

---

## 5. The 9 POST verbs — gating matrix, transitions, refusals, audit

All 9 are `@require_POST`. Decorator nesting is `login_required(tenant_admin_required(
require_POST(view)))` for the admin-gated ones and `login_required(require_POST(view))` for the
member-level ones — the same shape 7.1 verified by running, so the status table carries over (the
7.3 security lane re-proves it):

| actor / method | admin-gated verb (`ral_assign`, `ral_substitute`, `rte_approve`, `rte_reject`, `rte_approve_week`) | login-only verb (`ral_commit`, `ral_complete`, `ral_cancel`, `rte_submit`) |
|---|---|---|
| anonymous, POST | **302** → login | **302** → login |
| tenant admin, GET | **405** | **405** |
| non-admin member, GET | **403** (role beats method) | **405** |
| non-admin member, POST | **403** | runs |
| tenant A admin, POST on a tenant B pk | **404** | **404** |
| tenant A member, POST on a tenant B pk | **403** (never reaches the 404) | **404** |
| any actor, POST with no CSRF token | **403** | **403** |

That member-vs-admin split on a cross-tenant pk is a real contract: the role gate runs before
`get_object_or_404`, so IDOR-404 assertions must use `client_a` (an admin).

### Transitions and refusals (every refusal = `messages.*` + 302 to the object's detail, row unchanged)

| verb | gating | allowed from → to | refusal / note | audit action |
|---|---|---|---|---|
| `ral_assign` | admin | placeholder (`resource_id is None`) with status `requested`/`soft` → sets `resource` from POST `resource` (tenant-resolved via `as_db_int`); `requested` additionally → `soft` | already named: "That allocation already names a resource — use Substitute to replace it." · status not in (requested, soft): `f"A {display.lower()} allocation cannot be staffed."` · no/bad POST resource: "Choose a resource to assign." | `assign` |
| `ral_substitute` | admin | named, `soft`/`firm` → inside `transaction.atomic()`: current → `released`; successor row created (copies project/request/task/role/skills/unit/magnitudes/window/notes + `requested_by`; `resource` = POST `resource`; `booking_status` = ORIGINAL status; `substitute_of` = current); redirects to the SUCCESSOR's detail | placeholder: "That allocation is a placeholder — assign a resource to it instead." · status not in (soft, firm) OR a successor already exists (as-built in-transaction re-check, `select_for_update`): `f"Only a soft or firm booking can be substituted — this one is {display.lower()}."` · replacement == current resource: info "That is already the assigned resource." · no/bad POST resource: "Choose the replacement resource." | `substitute` (ONE row, on the released allocation; changes carries `released` + `successor` numbers + `resource` name) |
| `ral_commit` | member | `requested` → `soft` (placeholder allowed — that IS the pipeline signal), or `soft` → `firm` (**named only** — as-built L35 guard: a soft placeholder is refused "Assign a resource before committing a placeholder to firm."; the build contract does not have this refusal) | other statuses: `f"Only a requested or soft booking can be committed — this one is {display.lower()}."` | `commit` (changes carries `from`/`to`) |
| `ral_complete` | member | `soft`/`firm` → `completed` | other statuses: `f"Only a soft or firm booking can be completed — this one is {display.lower()}."` | `complete` |
| `ral_cancel` | member | `requested`/`soft`/`firm` → `cancelled` | already cancelled: info "That allocation is already cancelled." · completed/released: `f"A {display.lower()} booking cannot be cancelled."` | `cancel` |
| `rte_submit` | member | `draft` → `submitted`, stamps `submitted_at = timezone.now()` once | already submitted: info "That entry is already awaiting approval." · approved/rejected: "An approved or rejected entry cannot be submitted." (a rejected entry can NEVER be resubmitted — re-log instead) | `submit` |
| `rte_approve` | admin | `submitted` → `approved`, stamps `approved_by`/`approved_at` once | other statuses: `f"Only a submitted entry can be approved — this one is {display.lower()}."` | `approve` |
| `rte_reject` | admin | `submitted` → `rejected`; stamps `approved_by`/`approved_at` + `decision_note = request.POST.get("reason", "").strip()` (textarea named `reason`) | same refusal, "rejected" variant | `reject` (changes carries the `reason`) |
| `rte_approve_week` | admin, args `(resource, year, week)` | every `submitted` entry of that person-week (`entry_date__iso_year=year, entry_date__week=week`) → `approved` with the same stamps, one `bulk_update` inside `transaction.atomic()` (with `updated_at` re-stamped — `bulk_update` skips auto_now); redirects `rte_list` | person resolved FIRST (`get_object_or_404(ResourceProfile, pk=resource, tenant=...)` → foreign pk 404s before any week check) · week outside 1..53: "Week must be between 1 and 53." · not a real ISO week (`date.fromisocalendar` ValueError): `f"{year} week {week} is not a real ISO week."` · zero matching rows: info `f"No submitted entries for {resource.name} in week {week}."` | `approve` — ONE row on the RESOURCE, changes `{"verb": "approve_week", "week": "YYYY-Wnn", "count": n}` |

Success messages carry the number/`count` and the model labels are `Resource` / `Allocation` /
`Time entry` (`f"Resource {obj.number} created."` etc.). Audit actions used by 7.3: `create`
`update` `delete` `assign` `substitute` (exactly 10 chars) `commit` `complete` `cancel` `submit`
`approve` `reject` — all fit `AuditLog.action` varchar(10); the verb detail goes in `changes`.

### IDOR set (cross-tenant `<int:pk>` → 404, as tenant-A ADMIN; B's rows unchanged)

* `resource_profile_b`: `rsp_detail` / `rsp_edit` / `rsp_delete`.
* `resource_allocation_b`: `ral_detail` / `ral_edit` / `ral_delete` + all five verbs
  (`ral_assign`, `ral_substitute`, `ral_commit`, `ral_complete`, `ral_cancel`).
* `resource_entry_b`: `rte_detail` / `rte_edit` / `rte_delete` + `rte_submit`, `rte_approve`,
  `rte_reject`; `rte_approve_week` with `resource=<B profile pk>` (any year/week) → 404.
* `capacity_demand` takes no pk — tenant-scoped rows only; B's rows never render.
* Valid-but-foreign int filters (`?project=<B pk>`, `?resource=<B pk>`, `?org_unit=<B pk>`) → 200
  EMPTY (a legitimate narrowing that matches nothing — unlike junk, it does NOT skip).

---

## 6. Edit locks, tenant-less guards, status-code notes

* **`rte_edit`**: refuses `obj.status in ("approved", "rejected")` BEFORE `crud_edit` (double fetch
  accepted) → `messages.error` "An approved or rejected entry is locked — it cannot be edited." →
  302 `rte_detail`, row unchanged. Login-only (a member may edit drafts; the lock applies to
  everyone).
* **`rte_delete`**: same lock with "…it cannot be deleted." before `crud_delete`.
* `rsp_edit` / `ral_edit` have **no lock** — straight `crud_edit`.
* All three create views (`rsp_create`, `ral_create`, `rte_create`) guard `request.tenant is None`
  on their FIRST line → error message + `redirect("dashboard:home")`.
* Cross-tenant `detail`/`edit`/`delete` on all three models → **404** (§5 IDOR set).
* Status codes: creates/edits render 200 on invalid POST (form redisplay) and 302 to `*_detail` on
  success; deletes 302 to `*_list`; `crud_list` junk params → 200 default page (L11), `?page=99` →
  last page, `?page=abc` → page 1 (L9).

---

## 7. Fixtures (`apps/projects/tests/conftest.py`, the `# --- 7.3 resource ---` block)

### From the ROOT conftest — reuse, never redefine

`tenant_a` (Acme) · `tenant_b` (Globex) · `admin_user` · `member_user` · `admin_b` · `client_a`
(tenant A ADMIN client — **the 7.3 admin client; there is no `resource_client`**, 7.1/7.2 define
none either) · `client_b` · `member_client`. The lane's aliases are thin: `resource_tenant` /
`resource_tenant_b` → `tenant_a`/`tenant_b`, `resource_admin` → `admin_user`, `resource_member` →
`member_user`.

### Reused 7.1 factories (import the FUNCTIONS, not fixtures)

`_projectinitiation_project(tenant, **overrides)` — every `Project`: pass `status="active"`,
`charter_status="approved"` for the host. `_projectinitiation_request(tenant, **overrides)` — the
pipeline request: pass `status="approved"`, `decision="go"`, decided stamps; never call
`convert_to_project` on it (it must stay demand).

### New helpers

| helper | signature | builds |
|---|---|---|
| `_resource_today` | `()` | `timezone.localdate()` — the only date basis in the lane (L16) |
| `_resource_profile` | `(tenant, employee=None, party=None, **overrides)` | saved `ResourceProfile`; auto-mints a person `core.Party` when neither identity is given (a row that identifies nobody is bad seed data even though `save()` never runs `clean()`); `resource_type` defaults `contractor` for party-keyed / `internal` for employee-keyed; distinct per-tenant `default_role` ("Role NN"), `skill_summary="Python, Django"`, capacity 40.00 |
| `_resource_allocation` | `(tenant, **overrides)` | saved `ResourceAllocation`: `role_name="Backend developer"`, `hours_per_week=16.00` + `allocation_unit="hours_per_week"`, `booking_status="soft"`, live window `today-7..today+35`; nothing attached — pass `project=` / `project_request=` / `resource=` explicitly |
| `_resource_entry` | `(tenant, resource, **overrides)` | saved `ResourceTimeEntry`: `entry_date=today` (current ISO week), `hours=6.00`, `status="draft"`, `project=None`. Nothing auto-stamps the audit fields — an `approved`/`rejected` row is only honest when the caller sets `submitted_at` + `approved_by` + `approved_at` (and `decision_note` for rejected) explicitly |
| `_resource_fill_profiles` | `(tenant, count, **overrides)` | `count` party-keyed rows, distinct roles ("Backlog role NN") — pagination/search fills |
| `_resource_fill_allocations` | `(tenant, count, **overrides)` | `count` bookings, distinct role_names ("Backlog booking NN") |
| `_resource_fill_entries` | `(tenant, resource, count, **overrides)` | `count` draft entries on ONE resource, dates walking back a day per row, distinct descriptions ("Backlog entry NN") |

### Fixtures — one row per state the verbs/branches need (all tenant-scoped, all `.save()`-built)

Core spine / actors:
`resource_tenant` (tenant A) · `resource_tenant_b` · `resource_admin` (tenant A admin) ·
`resource_member` (tenant A member) · `resource_member_b` (non-admin, tenant B) ·
`resource_tenantless_user` / `resource_tenantless_client` (`request.tenant is None`) ·
`resource_anon_client` · `resource_csrf_client` (`Client(enforce_csrf_checks=True)` as
`admin_user`).

Spine rows:
`resource_org_unit_a` (tenant A) · `resource_org_unit_b` (tenant B, crafted-POST value) ·
`resource_party_a` (tenant A person — the contractor identity) · `resource_party_b` (tenant B,
crafted-POST value) · `resource_employee_a` (an `hrm.EmployeeProfile` in tenant A on its own
person Party) · `resource_project` (tenant A ACTIVE chartered host, via the 7.1 factory) ·
`resource_project_b` (tenant B host) · `resource_request` (tenant A approved UNCONVERTED
`ProjectRequest` — the pipeline-demand anchor).

`ResourceProfile`:
`resource_profile_internal` (EMPLOYEE-keyed via `resource_employee_a`, org-unit'd, 40h, "Data
engineer") · `resource_profile_contractor` (PARTY-keyed via `resource_party_a`, `contractor`,
engagement window today-30..today+90, 40h) · `resource_profile_minimal` (party-keyed,
**`weekly_capacity_hours=24`** — the `% of Capacity` denominator; no org unit, no window, empty
skill summary) · `resource_profile_b` (tenant B).

`ResourceAllocation` (all requested_by `resource_admin`, all project-linked to
`resource_project` unless stated):
`resource_allocation_named_firm` (firm, contractor, 12h/wk, today-14..today+28 — live; assign must
refuse "already names a resource") · `resource_allocation_named_soft` (soft, internal, 16h/wk,
today-7..today+35 — live; the substitute happy path, the soft→firm commit, and the PLAN side of
the actuals row) · `resource_allocation_soft_pct` (soft, named on the 24h `minimal` resource,
`pct_capacity=50` — unit-2; a full week plans 12.00h) · `resource_allocation_placeholder_requested`
(`resource=None`, `requested`, today+7..today+49 — assign happy path, requested→soft commit, a
demand-board gap) · `resource_allocation_placeholder_soft` (`resource=None`, `soft`,
today-21..today+21 — the as-built commit REFUSAL case; assign still accepts it) ·
`resource_allocation_request_placeholder` (`project=None`, `project_request=resource_request`,
`requested`, today+14..today+70 — the request-linked demand row) · `resource_allocation_completed`
(completed past booking today-90..today-30 — cancel/complete refuse it) ·
`resource_allocation_cancelled` (cancelled, window today-21..today+21 — a window match is not
enough: `planned_hours` → ZERO, cancel answers "already cancelled") ·
`resource_allocation_released` (released, internal, 10h/wk, today-28..today+28 — `planned_hours`
→ ZERO) · `resource_allocation_successor` (firm, contractor, SAME window/magnitude as the
released row, `substitute_of=resource_allocation_released` — hand-built chain; `ral_detail` of the
released row must surface it as `successor`) · `resource_allocation_b` (tenant B).

`ResourceTimeEntry` (all on the current-ISO-week `today` unless stated, stamps set honestly):
`resource_entry_draft` (internal, host project, 6.00h, no stamps) · `resource_entry_submitted`
(internal, host project, 6.00h, `submitted_at` = now−2h ONLY — the approval queue and the
`rte_approve_week` target; compute its `iso_year`/`iso_week` from the row, never hardcode) ·
`resource_entry_approved` (internal, host project, 6.00h, `submitted_at` now−1d →
`approved_by=admin` + `approved_at` now−2h; pairs with `resource_allocation_named_soft` so the
actuals section has one real row: actual 6.00 vs planned = that booking's `planned_hours`) ·
`resource_entry_rejected` (internal, host project, 8.00h, full honest stamp set + `decision_note`
"Client call overran — re-log the extra hour under support." — the edit/delete LOCK row) ·
`resource_entry_approved_nonproject` (contractor, `project=None`, "Internal training", 4.00h,
approved — the actuals "Non-project time" row, planned 0.00) · `resource_entry_b` (tenant B).

**Board baselines (deterministic for THIS fixture set, but compute them in tests — see §4):**
with the default fixture set pulled, `over_count == 0` (16 ≤ 40, 12 ≤ 40, 12 ≤ 24), the demand
section carries 5 rows (4 project-linked by start_date, then 1 request-linked) with
`gap_count == 3`, and `actuals_rows` has exactly 2 rows — (contractor, None) variance +4.00 first,
then (internal, project) actual 6.00 / planned 16.00 / variance −10.00. Any test that pulls
additional allocation fixtures changes these sums — always recompute from the pulled rows.

---

## 8. Reminders that have bitten this repo

* **L16** — `USE_TZ=True`: derive every date from `timezone.localdate()` / `timezone.now()` (the
  same basis `is_live`, `capacity_demand`'s horizon and the actuals window use).
  `datetime.date.today()` flakes around local midnight.
* **L11** — junk enum + junk/0/over-range int FK filters must 200 with the filter SKIPPED (the
  register never silently empties); a valid FOREIGN pk filters → 200 EMPTY; `?week=0` is a
  non-pk int filter and legitimately matches nothing; `?year=0`/`?year=9999` are special-cased
  (`qs.none()` + actuals fallback — §4).
* **L9** — page 2 and past-the-end with `RESOURCE_PAGE_SIZE + 1` rows.
* **L35** — an absent prerequisite must be REJECTED, not fall through: `ral_assign` on a
  `completed` booking, `ral_commit` on a soft PLACEHOLDER (as-built), `rte_approve` on a
  never-submitted draft, `rte_approve_week` with zero submitted rows.
* **L20/L22** — `booking_status`, `substitute_of`, `requested_by`, `status`, `submitted_at`,
  `approved_at`, `approved_by`, `decision_note` must NOT be form fields anywhere; assert a
  smuggled value in an edit POST changes nothing.
* **L47/L49** — the closing run is unfiltered with migrations ON.
* 403-vs-404 depends on the ACTOR: the role check runs before `get_object_or_404`, so IDOR-404s
  must use `client_a` (admin); member tests must never claim a 404 on an admin-gated verb.
* **Seeder figures are not test data.** Tests NEVER touch or call
  `management/commands/seed_projects.py`; the post-M4 seed numbers (RAL-00001 48h/wk,
  `over_count=4` on the demo tenant) are demo data. Every expectation is computed from the
  fixture rows the test itself built.
* Do not pin cross-database NULL-ordering of `ResourceProfile.Meta.ordering` (employee-NULL rows
  first is a SQLite/MariaDB ASC artifact); pin ordering only within same-kind rows.
* A concurrent session owns other `apps/projects` files (`test_planning_views.py`,
  `CostManagement/*`) — 7.3 tests import nothing from them and never touch their files.
