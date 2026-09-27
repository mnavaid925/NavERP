# Contract — sub-module 0.20 Admin Console & System Operations (`core`)

**Frozen before the first line of 0.20 code.** Sources: `.claude/tasks/research-core-0.20.md`
(`a589ebe6`) and the appended plan in `.claude/tasks/todo.md` (`98a59640`). `BASE = 463f7a06`.
Migration **`core.0017_*`**.

A name left unpinned here is a silently blank region (L7) or a `NoReverseMatch`. Where this
contract and the code disagree, **this contract was reviewed and the code is wrong** — fix the
code, or record a RULING here first (as 0.19 did for `LicenseAssignment.notes`).

---

## 0. Four facts that decide whether this build works

1. **`requirements.txt` has no Celery / RQ / APScheduler / django-q / redis.** `core.SyncSchedule`
   still says "Nothing runs it". **0.20 ships a register and a manually triggered run. It adds no
   dependency and imports no handler.** Any page that implies otherwise states the decline in
   words (the 0.19 precedent: TEN declines listed in the nav comment).
2. **Bullet 5 declares no ticket table and no knowledge base.** `crm.Case`, `crm.KnowledgeArticle`
   (the class inside `CustomerService/KnowledgeBase.py` — there is **no `KnowledgeBase` class**),
   `crm.KbCategory`, `hrm.HelpdeskTicket`, `hrm.HelpdeskCategory`, `hrm.KnowledgeArticle` all exist.
   The support board **reads and links** them. `core.SupportTicket` / `core.HelpArticle` /
   `core.KnowledgeBase` are **declined** and must not appear in any import.
3. **Bullet 1 aggregates; it replaces nothing.** The 25 existing `templates/core/*.html` boards keep
   their url names and their `LIVE_LINKS` rows. `adminboard.html` re-derives no health, security,
   backup or config logic — every tile is a link.
4. **`core` is a foundation app (backend rule 9): entity files sit FLAT at the package root, and
   `apps/core/urls.py` stays a flat `crud(slug, name)` factory.** No `<SubModule>/` folder, no
   per-entity `urlpatterns` list, no `*_advanced.py`.

---

## 1. Models — 4 entities, 5 classes, all tenant-scoped

Every model: `class X(models.Model)`, a `tenant = models.ForeignKey("core.Tenant",
on_delete=models.CASCADE, related_name="…", db_index=True)`, a literal-minted `number`
(`editable=False`, `max_length=20`), a `Meta.ordering`, and a `(tenant, …)` index whose name is
**under 30 characters** (MariaDB's hard limit). Every file docstring repeats fact 1 and names the
spine it extends (L29/L36).

`core` has **no `TenantNumbered` base**, so the mint is the `EntitlementFeature` pattern verbatim:

```python
def save(self, *args, **kwargs):
    if self.number:
        return super().save(*args, **kwargs)
    for _ in range(5):
        self.number = next_number(JobDefinition, self.tenant, "JOB")
        try:
            with transaction.atomic():
                return super().save(*args, **kwargs)
        except IntegrityError:
            self.number = ""
    return super().save(*args, **kwargs)
```

Imports: `from apps.core.models._base import *`, `from django.db import IntegrityError,
transaction`, `from apps.core.utils import next_number`.

### 1.1 `JobDefinition` — `apps/core/models/JobScheduler.py` — `JOB-`

| Field | Definition |
|---|---|
| `number` | `CharField(max_length=20, editable=False)` — `JOB-` |
| `name` | `CharField(150)` |
| `module_slug` | `CharField(60)` — which module owns the work |
| `job_type` | `CharField(20, choices=JOB_TYPE_CHOICES, default="scheduled_task")` |
| `description` | `TextField(blank=True)` |
| `schedule_kind` | `CharField(10, choices=SyncSchedule.FREQUENCY_CHOICES, default="manual")` — **BY REFERENCE** (assign the object; `Monitoring.py:84` precedent). Never paste a copy. |
| `cron_expression` | `CharField(60, blank=True)` — free text, so a cron string stays recordable without a second vocabulary |
| `interval_minutes` | `IntegerField(null=True, blank=True)` |
| `handler_path` | `CharField(200)` — the **declared** target; `help_text` says nothing imports or calls it |
| `sync_schedule` | FK `core.SyncSchedule` SET_NULL null blank `related_name="job_definitions"` |
| `environment` | FK `core.EnvironmentInstance` SET_NULL null blank `related_name="environment_job_definitions"` |
| `is_active` | `BooleanField(default=True)` |
| `priority` | `SmallIntegerField(default=100)` — lower first, **recorded** order only |
| `timeout_seconds` | `IntegerField(null=True, blank=True)` |
| `max_active_runs` | `SmallIntegerField(default=1)` |
| `pool_name` | `CharField(60, blank=True)` · `pool_slots` `SmallIntegerField(default=1)` — Airflow pools **as a declaration** |
| `max_consecutive_failures` | `SmallIntegerField(default=3)` · `auto_pause_after` `SmallIntegerField(default=10)` — a recorded policy, **not** an auto-pause |
| `last_run_at`, `next_run_at` | `DateTimeField(null=True, blank=True)` — recorded intent; **nothing advances them** |
| `is_muted` | `BooleanField(default=False)` — a window silences a job |
| `notes` | `TextField(blank=True)` · `created_at` `DateTimeField(auto_now_add=True)` |

`JOB_TYPE_CHOICES` exactly: `scheduled_task`, `integration_sync`, `bulk_operation`, `report`,
`cleanup`, `maintenance`.
`Meta`: `ordering = ["name"]`; index `(tenant, is_active)` → `jobdef_tenant_active_idx`;
`(tenant, module_slug)` → `jobdef_tenant_module_idx`.
**The two `environment`/FK `related_name`s must be distinct** — `EnvironmentInstance` carries both
`environment_job_definitions` and `maintenance_windows` and `change_requests`.

### 1.2 `JobRun` — same file, child of `JobDefinition` — `RUN-`

`number` (`RUN-`) · `job` FK `JobDefinition` CASCADE `related_name="runs"` · `triggered_at`
`DateTimeField(auto_now_add=True)` · `started_at` / `finished_at` null blank ·
`trigger_kind` ∈ `manual`, `scheduled`, `backfill`, `api` default `manual` ·
`status` ∈ `queued`, `running`, `success`, `failed`, `skipped`, `cancelled` default `queued` ·
`is_dry_run` `BooleanField(default=True)` — **defaults True because nothing executes** ·
`triggered_by` FK `settings.AUTH_USER_MODEL` SET_NULL null blank `related_name="+"` ·
`exit_code` null int · `records_processed` null int · `duration_ms` null int ·
`error_message` `TextField(blank=True)` · `notes` `TextField(blank=True)`.

`Meta`: `ordering = ["-triggered_at", "-id"]`; index `(tenant, status)` → `jobrun_tenant_status_idx`;
`(job, -triggered_at)` → `jobrun_job_time_idx`.

`clean()`: `status="success"` **requires** `finished_at`; `status="failed"` **requires**
`error_message` (non-blank) **and** `finished_at`; `finished_at` earlier than `started_at` is
refused. Enforced on form, admin and seeder alike.

Derived, never stored: `duration_display` (`"—"` when either stamp is NULL — **never `0`**, a
zero-duration run and an unmeasured run are different statements), `is_open` (`queued`/`running`).

### 1.3 `MaintenanceWindow` — `apps/core/models/Maintenance.py` — `MNTW-`

`number` (`MNTW-`) · `title` `CharField(200)` · `purpose` `TextField(blank=True)` (PagerDuty
windows have a scheduled purpose) · `starts_at` / `ends_at` `DateTimeField` ·
`recurrence` ∈ `once`, `daily`, `weekly`, `monthly` default `once` · `timezone_label`
`CharField(60, blank=True)` · `status` ∈ `draft`, `scheduled`, `active`, `ended_early`,
`completed`, `cancelled` default `draft` · `ended_at` null blank (PagerDuty "End Now") ·
M2M `affected_services` → `core.ServiceComponent` blank `related_name="maintenance_windows"` ·
M2M `suppressed_alert_rules` → `core.AlertRule` blank `related_name="maintenance_windows"` ·
M2M `suppressed_notification_rules` → `core.NotificationRule` blank `related_name="maintenance_windows"` ·
FK `incident` → `core.Incident` SET_NULL null blank **`related_name="+"`** ·
FK `environment` → `core.EnvironmentInstance` SET_NULL null blank `related_name="maintenance_windows"` ·
FK `change_request` → `ChangeRequest` SET_NULL null blank `related_name="maintenance_windows"` ·
`suppresses_jobs` / `blocks_admin_writes` `BooleanField(default=False)` — **recorded, not enforced** ·
`notes` `TextField(blank=True)` · `created_at` auto_now_add.

`clean()`: **both** ends required and `ends_at >= starts_at` — a one-ended window is not a window
(`core.Incident`'s `window_valid` precedent); `status="ended_early"` **requires** `ended_at`;
`ended_at` after `ends_at` is refused (you cannot end later than the window ran to).

`Meta`: `ordering = ["-starts_at", "-id"]`; index `(tenant, status)` → `mntwin_tenant_status_idx`;
`(tenant, starts_at)` → `mntwin_tenant_starts_idx`.
Derived: `is_future` (drives deletability), `is_current` (`starts_at <= now < ends_at`),
`duration_human` (`"—"` when either end is NULL).

**Past windows are kept as history; only a FUTURE window is deletable** — guarded in the view
*and* reflected in each template's Actions column.

### 1.4 `ChangeRequest` + `FeatureRollout` — `apps/core/models/Change.py` — `CHG-`

`ChangeRequest`: `number` (`CHG-`) · `title` `CharField(200)` · `summary` `TextField(blank=True)` ·
`change_type` ∈ `standard`, `normal`, `emergency` default `normal` ·
`risk_level` ∈ `low`, `medium`, `high` default `medium` ·
`impact_level` ∈ `minor`, `moderate`, `major` default `minor` ·
`status` ∈ `draft`, `submitted`, `approved`, `rejected`, `scheduled`, `in_progress`, `completed`,
`rolled_back`, `cancelled` default `draft` ·
FK `environment` → `core.EnvironmentInstance` SET_NULL null blank `related_name="change_requests"` ·
FK `requestor` FK `settings.AUTH_USER_MODEL` SET_NULL null blank `related_name="+"` ·
FK `approved_by` FK `settings.AUTH_USER_MODEL` SET_NULL null blank `related_name="+"` ·
`requested_at` null blank · `approved_at` null blank · `implemented_at` null blank ·
`rollback_reason` `TextField(blank=True)` · `rollback_at` null blank ·
`post_review` `TextField(blank=True)` · `downtime_required` `BooleanField(default=False)` ·
`notes` `TextField(blank=True)` · `created_at` auto_now_add.

`FeatureRollout` (child, **no `number`, no prefix** — a fifth prefix would mint a number no
operator looks up): FK `change` → `ChangeRequest` CASCADE `related_name="rollouts"` ·
FK `feature_flag` → `core.FeatureFlag` CASCADE `related_name="rollouts"` ·
`stage` ∈ `internal`, `pilot`, `partial`, `general` default `internal` ·
`percentage` `PositiveSmallIntegerField` default 0, `MaxValueValidator(100)` ·
`cohort_label` `CharField(120, blank=True)` · `scheduled_at` null blank · `started_at` /
`completed_at` null blank · `status` ∈ `planned`, `running`, `paused`, `completed`, `rolled_back`
default `planned` · `notes` `TextField(blank=True)`.
`Meta`: `ordering = ["stage", "id"]`; unique_together `(change, feature_flag)`.
`clean()`: `stage="partial"` **requires** `0 < percentage < 100`; `stage="general"` requires
`percentage == 100`; `stage="internal"` requires `percentage == 0`; a `completed` stage requires
`completed_at`.

**Both `clean()` sets are enforced by the form** (`ModelForm._post_clean()` calls `full_clean()`),
so they hold on the seeder and the admin too.

---

## 2. `LITERAL_PREFIX_MODELS` — four MANDATORY entries

`prefix_usage()` (`apps/core/settings_engine.py:179`) scans only the `NUMBER_PREFIX` class
attribute, so a literal-minted prefix is invisible to it. **Without these four entries the
`core:numbering_board` reports `JOB` / `RUN` / `MNTW` / `CHG` as `model_only` with no model
named** — the false negative the `SINV` comment and the four 0.19 entries exist to prevent.
The label must read `app_label.ModelName` **exactly**:

```python
"JOB":  ["core.JobDefinition"],
"RUN":  ["core.JobRun"],
"MNTW": ["core.MaintenanceWindow"],
"CHG":  ["core.ChangeRequest"],
```

**Surgical `Edit` into the existing dict only** — a full rewrite of `settings_engine.py` from an
agent is forbidden (L43).

---

## 3. Forms — `apps/core/forms/`

Every form subclasses `TenantModelForm` (`apps/core/forms/_common.py`) and passes
`tenant=request.tenant`, which also scopes every FK/M2M queryset to the tenant.

| Form | `Meta.model` | `Meta.fields` | excluded |
|---|---|---|---|
| `JobDefinitionForm` | `JobDefinition` | `name, module_slug, job_type, description, schedule_kind, cron_expression, interval_minutes, handler_path, sync_schedule, environment, is_active, priority, timeout_seconds, max_active_runs, pool_name, pool_slots, max_consecutive_failures, auto_pause_after, is_muted, notes` | `tenant, number, created_at, last_run_at, next_run_at` — the last two are system-stamped (L22) |
| `JobRunForm` | `JobRun` | `job, trigger_kind, status, is_dry_run, started_at, finished_at, exit_code, records_processed, duration_ms, error_message, notes` | `tenant, number, triggered_at, triggered_by` |
| `MaintenanceWindowForm` | `MaintenanceWindow` | `title, purpose, starts_at, ends_at, recurrence, timezone_label, status, affected_services, suppressed_alert_rules, suppressed_notification_rules, incident, environment, change_request, suppresses_jobs, blocks_admin_writes, notes` | `tenant, number, created_at, ended_at` |
| `ChangeRequestForm` | `ChangeRequest` | `title, summary, change_type, risk_level, impact_level, status, environment, requested_at, downtime_required, notes` | `tenant, number, created_at, requestor, approved_by, approved_at, implemented_at, rollback_at, rollback_reason, post_review` |
| `FeatureRolloutForm` | `FeatureRollout` | `change, feature_flag, stage, percentage, cohort_label, scheduled_at, status, notes` | `started_at, completed_at` |

Integer fields get `class="form-input"`; datetimes get the `datetime-local` widget
`TenantModelForm` already installs. The `pool_*` and `max_consecutive_failures` help texts must say
"recorded, not enforced".

---

## 4. Views — `apps/core/views/` + every context key

Entity views are thin and delegate to `apps/core/crud.py`. **The pinned context-var contract from
`crud.py` applies: list → `object_list` + `page_obj` + `q` (+ filter choices); detail/edit object →
`obj`; form → `form` + `is_edit`.**

Filters are applied to the queryset **before** `paginate()`, and every int-FK GET value goes
through `as_db_int()` (L11) so `?job=abc` is refused rather than 500ing in the driver.

| View | Url name | Kind | Extra context keys the template may use |
|---|---|---|---|
| `jobdefinition_list` | `core:jobdefinition_list` | `crud_list` | `status_choices` = `JOB_TYPE_CHOICES`; `schedule_choices` = `SyncSchedule.FREQUENCY_CHOICES`; `sync_schedules`; `environments` |
| `jobdefinition_create` / `_edit` / `_detail` / `_delete` | `core:jobdefinition_*` | `crud_*` | `sync_schedules`, `environments` (form pages) |
| `jobrun_list` | `core:jobrun_list` | `crud_list` | `status_choices` = `JobRun.STATUS_CHOICES`; `trigger_choices`; `jobs` |
| `jobrun_detail` / `_edit` / `_delete` | `core:jobrun_*` | `crud_*` | `jobs` — **no create route**: only the `run_now` verb and the seeder write a `JobRun` |
| `maintenancewindow_list` | `core:maintenancewindow_list` | `crud_list` | `status_choices`; `recurrence_choices`; `services`; `environments`; `incidents`; `changes` |
| `maintenancewindow_*` | `core:maintenancewindow_*` | `crud_*` | the same five querysets on form pages |
| `changerequest_list` | `core:changerequest_list` | `crud_list` | `status_choices`; `type_choices`; `risk_choices`; `impact_choices`; `environments` |
| `changerequest_*` | `core:changerequest_*` | `crud_*` | `environments` |
| `featurerollout_list` | `core:featurerollout_list` | `crud_list` | `stage_choices`; `status_choices`; `changes`; `feature_flags` |
| `featurerollout_*` | `core:featurerollout_*` | `crud_*` | `changes`, `feature_flags` |
| `admin_board` | `core:admin_board` | board | `tiles` (list of dicts: `key,label,value,hint,url,icon,tone`) · `needs_attention` · `recent_activity` · `boards` (the existing-board link list) |
| `support_board` | `core:support_board` | board | `crm_cases`, `hrm_tickets`, `crm_articles`, `hrm_articles`, `crm_categories`, `hrm_categories`, `counts`, `links` |
| `bulk_board` | `core:bulk_board` | board | `tool_choices`, `preview`, `counts`, `declines` |
| `ops_audit_trail` | `core:ops_audit_trail` | read-only list | `object_list`, `page_obj`, `q`, `action_choices` |

POST-only action views (`@require_POST`, each `@login_required`, each tenant-filtered):

| View | Url name | Effect |
|---|---|---|
| `jobdefinition_run_now` | `core:jobdefinition_run_now` | writes **exactly one** `JobRun` (`trigger_kind="manual"`, `is_dry_run=True`, `triggered_by=request.user`) + `write_audit_log`; success message is exactly **"Run recorded — no job was executed; this repository has no scheduler."**; imports and calls nothing |
| `maintenance_window_end_now` | `core:maintenance_window_end_now` | `status="ended_early"` + `ended_at=timezone.now()` (PagerDuty "End Now") |
| `change_request_submit` | `core:change_request_submit` | `draft → submitted`, stamps `requested_at` |
| `change_request_approve` | `core:change_request_approve` | `submitted → approved`, stamps `approved_by`/`approved_at`; a refusal reason goes in `notes` |
| `change_request_rollback` | `core:change_request_rollback` | `completed → rolled_back`, requires `rollback_reason` in POST, stamps `rollback_at` |
| `bulk_preview` | `core:bulk_preview` | **writes nothing** — renders a count-only preview and says the repo has no executor |

Every guard lives in the **view**, not only in a hidden button, so a hand-made POST cannot reach
it and the audit row is not written either. `AuditLog.action` is `varchar(10)` — a long verb goes
in `changes`. `ops_audit_trail` is **read-only**: it reuses `AuditLog` and must not offer
create/edit/delete of audit rows.

---

## 5. Urls — `apps/core/urls.py` stays FLAT, and the `crud()` factory is the shape

```python
# literal segments FIRST (Django is first-match-wins, so a greedy <int:pk> declared
# ahead of "add/" would shadow it), then the crud() groups, then the POST-only verbs
# AFTER the group that owns them.
path("ops/board/",   views.admin_board,      name="admin_board"),
path("ops/support/", views.support_board,    name="support_board"),
path("ops/bulk/",    views.bulk_board,       name="bulk_board"),
path("ops/audit/",   views.ops_audit_trail,  name="ops_audit_trail"),
+ crud("ops/jobs",                "jobdefinition")
+ crud("ops/job-runs",            "jobrun")
+ crud("ops/maintenance-windows", "maintenancewindow")
+ crud("ops/changes",             "changerequest")
+ crud("ops/rollouts",            "featurerollout")
+ [path("ops/jobs/<int:pk>/run-now/", …),
   path("ops/maintenance-windows/<int:pk>/end-now/", …),
   path("ops/changes/<int:pk>/submit/", …),
   path("ops/changes/<int:pk>/approve/", …),
   path("ops/changes/<int:pk>/rollback/", …),
   path("ops/bulk/preview/", …)]
```

**`jobrun` gets its five routes but the `create` one is never linked** — `crud()` generates it,
and the template's Actions column simply never offers Add. Each new literal route is checked
against the **whole concatenated list**, not just its own block.

---

## 6. Templates — flat, one folder per entity

`templates/core/<entity>/{list,detail,form}.html` — **never** `ops/jobdefinition_list.html`,
never a flat `<entity>_<page>.html`. Boards are standalone pages at the app root (rule 6):
`templates/core/adminboard.html`, `supportboard.html`, `bulkboard.html`, `opstrail.html`.

Every list page: filter bar reflecting `request.GET` (`q` + the `*_choices` the view passes, FK
selects compared with `|stringformat:"d"` — **never `|slugify` on a pk**), an Actions column
(view/edit/delete-POST+confirm+csrf, status-conditional), pagination with `has_previous`/
`has_next` guards (L9), and a real `.empty-state`. Badges use the **colour-named** theme classes
`badge-green/red/amber/info/muted/slate` only (L33 — the semantic `-success`/`-danger` names do not
exist), each matching the model's exact CHOICES value with an `{% else %}` falling back to
`{{ obj.get_<field>_display }}`. Detail pages get an Actions sidebar (edit · delete-POST+confirm ·
back to list, each status-conditional). **No `{#` and no `{% comment` leaks** (L2/L3).

---

## 7. Wire-up

- **One** new `LIVE_LINKS["0.20"]` block in `apps/core/navigation.py`. **No `settings.py` edit, no
  root `urls.py` edit** — the app is already mounted. Surgical `Edit` only.
- The five bullet keys copied **BYTE-IDENTICALLY** from `NavERP.md` lines 267-271 —
  `parse_catalog()` matches by exact string and one character of drift renders a fully built page
  as a "soon" roadmap pill **with no error anywhere**:
  - `Unified Admin Dashboard` → `core:admin_board`
  - `Job Scheduler & Background Tasks` → `core:jobdefinition_list`
  - `Maintenance & Release Management` → `core:maintenancewindow_list`
  - `Bulk Operations & Data Tools` → `core:bulk_board`
  - `Self-Service Support & Help Center` → `core:support_board`
- Extras (after the bullets, so they read as operational leaves): `Job Run History` →
  `core:jobrun_list` · `Change Register` → `core:changerequest_list` · `Feature Rollouts` →
  `core:featurerollout_list` · `Operations Audit Trail` → `core:ops_audit_trail`.
  **9 labels over 9 DISTINCT targets** — asserted (`len(set(links.values())) == len(links)`)
  before the block counts as wired.
- The block's comment **lists the declines in numbered form**, as 0.19 does.

---

## 8. Seeder — `seed_core.py`, idempotent

Extend in place; keep the existing early-return guards and the `--flush` behaviour. New
`NumberingScheme` rows via `get_or_create(tenant=tenant, prefix=…, defaults={…})`, and **keep the
`ZZZ` "configured but nothing mints it" row** — the reconciliation board's `configured_only`
branch needs its demonstration row.

**No green successes.** Nothing in 0.20 *detects* or *executes* anything, so a seeded
`status="success"` `JobRun` is a recorded event that did not happen. Seed `queued` (with
`is_dry_run=True`) and `skipped` runs only, and every seeded row's `notes` must say in plain words
that no scheduler produced it. Print the tenant-admin hint and the standing `admin`/`tenant=None`
warning.

---

## 9. Verify gate (all must pass before Phase 4)

`makemigrations core` → `core/migrations/0017_*.py` (re-list the directory first — L43) ·
`migrate` · `makemigrations --check` → "No changes detected" · `seed_core` ×2 verified **by COUNT,
not stdout** · `manage.py check` clean · `temp/` smoke as `admin_acme`/`password` with **content**
assertions on every new page (title + a seeded record + no comment leaks + no blank region from a
mismatched context var) · junk-param list · page 2 · **cross-tenant IDOR → 404 on all five
models** · `bulk_preview` writes nothing (count before/after) · `run_now` writes exactly one
`JobRun` and imports no handler · the four `LITERAL_PREFIX_MODELS` entries render as `used` on
`core:numbering_board` · every `LIVE_LINKS["0.20"]` value reverses and the distinct-target
assertion holds · `temp/audit_integrity.py` drops module 0 to **1** remaining (0.21).

---

## 10. Phase discipline

Entity by entity, one finished before the next starts: each entity's **model file, then its form,
view, and its three templates**, then move on. `admin.py`, `seed_core.py`, `navigation.py`,
`settings_engine.py`, `urls.py` and the four package `__init__.py` files are **single-writer
integrate work** and wait until every entity file has landed. Shared files get surgical `Edit`
calls only (L43). **One file per commit, `;` separator, never `&&`, never `git push`.**





