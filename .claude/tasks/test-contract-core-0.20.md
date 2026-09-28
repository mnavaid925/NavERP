# Test contract — 0.20 Admin Console & System Operations

**Subslug:** `adminconsole` · **App:** `core` · **Phase:** 6, step 1 · **BASE:** `6d64a8e`
**Lanes:** `test_adminconsole_models.py` → `_forms.py` → `_views.py` → `_security.py`, one at a time.

Every test function is named `test_adminconsole_*` and every module-level helper
`_adminconsole_*`, so the sub-modules appending nearby (0.21 `cml021_`, 0.18 `sec_`, 0.17 `mon_`,
0.16 `bkp_`, 0.15 `localization_`) cannot shadow them. The conftest block is `ac0_`-prefixed for
the same reason (L43).

**Every name below was read out of the code, not inferred.** A name invented here becomes a
`NoReverseMatch` or a blank region (L7/L8) three files from now.

> Rewritten from scratch twice. The first draft's tail was scrambled by an interrupted write, and
> the rebuild then mis-placed two sections. This file is now assembled strictly top-down, and
> every claim in it was re-read against the sources in §0.

---

## 0. The files this contract is pinned against

| concern | file |
|---|---|
| models | `apps/core/models/JobScheduler.py` (`JobDefinition`, `JobRun`), `apps/core/models/Maintenance.py` (`MaintenanceWindow`), `apps/core/models/Change.py` (`ChangeRequest`, `FeatureRollout`) |
| forms | `apps/core/forms/AdminConsole.py` (all five) |
| form base | `apps/core/forms/_common.py` → `TenantModelForm` |
| views | `apps/core/views/AdminConsole.py` |
| routes | `apps/core/urls.py` lines 273–318 (the 0.20 block) + the `crud()` factory at lines 8–16 |
| CRUD helpers | `apps/core/crud.py` → `crud_list`, `crud_create`, `crud_edit`, `crud_detail`, `crud_delete`, `as_db_int` |
| numbering board | `apps/core/settings_engine.py` → `LITERAL_PREFIX_MODELS` (0.20 entries at lines 183–186) |
| migration | `apps/core/migrations/0017_changerequest_featurerollout_jobdefinition_jobrun_and_more.py` |
| templates | `templates/core/{jobdefinition,jobrun,maintenancewindow,changerequest,featurerollout}/{list,detail,form}.html` + `core/adminboard.html`, `core/supportboard.html`, `core/bulkboard.html`, `core/opstrail.html` |

Spine rows 0.20 points **at** rather than re-declares (L29/L36): `core.SyncSchedule` (0.13),
`core.EnvironmentInstance` (0.16), `core.FeatureFlag` (0.10), `core.ServiceComponent`,
`core.AlertRule`, `core.NotificationRule`, `core.Incident` (0.17), `accounts.User`.

---

## 1. The five models — real field names and real CHOICES

### 1.1 `JobDefinition` — `JOB-#####` (`models/JobScheduler.py`)

Fields, in declaration order: `tenant`, `number` (`CharField(max_length=20, editable=False)`),
`name`, `module_slug`, `job_type`, `description`, `schedule_kind`, `cron_expression`,
`interval_minutes`, `handler_path`, `sync_schedule` (FK `core.SyncSchedule`, SET_NULL),
`environment` (FK `core.EnvironmentInstance`, SET_NULL), `is_active`, `priority`,
`timeout_seconds`, `max_active_runs`, `pool_name`, `pool_slots`, `max_consecutive_failures`,
`auto_pause_after`, `last_run_at`, `next_run_at`, `is_muted`, `notes`, `created_at`
(`auto_now_add`). `Meta.ordering = ["name"]`, two indexes, **no `unique_together`**.
**No `clean()`.** `__str__` → `"%s %s" % (self.number, self.name)`.

- `JOB_TYPE_CHOICES` (re-exposed as `JobDefinition.JOB_TYPE_CHOICES`) = `scheduled_task`,
  `integration_sync`, `bulk_operation`, `report`, `cleanup`, `maintenance`; default
  `scheduled_task`.
- `SCHEDULE_KIND_CHOICES` — **reused BY REFERENCE**: `JobDefinition.SCHEDULE_KIND_CHOICES is
  SyncSchedule.FREQUENCY_CHOICES`. Assert with `is`, not `==` (Django normalises a *field's*
  `choices` into a fresh list, so identity is only observable on the class). Values are
  `manual`, `hourly`, `daily`, `weekly`; default `manual`.
- `priority` default `100`; `max_active_runs` default `1`; `pool_slots` default `1`;
  `max_consecutive_failures` default `3`; `auto_pause_after` default `10`; `is_muted` default
  `False`; `is_active` default `True`. `last_run_at` / `next_run_at` default `None` and **nothing
  advances them** — there is no scheduler, so `None` is the honest default, not a bug.
- `number` is minted in `save()` by `next_number(JobDefinition, self.tenant, "JOB")` with a
  5-attempt `IntegrityError` retry; a row saved with `number` already set is left alone.

### 1.2 `JobRun` — `RUN-#####` (`models/JobScheduler.py`)

Fields: `tenant`, `number` (editable=False), `job` (FK `JobDefinition`, CASCADE,
`related_name="runs"`), `triggered_at` (**`auto_now_add`**), `started_at`, `finished_at`,
`trigger_kind`, `status`, `is_dry_run` (**default `True`**), `triggered_by` (FK `accounts.User`,
SET_NULL, `related_name="+"`), `exit_code`, `records_processed`, `duration_ms`, `error_message`,
`notes`. `Meta.ordering = ["-triggered_at", "-id"]`.
`__str__` → `"%s %s" % (self.number, self.get_status_display())`.

- `TRIGGER_KIND_CHOICES` = `manual`, `scheduled`, `backfill`, `api`; default `manual`.
- `STATUS_CHOICES` / `JOB_RUN_STATUS_CHOICES` = `queued`, `running`, `success`, `failed`,
  `skipped`, `cancelled`; default `queued`.

`clean()` guards — each keyed on a field that **is** on the form, so each surfaces as a real form
error rather than a non-field one:

| condition | key | message |
|---|---|---|
| `status == "success"` and no `finished_at` | `finished_at` | "A successful run must record when it finished." |
| `status == "failed"` and blank `error_message` | `error_message` | "A failed run must say what went wrong." |
| `status == "failed"` and no `finished_at` | `finished_at` | "A failed run must record when it finished." |
| `finished_at < started_at` | `finished_at` | "A run cannot finish before it started." |

### 1.3 `MaintenanceWindow` — `MNTW-#####` (`models/Maintenance.py`)

Fields: `tenant`, `number` (editable=False), `title`, `purpose`, `starts_at` (**required**),
`ends_at` (**required**), `recurrence`, `timezone_label`, `status`, `ended_at`,
`affected_services` (M2M `core.ServiceComponent`), `suppressed_alert_rules` (M2M
`core.AlertRule`), `suppressed_notification_rules` (M2M `core.NotificationRule`), `incident`
(FK `core.Incident`, SET_NULL, `related_name="+"`), `environment` (FK
`core.EnvironmentInstance`, SET_NULL), `change_request` (FK `core.ChangeRequest`, SET_NULL),
`suppresses_jobs`, `blocks_admin_writes`, `notes`, `created_at` (`auto_now_add`).
`Meta.ordering = ["-starts_at", "-id"]`. `__str__` → `"%s %s" % (self.number, self.title)`.

- `RECURRENCE_CHOICES` = `once`, `daily`, `weekly`, `monthly`; default `once`.
- `STATUS_CHOICES` / `WINDOW_STATUS_CHOICES` = `draft`, `scheduled`, `active`, `ended_early`,
  `completed`, `cancelled`; default `draft`.
- Module constant `FUTURE_STATUSES = ("draft", "scheduled")` — **declared but never read by the
  delete guard**, which reads the `is_future` property. Assert the property is what the view uses;
  do not "fix" the view to use the tuple (the property is the one with a timestamp in it).

`clean()` guards — note which key each uses, because the key decides whether it renders or 500s:

| condition | key | message |
|---|---|---|
| no `starts_at` | `starts_at` | "A maintenance window must say when it opens." |
| no `ends_at` | `ends_at` | "A maintenance window must say when it closes." |
| `ends_at < starts_at` | `ends_at` | "A window cannot close before it opens." |
| `status == "ended_early"` and no `ended_at` | `NON_FIELD_ERRORS` | "An ended-early window must record when it was ended." |
| `ended_at > ends_at` | `NON_FIELD_ERRORS` | "A window cannot be ended after it was due to close." |

The last two are keyed on `NON_FIELD_ERRORS` **deliberately**: `ended_at` is excluded from
`MaintenanceWindowForm`, and `ModelForm` routes a `ValidationError` key through `add_error()`,
which raises `ValueError` for a key that is not a form field — that is what turned an ordinary
dropdown choice into a 500. A regression test must assert the error **lands in
`form.non_field_errors()`**, not that it raises.

### 1.4 `ChangeRequest` — `CHG-#####` (`models/Change.py`)

Fields: `tenant`, `number` (editable=False), `title`, `summary`, `change_type`, `risk_level`,
`impact_level`, `status`, `environment` (FK `core.EnvironmentInstance`, SET_NULL), `requestor`
(FK `accounts.User`, SET_NULL, `related_name="+"`), `approved_by` (FK `accounts.User`, SET_NULL,
`related_name="+"`), `requested_at`, `approved_at`, `implemented_at`, `rollback_reason`,
`rollback_at`, `post_review`, `downtime_required`, `notes`, `created_at` (`auto_now_add`).
`Meta.ordering = ["-created_at", "-id"]`. `__str__` → `"%s %s" % (self.number, self.title)`.

- `CHANGE_TYPE_CHOICES` = `standard`, `normal`, `emergency`; default `normal`.
- `RISK_LEVEL_CHOICES` = `low`, `medium`, `high`; default `medium`. **Deliberately NOT
  `AlertRule.SEVERITY_CHOICES`** — assert `is not`, with a comment, so nobody "unifies" it.
- `IMPACT_LEVEL_CHOICES` = `minor`, `moderate`, `major`; default `minor`.
- `STATUS_CHOICES` / `CHANGE_STATUS_CHOICES` = `draft`, `submitted`, `approved`, `rejected`,
  `scheduled`, `in_progress`, `completed`, `rolled_back`, `cancelled`; default `draft`.

`clean()` guards — **all four keyed on `NON_FIELD_ERRORS`**, because `approved_by` and
`approved_at` are both off the form and a keyed error would 500 the save:

| condition | message |
|---|---|
| `status == "approved"` and no `approved_by_id` | "An approved change must name its approver." |
| `status == "approved"` and no `approved_at` | "An approved change must record when." |
| `status == "rolled_back"` and blank `rollback_reason` | "A rollback must say why." |
| `status == "rolled_back"` and no `rollback_at` | "A rollback must record when." |

`submitted` and `completed` place **no** rule in `clean()` — a row in either state is always
saveable, which is exactly what makes them the right fixture states (§8).


### 1.5 `FeatureRollout` — **no number, no prefix** (`models/Change.py`)

Fields: `tenant`, `change` (FK `ChangeRequest`, CASCADE, `related_name="rollouts"`),
`feature_flag` (FK `core.FeatureFlag`, CASCADE, `related_name="rollouts"`), `stage`, `percentage`
(`PositiveSmallIntegerField`, `MaxValueValidator(100)`, default `0`), `cohort_label`,
`scheduled_at`, `started_at`, `completed_at`, `status`, `notes`.
`Meta.ordering = ["stage", "id"]` and
**`unique_together = (("change", "feature_flag"),)`** — a child row with no number column.
`__str__` → `"%s / %s (%d%%)" % (self.change.number, self.get_stage_display(), self.percentage)`.

- `STAGE_CHOICES` / `ROLLOUT_STAGE_CHOICES` = `internal` ("Internal only"), `pilot`, `partial`,
  `general` ("General availability"); default `internal`.
- `STATUS_CHOICES` / `ROLLOUT_STATUS_CHOICES` = `planned`, `running`, `paused`, `completed`,
  `rolled_back`; default `planned`.

`clean()` guards — the ladder bookends are **exact**, and the last two are keyed on
`NON_FIELD_ERRORS` because `completed_at` / `started_at` are off the form:

| condition | key | message |
|---|---|---|
| `stage == "internal"` and `percentage != 0` | `percentage` | "An internal-only stage reaches no users (0%)." |
| `stage == "general"` and `percentage != 100` | `percentage` | "General availability is 100%." |
| `stage == "partial"` and not `0 < percentage < 100` | `percentage` | "A partial stage must be between 1% and 99%." |
| `status == "completed"` and no `completed_at` | `NON_FIELD_ERRORS` | "A completed stage must record when it finished." |
| `completed_at < started_at` | `NON_FIELD_ERRORS` | "A stage cannot finish before it started." |

### 1.6 Tenancy

All five carry `tenant = FK("core.Tenant", CASCADE, db_index=True)` and every view filters
`tenant=request.tenant`, including all six verbs. A tenant-less (superuser) request sees **empty**
lists by design, and `crud_create` refuses outright when `request.tenant is None`
(`messages.error` + redirect to `dashboard:home`) rather than creating an orphan row.

---

## 2. The five forms — exact `Meta.fields` and exclusions

All five subclass `TenantModelForm` (`forms/_common.py`), which (a) rewrites every `DateTimeField`
to a `datetime-local` `DateTimeInput` with `input_formats = ["%Y-%m-%dT%H:%M",
"%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]` and every `DateField` to `%Y-%m-%d`, and (b) narrows
every `ModelChoiceField` whose model has a `tenant` field to `tenant=<the one passed in>` **when
`tenant=` is not `None`**. `tenant` is on **none** of these five forms — `crud_create`/`crud_edit`
stamp it from `request.tenant` via `form.save(commit=False)` + `obj.save()` + `form.save_m2m()`.
Note M2M fields are `ModelMultipleChoiceField`, **not** `ModelChoiceField`, so that tenant
narrowing does **not** apply to `affected_services` / `suppressed_alert_rules` /
`suppressed_notification_rules`. Do not assert a queryset guard there that the code lacks.

### `JobDefinitionForm` — 20 fields
```
name, module_slug, job_type, description, schedule_kind, cron_expression, interval_minutes,
handler_path, sync_schedule, environment, is_active, priority, timeout_seconds, max_active_runs,
pool_name, pool_slots, max_consecutive_failures, auto_pause_after, is_muted, notes
```
Excluded: `tenant`, `number` (`editable=False`), **`last_run_at`**, **`next_run_at`**, `created_at`.
`handler_path` **stays editable** — recording the declared target is the point of the register;
the model's `help_text` says nothing imports it. No `__init__` narrowing. Required: `name`,
`module_slug`, `handler_path`.

### `JobRunForm` — 10 fields
```
job, trigger_kind, status, started_at, finished_at, exit_code, records_processed, duration_ms,
error_message, notes
```
Excluded: `tenant`, `number`, **`triggered_at`**, **`triggered_by`**, **`is_dry_run`**.
`is_dry_run` is dropped for the same reason it defaults `True`: nothing here can legitimately clear
it, so a checkbox that could would edit a dry run into asserting a real one. No `__init__`
narrowing. **There is no create route and no Add button** — the form exists to correct a recorded
outcome. Required: `job`.


### `MaintenanceWindowForm` — 16 fields
```
title, purpose, starts_at, ends_at, recurrence, timezone_label, status, affected_services,
suppressed_alert_rules, suppressed_notification_rules, incident, environment, change_request,
suppresses_jobs, blocks_admin_writes, notes
```
Excluded: `tenant`, `number`, **`ended_at`**, `created_at`. `__init__` narrows `status` to
`authorable={"draft", "scheduled", "active", "completed", "cancelled"}` — `ended_early` is dropped
because only the verb can write `ended_at`. `suppresses_jobs` / `blocks_admin_writes` **stay
editable** (stating the intent is the operator's job; each carries a `help_text`).
Required: `title`, `starts_at`, `ends_at`.

### `ChangeRequestForm` — 9 fields
```
title, summary, change_type, risk_level, impact_level, status, environment, downtime_required, notes
```
Excluded: `tenant`, `number`, **`requestor`**, **`approved_by`**, **`requested_at`**,
**`approved_at`**, **`implemented_at`**, **`rollback_at`**, **`rollback_reason`**,
**`post_review`**, `created_at`. `__init__` narrows `status` to `authorable={"draft"}` — **only**
`draft`. Every other lifecycle value needs a stamp this form cannot supply. Required: `title`.

### `FeatureRolloutForm` — 8 fields
```
change, feature_flag, stage, percentage, cohort_label, scheduled_at, status, notes
```
Excluded: `tenant`, **`started_at`**, **`completed_at`**. `__init__` narrows `status` to
`authorable={"planned", "running", "paused", "rolled_back"}` — `completed` needs `completed_at`.
**The one hand-written rule in the sub-module:** `clean_feature_flag()` refuses a second stage for
the same flag under the same change, scoped with `.exclude(pk=self.instance.pk)` on edit. It
exists because a `unique_together` is **never** validated by a `ModelForm` —
`Model._get_unique_checks()` only sees fields in `Meta.fields` — so without it a duplicate is a 500
rather than a field error. Required: `change`, `feature_flag`.

### The narrowing helper — `_narrow_status(form, status_choices, authorable)`
Sets `form.fields["status"].widget.choices` to the `authorable` subset **plus the instance's
current status labelled `"<Label> (current)"`** when the instance is saved and its status sits
outside `authorable`. An unsaved instance has nothing to preserve, so a create form offers only
`authorable`. The regression to guard: the current value must stay selectable on edit, or the
browser posts `""` and the status is silently blanked.

### L20/L22 — the negative-form assertions
Assert these names are absent from the **constructed** form's `fields` (never by reading source):
`tenant`, `number`, `created_at`, `last_run_at`, `next_run_at`, `triggered_at`, `triggered_by`,
`is_dry_run`, `ended_at`, `requestor`, `approved_by`, `requested_at`, `approved_at`,
`implemented_at`, `rollback_at`, `rollback_reason`, `post_review`, `started_at` (rollout),
`completed_at` (rollout).

---

## 3. The six derived properties

None of these is a stored column; each must be tested against the model, not against a template.

| property | model | exact behaviour |
|---|---|---|
| `is_open` | `JobRun` | `self.status in ("queued", "running")` — True for 2 of the 6 statuses; `success`, `failed`, `skipped`, `cancelled` are all terminal. |
| `duration_display` | `JobRun` | `"—"` (em dash, U+2014) when **either** `started_at` or `finished_at` is missing; otherwise `"%d ms" % max(0, int((finished_at - started_at).total_seconds() * 1000))`. **Never `0`** — a run that took no measurable time and a run nobody measured are different statements. |
| `is_future` | `MaintenanceWindow` | `bool(self.starts_at) and self.starts_at > timezone.now()`. **This is the deletability rule** the `maintenancewindow_delete` guard reads. |
| `is_current` | `MaintenanceWindow` | `bool(starts_at) and bool(ends_at) and starts_at <= now < ends_at` — half-open, so a window is never both `is_future` and `is_current`. |
| `duration_human` | `MaintenanceWindow` | `"—"` when either end is missing; `"0m"` when `seconds <= 0`; `"%dh %dm"` when both non-zero; `"%dh"` when hours only; `"%dm"` when minutes only. |
| `rollout_count` | `ChangeRequest` | `len(self._prefetched_objects_cache["rollouts"])` when prefetched, else `self.rollouts.count()`. **Prefetch-aware on purpose.** Pin (a) it agrees with `.count()` either way, and (b) it must **never** become an `annotate()` alias of the same name — a `property` is a data descriptor, `ModelIterable` cannot `setattr` it, and the query dies with `AttributeError: can't set attribute` the first time a row is instantiated (L57, which shipped twice in 0.21). `changerequest_detail` passes `prefetch_related=("rollouts",)`. |


---

## 4. The four number prefixes and the numbering board

`next_number()` (`apps/core/utils.py`) mints `PREFIX-#####` scoped by `(tenant, prefix)`, and all
four are minted by a **hardcoded literal in `save()`**, not by a `NUMBER_PREFIX` class attribute.
That is precisely why they must be registered in `core.settings_engine.LITERAL_PREFIX_MODELS`,
whose values are `app_label.ModelName` strings:

| prefix | model | registered? |
|---|---|---|
| `JOB` | `core.JobDefinition` | yes — `settings_engine.py` line 183 |
| `RUN` | `core.JobRun` | yes — line 184 |
| `MNTW` | `core.MaintenanceWindow` | yes — line 185 |
| `CHG` | `core.ChangeRequest` | yes — line 186 |
| — | `core.FeatureRollout` | **deliberately absent** — a child row with no number column at all |

Tests: assert each number matches `^(JOB|RUN|MNTW|CHG)-\d{5}$` after `save()`; assert numbering is
per-tenant (tenant B's first `JobDefinition` is also `JOB-00001`); assert re-saving a row does not
re-mint; and assert `LITERAL_PREFIX_MODELS["JOB"] == ["core.JobDefinition"]` (plus the other
three), so a prefix can never be reported as "configured but minted by no model" — the false
negative the SINV and 0.19 comments describe.

---

## 5. All 34 `core:` url names for 0.20

`app_name = "core"`. Every name below is declared in `apps/core/urls.py` lines 273–318. Every view
is `@tenant_admin_required` (→ `@login_required`, then `PermissionDenied` for a non-admin tenant
member). **Order is behaviour**: the literal `ops/` segments come first, then the `crud()` groups,
then the longhand `jobrun` block, then the POST-only verbs **after** the group that owns them.

| # | name | path | view |
|---|---|---|---|
| 1 | `core:admin_board` | `ops/board/` | `admin_board` |
| 2 | `core:support_board` | `ops/support/` | `support_board` |
| 3 | `core:bulk_board` | `ops/bulk/` | `bulk_board` |
| 4 | `core:ops_audit_trail` | `ops/audit/` | `ops_audit_trail` |
| 5 | `core:bulk_preview` | `ops/bulk/preview/` | `bulk_preview` — **POST-only** |
| 6–10 | `core:jobdefinition_list` / `_create` / `_detail` / `_edit` / `_delete` | `ops/jobs/`, `ops/jobs/add/`, `ops/jobs/<int:pk>/`, `…/edit/`, `…/delete/` | `crud("ops/jobs", "jobdefinition")` |
| 11–15 | `core:maintenancewindow_list` / `_create` / `_detail` / `_edit` / `_delete` | `ops/maintenance-windows/…` | `crud("ops/maintenance-windows", "maintenancewindow")` |
| 16–20 | `core:changerequest_list` / `_create` / `_detail` / `_edit` / `_delete` | `ops/changes/…` | `crud("ops/changes", "changerequest")` |
| 21–25 | `core:featurerollout_list` / `_create` / `_detail` / `_edit` / `_delete` | `ops/rollouts/…` | `crud("ops/rollouts", "featurerollout")` |
| 26 | `core:jobrun_list` | `ops/job-runs/` | `jobrun_list` |
| 27 | `core:jobrun_detail` | `ops/job-runs/<int:pk>/` | `jobrun_detail` |
| 28 | `core:jobrun_edit` | `ops/job-runs/<int:pk>/edit/` | `jobrun_edit` |
| 29 | `core:jobrun_delete` | `ops/job-runs/<int:pk>/delete/` | `jobrun_delete` — POST-only |
| 30 | `core:jobdefinition_run_now` | `ops/jobs/<int:pk>/run-now/` | **POST-only verb** |
| 31 | `core:maintenance_window_end_now` | `ops/maintenance-windows/<int:pk>/end-now/` | **POST-only verb** |
| 32 | `core:change_request_submit` | `ops/changes/<int:pk>/submit/` | **POST-only verb** |
| 33 | `core:change_request_approve` | `ops/changes/<int:pk>/approve/` | **POST-only verb** |
| 34 | `core:change_request_rollback` | `ops/changes/<int:pk>/rollback/` | **POST-only verb** |

**Every `_delete` route is POST-only too** (`@require_POST` above `@tenant_admin_required`, then
`crud_delete`, which re-checks `request.method == "POST"` itself). A GET on any delete must be
**405** and must not delete.

**`core:jobrun_create` does not exist, and must not.** `jobrun` is the one entity that bypasses the
`crud()` factory: a `JobRun` is written by the `run_now` verb and the seeder, never by a person, so
there is no create route at all. `reverse("core:jobrun_create")` must raise `NoReverseMatch` — that
is the test.

**`@require_POST` sits ABOVE the role gate on purpose** (decorators apply bottom-up), so a GET on a
verb is refused as a method error before the role gate is consulted. Assert what the code actually
does per route rather than assuming one consistent 302.


---

## 6. The six POST-only verbs — guard and refusal

Each re-reads the row with `get_object_or_404(..., tenant=request.tenant)` **before** writing
anything, so a hand-made POST cannot reach the write and **no audit row is written for a refusal**.
Every refusal is `messages.error(...)` + `redirect(...)` → **302**, never a 4xx and never a 200
re-render. Every success writes an `AuditLog` row and redirects to the owning entity's detail page
— except `bulk_preview`, which redirects to `core:bulk_board`.

| # | verb | guard | on refusal | on success |
|---|---|---|---|---|
| 1 | `jobdefinition_run_now` | **none** — any job status is accepted, and `is_active` is *not* consulted | — (never refuses) | creates exactly one `JobRun(status="queued", trigger_kind="manual", is_dry_run=True, triggered_by=request.user)` with the fixed "no scheduler exists" note; **leaves `last_run_at` / `next_run_at` untouched**; audit action `run_now`; message says "Run recorded — no job was executed"; redirects to `core:jobdefinition_detail` |
| 2 | `maintenance_window_end_now` | `status in ("draft", "cancelled")` → nothing to end; **or** `ended_at is not None or status == "ended_early"` → already ended | 302 to detail: "has not started — there is nothing to end." / "has already been ended (at %s)." | sets `status="ended_early"` + `ended_at=timezone.now()` via `save(update_fields=[...])`; audit `end_now`; message says no alerts were silenced |
| 3 | `change_request_submit` | `status != "draft"` | 302 to detail, "%s is %s — only a draft can be submitted." | `status="submitted"`, `requested_at=now`, `requestor=request.user`; audit `submit` |
| 4 | `change_request_approve` | `status != "submitted"` | 302 to detail, "only a submitted change can be approved." | `status="approved"`, `approved_at=now`, `approved_by=request.user`; audit `approve` |
| 5 | `change_request_rollback` | `status != "completed"`, **and** blank `request.POST["rollback_reason"]` | 302 to detail, "only a completed change can be rolled back." / "A rollback must state its reason…" | `status="rolled_back"`, `rollback_reason` (stripped), `rollback_at=now`; audit `rollback` |
| 6 | `bulk_preview` | `request.POST["tool"]` not in `BULK_AFFECTED` — an unrecognised name is **refused, never defaulted**, so a hand-made POST cannot reach a lookup with a key that does not exist | 302 to `core:bulk_board`, "Choose one of the listed tools to preview." | `messages.info` with the count; audit action **`update`** carrying `{"verb": "bulk_preview", "tool", "would_affect", "executed": False}` — the verb goes in `changes`, never in the 10-char `action` column. **Writes no domain row**: the only DB access is `.count()` |

`BULK_AFFECTED` keys (all six): `rebuild_derived_totals`, `backfill_numbering`,
`normalize_module_slugs`, `recalculate_balances`, `purge_orphaned_relations`, `reindex_search`.
Three count `0` by construction (accounting owns the ledger, CASCADE leaves no orphans, search has
no separate index) — a `0` there means "nothing to do", and the board's note says so.

Also POST-only, and the one delete with a **state** guard: `core:maintenancewindow_delete` refuses
when `not obj.is_future` (`messages.error` + 302 to `core:maintenancewindow_detail`) and succeeds
only for a future window. A window somebody ran is evidence an incident review may need.

---

## 7. Context keys per view (L7 — pin every one, not just the list var)

`crud_list` always contributes `object_list`, `page_obj`, `q` (`crud.py` line 181), then
`extra_context`. `crud_create` → `form`, `is_edit=False`. `crud_edit` → `form`, `obj`,
`is_edit=True`. `crud_detail` → `obj`. Every 0.20 view adds `notes` = `OPS_NOTES` (3 lines).

| view | extra keys |
|---|---|
| `jobdefinition_list` | `status_choices` (= `JOB_TYPE_CHOICES` — note the name), `schedule_choices`, `sync_schedules`, `environments`, `unrun_count` (`last_run_at__isnull=True`), `muted_count` |
| `jobdefinition_detail` | `runs` (latest 10, `select_related("triggered_by")`, **not** `job`), `run_count` |
| `jobrun_list` | `status_choices`, `trigger_choices`, `jobs`, `open_count` |
| `maintenancewindow_list` / `_create` / `_detail` / `_edit` | `status_choices`, `recurrence_choices`, `services`, `environments`, `incidents` (only `incident_type="scheduled_maintenance"`), `changes`; the list also has `current_count` (a SQL count, not a Python walk) |
| `changerequest_list` | `status_choices`, `type_choices`, `risk_choices`, `impact_choices`, `environments`, `awaiting_count` (`status="submitted"`), `high_risk_open` |
| `changerequest_detail` | `rollouts`, `windows`, `environments` (plus `prefetch_related=("rollouts",)`) |
| `featurerollout_list` / `_create` / `_detail` / `_edit` | `stage_choices`, `status_choices`, `changes`, `feature_flags` |
| `admin_board` | `tiles` (dicts: `key`, `label`, `value`, `hint`, `url`, `icon`, `tone`), `needs_attention` (dicts: `label`, `value`, `url`), `recent_activity`, `boards`, `notes`. Tile tones are **blue/green/orange/purple/slate/red only** — no `amber`, no `yellow` |
| `support_board` | `crm_cases`, `hrm_tickets`, `crm_articles`, `hrm_articles`, `crm_categories`, `hrm_categories`, `counts` (8 keys), `links` |
| `bulk_board` | `tool_choices`, `preview` (always `None`), `counts` (7 keys), `declines` |
| `ops_audit_trail` | `object_list`, `page_obj`, `q`, `action_choices` (bounded to 200), `notes` — `per_page=25`, filters on `?q=` and `?action=` |


Filters and search fields, so the negative-input lane can be aimed:

| list | `?q=` searches | filters (`param` → lookup, is_int) |
|---|---|---|
| `jobdefinition_list` | `name`, `module_slug`, `handler_path`, `description` | `job_type`, `schedule_kind`, `environment`→`environment_id` (int), `is_muted` (bool) |
| `jobrun_list` | `number`, `error_message`, `notes` | `status`, `trigger_kind`, `job`→`job_id` (int) |
| `maintenancewindow_list` | `title`, `number`, `purpose`, `notes` | `status`, `recurrence`, `environment`→`environment_id` (int) |
| `changerequest_list` | `title`, `number`, `summary`, `notes` | `status`, `change_type`, `risk_level`, `impact_level`, `environment`→`environment_id` (int) |
| `featurerollout_list` | `cohort_label`, `change__title`, `feature_flag__key`, `notes` | `stage`, `status`, `change`→`change_id` (int) |

`per_page` is 15 on every `crud_list` here and 25 on `ops_audit_trail`. A junk enum value is
**ignored** (not matched, not a 500) and a junk int FK is skipped by `as_db_int` (L11) — assert
that property, not merely a 200.

---

## 8. The fixtures added to `apps/core/tests/conftest.py` (30, all `ac0_`-prefixed)

Appended at the END of the file, purely additive (L43): every existing fixture is byte-identical
and the 0.21 `cml021_` block above them is untouched. **Reuse the root conftest's `tenant_a`,
`tenant_b`, `admin_user`, `admin_b`, `client_a`, `client_b`, `member_client`** — do not redefine
any of them, and do not redefine `party_a` / `party_b` either (they already exist here).

The module-level helper is `_ac0_stamp(days=0, hours=0)` — a `%Y-%m-%dT%H:%M` string offset from
`timezone.now()`, i.e. the format `TenantModelForm`'s `datetime-local` widget posts.

| fixture | what it is |
|---|---|
| `ac0_actor` | a **second** tenant admin in `tenant_a` (distinct from `admin_user`), so an approval can be attributed to a name that is not the requester's |
| `ac0_actor_client` | a `Client` force-logged in as `ac0_actor` |
| `ac0_env` | one 0.16 `EnvironmentInstance(kind="staging", copy_scope="metadata_only", status="active")` |
| `ac0_flag` | 0.10 `FeatureFlag(key="ops.reconciliation_job", is_enabled=False)` in `tenant_a` |
| `ac0_flag_alt` | a **second** flag, so two stages can hang off one change |
| `ac0_service` | a `ServiceComponent(kind="api", current_status="operational")`, attached to `ac0_window.affected_services` |
| `ac0_job` | a declared `JobDefinition`, `schedule_kind="daily"`, `last_run_at`/`next_run_at` NULL |
| `ac0_job_muted` | a `JobDefinition` with `is_muted=True` |
| `ac0_job_b` | a `JobDefinition` in `tenant_b` — the IDOR target |
| `ac0_run` | an OPEN run: `queued`, no start/finish stamp, `triggered_by=ac0_actor`, `is_dry_run` left at the model default |
| `ac0_run_success` | a run with both stamps and `exit_code=0` — `is_open` False, `duration_display` real |
| `ac0_run_b` | a `JobRun` in `tenant_b` — the IDOR target |
| `ac0_window` | a FUTURE window (+2 days) carrying `ac0_env`, `ac0_change_draft` and one `ac0_service`; `suppresses_jobs=True`, `blocks_admin_writes=False` |
| `ac0_window_running` | a window open now (−1h → +1h), `status="active"` — the legal `end_now` target |
| `ac0_window_past` | a window that ran its course, `status="completed"` |
| `ac0_window_b` | a window in `tenant_b` — the IDOR target |
| `ac0_change_draft` | a `draft` change with no actor and no stamp |
| `ac0_change` | a **`submitted`** change, `requestor=admin_user`, `requested_at` set — the Approve target, and **editable** |
| `ac0_change_approved` | an `approved` change that **carries** `approved_by=ac0_actor` and `approved_at` — the counter-example proving the refusal is about the missing evidence |
| `ac0_change_completed` | a `completed` change with an approver and `implemented_at` — the only legal `rollback` starting point |
| `ac0_change_b` | a `ChangeRequest` in `tenant_b` — the IDOR target |
| `ac0_rollout` | `stage="partial"`, 25%, on `ac0_flag` under `ac0_change` |
| `ac0_rollout_alt` | `stage="general"`, 100%, on `ac0_flag_alt` under the **same** change — makes `rollout_count == 2` |
| `ac0_rollout_b` | a rollout in `tenant_b` |
| `ac0_job_payload` | a minimal **valid** `JobDefinitionForm` create payload |
| `ac0_run_payload` | a valid `JobRunForm` payload recording a `success` (with both stamps) |
| `ac0_window_payload` | a valid `MaintenanceWindowForm` payload (`suppresses_jobs="on"`, `blocks_admin_writes` absent) |
| `ac0_change_payload` | a valid `ChangeRequestForm` payload with `status="draft"` |
| `ac0_rollout_payload` | a valid `FeatureRolloutForm` payload (`stage="partial"`, 25%, `status="planned"`) |

Each payload fixture carries the **whole** form, because a partial dict silently exercises the
"field absent" path rather than the "field supplied" one, and M2M values are **lists of pks** while
an unchecked checkbox is simply **absent**.


### The two self-consistency rules these fixtures must hold

1. **`ac0_change` is `submitted`, not `approved`, and it is genuinely editable.**
   `ChangeRequest.clean()` refuses an `approved` row with no `approved_by` and no `approved_at`,
   and `crud_edit` runs `full_clean()` on **every** save — so an approved row with no approver can
   never be saved through the form again and every POST would fail. A fixture in that state could
   not exercise the edit page at all, which is exactly why Phase 5 changed the seeded demo row back
   to `submitted` in the same fix. `submitted` places no rule in `clean()` and needs no actor, so
   the row saves cleanly. `requested_at` / `requestor` are set because the submit verb is their only
   writer and both are off the form — a test that wants to prove the form never touches them needs
   a row that already carries them. `ac0_change_approved` carries both stamps and therefore **is**
   editable, which is what makes the pair prove the refusal is about the missing evidence rather
   than about the status.
2. **`ac0_rollout`'s `(change, feature_flag)` pair is unique.**
   `FeatureRollout.unique_together` is enforced by the database only, so a duplicate is an
   `IntegrityError` → 500. `ac0_rollout` uses `(ac0_change, ac0_flag)`; `ac0_rollout_alt` uses
   `(ac0_change, ac0_flag_alt)` — a **different flag**, the only legal way to put two stages under
   one change, and what makes `rollout_count == 2` and `clean_feature_flag` provable against a real
   sibling row. `ac0_rollout_b` reuses `ac0_flag` on purpose: the pair is unique per **change**, and
   that is a different row.

Every other fixture row must survive `full_clean()`, and every date is derived from
`timezone.now()` — never `datetime.date.today()` (L16).

---

## 9. Lane reminders

**Models** — defaults, `__str__`, every CHOICES value, `SCHEDULE_KIND_CHOICES is
SyncSchedule.FREQUENCY_CHOICES` (identity), the four prefixes plus the four `LITERAL_PREFIX_MODELS`
entries, all six derived properties, every `clean()` guard (asserting the **key** as well as the
message), `unique_together` on the rollout, and tenancy.

**Forms** — required fields; the L20/L22 exclusion list asserted on the **constructed** form; the
`TenantModelForm` FK tenant scoping (a `tenant_b` pk is rejected for `JobRun.job`,
`FeatureRollout.change`, `FeatureRollout.feature_flag`, `MaintenanceWindow.incident`, …);
`_narrow_status` on create vs. edit (including the "(current)" label); `clean_feature_flag` on
create, on edit (excluded by pk) and on a genuine duplicate; that every `NON_FIELD_ERRORS` guard
**renders** rather than raising `ValueError`; and that the model `clean()`s hold through
`ModelForm._post_clean()`. Every `*_payload` fixture is a lane-3 asset: POST it, assert the row,
and assert the off-form stamps are untouched.

**Views** — 200 **plus a seeded name in the body** on every list (a status code alone does not
prove the page renders, L8); every pinned context key in §7; `?q=`, page 2 and page 99999 return
200; junk enum and junk FK params return 200 and do not empty the register (L11); each delete is
405 on GET and does not delete; each verb's happy path **and** every refusal, including that a
refusal writes **no** `AuditLog` row; `bulk_preview` changes no domain row; `run_now` leaves
`last_run_at`/`next_run_at` alone; `rollout_count` costs no extra query on the prefetched detail
page — prove the N+1 by **row-count invariance**, not by a fixed query budget (L58).

**Security** — cross-tenant: `client_b` gets **404** on the detail, edit, delete and every verb of
all five entities, and sees none of tenant A's rows in any list or board. A tenant member
(`member_client`) gets **403** on all 34 routes; anonymous is **redirected to login** on the
GET-able pages. CSRF enforced on POST with `Client(enforce_csrf_checks=True)`. A crafted POST
carrying a `tenant_b` pk in an FK field is rejected. No board tile or `needs_attention` figure may
ever include another tenant's row.

**Determinism (L16)** — derive every reference date from `timezone.now()` / `timezone.localdate()`,
never `datetime.date.today()`; the window/run properties compare against `timezone.now()`
internally, so a fixture that straddles "now" by minutes is a flaky fixture.

