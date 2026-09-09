# Contract — Projects 7.3 Resource Management

Frozen before any code (Phase 3 step 1). Every model field, CHOICES tuple, url name, template
path, context key, filter param, verb transition and audit action below is **the spec** — the
build, `temp/smoke_73.py` and the six reviewers diff against these exact strings. A name left
unpinned here is a silently blank page or a NoReverseMatch (lessons L7/L8).

## Namespaces

| thing | value |
|---|---|
| app | `apps.projects` (`app_name = "projects"`) — exists, no settings/urls wire-up |
| backend sub-module folder | `ResourceManagement/` in each of `models/ forms/ views/ urls/` |
| entity files | `ResourceProfiles.py`, `ResourceAllocations.py`, `ResourceTimeEntries.py`, plus `CapacityDemand.py` in `views/` + `urls/` only |
| template slug | `templates/projects/resource/` |
| template entity folders | `resourceprofile/`, `resourceallocation/`, `resourcetimeentry/` (lowercase singular) |
| url stems | `rsp_`, `ral_`, `rte_` (+ `capacity_demand`) |
| path prefixes | `resource-profiles/`, `allocations/`, `time-entries/`, `capacity-demand/` — all four are literals disjoint from 7.1/7.2's first segments |
| number prefixes | `RSP`, `RAL`, `RTE` (verified unused repo-wide; `crm.ResourceAllocation` [RA-] and `crm.Timesheet` [TS-] stay untouched stand-ins) |
| migration | next incremental = **`0004_<auto>`** via `makemigrations projects` (current highest: `0003_projecttask_projectmilestone_schedulebaseline_and_more.py`) |
| test subslug | `resource` → fixtures `resource_*`, helpers `_resource_*`, tests `test_resource_*` |

**Scope guard:** 7.3 owns the *people* layer — pool, bookings, project-facing time actuals. NO
money columns anywhere (no rates, no billable flag, no cost — 7.4/7.11/7.15, L29). No skill table
(the matrix/certifications stay the `hrm:employeeskill_list` lens, 3.40). No timesheet header
model (flat entries + weekly verbs). No request table (`booking_status="requested"` folds the
Certinia/Planview request into the allocation). No smoothing engine (alert + manual rebalance
only). No leave deduction (uniform weekly hours, stated on the board).

## 🚨 Invariants carried from 7.1/7.2

- `AuditLog.action` is varchar(10): actions this pass = `create`, `update`, `delete`,
  `assign`, `substitute` (exactly 10 chars), `commit`, `complete`, `cancel`, `submit`,
  `approve`, `reject`. The verb detail goes in `changes`.
- Audit helper is **`apps.core.utils.write_audit_log(user, obj, action, changes=None)`** —
  imported via `apps.projects.views._common`. There is no `log_action`.
- Decorators: `@login_required` (from `_common` star-import), `@tenant_admin_required`
  (from `apps.core.decorators`, raises `PermissionDenied` → 403 for members),
  `@require_POST` (from `django.views.decorators.http`). Gate order on verbs:
  `@login_required` → (`@tenant_admin_required`) → `@require_POST` (sibling order).
- Context-var contract (L7, `apps/core/crud.py`): list → `object_list` + `page_obj` + `q`;
  detail/edit object → `obj`; form → `form` + `is_edit`.
- Every queryset `filter(tenant=request.tenant)`; every enum filter allow-listed against
  CHOICES by `crud_list` (L11); all GET filters parsed BEFORE pagination.
- A nullable FK must never sit inside a `|default:` filter argument in a template (hard 500).
- Multi-line template notes use `{% comment %}` blocks, never `{# #}` (smoke asserts no leaks).
- Badge classes colour-named only: `badge-green/-amber/-red/-info/-slate/-muted` (L33), with a
  `{% else %}<span class="badge badge-muted">{{ obj.get_<field>_display }}</span>` fallback.
- FK `<select>` comparisons in templates use `|stringformat:"d"`
  (`request.GET.project == p.pk|stringformat:"d"` — milestone list precedent).
- Entity modules star-import `_base` / `_common` (+ explicit second import lines); absolute
  imports; sub-package `ResourceManagement/__init__.py` files stay EMPTY (7.1/7.2 precedent);
  re-export blocks go in the four TOP-LEVEL `__init__.py` files only.
- `TenantUniqueMixin` BEFORE `TenantModelForm` on all three forms (the RSP `clean()` reads
  `self.tenant_id`, which is only stamped on CREATE by the mixin).
- `_reject_foreign` re-checks every tenant-scoped FK that renders as a field. **User FKs
  (`requested_by`, `approved_by`) are NEVER in the list** — users can be tenant-less (TaskForm
  `owner` precedent); they are excluded from the forms anyway.
- Factory saves in seeder/tests are `obj.save()`, never `bulk_create` (numbering).
- Tenant-admin verb buttons are hidden for members with the
  `{% if request.user.is_superuser or request.user.is_tenant_admin %}` idiom (mst_achieve
  precedent) — rendering them would serve a hard 403.
- Pagination include is exactly `{% include "partials/pagination.html" %}`
  (`templates/partials/pagination.html` — verified present; consumes `page_obj.window`).

## Model 1 — ResourceProfile [RSP-]

`models/ResourceManagement/ResourceProfiles.py`. One bookable person in the tenant's pool —
an HR employee **or** an external party, never a second person master (L28). Base
`TenantNumbered`, `NUMBER_PREFIX = "RSP"`.

`Meta.ordering = ["employee__party__name", "party__name", "id"]` (the pool register is a
people list — alphabetical like Float/Resource Guru; NULL `employee` rows — contractors — sort
first under MariaDB ASC, then by `party__name`).
`unique_together = ("tenant", "number")`.

### CHOICES (exact tuples, verbatim)

```python
RESOURCE_TYPE_CHOICES = [
    ("internal", "Internal"),
    ("contractor", "Contractor"),
    ("freelancer", "Freelancer"),
    ("consultant", "Consultant"),
]
STATUS_CHOICES = [
    ("active", "Active"),
    ("inactive", "Inactive"),
]
```

### Fields

| field | definition |
|---|---|
| `employee` | FK `"hrm.EmployeeProfile"` SET_NULL, null+blank, `related_name="resource_profiles"` (internal staff; string FK — sanctioned cross-app pattern) |
| `party` | FK `"core.Party"` SET_NULL, null+blank, `related_name="resource_profiles"` (external contractor/freelancer identity) |
| `resource_type` | CharField(12), choices above, default `"internal"` |
| `default_role` | CharField(80) (required — the role bookings copy) |
| `org_unit` | FK `"core.OrgUnit"` SET_NULL, null+blank, `related_name="resource_profiles"` (home team / pool filter) |
| `skill_summary` | CharField(255) blank (quick filter; the matrix is the HRM lens) |
| `weekly_capacity_hours` | DecimalField(max_digits=6, decimal_places=2), default `Decimal("40.00")`, `validators=[MinValueValidator(Decimal("0"))]` — the denominator of every capacity computation |
| `utilization_target_pct` | PositiveSmallIntegerField, default `80`, `validators=[MinValueValidator(1), MaxValueValidator(100)]` |
| `available_from` | DateField null+blank (contractor engagement window start) |
| `available_to` | DateField null+blank (engagement window end) |
| `status` | CharField(8), choices above, default `"active"` — a lens toggle, ON the form |
| `notes` | TextField blank |

Index names: `("tenant","resource_type")` → `rsp_tnt_rtype_idx`; `("tenant","status")` →
`rsp_tnt_status_idx`; `("tenant","employee")` → `rsp_tnt_employee_idx`;
`("tenant","party")` → `rsp_tnt_party_idx`.

`__str__` → `f"{self.number} · {self.name}"`.

### Derived + guards

- Property `name` (no args): `self.employee.party.name` when `employee_id` set
  (EmployeeProfile.party is non-null), else `self.party.name` when `party_id` set,
  else `self.number`.
- `clean()` — one sentence each:
  1. Exactly one of `employee`/`party`: `if bool(self.employee_id) == bool(self.party_id):`
     raise non-field `ValidationError("Choose an employee or an external party — exactly one of the two.")`.
  2. Pool uniqueness per tenant (deliberately NO conditional unique constraint — 7.2 BSL
     MariaDB precedent): when `employee_id` and `tenant_id` and
     `ResourceProfile.objects.filter(tenant_id=self.tenant_id, employee_id=self.employee_id).exclude(pk=self.pk).exists()`
     → raise `{"employee": "This employee is already in this tenant's resource pool."}`.

### Form — ResourceProfileForm

`forms/ResourceManagement/ResourceProfiles.py`:

```python
class ResourceProfileForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ResourceProfile
        fields = [
            "employee", "party", "resource_type", "default_role", "org_unit",
            "skill_summary", "weekly_capacity_hours", "utilization_target_pct",
            "available_from", "available_to", "status", "notes",
        ]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["employee", "party", "org_unit"])
        return cleaned
```

- Order matters (matches the field table). Excludes: `tenant`, `number`, created/updated
  stamps. `status` stays ON (active/inactive is a lens toggle, not governance state).
- NO bespoke `__init__` narrowing: `core.TenantModelForm` auto-scopes every ModelChoiceField
  whose target carries `tenant` (EmployeeProfile/Party/OrgUnit all do). The narrowing the todo
  calls "per tenant" IS this; `_reject_foreign` is the crafted-POST boundary re-check.
- No further queryset filter (all tenant EmployeeProfiles / Parties — a dropdown that silently
  omits the one you need is worse than one that lists everyone; `clients()` precedent).

## Model 2 — ResourceAllocation [RAL-]

`models/ResourceManagement/ResourceAllocations.py`. One booking: a role (+ optionally a named
resource) asked for or committed to a project / pipeline request / work package for a magnitude
over a date window. NULL `resource` = **placeholder** — a state of the booking, never a fake
person row. Base `TenantNumbered`, `NUMBER_PREFIX = "RAL"`.

`Meta.ordering = ["-start_date", "-id"]` (window-ordered register; the `("tenant","start_date")`
index serves it — there is no `created_at` index in this pass's index list).
`unique_together = ("tenant", "number")`.

### CHOICES (exact tuples, verbatim)

```python
ALLOCATION_UNIT_CHOICES = [
    ("hours_per_week", "Hours per Week"),
    ("pct_capacity", "% of Capacity"),
    ("total_hours", "Total Hours"),
]
BOOKING_STATUS_CHOICES = [
    ("requested", "Requested"),
    ("soft", "Soft Booked"),
    ("firm", "Firm Booked"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
    ("released", "Released"),
]
```

`max_length` for `allocation_unit` is **14** (`hours_per_week` = 14 chars, fields.E009);
`booking_status` max_length **12**.

### Fields

| field | definition |
|---|---|
| `project` | FK `"projects.Project"` CASCADE, null+blank, `related_name="allocations"` |
| `project_request` | FK `"projects.ProjectRequest"` SET_NULL, null+blank, `related_name="allocations"` (pipeline demand with no project yet) |
| `project_task` | FK `"projects.ProjectTask"` SET_NULL, null+blank, `related_name="allocations"` (task-grain booking, planning grain only) |
| `resource` | FK `"projects.ResourceProfile"` SET_NULL, null+blank, `related_name="allocations"` — **NULL = placeholder** |
| `role_name` | CharField(80) (required — the placeholder's whole identity) |
| `skill_requirements` | CharField(255) blank (free text until a taxonomy is justified) |
| `allocation_unit` | CharField(14), choices above, default `"hours_per_week"` |
| `hours_per_week` | DecimalField(6, 2), null+blank, `validators=[MinValueValidator(Decimal("0"))]` |
| `pct_capacity` | PositiveSmallIntegerField, null+blank, `validators=[MinValueValidator(1), MaxValueValidator(100)]` |
| `total_hours` | DecimalField(8, 2), null+blank, `validators=[MinValueValidator(Decimal("0"))]` |
| `start_date` | DateField (required) |
| `end_date` | DateField null+blank — **null = ongoing** (proven `crm.ResourceAllocation` convention), `help_text="Leave blank for an ongoing booking."` |
| `booking_status` | CharField(12), choices above, default `"requested"` — verb-driven, never on the form |
| `substitute_of` | FK `"self"` SET_NULL, null+blank, `related_name="substituted_by"` (the substitution chain) |
| `requested_by` | FK `settings.AUTH_USER_MODEL` SET_NULL, null+blank, **editable=False**, `related_name="requested_allocations"` (provenance — stamped by `ral_create`) |
| `notes` | TextField blank |

Index names: `("tenant","resource")` → `ral_tnt_resource_idx`;
`("tenant","project")` → `ral_tnt_project_idx`;
`("tenant","project_request")` → `ral_tnt_request_idx`;
`("tenant","booking_status")` → `ral_tnt_status_idx`;
`("tenant","start_date")` → `ral_tnt_start_idx`.

`__str__` → `f"{self.number} · {self.role_name}"`.

### Derived + guards

- Property `is_live` (no args): `booking_status in ("soft", "firm")` AND
  `start_date <= timezone.localdate()` AND (`end_date is None or end_date >= today`).
- Method `planned_hours(self, win_start, win_end) -> Decimal` — the proven
  `crm.ResourceAllocation.overlap_hours()` proration (copy the shape verbatim) extended to the
  three units. Returns `ZERO` when `booking_status in ("cancelled", "released")`; clamps a null
  `end_date` to `win_end`; `ov = overlap of [start_date, a_end] with [win_start, win_end]`,
  `days = (ov_end - ov_start).days + 1`, `0` when `ov_end < ov_start`; then:
  - `hours_per_week` → `q2(hours_per_week * days / 7)`;
  - `pct_capacity` → `q2(pct / 100 * resource.weekly_capacity_hours * days / 7)`, and `ZERO`
    when `resource_id` is None (a % of an unknown person's capacity is unknowable — the demand
    lens flags placeholders by presence, not hours);
  - `total_hours` → spread over the booking's own window:
    `window_days = (a_end - start_date).days + 1` (`0` when `<= 0`), then
    `q2(total_hours * days / window_days)`.
  (`q2`/`ZERO` come from `models/_base` — they clamp to the house Decimal column shape.)
- `clean()` — one sentence each:
  1. `project` or `project_request` required: non-field
     `ValidationError("Attach the allocation to a project or a project request.")`.
  2. `end_date >= start_date`: `{"end_date": "End date cannot precede start date."}`.
  3. Exactly one magnitude, matching `allocation_unit`: the unit's field being None →
     `{"<field>": "Required when the allocation unit is <allocation_unit>."}`; either of the
     other two fields set → `{"<field>": "Leave blank — the allocation unit is <allocation_unit>."}`
     (mapping: `hours_per_week`/`pct_capacity`/`total_hours`).

### Form — ResourceAllocationForm

`fields` order (order matters): `project`, `project_request`, `project_task`, `resource`,
`role_name`, `skill_requirements`, `allocation_unit`, `hours_per_week`, `pct_capacity`,
`total_hours`, `start_date`, `end_date`, `notes`.
**Deliberately NOT on the form:** `tenant`, `number`, `booking_status` + `substitute_of`
(verb-driven), `requested_by` (provenance). Form `clean()` = `_reject_foreign` on
`["project", "project_request", "project_task", "resource"]` only; the model `clean()` carries
the three guards. No bespoke `__init__` (auto-narrowing). Form help note:
"Set only the magnitude matching the allocation unit — the others stay blank."

## Model 3 — ResourceTimeEntry [RTE-]

`models/ResourceManagement/ResourceTimeEntries.py`. One day's logged hours against a project
(and optionally a work package), with the submit → approve routing and the approved hours that
make actuals-to-plan joinable to `projects.Project` (the gap `hrm.TimesheetEntry` cannot fill —
its `project` FK points at the 2.9 `accounting.Project` stand-in). The *thinnest* projects-side
time table — NOT a fourth timesheet. Base `TenantNumbered`, `NUMBER_PREFIX = "RTE"`.

`Meta.ordering = ["resource_id", "-entry_date", "-id"]` (resource asc, newest date first —
keeps each person's ISO-week block contiguous so the list template's
`{% regroup object_list by week_key %}` is correct; the `("tenant","resource","entry_date")`
index serves it).
`unique_together = ("tenant", "number")`.

### CHOICES (exact tuples, verbatim)

```python
STATUS_CHOICES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]
```

### Fields

| field | definition |
|---|---|
| `resource` | FK `"projects.ResourceProfile"` **CASCADE**, `related_name="time_entries"` (mirrors `hrm.Timesheet.employee`; an entry dies with its person) |
| `project` | FK `"projects.Project"` SET_NULL, null+blank, `related_name="time_entries"` (non-project time is loggable) |
| `project_task` | FK `"projects.ProjectTask"` SET_NULL, null+blank, `related_name="time_entries"` (7.8 extends the task in place) |
| `entry_date` | DateField (required) |
| `hours` | DecimalField(max_digits=5, decimal_places=2), `validators=[MinValueValidator(Decimal("0.01"))]` — "greater than 0" pinned as 0.01 (the smallest loggable unit) |
| `task_description` | CharField(255) blank |
| `status` | CharField(12), choices above, default `"draft"` — verb-driven, never on the form |
| `submitted_at` | DateTimeField null+blank, **editable=False** |
| `approved_by` | FK `settings.AUTH_USER_MODEL` SET_NULL, null+blank, **editable=False**, `related_name="approved_time_entries"` |
| `approved_at` | DateTimeField null+blank, **editable=False** |
| `decision_note` | TextField blank (the rejection reason) |
| `notes` | TextField blank |

**NO billable flag, NO rates, NO money columns** (7.11/7.4/7.15, L29).

Index names: `("tenant","resource","entry_date")` → `rte_tnt_res_date_idx`;
`("tenant","project","entry_date")` → `rte_tnt_prj_date_idx`;
`("tenant","status")` → `rte_tnt_status_idx`.

`__str__` → `f"{self.number} · {self.hours}h on {self.entry_date:%Y-%m-%d}"` (no FK deref —
admin changelist calls `str()` per row).

### Derived + guards

- Properties (all no-args, derived from `entry_date.isocalendar()`):
  - `iso_year` → `self.entry_date.isocalendar()[0]` (int)
  - `iso_week` → `self.entry_date.isocalendar()[1]` (int)
  - `week_key` → `f"{self.resource_id}:{self.iso_year}-W{self.iso_week:02d}"` — the
    `{% regroup %}` key for the weekly lens (one key = one person-week).
- No model `clean()` beyond the base — `hours > 0` is the validator; status moves only through
  the verbs. Guard semantics pinned at the VIEW layer:
  - approval stamps (`submitted_at`, `approved_by`, `approved_at`) are written exactly once by
    the verbs and never rewound by edit (the form excludes them, so an edit cannot touch them);
  - `approved`/`rejected` rows refuse edit and delete (7.1 evidence ruling) — see `rte_edit`/
    `rte_delete` below.

### Form — ResourceTimeEntryForm

`fields` order: `resource`, `project`, `project_task`, `entry_date`, `hours`,
`task_description`, `notes`.
**Deliberately NOT on the form:** `tenant`, `number`, `status`, `submitted_at`, `approved_at`,
`approved_by`, `decision_note`. Form `clean()` = `_reject_foreign` on
`["resource", "project", "project_task"]`. Form help note: "Status and approval stamps are
verb-driven — they never appear on this form."

## URLs — the complete route table (25 routes)

Four new modules concatenated in `urls/__init__.py` **after `_pp_baselines`** (order there
cannot shadow anything — first segments are disjoint literals). Within each module, literal
routes precede `<int:pk>/` routes (Django is first-match-wins — house rule, commented).

| # | module file | path literal (under `/projects/`) | view | url name |
|---|---|---|---|---|
| 1 | `ResourceProfiles.py` | `resource-profiles/` | `rsp_list` | `rsp_list` |
| 2 | | `resource-profiles/add/` | `rsp_create` | `rsp_create` |
| 3 | | `resource-profiles/<int:pk>/` | `rsp_detail` | `rsp_detail` |
| 4 | | `resource-profiles/<int:pk>/edit/` | `rsp_edit` | `rsp_edit` |
| 5 | | `resource-profiles/<int:pk>/delete/` | `rsp_delete` | `rsp_delete` |
| 6 | `ResourceAllocations.py` | `allocations/` | `ral_list` | `ral_list` |
| 7 | | `allocations/add/` | `ral_create` | `ral_create` |
| 8 | | `allocations/<int:pk>/` | `ral_detail` | `ral_detail` |
| 9 | | `allocations/<int:pk>/edit/` | `ral_edit` | `ral_edit` |
| 10 | | `allocations/<int:pk>/delete/` | `ral_delete` | `ral_delete` |
| 11 | | `allocations/<int:pk>/assign/` | `ral_assign` | `ral_assign` |
| 12 | | `allocations/<int:pk>/substitute/` | `ral_substitute` | `ral_substitute` |
| 13 | | `allocations/<int:pk>/commit/` | `ral_commit` | `ral_commit` |
| 14 | | `allocations/<int:pk>/complete/` | `ral_complete` | `ral_complete` |
| 15 | | `allocations/<int:pk>/cancel/` | `ral_cancel` | `ral_cancel` |
| 16 | `ResourceTimeEntries.py` | `time-entries/` | `rte_list` | `rte_list` |
| 17 | | `time-entries/add/` | `rte_create` | `rte_create` |
| 18 | | `time-entries/week/<int:resource>/<int:year>/w<int:week>/approve/` | `rte_approve_week` | `rte_approve_week` |
| 19 | | `time-entries/<int:pk>/` | `rte_detail` | `rte_detail` |
| 20 | | `time-entries/<int:pk>/edit/` | `rte_edit` | `rte_edit` |
| 21 | | `time-entries/<int:pk>/delete/` | `rte_delete` | `rte_delete` |
| 22 | | `time-entries/<int:pk>/submit/` | `rte_submit` | `rte_submit` |
| 23 | | `time-entries/<int:pk>/approve/` | `rte_approve` | `rte_approve` |
| 24 | | `time-entries/<int:pk>/reject/` | `rte_reject` | `rte_reject` |
| 25 | `CapacityDemand.py` | `capacity-demand/` | `capacity_demand` | `capacity_demand` |

Route 18's literal `week/` segment **must precede** the `<int:pk>/` routes in the module's
`urlpatterns` (the house rule is commented even though `<int:pk>` cannot match `week` — the
`<int:week>` in the middle position is unique in the app). `capacity-demand/` is GET-only.

## Views & context keys — the critical section

All entity views live in `views/ResourceManagement/<Entity>.py`;
`capacity_demand` in `views/ResourceManagement/CapacityDemand.py`.
`views/_helpers.py` gains two helpers (same shape as the existing `projects()`/`org_units()` —
`.none()` for a tenant-less user, never an error):

```python
def resource_profiles(tenant):   # OrgUnit-style dropdown queryset, order_by Meta.ordering
def project_requests(tenant):    # Party-style dropdown queryset, order_by("title", "id")
```

### List views — filters (GET param → ORM lookup), all parsed BEFORE pagination

| view | search_fields (`?q=` icontains OR) | `crud_list` `filters` | hand-parsed (before `crud_list`) | `extra_context` |
|---|---|---|---|---|
| `rsp_list` | `employee__party__name`, `party__name`, `number`, `default_role`, `skill_summary` | `("resource_type","resource_type",False)`, `("status","status",False)`, `("org_unit","org_unit_id",True)` | — | `resource_type_choices`, `status_choices`, `org_units` (helper queryset) |
| `ral_list` | `role_name`, `number`, `skill_requirements`, `project__name` | `("project","project_id",True)`, `("project_request","project_request_id",True)`, `("resource","resource_id",True)`, `("booking_status","booking_status",False)` | `?placeholder=True|False` → `resource__isnull=True/False`; `?is_live=True|False` → `booking_status__in=("soft","firm") + start_date__lte=today + (end_date__isnull=True \| end_date__gte=today)`; any other value ignored | `booking_status_choices`, `projects` (helper), `project_requests` (helper), `resources` (helper) |
| `rte_list` | `number`, `task_description`, `resource__employee__party__name`, `resource__party__name`, `project__name` | `("status","status",False)`, `("resource","resource_id",True)`, `("project","project_id",True)`, `("year","entry_date__iso_year",True)`, `("week","entry_date__week",True)` | — | `status_choices`, `resources` (helper), `projects` (helper), `actuals_rows` (below) |

Notes: `?resource=0` is skipped by `crud_list`'s zero-guard (`_id` pk lookup) → default page;
`?status=nope` is skipped by the enum guard → default page. `?year=0`/`?week=0` are **non-pk**
int filters and legitimately match no rows (documented so smoke does not mis-assert).
`entry_date__week` is Django's ISO-8601 week lookup; it is paired with `__iso_year` (NOT
`__year`) so the year/week lens stays consistent across ISO-year boundaries. `per_page` stays
the `crud_list` default 15 on all three lists.

**`rte_list` weekly lens + actuals section.** The page is `crud_list`'s flat paginated rows;
the weekly grouping is template-side `{% regroup object_list by week_key as week_groups %}`
(valid because `Meta.ordering` keeps person-weeks contiguous; a group MAY straddle a page
boundary — accepted). The `actuals-to-plan` section is computed in the view over the window
`?year=`+`?week=` when both given, else the current ISO year/week, ignoring `?q=`/`?status=`:
per (resource, project) over APPROVED entries in that window — `actual_hours` = SUM(hours);
`planned_hours` = Σ live allocations' `planned_hours(win_start, win_end)` for that
resource+project; `variance = actual_hours − planned_hours`; ordered by variance descending.
`actuals_rows` = list of dicts with keys `resource` (ResourceProfile), `project` (may be None
→ the row renders "Non-project time"), `actual_hours`, `planned_hours`, `variance` (Decimals).
Section carries `id="actuals"`.

### CRUD views (all three entities, same shape as 7.2)

| view | template | context | behaviour |
|---|---|---|---|
| `*_list` | `<entity>/list.html` | see tables above | `crud_list` |
| `*_create` | `<entity>/form.html` | `form`, `is_edit=False` | tenant-less guard FIRST ("Select a tenant workspace before creating records." → `dashboard:home`); hand-rolled (mst_create shape): save → `write_audit_log(request.user, obj, "create")` → success message `f"{Model label} {obj.number} created."` (labels: "Resource" / "Allocation" / "Time entry") → redirect `*_detail`. `ral_create` stamps `obj.requested_by = request.user` and takes `initial={"project": request.GET.get("project", "")}`; `rte_create` takes `initial={"resource": request.GET.get("resource", "")}`; `rsp_create` no initial |
| `*_detail` | `<entity>/detail.html` | `obj` (+ extras below) | `get_object_or_404(...select_related..., pk=pk, tenant=request.tenant)`. `rsp_detail` select_related `employee__party`, `party`, `org_unit`. `ral_detail` select_related `project`, `project_request`, `project_task`, `resource`, `substitute_of`; extras `resources` (helper queryset — renders the assign/substitute `<select name="resource">`) and `successor` (`obj.substituted_by.order_by("pk").first()`, may be None). `rte_detail` select_related `resource`, `project`, `project_task`, `approved_by` |
| `*_edit` | `<entity>/form.html` | `form`, `obj`, `is_edit=True` | `crud_edit(model=…, form_class=…, template=…, success_url="projects:<stem>_list")` — EXCEPT `rte_edit`, which first guards `obj.status in ("approved","rejected")` → `messages.error("An approved or rejected entry is locked — it cannot be edited.")` → redirect `rte_detail`, then delegates to `crud_edit` (double fetch accepted) |
| `*_delete` | — | — | `@login_required @require_POST` + `crud_delete(success_url="projects:<stem>_list")` — EXCEPT `rte_delete`, same lock guard as `rte_edit` (message "An approved or rejected entry is locked — it cannot be deleted.") before delegating |

### Verbs — gating, transitions, refusal text, audit

Every verb: `get_object_or_404(<Model>, pk=pk, tenant=request.tenant)`, refusals are
`messages.*` + redirect to the object's detail (never 500/silent), success messages carry the
number, audit `changes` dict carries the verb detail.

| verb | gating | allowed from → to | refusal text (`messages.error/info`) | audit action | success message |
|---|---|---|---|---|---|
| `ral_assign` | `@tenant_admin_required` + `@require_POST` | placeholder (`resource_id is None`) with status `requested`/`soft` → sets `resource` from POST `resource` (tenant-resolved via `as_db_int`; `ResourceProfile.objects.filter(tenant=…)`), status → `soft` if it was `requested` | already named: "That allocation already names a resource — use Substitute to replace it." · status not in (requested, soft): `f"A {obj.get_booking_status_display().lower()} allocation cannot be staffed."` · no/bad POST resource: "Choose a resource to assign." | `assign` | `f"Assigned {resource.name} to allocation {obj.number}."` |
| `ral_substitute` | `@tenant_admin_required` + `@require_POST` | named, status `soft`/`firm` → inside `transaction.atomic()`: current row → `released`; successor row created copying project/project_request/project_task/role_name/skill_requirements/allocation_unit/magnitudes/start_date/end_date/notes + `requested_by`, `resource` = POST `resource`, `booking_status` = the ORIGINAL status, `substitute_of` = current; redirect to the SUCCESSOR's detail | placeholder: "That allocation is a placeholder — assign a resource to it instead." · status not in (soft, firm): `f"Only a soft or firm booking can be substituted — this one is {display.lower()}."` · replacement is the current resource: info "That is already the assigned resource." · no/bad POST resource: "Choose the replacement resource." | `substitute` (one row, on the released allocation; changes carries `released` + `successor` numbers + `resource` str) | `f"Released {obj.number}; {replacement.name} booked on successor {successor.number}."` |
| `ral_commit` | `@login_required` + `@require_POST` (member-level) | `requested` → `soft`, or `soft` → `firm` (one step per POST) | other statuses: `f"Only a requested or soft booking can be committed — this one is {display.lower()}."` | `commit` | requested→soft: `f"Allocation {obj.number} soft-booked."` · soft→firm: `f"Allocation {obj.number} committed."` |
| `ral_complete` | `@login_required` + `@require_POST` | `soft`/`firm` → `completed` | other statuses: `f"Only a soft or firm booking can be completed — this one is {display.lower()}."` | `complete` | `f"Allocation {obj.number} completed."` |
| `ral_cancel` | `@login_required` + `@require_POST` | `requested`/`soft`/`firm` → `cancelled` | already cancelled: info "That allocation is already cancelled." · completed/released: `f"A {display.lower()} booking cannot be cancelled."` | `cancel` | `f"Allocation {obj.number} cancelled."` |
| `rte_submit` | `@login_required` + `@require_POST` | `draft` → `submitted`, stamps `submitted_at = timezone.now()` once | already submitted: info "That entry is already awaiting approval." · approved/rejected: "An approved or rejected entry cannot be submitted." | `submit` | `f"Entry {obj.number} submitted for approval."` |
| `rte_approve` | `@tenant_admin_required` + `@require_POST` | `submitted` → `approved`, stamps `approved_by = request.user`, `approved_at = timezone.now()` once | other statuses: `f"Only a submitted entry can be approved — this one is {display.lower()}."` | `approve` | `f"Entry {obj.number} approved."` |
| `rte_reject` | `@tenant_admin_required` + `@require_POST` | `submitted` → `rejected`; stamps `approved_by`/`approved_at` once; `decision_note = request.POST.get("reason", "").strip()` (the detail template's reject form carries a textarea named `reason`) | same refusal as approve, "rejected" variant: `f"Only a submitted entry can be rejected — this one is {display.lower()}."` | `reject` | `f"Entry {obj.number} rejected."` |
| `rte_approve_week` | `@tenant_admin_required` + `@require_POST`, args `(resource, year, week)` from route 18 | bulk: every `submitted` entry of that person-week → `approved` with the same stamps, inside `transaction.atomic()`; person resolved `get_object_or_404(ResourceProfile, pk=resource, tenant=request.tenant)`; week clamped to `1 <= week <= 53` else error + redirect `rte_list`; filter `entry_date__iso_year=year, entry_date__week=week` | zero matching rows: info `f"No submitted entries for {resource.name} in week {week}."` | `approve` — ONE row via `write_audit_log(request.user, resource, "approve", changes={"verb": "approve_week", "week": f"{year}-W{week:02d}", "count": n})` | `f"Approved {n} entries for {resource.name}, week {week}."` |

Verb summary: **9 verbs** — 5 on RAL (`assign`, `substitute` admin-gated; `commit`, `complete`,
`cancel` member-level), 4 on RTE (`submit` member-level; `approve`, `reject`, `approve_week`
admin-gated). All `@require_POST` (GET → 405). Members POSTing admin-gated verbs → 403.

### `capacity_demand` (computed board, no model)

`@login_required`, GET-only. Template `projects/resource/capacity_demand.html`.

- GET param: `?weeks=<int>` — horizon length, clamped to 4..13, default 8. Horizon starts at
  the current ISO week (Monday–Sunday windows).
- Capacity board counts `booking_status in ("soft", "firm")` ONLY (requested placeholders are
  the demand section's data, not supply); demand section counts
  `booking_status in ("requested", "soft")` overlapping the horizon.
- Context keys:
  - `weeks` — int, the chosen horizon length;
  - `week_windows` — list of dicts `{"year": int, "week": int, "start": date, "end": date,
    "label": str}` for the horizon (label e.g. `"W37 · Sep 7"`);
  - `capacity_rows` — list of ACTIVE `ResourceProfile` instances (tenant-scoped, Meta.ordering),
    each decorated in Python (never stored) with `.cells` = one dict per week window
    `{"planned": Decimal, "over": bool}` where `planned` = Σ `allocation.planned_hours(start,
    end)` over that resource's soft/firm allocations and `over = planned > weekly_capacity_hours`;
  - `over_count` — int, number of over-capacity (resource, week) cells (drives the alert line);
  - `demand_rows` — list of `ResourceAllocation` instances (requested/soft, window overlapping
    the horizon; project-linked rows first ordered by `start_date`, then request-linked), each
    decorated with `.demand_label` (project name or request title), `.demand_url_name`
    (`"projects:prj_detail"` / `"projects:prq_detail"` / None), `.demand_url_pk`, `.demand_hours`
    (Σ `planned_hours` over the horizon windows), `.is_gap` (bool — `resource_id is None`, the
    coverage-gap/hiring-trigger flag);
  - `gap_count` — int, `len([r for r in demand_rows if r.is_gap])`.
- The page MUST state the caveat verbatim: "Capacity is uniform weekly hours — leave and
  absence (HRM 3.10) are not deducted yet."

## Templates — `templates/projects/resource/`

All extend `{% extends "base.html" %}`; page-header with breadcrumb rooted at
`{% url 'projects:overview' %}`; `filter-bar` GET form inside a card; `table.table` with a
trailing `<th class="table-actions">Actions</th>`; `{% empty %}` empty-state row;
`{% include "partials/pagination.html" %}`. Detail pages use `dl.detail-grid` and end with
`div.form-actions` (Back link + Delete POST form with `confirm()`). Forms are the shared
create/edit `form.html` (non_field_errors loop + `form-grid` field loop + Save/Cancel), with
`{% if is_edit %}` breadcrumbs/titles.

| file | must contain |
|---|---|
| `resourceprofile/list.html` | Title "Resource Pool". Filter bar: `q` ("Search name, role or skills…"), `resource_type` select from `resource_type_choices` ("All types"), `status` select from `status_choices` ("All statuses"), `org_unit` select from `org_units` ("Any team", `stringformat:"d"` compare). Columns: Resource (name → `rsp_detail` + number muted), Type badge, Role, Team, Capacity (`{{ obj.weekly_capacity_hours }}h / {{ obj.utilization_target_pct }}%`), Status badge (active → `badge-green`, else → `badge-muted`), Actions (eye/pencil/trash with delete confirm). Empty state icon `users`: "No resources match" / "Add the first bookable person to the pool." |
| `resourceprofile/detail.html` | Title `{{ obj.name }}`. detail-grid: Number, Type badge (internal → `badge-info`, contractor → `badge-amber`, freelancer → `badge-muted`, consultant → `badge-slate`), Role, Team, Capacity, Utilization target, Available from/to (`|default:"—"` on plain dd, never around FKs), Status badge, Person (employee → `hrm:employee_detail` link with `{{ obj.employee.party.name }}`; else party name), Notes. **Skills & certifications lens card** (only `{% if obj.employee_id %}`): link `{% url 'hrm:employeeskill_list' %}?employee={{ obj.employee_id }}` with copy noting the matrix/certifications live in HRM (3.40). Page actions: Edit (+ Delete in form-actions). |
| `resourceprofile/form.html` | Shared form; note "A resource is either an HR employee or an external party — exactly one of the two." |
| `resourceallocation/list.html` | Title "Allocations". Filter bar: `q`, `project` select ("Any project"), `project_request` select ("Any request"), `resource` select ("Any resource"), `booking_status` select ("All statuses"), `placeholder` select ("All bookings" / value `True` "Placeholders only" / `False` "Named only"), `is_live` select ("All windows" / `True` "Live now" / `False` "Not live"). Columns: Booking (number + role_name), Project/Request link, Resource (name → `rsp_detail`, or `badge-muted` "Placeholder"), Unit + magnitude (`{{ obj.get_allocation_unit_display }}` + the populated magnitude field), Window (`start – end` or "ongoing" when `end_date` null), Status badge, Actions. Badge map: `requested` → `badge-muted`, `soft` → `badge-amber`, `firm` → `badge-green`, `completed` → `badge-info`, `cancelled` → `badge-red`, `released` → `badge-slate`; `{% if obj.is_live %}` extra `badge-info` "Live". Empty state icon `calendar-range`: "No allocations match" / "Book a person or a placeholder role against a project." |
| `resourceallocation/detail.html` | Page actions (each a POST form with `onsubmit="return confirm(...)"` + `{% csrf_token %}`): **Assign** (admin-gated + `{% if not obj.resource_id and obj.booking_status == 'requested' or obj.booking_status == 'soft' %}`, renders `<select name="resource">` over `resources`) · **Substitute** (admin-gated + `{% if obj.resource_id and obj.booking_status == 'soft' or obj.booking_status == 'firm' %}`, also `<select name="resource">`) · **Commit** (`{% if obj.booking_status == 'requested' or obj.booking_status == 'soft' %}`) · **Complete** (`soft`/`firm`) · **Cancel** (`requested`/`soft`/`firm`). detail-grid: Number, Status badge, Project link or Request link, Task link (if set), Resource or Placeholder badge, Role, Skills required, Unit + magnitude, Window, Substitute of (link if set), Substituted by (`{{ successor.number }}` link if set), Requested by (`obj.requested_by.username` if set), Notes. |
| `resourceallocation/form.html` | Shared form; note "Set only the magnitude matching the allocation unit — the others stay blank. Booking status moves through the commit/assign verbs, never this form." |
| `resourcetimeentry/list.html` | Title "Time Entries". Filter bar: `q`, `status` select ("All statuses"), `resource` select ("Any resource"), `project` select ("Any project"), `year` number input, `week` number input. **Weekly lens**: `{% regroup object_list by week_key as week_groups %}`; per group a subheader `{{ group.list.0.resource.name }} · Week {{ group.list.0.iso_week }}, {{ group.list.0.iso_year }}` + (admin-gated) an **Approve Week** POST button to `{% url 'projects:rte_approve_week' group.list.0.resource_id group.list.0.iso_year group.list.0.iso_week %}`. Row columns: Date, Resource, Project/Task (project link or "Non-project time"; task link if set), Hours, Description, Status badge (`draft` → `badge-muted`, `submitted` → `badge-amber`, `approved` → `badge-green`, `rejected` → `badge-red`), Actions. **Actuals-to-plan section** `id="actuals"` (card below the table): columns Resource, Project, Planned, Actual, Variance (variance badge `badge-red` when positive over-plan, `badge-green` when on/under); renders `actuals_rows`; empty state "No approved time in this window yet." Empty state icon `clock`: "No time entries match" / "Log the first day of project time." |
| `resourcetimeentry/detail.html` | detail-grid: Number, Resource (link), Project/Task, Date, Hours, Description, Status badge, Submitted at, Approved by/at, Decision note (when rejected). Page actions: **Submit** (`{% if obj.status == 'draft' %}`), **Approve** + **Reject** (admin-gated + `{% if obj.status == 'submitted' %}`; the reject form carries `<textarea name="reason">` for the decision note). |
| `resourcetimeentry/form.html` | Shared form; note "Status and approval stamps are verb-driven — they never appear on this form." |
| `capacity_demand.html` (sub-module root) | Title "Capacity & Demand". Caveat line verbatim (see `capacity_demand` above). Over-allocation alert line when `over_count` > 0 (`badge-red` summary "N over-booked resource-weeks"). Capacity table: first column Resource (name → `rsp_detail` + number + `{{ obj.weekly_capacity_hours }}h`), one column per `week_windows` entry (label), cell = planned hours with `badge-red` "Over" when `cell.over`. Then `<section id="demand">` card: intro "Unfilled demand is the hiring/outsourcing trigger — placeholders and soft bookings against pipeline work."; table columns: Booking (number + role_name), Demand on (`demand_label` link via `demand_url_name`/`demand_url_pk`), Hours (`demand_hours`), Window, Status badge, Gap (`{% if r.is_gap %}` `badge-red` "Unassigned"); coverage line "`gap_count` unassigned booking(s) in the horizon". Empty states for both tables. |

## Seeder — `seed_projects.py` block `_resourcing(self, tenant, now)`

Called from `_seed_tenant` after `_planning`. **Own idempotency guard:**
`if ResourceProfile.objects.filter(tenant=tenant).exists(): print skip + return` (same
"already exist. Use --flush to re-seed." wording as `_planning`). Fetches: tenant users
(`get_user_model().objects.filter(tenant=tenant).order_by("id")`), first OrgUnit, tenant
EmployeeProfiles (`from apps.hrm.models import EmployeeProfile` — hrm is installed), the active
project (`Project.objects.filter(tenant=tenant, status="active").first()`), the unconverted
approved request (`ProjectRequest.objects.filter(tenant=tenant, status="approved",
converted_project__isnull=True).first()`). If no users/Party → skip with the standard warning;
if no active project or no unconverted approved request → seed the profiles, warn, and skip the
RAL/RTE rows that would have used them (never crash a partially seeded workspace).

Rows per tenant (all `obj.save()`, never bulk_create):

- **~5 ResourceProfile** (capacities varied so over-allocation is honest): 3 internal from the
  tenant's first EmployeeProfiles — `weekly_capacity_hours` 40, 40, 32; 1 part-timer internal
  at **24h**; 1 **contractor** built from a tenant Party (`resource_type="contractor"`,
  `default_role` set, `available_from = today − 30`, `available_to = today + 90`, 40h). If the
  tenant has fewer EmployeeProfiles than 4, the remaining "internal" rows fall back to
  party-keyed rows (the one-of clean allows party-keyed internals). `skill_summary` filled
  (e.g. "Python, Django, Airflow") so the skills filter facet has data.
- **~10 ResourceAllocation** (start offsets relative to `timezone.localdate()`):
  1. firm named — resource#1, 16h/wk, −14..+28, on the active project;
  2. firm named — resource#2, 12h/wk, −7..+35, `project_task` = the active project's first work
     package (if 7.2 seeded) else None;
  3. soft named — resource#4 (24h part-timer), **`allocation_unit="pct_capacity"`,
     `pct_capacity=50`** (exercises unit 2 against a small denominator);
  4. **placeholder, project-linked** — `resource=None`, `role_name="Data engineer"`,
     `skill_requirements="Python, Airflow"`, `booking_status="requested"`,
     `requested_by` = the active project's manager, +7..+49;
  5. **placeholder, request-linked** — on the unconverted approved PRQ
     (`project_request=…, project=None`), `role_name="Backend developer"`,
     `skill_requirements="Django"`, `booking_status="requested"`, `requested_by` set, +14..+70;
  6. placeholder, project-linked, `booking_status="soft"`, `role_name="QA analyst"`,
     −21..+21 (a second assign-verb target);
  7. completed past booking — resource#1, −90..−30, `booking_status="completed"`;
  8. released booking — resource#2, −28..+28, `booking_status="released"`;
  9. its **successor** — resource#3, same window/magnitude, `booking_status="firm"`,
     `substitute_of=row 8` (the substitution chain);
  10. `allocation_unit="total_hours"`, `total_hours=40`, resource#5, +7..+21 (exercises unit 3).
- **~16 ResourceTimeEntry** across resources #1/#2/#3 and three ISO weeks (last week, this
  week, week before), covering **all four statuses**: ~8 approved past entries (6h each, on the
  active project), 3 submitted this-week (the approval queue for `rte_approve_week`), 2 draft
  this-week, 1 rejected this-week with `decision_note="Client call overran — re-log the extra
  hour under support."`, plus 1 approved **non-project** entry (`project=None`,
  `task_description="Internal training"`), remainder topped up to ~16 across the same
  resources/weeks.
- `--flush` extends the existing children-first block with
  `ResourceTimeEntry → ResourceAllocation → ResourceProfile` (before the 7.2 deletions), and
  the `add_arguments` help string mentions them.

## `LIVE_LINKS["7.3"]` — inserted immediately after the 7.2 block (~`navigation.py:1730`)

```python
    # ----- 7.3 Resource Management -----
    "7.3": {
        "Resource Pool & Skills Inventory":      "projects:rsp_list",
        # The leveling bullet lands on the computed capacity board — bookings vs capacity with
        # over-allocation alerts and the manual-rebalance lens (7.2's lens-on-a-register
        # precedent; the smoothing engine is deliberately not built).
        "Resource Allocation & Leveling":        "projects:capacity_demand",
        "Team Assembly & Role Assignment":       "projects:ral_list",
        # The forecasting bullet is the demand section of the same board (`#demand` fragment —
        # the 6.13 `#search` precedent; `_safe_reverse` supports `url#frag`).
        "Resource Forecasting & Demand Planning": "projects:capacity_demand#demand",
        "Time Tracking & Timesheets":            "projects:rte_list",
        # Extra live leaf: the approval queue is the register's `?status=submitted` lens.
        "Time Approvals":                        "projects:rte_list?status=submitted",
    },
```

The five NavERP.md bullet names are verbatim; "Time Approvals" is the extra live leaf
(non-bullet labels are appended by the parser — 7.2's "Task Register" precedent). The
`rsp_detail` skills/certs lens deep-link is `{% url 'hrm:employeeskill_list' %}?employee=<pk>`
(3.40's page; its `employee` filter renders for tenant admins).

## Wire-up (Integrate — single writer, one file per commit)

1. **Migration `0004_<auto>`** — `makemigrations projects`; creates the three tables + 12
   named indexes.
2. **`urls/__init__.py`** — imports (alphabetical, after the `_pp_*` block):
   `from .ResourceManagement.CapacityDemand import urlpatterns as _rm_capacitydemand`,
   `from .ResourceManagement.ResourceAllocations import urlpatterns as _rm_allocations`,
   `from .ResourceManagement.ResourceProfiles import urlpatterns as _rm_profiles`,
   `from .ResourceManagement.ResourceTimeEntries import urlpatterns as _rm_timeentries`;
   concatenate `+ _rm_profiles + _rm_allocations + _rm_timeentries + _rm_capacitydemand` after
   `_pp_baselines` with the disjoint-first-segments comment.
3. **`models/__init__.py`**:
   ```python
   # --- 7.3 Resource Management ------------------------------------------------------------------
   from .ResourceManagement.ResourceAllocations import ResourceAllocation  # noqa: F401
   from .ResourceManagement.ResourceProfiles import ResourceProfile  # noqa: F401
   from .ResourceManagement.ResourceTimeEntries import ResourceTimeEntry  # noqa: F401
   ```
4. **`forms/__init__.py`**:
   ```python
   # --- 7.3 Resource Management ------------------------------------------------------------------
   from .ResourceManagement.ResourceAllocations import ResourceAllocationForm  # noqa: F401
   from .ResourceManagement.ResourceProfiles import ResourceProfileForm  # noqa: F401
   from .ResourceManagement.ResourceTimeEntries import ResourceTimeEntryForm  # noqa: F401
   ```
5. **`views/__init__.py`** (alphabetized within each import, house style):
   ```python
   # --- 7.3 Resource Management ------------------------------------------------------------------
   from .ResourceManagement.CapacityDemand import capacity_demand  # noqa: F401
   from .ResourceManagement.ResourceAllocations import (  # noqa: F401
       ral_assign,
       ral_cancel,
       ral_commit,
       ral_complete,
       ral_create,
       ral_delete,
       ral_detail,
       ral_edit,
       ral_list,
       ral_substitute,
   )
   from .ResourceManagement.ResourceProfiles import (  # noqa: F401
       rsp_create,
       rsp_delete,
       rsp_detail,
       rsp_edit,
       rsp_list,
   )
   from .ResourceManagement.ResourceTimeEntries import (  # noqa: F401
       rte_approve,
       rte_approve_week,
       rte_create,
       rte_delete,
       rte_detail,
       rte_edit,
       rte_list,
       rte_reject,
       rte_submit,
   )
   ```
6. **`views/_helpers.py`** — add `resource_profiles(tenant)` + `project_requests(tenant)`
   (`.none()` for tenant None; ordered for dropdowns).
7. **`admin.py`** — house decorator style, `list_display` led by `number`, `list_select_related`,
   readonly stamps:
   ```python
   @admin.register(ResourceProfile)
   class ResourceProfileAdmin(admin.ModelAdmin):
       list_display = ("number", "resource_type", "default_role", "org_unit",
                       "weekly_capacity_hours", "status", "tenant")
       list_filter = ("resource_type", "status")
       list_select_related = ("tenant", "org_unit", "employee__party", "party")
       search_fields = ("number", "skill_summary")
       readonly_fields = ("created_at", "updated_at")

   @admin.register(ResourceAllocation)
   class ResourceAllocationAdmin(admin.ModelAdmin):
       list_display = ("number", "role_name", "project", "resource", "allocation_unit",
                       "start_date", "end_date", "booking_status", "tenant")
       list_filter = ("booking_status", "allocation_unit")
       list_select_related = ("tenant", "project", "project_request", "resource")
       search_fields = ("number", "role_name", "skill_requirements")
       readonly_fields = ("created_at", "updated_at")

   @admin.register(ResourceTimeEntry)
   class ResourceTimeEntryAdmin(admin.ModelAdmin):
       list_display = ("number", "resource", "project", "entry_date", "hours", "status", "tenant")
       list_filter = ("status",)
       list_select_related = ("tenant", "resource", "project", "approved_by")
       search_fields = ("number", "task_description")
       readonly_fields = ("created_at", "updated_at", "submitted_at", "approved_at", "approved_by")
   ```
8. **Overview** — `views/ProjectInitiation/Overview.py` adds three flat counts (one COUNT each,
   same style as the 7.2 block): `resource_count`, `allocation_count`, `time_entry_count`.
   `templates/projects/overview.html`: three stat cards after "Baselines" — `resource_count`
   (`stat-icon blue`, lucide `users`, label "Resources"), `allocation_count`
   (`stat-icon orange`, lucide `calendar-range`, label "Allocations"), `time_entry_count`
   (`stat-icon green`, lucide `clock`, label "Time entries"); four quick-link rows in the
   "Start here" table (Resource Pool → `projects:rsp_list`, Allocations → `projects:ral_list`,
   Time Entries → `projects:rte_list`, Capacity & Demand → `projects:capacity_demand`); update
   the muted intro copy (~line 8) to mention the 7.3 resourcing layer.

## Verify (what smoke + reviewers diff)

- `makemigrations projects` → `0004`; `migrate`; `seed_projects` twice (second run no-op
  without `--flush`); `manage.py check` + `makemigrations --check` clean.
- `temp/smoke_73.py` as **admin_acme / password**: all 25 routes GET 200 with CONTENT asserts
  (page titles, seeded RSP/RAL/RTE numbers, the `id="demand"` and `id="actuals"` sections, no
  `{#`/`{% comment` leaks); junk params (`?status=nope`, `?resource=0`, `?page=9999`) → default
  page, never 500; page 2 of `rte_list`; every verb GET → 405; member users → 403 on the five
  admin-gated verbs; cross-tenant `<int:pk>` IDOR → 404 on all three entities; sidebar shows
  "7.3 Live" with the five bullets + Time Approvals leaf.

## Divergences (research/todo wording vs the pinned CODE way)

1. **Template slug.** Research floated `templates/projects/resourcing/<entity-slug>/` with the
   slug "the todo agent's to finalize"; the build todo pins **`templates/projects/resource/`**
   with folders `resourceprofile/ resourceallocation/ resourcetimeentry/`. Pinned as the todo.
2. **Weekly grouping is template-side, within the paginated page.** Research says "list view
   grouped by resource + ISO week"; the house register shape is `crud_list`'s flat pagination,
   so grouping is `{% regroup object_list by week_key %}` over the current page (a person-week
   may straddle pages — accepted). No header model, no separate weekly route.
3. **"Narrowed per tenant" FK choices need no bespoke `__init__`.** `core.TenantModelForm`
   auto-scopes every ModelChoiceField whose target carries `tenant`; the forms add only
   `_reject_foreign`. (Verified in `apps/core/forms/_common.py`.)
4. **`?year=` maps to `entry_date__iso_year`, not `__year`.** Django's `week` lookup is already
   ISO-8601; pairing it with the calendar-year lookup would mis-bucket the ISO year boundary.
5. **`?year=0`/`?week=0` empty the register instead of falling back** — they are non-pk int
   filters, so `crud_list`'s zero-guard does not apply. Smoke's junk-param asserts use
   `?status=nope` / `?resource=0` / `?page=9999` exactly as listed above.
6. **`Meta.ordering` choices the research left open, pinned here:** RSP name-ordered via joins
   (pool register = people list); RAL `["-start_date","-id"]` (window-ordered; the pinned
   `("tenant","start_date")` index serves it — no `created_at` index exists in this pass);
   RTE `["resource_id","-entry_date","-id"]` (keeps person-week blocks contiguous for the
   regroup).
7. **`completed` badge pinned `badge-info`** — the todo pinned the other five booking-status
   badge colours but not `completed`.
8. **Capacity vs demand split pinned.** The capacity board sums `soft`+`firm` only;
   `requested` placeholders (project- and request-linked) appear only in the `id="demand"`
   section. `released` bookings count zero via `planned_hours` (the research table only
   excluded `cancelled` — the released successor must not double-count).
9. **`rte_submit` is allowed only from `draft`.** A rejected entry cannot be resubmitted —
   the approved/rejected lock rule (todo: "approved/rejected rows refuse edit/delete") wins;
   re-log instead. The decision note explains the rejection.
10. **The HRM skills lens employee filter is admin-only** in `hrm.employeeskill_list`, so the
    `rsp_detail` deep link `?employee=<pk>` narrows the lens only for tenant admins; members
    land on the full lens. Link target unchanged.
11. **Prefix check re-verified:** no `RSP`/`RAL`/`RTE` `NUMBER_PREFIX` anywhere in
    `apps/*/models/` (the only case-insensitive grep hits were path-name false positives in
    `GeneralLedger/JournalEntries.py` and `OfferLetterTemplate.py`).
