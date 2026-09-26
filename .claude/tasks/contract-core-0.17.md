# Contract - Module 0 0.17 Monitoring, Logging & Observability (`core`)

**Source of truth:** `.claude/tasks/research-core-0.17.md` · `.claude/tasks/plan-core-0.17.md`
**BASE:** `320670bb` · **Migration:** `core/0015_*` (0.16 landed `0013` + `0014`; L43 agreement required)
**App:** `core` - **FLAT** entity files at the package root. `urls.py` is a **flat file**.
**Templates:** `templates/core/<entity>/<page>.html` · **Test subslug:** `monitoring`

> A name left unpinned in this file is a silently blank page or a `NoReverseMatch` (L7). Everything the
> views pass and everything the templates read is pinned below. **Do not invent a context key at template
> time - if a template needs something not listed in section 5, add it to this contract first.**
>
> **Encoding:** plain UTF-8, no BOM. Written with the editor tool, never with a PowerShell
> `Get-Content | Set-Content` round-trip (that double-encodes to mojibake and adds a BOM - see
> `contract-core-0.16.md`, which is corrupted that way).

---

## 1. Ownership - the L36 no-re-declaration list

0.17 must **never** declare any of these. It links to them or is layered over them. This is the list the
Phase 4 reviewers test against.

| symbol | where it lives | 0.17's relationship |
|---|---|---|
| `core.AuditLog` | `apps/core/models/Audit.py` | **never re-declared.** Answers "who changed which row" (`action`, `changes`, generic FK). `AlertEvent` answers "a threshold was crossed". Different subject, different evidence. |
| `core.BusinessRule` / `core.BusinessRuleLog` | `apps/core/models/BusinessRule.py` | `AlertRule.COMPARATORS = BusinessRule.OPERATORS` is **constant reuse, not a relationship**. No FK either direction. Do not let the reuse drift into inheritance. |
| `tenants.HealthMetric` | `apps/tenants/models/HealthMetric.py` | **read by the health board.** 0.17 declares no metric/sample/timeseries table. `AlertRule.metric_key` is a *vocabulary*, not a store. |
| `tenants.UsageRecord` | `apps/tenants/` | **read by the capacity board.** Quota/allowance/overage is 0.19's. 0.17 contributes only the *scaling trigger*. |
| `core.NotificationRule` / `Channel` / `Template` | `apps/core/models/Notification.py` | `AlertRule.notification_rule` is the single seam. 0.17 declares no channel, template or routing tree. |
| `core.SlaRule` / `ApprovalLimit` | `apps/core/models/Workflow.py` | untouched - escalation is 0.11's. `Incident` has **no** FK to `SlaRule`. |
| `core.SyncSchedule` | `apps/core/models/Integration.py` | `AlertRule.frequency` reuses `SyncSchedule.FREQUENCY_CHOICES` by reference. 0.17 declares no scheduler. |
| `core.RateLimitPolicy` | `apps/core/models/Integration.py` | untouched - 0.18's. |
| `core:retention_board`, `core:integration_board` | 0.8 / 0.13 | **linked, never duplicated.** The 0.17 boards copy their *zero rule*, not their code. |

**Deferred on purpose - do NOT build:** a centralized log store / `LogEntry` table, log shipping,
distributed tracing (`Trace`/`Span`), a raw metric time-series table, a quota/allowance table,
notification channels or routing, a scheduler or job registry.

---

## 2. The four models - all in `apps/core/models/Monitoring.py`

All four inherit `TenantConsistentMixin` (imported from `apps.core.models.Backup`, exactly as
`LegalHold.py` does - one-way, cycle-free).


### 2.1 `ServiceComponent` - the thing that can go down

| field | type | null/default |
|---|---|---|
| `tenant` | `FK("core.Tenant", CASCADE, related_name="service_components", db_index=True)` | no |
| `name` | `CharField(max_length=150)` | no |
| `code` | `CharField(max_length=40, blank=True)` | blank - free text, **not** a `SlugField` |
| `kind` | `CharField(max_length=20, choices=KIND_CHOICES, default="web_service")` | no |
| `description` | `TextField(blank=True)` | blank |
| `owner_role` | `FK("accounts.Role", SET_NULL, related_name="owned_service_components")` | null/blank |
| `is_public` | `BooleanField(default=False)` | |
| `is_critical` | `BooleanField(default=False)` | |
| `display_order` | `PositiveIntegerField(default=0)` | |
| `current_status` | `CharField(max_length=20, choices=STATUS_CHOICES, default="unknown")` | a hand-set claim |
| `last_status_at` | `DateTimeField(null=True, blank=True)` | **null** - system-set, off the form (L22) |
| `notes` | `TextField(blank=True)` | blank |
| `is_active` | `BooleanField(default=True)` | |
| `created_at` / `updated_at` | `auto_now_add` / `auto_now` | |

`KIND_CHOICES` (10): `web_service, api, database, background_job, queue, integration, storage,
external_dependency, infrastructure, other`
`STATUS_CHOICES` (5): `operational, degraded, partial_outage, major_outage, unknown` (default `unknown`)

### 2.2 `AlertRule` - the threshold, as an intention

FK `service` -> `ServiceComponent` (SET_NULL), `notification_rule` -> `core.NotificationRule` (SET_NULL,
`related_name="+"`).
`COMPARATORS = BusinessRule.OPERATORS` **by reference**. `FREQUENCY_CHOICES = SyncSchedule.FREQUENCY_CHOICES`
**by reference**. `unique_together = ("tenant", "name")`.
`CATEGORY_CHOICES`: `availability, error, performance, capacity, security` - the `security` value is the
0.18 seam.
`SEVERITY_CHOICES`: `info, warning, critical` - overlaps `HealthMetric.STATUS_CHOICES` **by string** on
purpose so the board cross-references cleanly.
`NO_DATA_CHOICES`: `fire, ignore, ok` - the NULL-is-not-0 discipline made structural.
`METRIC_CHOICES` is a strict superset of what 0.1 stores: adds `latency_p95_ms, throughput_rps,
error_rate_pct, slow_query_ms, cpu_pct, memory_pct, disk_usage_pct, db_connection_pct, queue_depth,
job_failures`. **`uptime_pct` and `storage_mb` mean different things here** (a platform bound, not tenant
consumption) - the docstring must say so or the next agent will "fix" it (L52).
`warning_threshold` / `critical_threshold` are **nullable** Decimals; `NULL` = tier unset, never `0`.
`must_persist_seconds` is Grafana's duration. A `clean()` refuses an **active** rule with no bound.

### 2.3 `AlertEvent` - one firing, as evidence

FK `rule` -> `AlertRule` (**SET_NULL** - the event must survive the rule being retired, copying
`BusinessRuleLog.rule`'s exact reasoning), FK `service` -> `ServiceComponent` (SET_NULL) **plus a
denormalised `service_label` snapshot** so the row still reads after deletion.
`STATE_CHOICES` (5): `firing, acknowledged, resolved, expired, no_data`.
`severity_at_fire` and `threshold_at_fire` are **snapshots, not joins** - the rule may be edited later
and history must not move. `observed_value` nullable; a `*_display` property renders `None` as an em
dash. `muted_until` is a **recorded** mute that nothing enforces.
`evidence` is free-text, the same field shape as `BackupJob.evidence` / `DisposalRecord.evidence`.
**Explicitly absent:** stack trace, log line, request/response body, raw payload.
Indexes: `(tenant, -fired_at)`, `(tenant, state)`, `(tenant, service, -fired_at)`.

### 2.4 `Incident` - the comms artifact

FK `service` -> `ServiceComponent` (SET_NULL); M2M `affected_services` -> `ServiceComponent`;
FK `primary_alert` -> `AlertEvent` (SET_NULL, `related_name="+"`) so a firing can *become* an incident.
`INCIDENT_TYPE_CHOICES`: `incident, scheduled_maintenance, postmortem` - **`postmortem` is reserved and
unused** (0.21's).
`STATUS_CHOICES` is a **union** enum because one list renders both incident and maintenance:
`scheduled, investigating, identified, in_progress, monitoring, verifying, resolved, completed`.
`IMPACT_CHOICES`: `none, minor, major, critical` - `impact` is what drives `ServiceComponent.current_status`
in the roll-up.
`public_note` vs `internal_note` (Statuspage public vs private). `scheduled_for` / `scheduled_until` are
the **notice window**, not the change itself.

---

## 3. Forms - `apps/core/forms/Monitoring.py`

One `ModelForm` per model, all `Meta`-only, all inheriting `TenantModelForm`.

**L22 is absolute: zero editable `DateTimeField`s on any form.** Out of `Meta.fields` everywhere:
`last_status_at`, `fired_at`, `acknowledged_at`, `resolved_at`, `first_seen_at`, `last_seen_at`,
`started_at`, `scheduled_until`, `notified_at`, `created_at`, `updated_at`.

**The one exception is deliberate and documented:** `ServiceComponentForm.save()` stamps `last_status_at`
in the **form**, not the view, so the admin path gets it too. One extra query per edit POST - nowhere
else. It compares the persisted `current_status` against the submitted one and only stamps on a change.

---

## 4. Views - `apps/core/views/Monitoring.py`

Preamble: `from apps.core.views._common import *  # noqa: F401,F403`, plus `Count, Q` and `reverse`.
Import models from `apps.core.models` and forms from `apps.core.forms` (**absolute imports only**).
Import `accounts.models.Role` **lazily inside the function** - `core` is imported before `accounts` at
startup. Every view is `@tenant_admin_required`; delete views are `@require_POST` **above** the role gate
so GET is 405 regardless of role (the 7.7 pattern).

A module-level `MONITORING_NOTES` list holds the honest-limit lines that the overview and all three
boards print verbatim, so a page and a board cannot disagree (mirrors `BACKUP_NOTES` in `Backup.py`):

```python
MONITORING_NOTES = [
    "This is a register of claims a person wrote, not a monitoring system. NavERP has no probe, no "
    "collector, no log pipeline and no scheduler - nothing here measures, evaluates, notifies or "
    "publishes anything.",
    "A component's status is hand-set. An alert event is a report that a threshold was crossed. Neither "
    "is a measurement NavERP took, and recording either does not make it true.",
    "Where a figure cannot be determined the boards say so and print an em dash, never a 0: a zero that "
    "means 'cannot tell' is the most dangerous number an operations board can show.",
]
```

---

## 5. THE CONTEXT CONTRACT - every key, every list view (L7/L8)

**This section decides whether the build works. A template may not read a key not listed here.**

### 5.1 `service_component_list`
- `qs`: `ServiceComponent.objects.filter(tenant=request.tenant).select_related("owner_role")`
- `search_fields`: `["name", "code", "description"]`
- `filters`: `kind`->`kind`, `status`->`current_status`, `owner_role`->`owner_role_id` (int),
  `public`->`is_public`
- `extra_context`: `kind_choices`, `status_choices`, `owner_roles` (tenant-filtered, `order_by("name")`),
  `unreported_count`, `notes`
- **The GET param is `status` while the ORM lookup is `current_status`.** `unreported_count` is a real
  count over one nullable column, so `0` is legitimate. **No `critical_count`** - derivable by the reader.

### 5.2 `service_component_detail` `extra_context`
`rule_count` · `open_event_count` (`state__in=["firing", "acknowledged"]`) · `incident_count`
(`Q(service_id=pk) | Q(affected_services=pk)`, `.distinct()`) · `notes`

### 5.3 `alert_rule_list`
- `search_fields`: `["name", "module_slug", "metric_key", "notes"]`
- `filters`: `category`, `severity`, `metric`->`metric_key`, `service`->`service_id` (int),
  `active`->`is_active`
- `extra_context`: `category_choices`, `severity_choices`, `metric_choices`, `no_data_choices`,
  `services` (tenant-filtered, `order_by("name")`), `notes`
- **`comparator_choices` is NOT passed** - there is no comparator filter. **No `unbounded_count`** -
  `clean()` makes it structurally always `0`.

### 5.4 `alert_event_list`
- `search_fields`: `["message", "service_label", "evidence"]`
- `filters`: `state`, `severity`->`severity_at_fire`, `rule`->`rule_id` (int), `service`->`service_id` (int)
- `extra_context`: `state_choices`, `severity_choices`, `rules`, `services`, `notes`
- **`event_totals`** - a single `aggregate()` dict with `firing` / `open` / `total` / `unmeasured`.
  **Corrected 2026-09-26 (Phase 4):** this was originally pinned as three flat keys
  (`firing_count`, `open_count`, `total_count`), but the build computes all four in ONE query
  (a filtered `Count` inside `aggregate`) and the template reads them off the dict. The three flat
  keys do not exist and never did in the shipped build. A test written to the old pin would
  `KeyError`. All four are real counts over real columns, so a `0` is a legitimate figure.

### 5.5 `incident_list`
- `search_fields`: `["title", "public_note", "internal_note"]`
- `filters`: `status`, `type` (GET param) -> `incident_type`, `impact`, `public`->`is_public`
- `extra_context`: `status_choices`, **`type_choices`**, `impact_choices`, `notes`,
  `active_count` (register membership), `open_count` (`exclude(status__in=["resolved","completed"])`)
- **Corrected 2026-09-26 (Phase 4):** the key is `type_choices`, not `incident_type_choices` - the
  GET param is `type` and the choice list is named to match. `active_count` and `open_count` are
  **separate keys on purpose**: `is_active` is register membership and `is_open` is a status test.
  One register counted the other way makes a resolved-but-unarchived row read as "still open".

### 5.6 The four board / overview views
- `monitoring_overview` - `notes`, **`component_total`**, `retired_component_count`,
  `operational_count`, `unreported_count`, **`rule_total`**, `active_rule_count`, `firing_count`,
  `open_event_count`, `unmeasured_count`, `active_incident_count`, `archived_incident_count`,
  `latest_metrics`.
  **Corrected 2026-09-26 (Phase 4):** this was pinned as `component_count` / `rule_count`; the
  build uses `component_total` / `rule_total` to match the sibling sub-modules, and adds the
  retired/active split. The overview and the health board now share an **active-only** denominator,
  and the retired figure is passed explicitly so neither page can claim a component count the other
  disagrees with.
- `health_board` - `components` (active, `order_by("display_order", "name")`), `latest_metrics`,
  `component_total`, `registered_total`, `retired_count`, `critical_count`, `public_count`,
  `unreported_count`, `open_alert_count`, `rollup_status`, `status_counts`, **`status_rows`**,
  `notes`. **`status_rows` is `(label, count, value)`** - a zip, because a Django template cannot
  index a dict by a loop variable. The raw value is carried so the badge ladder keys off the stored
  value, not the display label.
- `firing_board` - `open_events`, `open_count`, **`open_total`**, `acknowledged_count`, `muted_count`,
  `unattributed_count`, `state_counts`, `state_rows`, `severity_counts`, `severity_rows`,
  `rule_total`, `notes`. **Corrected:** the key is `open_events`, not `firing_events`; the list is
  capped at 200 and `open_total` is passed so a truncated view can say so. **The zero rule:** an empty
  board must never render as "healthy" - it must say nothing is being reported.
- `capacity_board` - `usage_rows`, `capacity_rules`, `rule_count`, `over_threshold_count`,
  `unmetered_count`, `notes`. Each `capacity_rules` row carries `rule`, `bound`, `current`,
  `headroom`, `note`, **`comparator`**, `breached`, `inactive`. **Corrected:** the board is
  comparator-aware - `gt`/`gte` compute `bound - current` and `lt`/`lte` compute `current - bound`,
  and a non-ordering operator yields `headroom = None` rather than an invented number.

---

## 6. URLs - surgical `Edit` to the flat `apps/core/urls.py`

**Do not convert `core/urls.py` to a package** (backend rule 10 - the `crud()` factory is the better
abstraction). The 0.17 block mirrors 0.16's shape: literal routes **before** the `crud()` groups, and
the POST-only action routes **after** the group that owns them, so a greedy `<int:pk>` cannot shadow
`add/`.

**The URL prefix is `monitoring/...` while templates are flat `core/<entity>/`.** That asymmetry is
intentional and matches 0.16 (`backup/jobs` routes <-> `templates/core/backupjob/`). **Do not "fix" it
by creating `templates/core/monitoring/`.**

**All 28 url names, verbatim:**

| from | url names |
|---|---|
| `crud("monitoring/components", "service_component")` | `core:service_component_list` / `_create` / `_detail` / `_edit` / `_delete` |
| `crud("monitoring/rules", "alert_rule")` | `core:alert_rule_list` / `_create` / `_detail` / `_edit` / `_delete` |
| `crud("monitoring/events", "alert_event")` | `core:alert_event_list` / `_create` / `_detail` / `_edit` / `_delete` |
| `crud("monitoring/incidents", "incident")` | `core:incident_list` / `_create` / `_detail` / `_edit` / `_delete` |
| literal `path()`s | `core:monitoring_overview`, `core:health_board`, `core:firing_board`, `core:capacity_board`, `core:alertevent_acknowledge`, `core:alertevent_resolve`, `core:alertevent_recur`, `core:incident_notify` |

**No `config/urls.py` or `config/settings.py` edit is needed** - `apps.core` is already installed and
mounted. This is the L12 trap avoided by construction.

---

## 7. Seeder - L52 is the binding rule here

`ServiceComponent` and `AlertRule` **may** be seeded (a catalogue and a configured threshold are things
an operator genuinely sets up).

**`AlertEvent` and `Incident` must NOT be seeded.** They are evidence of a threshold being crossed and
of an outage having happened - NavERP observed neither. Seeding them would fabricate operational history
and make the boards lie. This is the same ruling as 0.16's `DisposalRecord` and 0.11's `BusinessRuleLog`.

**Consequence the build must not "fix":** the Acme tenant will have **zero** `AlertEvent` and **zero**
`Incident` rows, so a naive smoke run reads as contract drift. The smoke script creates them via the ORM
inside a `try/finally` and deletes them after. **Do not seed them instead.**

---

## 8. Navigation - exactly one `LIVE_LINKS["0.17"]` entry

Keys **byte-identical to the NavERP.md bullet text**, verified by the repo's own `parse_catalog()` -
mirror exactly how 0.16 did it in `apps/core/navigation.py`. The five bullets are: System Health
Dashboards / Application & Error Logging / Performance Metrics & APM / Capacity & Resource Planning /
Status Page & Incident Comms.

---

## 9. Migration

`core/0015_*`. `core` is at `0014_dataarchive_darch_tenant_at_idx_and_more.py`. **Agree the number with
any other live session before generating (L43)** - a peer session is mid-build on 8.2 in `apps/sales/`
and `makemigrations` operates on the app registry, so check no peer added a `core` model in this
checkout (L51).