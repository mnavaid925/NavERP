# Build contract — Sub-module 8.8: Sales Activity & Task Management

> Phase 3 step 1. `BASE = 07c051dfee72f596a7cb4aa93ff29fd7dd259a5d` (tree clean at claim; the
> untracked `.commandcode/ .gemini/ .workbuddy-ai/ .zcode/` dirs belong to another session — L45).
> Research: `.claude/tasks/research-sales-8.8.md`. Next migration: **`0016_salesactivitytaskmanagement`** —
> claimed before generation (L43/L51/L53).

## 0. Ownership ruling (L36/L37), restated so no reviewer has to infer it

8.8 **EXTENDS** the CRM 1.5 activity stack. It declares **no** `Activity`, `Task`, `Meeting`, `Call` or
`EmailLog` master with its own `channel`/`due_date`/`start`/`end` columns.

| Read-only owner | Models | 8.8's relationship |
|---|---|---|
| **CRM 1.5** | `crm.CommunicationLog`, `crm.CrmTask`, `crm.CalendarEvent`, `crm.EventAttendee` | FK'd / read / generated-into. Vocabularies **IMPORTED**, never re-spelled. |
| **core 0** | `core.Activity`, `core.Party` | `account` FKs `core.Party`. `core.Activity` untouched. |
| **CRM 1.2** | `crm.Opportunity`, `crm.Territory` | FK'd by `ActivityLog`, `TaskTemplate`, `SalesPlanCycle`. |
| **accounts** | `User` | `owner` FK on all four primaries. |

**Vocabulary imports are mandatory and checked:** `ActivityType.kind` ← `CommunicationLog.CHANNEL_CHOICES`;
`ActivityType.default_outcome` ← `CommunicationLog.OUTCOME_CHOICES`; `ActivityLog.capture_source` mirrors
`CommunicationLog.LOGGED_VIA_CHOICES`; `TaskTemplate.task_type` ← `CrmTask.TYPE_CHOICES`;
`TaskTemplate.priority` ← `CrmTask.PRIORITY_CHOICES`. A copied literal list is a bug — it is how the two
drift apart (the `ROUTING_OPERATORS` fork 8.7's docstring warns about).

---

## 1. Models — every field, every choice value

Package folder: `SalesActivityTaskManagement` in all four layers.
Base: `apps.sales.models._base.TenantNumbered` for primaries; `TenantEventOwned` for children.

### 1.1 `ActivityType` — `NUMBER_PREFIX = "ATY"`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(120)` | unique per tenant |
| `description` | `TextField(blank=True)` | |
| `kind` | `CharField(10, choices=CommunicationLog.CHANNEL_CHOICES, default="call")` | max_length 10 ≥ `no_answer` (9) |
| `default_outcome` | `CharField(20, choices=CommunicationLog.OUTCOME_CHOICES, blank=True)` | max_length 20 ≥ `wrong_number` (13) |
| `default_duration_seconds` | `PositiveIntegerField(null, blank, validators=[MinValueValidator(0), MaxValueValidator(86400)])` | |
| `default_priority` | `CharField(10, choices=CrmTask.PRIORITY_CHOICES, default="medium")` | |
| `requires_opportunity` | `BooleanField(default=False)` | |
| `is_billable` | `BooleanField(default=False)` | |
| `is_active` | `BooleanField(default=True)` | |
| `display_order` | `PositiveIntegerField(default=100)` | |

- `Meta.ordering = ["display_order", "name"]`; `UniqueConstraint(["tenant","name"], name="sales_aty_tenant_name_uniq")`.
- Index names ≤ 30 chars.
- `clean()` — **G1**: `default_outcome` set while `kind != "call"` → `ValidationError` on `default_outcome`.
  **G2**: `default_duration_seconds` out of 0–86400 → `ValidationError` on that field.

### 1.2 `ActivityLog` — `NUMBER_PREFIX = "SAL"`

**Carries NO interaction columns.** No `channel`, `subject`, `body`, `direction`, `occurred_at`,
`duration_seconds`, `outcome`, `email_message_id` — those belong to `crm.CommunicationLog`.

| Field | Type | Notes |
|---|---|---|
| `communication_log` | `FK("crm.CommunicationLog", CASCADE, related_name="sales_activity_logs")` | **required**, unique per tenant |
| `activity_type` | `FK("sales.ActivityType", PROTECT, null, blank, related_name="activity_logs")` | **PROTECT** — history never vanishes under a retired type |
| `owner` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null, blank, related_name="sales_activity_logs")` | |
| `opportunity` | `FK("crm.Opportunity", SET_NULL, null, blank, related_name="sales_activity_logs")` | |
| `account` | `FK("core.Party", SET_NULL, null, blank, related_name="sales_activity_logs")` | |
| `territory` | `FK("crm.Territory", SET_NULL, null, blank, related_name="sales_activity_logs")` | |
| `capture_source` | `CharField(20, choices=CAPTURE_SOURCE_CHOICES, default="manual")` | |
| `is_auto_captured` | `BooleanField(default=False)` | |
| `next_best_action` | `CharField(255, blank=True)` | |
| `next_best_action_due` | `DateField(null, blank)` | |
| `occurred_on` | `DateField(null, blank, editable=False)` | **FROZEN** |
| `planned_minutes` | `PositiveIntegerField(null, blank, editable=False)` | **FROZEN** |
| `opened_at` / `open_count` | `DateTimeField(null,blank,editable=False)` / `PositiveIntegerField(default=0, editable=False)` | **FROZEN** |
| `clicked_at` / `click_count` | same | **FROZEN** |
| `replied_at` | `DateTimeField(null, blank, editable=False)` | **FROZEN** |

```python
CAPTURE_SOURCE_CHOICES = [
    ("manual", "Manual"),
    ("call_log", "Call Log"),
    ("bcc_dropbox", "BCC Dropbox"),
    ("calendar_sync", "Calendar Sync"),
    ("template_task", "Template Task"),
    ("plan_goal", "Plan Goal"),
    ("import", "Import"),
]
AUTO_CAPTURE_SOURCES = {"call_log", "bcc_dropbox", "calendar_sync", "template_task", "plan_goal", "import"}
```

- `Meta.ordering = ["-occurred_on", "-pk"]` (explicit — L61). `UniqueConstraint(["tenant","communication_log"], name="sales_sal_comm_uniq")`.
- **Derived, never stored (L37):** `engagement_level` `@property` → `replied > clicked > opened > none`.
  A stored column would drift from its own five inputs.
- `clean()` — **G3** `(capture_source != "manual") != is_auto_captured` → `ValidationError` (non-field:
  one of the two is wrong and the author must be told which pair).
  **G4** every set FK (`activity_type`, `owner`, `opportunity`, `account`, `territory`) must be same-tenant.
- Monotonicity (research §8): the advancement helper only ever increments / stamps; it never clears
  `opened_at`/`clicked_at` or decrements a counter.
- `save()` stamps `occurred_on` from `communication_log.occurred_at` (via `timezone.localtime` →
  `localdate()`) and `planned_minutes` from `activity_type.default_duration_seconds`, falling back to
  `communication_log.duration_seconds // 60`, else `0`. Guarded so a **post-create re-save never rewrites
  a stamped value** (`if self.occurred_on is None`).

### 1.3 `TaskTemplate` — `NUMBER_PREFIX = "TTPL"` + child `TaskTemplateStep`

| Field | Type |
|---|---|
| `name` | `CharField(160)` |
| `description` | `TextField(blank=True)` |
| `task_type` | `CharField(20, choices=CrmTask.TYPE_CHOICES, default="todo")` |
| `priority` | `CharField(10, choices=CrmTask.PRIORITY_CHOICES, default="medium")` |
| `cadence` | `CharField(10, choices=CADENCE_CHOICES, default="weekly")` |
| `cadence_interval` | `PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(12)])` |
| `default_offset_days` | `SmallIntegerField(default=0, validators=[MinValueValidator(-365), MaxValueValidator(365)])` |
| `target_type` | `CharField(20, choices=TARGET_TYPE_CHOICES, default="opportunity")` |
| `activity_type` | `FK("sales.ActivityType", PROTECT, null, blank, related_name="task_templates")` |
| `territory` | `FK("crm.Territory", SET_NULL, null, blank, related_name="sales_task_templates")` |
| `owner` | `FK(settings.AUTH_USER_MODEL, SET_NULL, null, blank, related_name="sales_task_templates")` |
| `is_active` | `BooleanField(default=True)` |
| `last_generated_on` | `DateField(null, blank, editable=False)` — **FROZEN receipt** |
| `generated_count` | `PositiveIntegerField(default=0, editable=False)` — **FROZEN receipt** |

```python
CADENCE_CHOICES = [("once","One-Off"),("daily","Daily"),("weekly","Weekly"),
                   ("biweekly","Every Two Weeks"),("monthly","Monthly"),("quarterly","Quarterly")]
TARGET_TYPE_CHOICES = [("opportunity","Opportunity"),("account","Account"),("territory","Territory")]
```

- Unique `(tenant, name)`. `clean()` — **G6** `cadence=="once"` ⟹ `cadence_interval == 1`.
  **G8** `target_type=="territory"` ⟹ `territory` required.
  **G9** `target_type != "territory"` ⟹ `territory` must be **blank** (ambiguous target otherwise).
  **G7** interval 1–12 (field validators + model check).

**Child `TaskTemplateStep(TenantEventOwned)`** — plain, no auto-number.
`template` FK CASCADE `related_name="steps"`; `order` `PositiveSmallIntegerField(default=1)`;
`title` `CharField(255)`; `instructions` `TextField(blank=True)`;
`task_type` / `priority` re-use the **same imported** choice lists;
`offset_days` `SmallIntegerField(default=0, validators=[MinValueValidator(-365), MaxValueValidator(365)])`.
Unique `(template, order)`. **G10** — bounds enforced by the validators; `clean()` re-checks the tenant.

### 1.4 `SalesPlanCycle` — `NUMBER_PREFIX = "SPC"` + child `ActivityGoal`

| Field | Type |
|---|---|
| `name` | `CharField(160)` |
| `cadence` | `CharField(10, choices=[("daily","Daily"),("weekly","Weekly")], default="weekly")` |
| `period_start` / `period_end` | `DateField()` / `DateField()` |
| `owner` | `FK(User, SET_NULL, null, blank, related_name="sales_plan_cycles")` |
| `territory` | `FK("crm.Territory", SET_NULL, null, blank, related_name="sales_plan_cycles")` |
| `status` | `CharField(10, choices=STATUS_CHOICES, default="draft")` — `draft/active/closed` |
| `suggestion_mode` | `CharField(10, choices=[("manual","Manual"),("assisted","Assisted"),("automatic","Automatic")], default="manual")` |
| `notes` | `TextField(blank=True)` |
| `closed_at` | `DateTimeField(null, blank, editable=False)` — **FROZEN** |

- Unique `(tenant, owner, period_start, cadence)`. **G13**.
- `clean()` — **G11** `period_end >= period_start`; **G12** `cadence=="daily"` ⟹ `period_end == period_start`
  (the L39 trap: both dates individually valid, the pair is not).
- `save()` mirrors `CrmTask.completed_at`: stamp `closed_at` on draft/active→closed, **clear** it on
  re-open, using a pre-save status probe so a plain re-save never re-stamps.

**Child `ActivityGoal(TenantEventOwned)`**
`cycle` FK CASCADE `related_name="goals"`;
`metric` `CharField(16, choices=ACTIVITY_METRIC_CHOICES)` — `call/email/meeting/task/logged_total`;
`target_count` `PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1000)])`.
Unique `(cycle, metric)` — **G15**. Actuals are **derived on the board, never stored**.

---

## 2. Forms — `Meta.fields` and every exclusion, with the reason

All extend `TenantUniqueMixin` + `TenantModelForm` from `apps.sales.forms._common`, narrow every FK to
the tenant, and `_reject_foreign` the same-tenant guarantee on top of the narrowed queryset.
**`ActivityLogForm` and `SalesPlanCycleForm` take `tenant=`; every FK queryset is passed from the view.**

| Form | `Meta.fields` | Excluded, and why |
|---|---|---|
| `ActivityTypeForm` | `name, description, kind, default_outcome, default_duration_seconds, default_priority, requires_opportunity, is_billable, is_active, display_order` | `tenant` (set from `request.tenant`), `number` (`editable=False`, L22), `created_at`/`updated_at` (`auto_now*`) |
| `ActivityLogForm` | `communication_log, activity_type, owner, opportunity, account, territory, capture_source, is_auto_captured, next_best_action, next_best_action_due` | `tenant`; `number`; **all six FROZEN fields** (`occurred_on`, `planned_minutes`, `opened_at`, `open_count`, `clicked_at`, `click_count`, `replied_at`) — `editable=False` auto-excludes them, and they are written **only** by the create view and the two POST verbs; `created_at`/`updated_at` |
| `TaskTemplateForm` | `name, description, task_type, priority, cadence, cadence_interval, default_offset_days, target_type, activity_type, territory, owner, is_active` | `tenant`; `number`; `last_generated_on`/`generated_count` (**FROZEN receipt**, the generation verb is their only writer); `created_at`/`updated_at` |
| `SalesPlanCycleForm` | `name, cadence, period_start, period_end, owner, territory, status, suggestion_mode, notes` | `tenant`; `number`; `closed_at` (**FROZEN**, system-set — L22); `created_at`/`updated_at` |

---

## 3. URL names and paths — order is behaviour

`urls/__init__.py` gets **one** new import + **one** new `+ _sales_activity` line (two edits — L54 rule 2;
the concatenation line is what makes the module reachable).

| Prefix | Names |
|---|---|
| `activity-types/` | `activity_type_list` `_detail` `_create` `_edit` `_delete` |
| `activity-log/` | `activity_log_list` `_detail` `_create` `_edit` `_delete`, `activity_log_mark_opened`, `activity_log_mark_clicked` |
| `task-templates/` | `task_template_list` `_detail` `_create` `_edit` `_delete`, `task_template_generate` |
| `plan-cycles/` | `sales_plan_cycle_list` `_detail` `_create` `_edit` `_delete`, `sales_plan_cycle_toggle` |
| (boards) | `sales_activity_plan`, `sales_next_best_actions`, `sales_email_engagement` |

**Every module prefix above was verified free** against the whole concatenated `sales:urlpatterns`
(`LeadManagement`, `ContactAccountManagement`, `SalesForecasting`, `QuoteProposalCPQ`, `OrderManagement`,
`TerritoryQuotaManagement`, `OpportunityPipeline`, `OpportunityTeams`, `CompetitiveIntelligence`,
`OpportunityOutcomes`, `Workspace`). No greedy `<str:token>` route is added.

**Within each file the literal `…/add/` precedes `…/<int:pk>/`** (8.7's ordering note).
Every non-CRUD verb (`mark_opened`, `mark_clicked`, `generate`, `toggle`) is `@require_POST` in the view
**and** `@tenant_admin_required` where it writes.

---

## 4. Views — every context key, pinned (L7)

`crud_list` supplies `object_list`, `page_obj`, `q`; `crud_create`/`crud_edit` supply `form`.
**Everything else below is `extra_context` and MUST be passed or the page silently blanks (L8).**

### 4.1 `activity_type_list`
`search_fields=["number","name","description"]`, `per_page=15`.
`filters=[("kind","kind",False), ("default_priority","default_priority",False), ("active","is_active",True)]`
— **declared in the `filters` spec, not merely handed to the template** (L54 rule 3).
extra_context: `page_size=15`, `kind_choices`, `priority_choices`, `active_choices`
(`[("active","Active"),("inactive","Inactive")]` — the stringified-boolean pair, handled before pagination),
`stats` (`total`, `active`, `retired` via `Count(..., filter=Q(...))`).

### 4.2 `activity_log_list`
`search_fields=["number","next_best_action"]`, `per_page=15`.
`filters=[("capture_source","capture_source",False), ("owner","owner_id",True), ("opportunity","opportunity_id",True),
          ("territory","territory_id",True), ("activity_type","activity_type_id",True), ("account","account_id",True)]`.
extra_context: `page_size`, `capture_source_choices`, `owners` (tenant users, from `tenant_users()`),
`opportunities`, `territories` (all of the tenant's, `active_only=False` — a retired territory still explains
a historical row), `activity_types`, `accounts`, `stats` (`total`, `auto_captured`, `opened`,
`clicked`, `replied`).
**`engagement_level` is a property** — the template renders `{{ obj.engagement_level }}` via the property,
and the filters never offer it as a GET param (it is not a column).

### 4.3 `task_template_list`
`search_fields=["number","name","description"]`, `per_page=15`.
`filters=[("cadence","cadence",False), ("target_type","target_type",False), ("task_type","task_type",False),
          ("priority","priority",False), ("active","is_active",True)]`.
extra_context: `page_size`, `cadence_choices`, `target_type_choices`, `task_type_choices`, `priority_choices`,
`active_choices`, `territories`, `activity_types`, `owners`, `stats` (`total`, `active`, `never_generated`).

### 4.4 `sales_plan_cycle_list`
`search_fields=["number","name","notes"]`, `per_page=15`.
`filters=[("cadence","cadence",False), ("status","status",False), ("suggestion_mode","suggestion_mode",False),
          ("owner","owner_id",True), ("territory","territory_id",True)]`.
extra_context: `page_size`, `cadence_choices`, `status_choices`, `suggestion_mode_choices`, `owners`,
`territories`, `stats` (`total`, `active`, `closed`).

### 4.5 Detail views
`activity_type_detail` → `obj`, `usage_count`, `recent_activities`.
`activity_log_detail` → `obj`, `communication_log`, `goals_hit` (the plan cycles whose window contains
`obj.occurred_on`).
`task_template_detail` → `obj`, `steps`, `generated_tasks` (bounded, newest first).
`sales_plan_cycle_detail` → `obj`, `goals`, `actuals` (derived dict per metric), `open_tasks` (bounded),
`upcoming_events` (bounded, from `crm.CalendarEvent`), `can_close` (`status != "closed"`).

### 4.6 Create / edit
Every create/edit passes the same FK querysets its list passes, so the dropdowns can never be narrower
than the filter bar (`territories`, `activity_types`, `owners`, `opportunities`, `accounts`,
`communication_logs`).

### 4.7 Boards (`views/SalesActivityTaskManagement/Boards.py`)
Shared constants — the cap is **named, surfaced in the template, and never used to compute the figure it
bounds** (L40):
`MAX_BOARD_ACTIVITIES = 500`, `MAX_BOARD_TASKS = 200`, `MAX_BOARD_EVENTS = 100`, `MAX_BOARD_OPPS = 200`,
`MAX_SUGGESTIONS = 25`, `STALE_ACTIVITY_DAYS = 14`, `STALE_EMAIL_DAYS = 7`, `EVENT_PREP_DAYS = 3`.

- `sales_activity_plan` → `cycle` (may be `None`; the board says so), `cycles` (recent, for the picker),
  `goals` + `actuals` (paired lists), `open_tasks`, `upcoming_events`, `progress_rows`, `caps`.
- `sales_next_best_actions` → `suggestions`, `caps`, `suggested_at`. **Ordering is explicit
  `(-weight, due_date, pk)`** — never an unordered `.first()` (L61).
- `sales_email_engagement` → `rows` (per rep), `by_type` (per activity type), `totals`, `caps`.

---

## 5. Integration (single writer, after every file exists — L12)

1. `apps/sales/models/__init__.py` — import block **+** `__all__` entries (both edits).
2. `apps/sales/forms/__init__.py` — same.
3. `apps/sales/views/__init__.py` — same.
4. `apps/sales/urls/__init__.py` — import **+** `+ _sales_activity` concatenation (L54 rule 2).
5. `apps/sales/admin.py` — register all six models; boards get no admin (8.7 precedent).
6. `apps/sales/management/commands/seed_sales.py` — extend with an idempotent 8.8 block; update the
   success line and the summary count.
7. `apps/core/navigation.py` — **one** `LIVE_LINKS["8.8"]` entry with the five bullet strings **verbatim**,
   plus extra live leaves. The ownership comment is written here (one of the four durable places).
8. `makemigrations sales` → **`0016_…`** → `migrate` → `seed_sales` ×2 (idempotent) → `check`.
9. `templates/sales/overview.html` — link the new pages.

**Seeder rules:** `if <Model>.objects.filter(tenant=t).exists(): skip` per model; `get_or_create` on the
unique keys; reuse existing `core.Party` / `crm.CommunicationLog` / `crm.CrmTask` / `crm.Opportunity` /
`crm.Territory` / `User` rows rather than inventing duplicates; **backdate `CommunicationLog.occurred_at`**
(via a queryset `.update`, the only honest way — L54 rule 6) so the 14-day/7-day stale boards and the
engagement rollup are non-zero on a freshly seeded workspace.

## 6. Templates

`templates/sales/salesactivitytaskmanagement/<entity>/{list,detail,form}.html` — five entity folders
(`activitytype`, `activitylog`, `tasktemplate`, `salesplancycle`) plus `boards/` for the three boards
(8.7's `boards/` precedent). Badges use **colour-named** classes only (`badge-green/red/amber/info/muted/slate` —
L33) with an `{% else %}` `get_<field>_display` fallback. FK filter selects compare with
`|stringformat:"d"` (never `slugify`). Multi-line template notes use `{% comment %}` (single-line `{# #}`
leaks). Delete is a POST form + csrf + `confirm()` naming the **system** number, with `\'` escaping
(L42).

## 7. Verification gates

- `manage.py check` clean; `showmigrations sales` lists `0016` (L54 rule 1).
- `reverse()` **every** name in §3 (L54 rule 2).
- Smoke as `admin_acme`: every list/detail/form renders **200 with expected content**, not just a status;
  junk-param GETs (bad enum, `?owner=abc`, `?owner=999999999999999999999`, `?owner=0`) leave the register
  **intact**; page 2; cross-tenant pk → 404 (L54 rule 4's runtime name check applies to the star-importing
  board module: `hasattr`-test every name it uses).
- The full unfiltered `apps/sales` suite green (L47) — 8.7's 28 test modules included.