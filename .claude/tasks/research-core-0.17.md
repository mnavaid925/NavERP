# Research — 0.17 Monitoring, Logging & Observability (Module 0, `core`)

**Date:** 2026-09-26 · **Phase:** 1 (research) · **Target app:** `apps/core` (flat — Module 0 has no sub-module level, backend rule 9)
**BASE sha:** `320670bb3aa74d4f384d49b91c1232c69e0486e5` · Working tree was **dirty at session start** (not mine — L45); no application code was touched.

## NavERP.md 0.17 — the five bullets (verbatim)

> - **System Health Dashboards** — Uptime, resource usage, and service-status monitoring.
> - **Application & Error Logging** — Centralized logs, error tracking, and alert thresholds.
> - **Performance Metrics & APM** — Latency, throughput, slow-query detection, and distributed tracing.
> - **Capacity & Resource Planning** — Usage trends, scaling triggers, and quota management.
> - **Status Page & Incident Comms** — Internal/external status pages and maintenance notices.

---

## 0. The spine this sub-module must NOT re-declare (read before planning)

Verified by reading the files, not by inference.

| Already exists | Where | What it owns | Verdict for 0.17 |
|---|---|---|---|
| `core.AuditLog` | `AuditLog.py` | who/what/when of a **data or config change** (`action`, `changes` JSON, generic FK to the changed object) | **Not an observability log.** 0.17 adds no log store. |
| `core.BusinessRule` / `core.BusinessRuleLog` | `BusinessRule.py` | a **business condition** evaluated against a record; the log records what the *caller did* | **Not a threshold rule.** Different question (L36). `AlertRule` may reuse `BusinessRule.OPERATORS`; it does not extend or FK the class. |
| `tenants.HealthMetric` | `tenants/HealthMetric.py` | `(metric, value, status, recorded_at)` — a tenant-scoped **reading**; `METRIC_CHOICES = users / storage_mb / api_calls / db_rows / uptime_pct` | **Do not re-declare a metric table.** 0.17's board *reads* it. |
| `tenants.UsageRecord` / `Subscription` | `tenants/` | consumption per metric per period, `included_allowance`, derived overage | **Owns "quota management."** 0.17 bullet 4 keeps the *scaling trigger* only. |
| `core.RateLimitPolicy` | `Integration.py` | a recorded request limit (nothing enforces it) | Untouched. |
| `core.NotificationRule` / `Channel` / `Template` / `ProviderConfig` | `Notification.py` (0.12) | event → channel → audience; templates; provider failover | **`AlertRule` FKs `NotificationRule`.** 0.17 declares no channel, template or routing tree. |
| `core.SlaRule`, `ApprovalLimit`, `WorkflowDefinition` | `Workflow.py` (0.11) | escalation + approval timing, and the *process* monitoring board | 0.17 declares no escalation policy or on-call schedule. |
| `core.SyncSchedule` | `Integration.py` (0.13) | `FREQUENCY_CHOICES` — the schedule vocabulary, reused (not regrown) by 0.16 | `AlertRule.frequency` reuses this vocabulary. |

---

## 1. Prioritized feature catalog

Sources: Datadog (monitors, SLOs), New Relic (conditions), Dynatrace (problems), Grafana Cloud / Alertmanager, Sentry, SolarWinds Observability, PRTG, ManageEngine EventLog Analyzer, Atlassian Statuspage, PagerDuty, Uptime Kuma, OpenTelemetry.

| # | Feature | Source product(s) | Bullet | Priority |
|---|---|---|---|---|
| 1 | **Service / component catalogue** — the *thing* that is watched and shown up/down (name, kind, owner, public-vs-private, display order, current status) | Statuspage *components* + *component groups*; Dynatrace *entities*; PRTG *sensor groups*; Uptime Kuma `status_page_node` | 1, 5 | **Must** |
| 2 | **Alert threshold rule** — metric + comparator + warning/critical bound + how long it must persist + evaluation cadence + severity | Grafana *alert rule* (queries, condition, interval, **duration**); Dynatrace metric-threshold rule; PRTG channel *warning* vs *downtime* thresholds; New Relic *condition* (`threshold`, `violation_duration_limit`); Sentry *metric-breach* | 1, 2, 3, 4 | **Must** |
| 3 | **Alert event / firing** — state machine (firing → acknowledged → resolved), observed value at fire time, occurrence count, ack/resolve actors | Alertmanager *alerts* (`startsAt`/`endsAt`) + *silences*; Grafana *alert instance* (`state`, `isPaused`, `silencedBy`); Datadog *alert state*; Dynatrace *problem* (`problemState`, `impactLevel`, `affectedEntities`); Sentry *issue* (`firstSeen`/`lastSeen`/`count`, status, assignee) | 1, 2, 3, 4 | **Must** |
| 4 | **Incident + maintenance notice** — status-page entry with an impact level, a lifecycle, public vs internal text, and a link back to the alert/service that caused it | Statuspage *incidents* (`status`, `impact`, `shortlink`), *incident_updates*, *scheduled_maintenances*, *postmortems*; PagerDuty *incident* (`urgency`, `impact`, `acknowledged_at`, `resolved_at`) | 5 | **Must** |
| 5 | **No-data / error state distinct from "fine"** | Grafana alerting: *error and no data handling*; Uptime Kuma heartbeat `pending` | 2, 3 | **Must** — folds into #2/#3 as a `choices` value, not a table |
| 6 | **Two-tier severity (warning vs critical) rather than one** | PRTG warning/downtime channels; Dynatrace `severityLevel`; Datadog priority | 2, 3 | **Must** — folds into #2 as two nullable threshold columns |
| 7 | **Uptime / resource-usage board** | PRTG uptime; Statuspage *Uptime Showcase*; Datadog infrastructure | 1 | **Should** — a **computed page** over `tenants.HealthMetric` + `ServiceComponent`; no model |
| 8 | **Incident → component status roll-up** (one degraded service tints the whole page) | Statuspage | 1, 5 | **Should** — derived, never stored (SCM L37 posture) |
| 9 | **Mute / silence window on a firing** | Alertmanager *silences*; Datadog *downtimes*; Grafana *mute timings* | 2 | **Should** — one nullable `muted_until` on the event; a matcher DSL is deferred |
| 10 | **Alert category taxonomy** (availability / error / performance / capacity / security) | Sentry *issue categories*; Datadog alert types | 1–4 | **Should** — the field that keeps 0.18 out |
| 11 | **Error grouping by fingerprint** (many events → one issue) | Sentry *fingerprint* / grouping / regressed / archived | 2 | **Could** — a *board filter* over `AlertEvent`, not a model |
| 12 | **SLO / error budget** | Datadog SLOs (metric / monitor / timeslice types, `target`, `timeframe`, remaining budget) | 1, 3 | **Could** — a computed page; **no SLO table** in this build |
| 13 | **Capacity headroom board** (trend vs threshold, scaling trigger) | Datadog autoscaling / capacity; SolarWinds capacity; 0.1 `UsageRecord` | 4 | **Should** — computed over `tenants.UsageRecord` + `AlertRule`; no model |
| 14 | **Incident update timeline** (per-status public note) | Statuspage `incident_updates` | 5 | **Could** — deferred; would be a 5th model |
| 15 | **Postmortem** | Statuspage *postmortems*; Dynatrace `isPostMortem` | 5 | **Deferred** → 0.21 |
| 16 | **Distributed tracing (trace/span graph)** | OpenTelemetry spans (`trace_id`, `span_id`, parent, status); Datadog APM; Dynatrace | 3 | **Deferred** — no OTel SDK, collector or instrumentation in the repo |
| 17 | **Centralized log store / log shipping** | Datadog *Log Management*; Grafana Loki; ManageEngine EventLog Analyzer | 2 | **Deferred** — no log pipeline exists; a table nobody writes is the fake-claim sin |
| 18 | **Raw metric time-series store** | Prometheus / Mimir / Dynatrace Grail | 3, 4 | **Deferred** → `tenants.HealthMetric` already owns readings (0.1) |
| 19 | **Quota allowance / overage policy** | 0.19 bullet 3; `tenants.UsageRecord.included_allowance` | 4 | **Deferred → 0.19** (NavERP.md overlap; see Risks) |
| 20 | **Notification channels, routing tree, receivers, on-call escalation** | Datadog *services* + notification rules; Alertmanager routing tree; PagerDuty *escalation policies*; Grafana *notification policy* + *contact point* | 2 | **Deferred** → 0.12 owns delivery, 0.11 owns escalation. `AlertRule` FKs `NotificationRule`. |
| 21 | **Synthetic probe execution + heartbeat table** | Uptime Kuma `monitor` / `heartbeat`; PRTG *sensor* + *probe* | 1 | **Deferred** — no prober process; state is hand-set and labelled as such |
| 22 | **Status-page public rendering, subscriber lists, uptime % history** | Statuspage public/private/audience pages, *subscribers* | 5 | **Deferred** → 0.12 delivery + `tenants.HealthMetric.uptime_pct` |


### Bullet coverage summary

- **Bullet 1 (health dashboards): COVERED** — `ServiceComponent` + a computed board reading `tenants.HealthMetric` (#1, #7, #8).
- **Bullet 2 (error logging + alert thresholds): PARTIAL by design** — thresholds and the alert lifecycle are fully covered (#2, #3, #5, #6). **"Centralized logs" is deferred** (#17): NavERP has no log pipeline, so a log table would be a second log store nobody populates. Error *tracking* is covered at the level of a recorded firing with a message, not ingested events.
- **Bullet 3 (APM): PARTIAL by design** — latency / throughput / slow-query appear as **threshold vocabulary** on `AlertRule` and as a computed board (#2, #12); the **time-series store is 0.1's** (#18) and **distributed tracing is deferred** (#16).
- **Bullet 4 (capacity): COVERED as a trigger, deferred as a policy** — `AlertRule(category="capacity")` is the scaling trigger; the trend board reads `tenants.UsageRecord` (#13). **Quota management is 0.19's** (#19).
- **Bullet 5 (status page + incident comms): COVERED** — `ServiceComponent` (the public/private component) + `Incident` (#1, #4, #8). *Incident update timeline* and *subscriber lists* deferred (#14, #22).

---

## 2. Recommended build scope — 4 models

All four go in **one file**: `apps/core/models/Monitoring.py` (Module 0 = flat, backend rule 9). Templates flat at `templates/core/<entity>/{list,detail,form}.html`; URLs via the existing `crud()` factory in `core/urls.py`.


### 1. `ServiceComponent` — *the thing that can go down*
- **Serves:** bullet 1 (service-status monitoring) and bullet 5 (the status-page component).
- **Why it exists:** every researched product separates *"the monitored entity"* from *"the measurement"*. NavERP has the measurement half (`tenants.HealthMetric`) and **no entity half** — nothing in the repo can say "the payments API is degraded".
- **Key fields (plain English):** tenant; name; short code/slug; kind (`web_service`, `api`, `database`, `background_job`, `queue`, `integration`, `storage`, `external_dependency`, `infrastructure`, `other`); description; **owning role** (FK `accounts.Role`, `SET_NULL` — same shape as `NotificationRule.audience_role`); `is_public` (appears on the external status page vs internal-only — Statuspage's public/private page split); `is_critical` (a failure here tints the whole board); display order (Statuspage `position`); **current status** (`operational`, `degraded`, `partial_outage`, `major_outage`, `maintenance`, `unknown`); **`last_status_at` (nullable — "not reported" ≠ epoch, and never coerced to 0)**; notes; is_active; created/updated.
- **Relates to:** FK `tenant` → `core.Tenant`; `owner_role` → `accounts.Role`. **No FK to `tenants.HealthMetric`** — the board *reads* it one-to-many at render time. Nothing here is probed; `current_status` is a **hand-set claim** and the page must say so.
- **Decisions the todo agent should not re-open:** no auto-set `last_checked_at` (nothing checks it — L52); no sensor/probe FK (no prober exists).

### 2. `AlertRule` — *the threshold, recorded*
- **Serves:** bullets 1, 2, 3 and 4 simultaneously. This is the single artifact all four share: a capacity ceiling, a latency p95, an error-rate burn and an uptime floor are the same row with a different `metric_key`.
- **Why it exists:** NavERP has threshold-shaped *process* rules (`SlaRule`, `BusinessRule`) and *quota* rules (`RateLimitPolicy`, `UsageRecord.included_allowance`) but **no metric-threshold rule** — nothing can say "raise an alert if p95 latency exceeds 800 ms for 5 minutes".
- **Key fields:** tenant; **service** (FK → `ServiceComponent`, `CASCADE`, `related_name="alert_rules"`); name; `module_slug`; `metric_key`; comparator; **warning threshold** and **critical threshold** (both nullable Decimals — two tiers, PRTG/Dynatrace; `NULL` = "this tier is unset", **never** `0`); **`must_persist_seconds`** (Grafana's *duration* — the "how long before it counts" that stops flap); `frequency`; severity (`info`, `warning`, `critical` — deliberately overlapping `tenants.HealthMetric.STATUS_CHOICES`' `warning`/`critical` strings so the board cross-references cleanly); `category` (`availability`, `error`, `performance`, `capacity`, `security`); **`no_data_action`** (`fire`, `ignore`, `ok` — the NULL-is-not-0 discipline made structural); **notification route** (FK → `core.NotificationRule`, `SET_NULL`, `related_name="+"`); is_active; notes; created/updated; `unique_together = (tenant, name)`.
- **Reuse rulings (do not regrow — the 0.16 `Backup.py` precedent):**
  - `COMPARATORS` = **`BusinessRule.OPERATORS`** by reference. Same app, documented public constant, same operator vocabulary. Do not paste a second copy.
  - `frequency` = the **0.13 `SyncSchedule.FREQUENCY_CHOICES`** vocabulary, with `help_text` in the voice of 0.16: *"a recorded intention. Nothing in NavERP runs it."*
- **On `metric_key`:** declare 0.17's own `METRIC_CHOICES` because the **threshold vocabulary is a strict superset** of what 0.1 chose to *store* — add `latency_p95_ms`, `throughput_rps`, `error_rate_pct`, `slow_query_ms`, `cpu_pct`, `memory_pct`, `disk_usage_pct`, `db_connection_pct`, `queue_depth`, `job_failures`. **Two keys overlap `HealthMetric` by string (`uptime_pct`, `storage_mb`) and mean different things** — there a reading is *tenant consumption*, here it is a *platform bound*. The docstring must say so, or the next agent will "fix" it (L52).
- **Relates to:** FK `tenant`, `service` → `ServiceComponent`, `notification_rule` → `core.NotificationRule`. **No FK to `AuditLog`, `BusinessRule`, `RateLimitPolicy` or `UsageRecord`** — pointing at them is not possible (they are not services) and copying their columns is the parallel-schema bug.


### 3. `AlertEvent` — *one firing, as evidence*
- **Serves:** bullets 1, 2, 3, 4 — the read side of every alert.
- **Why it exists:** a rule with no firing record is an intention; this is the **hand-written-evidence posture of `DisposalRecord` / `RestoreRecord` / `BackupJob`**, applied to alerting. Nothing in NavERP evaluates a threshold (no scheduler), so each row is *a report that a threshold was crossed*.
- **Key fields:** tenant; **rule** (FK → `AlertRule`, **`SET_NULL` — copying `BusinessRuleLog.rule`'s exact reasoning: the event is the evidence a rule fired and must survive the rule being retired**); **service** (FK → `ServiceComponent`, `SET_NULL`, same reason — plus a denormalised `service_label` snapshot so the row still reads after the component is deleted); `state` (`firing`, `acknowledged`, `resolved`, `expired`, `no_data`); **`severity_at_fire`** (a **snapshot, not a join** — the rule's severity may be edited later and the historical record must not move); **`observed_value`** (nullable Decimal — the reading that crossed; `NULL` means *not measured*, and the 0.16 `*_display` pattern must render it `"—"`); **`threshold_at_fire`** (nullable, same reason); message/detail; `occurrence_count` (Sentry's *count* — how many times this has recurred); first/last seen; `fired_at`; `acknowledged_at` + `acknowledged_by`; `resolved_at` + `resolved_by`; resolution note; **`muted_until`** (nullable — Alertmanager *silence* / Datadog *downtime*, as a **recorded** mute; nothing enforces it); `evidence` (free-text ticket/runbook ref — the **same field shape** as `BackupJob.evidence` and `DisposalRecord.evidence`); created_at. Indexes: `(tenant, -fired_at)`, `(tenant, state)`, `(tenant, service, -fired_at)`.
- **Explicitly absent:** stack trace, log line, request/response body, raw payload. NavERP does not collect them (#17); a `traceback` field would be one that is permanently empty (L52).
- **Relates to:** FK `tenant`, `rule`, `service`, two `AUTH_USER_MODEL` FKs (`related_name="+"`, matching `DisposalRecord.performed_by`).

### 4. `Incident` — *the comms artifact*
- **Serves:** bullet 5, and the roll-up half of bullet 1.
- **Why it exists:** every status-page product's core is `component` + `incident`, and the incident has a **different lifecycle and a different audience** from an alert. NavERP has neither. It is also the only model here whose *purpose* is outward-facing, which is why `is_public` matters.
- **Key fields:** tenant; **service** (FK → `ServiceComponent`, `SET_NULL`); **affected services** (M2M → `ServiceComponent` — a real M2M; the auto-generated through table is not a hand-declared model, so this does not break the 4-model cap); **`primary_alert`** (FK → `AlertEvent`, `SET_NULL`, `related_name="+"` — lets a firing *become* a comms incident without a second store, and gives the status page a "why" link); title; `incident_type` (`incident`, `scheduled_maintenance`, `postmortem` — Statuspage's own variant set; *postmortem* is reserved and deferred, #15); **`status`** (a **union** enum, because one list renders both: `scheduled`, `investigating`, `identified`, `in_progress`, `monitoring`, `verifying`, `resolved`, `completed`); **`impact`** (`none`, `minor`, `major`, `critical` — Statuspage's, and the field that drives `ServiceComponent.current_status` in the roll-up); `public_note` vs `internal_note` (Statuspage public vs private page); progress percentage; `started_at`; `resolved_at`; `scheduled_for` / `scheduled_until` (maintenance notice window — **this is the *notice*, not the change**); `notified_at`; is_active; created/updated; notes.

### Pages implied by the 4 models (for the todo agent, not a build order)

`ServiceComponent` list/detail/form · `AlertRule` list/detail/form · `AlertEvent` list/detail (form only for the ack/resolve action) · `Incident` list/detail/form · plus **three computed boards, no models**: a **health board** (components + their latest `ServiceComponent.current_status` + `tenants.HealthMetric` latest readings), a **firing board** (`AlertEvent` grouped by state — the "zero rule": an empty board must not render as "healthy"), and a **capacity board** (`tenants.UsageRecord` per metric vs the `AlertRule` bound on that metric). The 0.8 `retention_board` and 0.13 `integration_board` are the precedents.


---

## 3. Explicitly deferred

- **Centralized log store, log shipping, log-level thresholds, sensitive-data scrubbing** (bullet 2) — `settings.LOGGING` writes to console/handlers; there is no collector, shipper or index. A `LogEntry` table would be a second log store *and* an empty one — both the AuditLog L36 violation and the 0.16 "reports success while nothing happened" lie.
- **Distributed tracing** (bullet 3) — no OpenTelemetry SDK, no collector, no instrumentation anywhere in the repo. `Trace`/`Span` rows with no spans are fiction. **Add when an OTel pipeline is actually deployed.**
- **Raw metric time-series / APM span store, continuous profiler, session replay, flame graphs** — `tenants.HealthMetric` (0.1) already owns readings; a second sample table is the parallel-schema bug (L36, SCM L37 posture).
- **Quota allowance, overage, fair-use** (bullet 4) — **`tenants.UsageRecord.included_allowance` + 0.19 bullet 3 "Usage Metering & Quotas"** own it. NavERP.md genuinely overlaps here; 0.17 keeps the *scaling trigger* and 0.19 keeps the *commercial limit*.
- **Notification channels, routing tree, receivers, contact points, on-call schedules, escalation policies** — 0.12 `Notification.py` owns delivery; 0.11 `SlaRule`/`ApprovalLimit` owns escalation. `AlertRule.notification_rule` is the single seam.
- **Silence/mute with matcher expressions; inhibition rules** (Alertmanager) — the scalar `AlertEvent.muted_until` covers the honest minimum. A matcher DSL is a 5th model for a feature nothing enforces.
- **Synthetic probe execution + heartbeat table** (Uptime Kuma `heartbeat`, PRTG probe) — no prober process. `ServiceComponent.current_status` is hand-set and the page must label it as a claim.
- **Error grouping by fingerprint as a stored issue** (Sentry) — served as a board filter over `AlertEvent` (metric + time window), not a table.
- **SLO / error budget as a table** (Datadog) — served as a computed page over `AlertEvent` + `ServiceComponent`; a stored SLO would duplicate 0.11's SLA vocabulary.
- **Incident update timeline** (Statuspage `incident_updates`) — deferred to stay at 4 models. **Trigger to add it:** when an incident needs more than `public_note` + `updated_at` to be defensible, add `IncidentUpdate` as a 5th model then.

---

## 4. Risks / boundary statements

**L36 — never re-declare a sibling's spine. 0.17 is the observability layer *over* the existing logs, not a second log store.**

1. **No new audit log.** Do not add `ErrorLog`, `AccessLog`, `SystemLog`, or a generic "event" table that could absorb `AuditLog`. `AuditLog` answers *"who changed which row"* (it has `action`, `changes`, a generic FK to the changed object). `AlertEvent` answers *"a threshold was crossed"* (it has a `rule`, an `observed_value`, a lifecycle). Different subject, different evidence — L36, not a merge.
2. **No new business-rule log.** Do not FK `AlertEvent` to `BusinessRule` or `BusinessRuleLog`. A `BusinessRule` evaluates a *condition over a record* and its log records what the *caller did*; an `AlertRule` bounds a *measured value* and its event records that the bound was crossed. Reusing `BusinessRule.OPERATORS` is a **constant reuse, not a relationship** — do not let that reuse drift into an inheritance or FK.
3. **No second metric table.** `tenants.HealthMetric` owns readings. `AlertRule` *names* a metric; it does not store values. Any `MetricSample`/`TimeSeries`/`HealthReading` model in 0.17 is a rebuild of 0.1's.
4. **No second usage/quota table.** `tenants.UsageRecord` owns consumption; 0.19 owns the commercial limit. 0.17's capacity contribution is a *trigger*.
5. **No connector-health model.** 0.13's `core:integration_board` already answers "are the connectors well?".

**Boundary vs 0.18 Threat Protection & Security Operations — the line is *what you are watching*, not *how loudly*.**

- 0.17 watches **availability and performance**: up/down, latency, throughput, error rate, resource saturation, slow queries.
- 0.18 watches **threats**: intrusion/anomaly, brute force, IP allow-deny, vulnerability/patch, WAF/CAPTCHA, SIEM. Its "Security Alerting & SIEM" bullet and "Security Incident Response" (breach notification, forensic logging) are **0.18's**.

**Boundary vs 0.20 Admin Console & System Operations — the line is *declaring intent* vs *executing it*.**

- 0.20 owns **"Job Scheduler & Background Tasks — cron jobs, queue management, and batch-process monitoring"** and **"Maintenance & Release Management"**. Therefore 0.17 declares **no scheduler, no job/queue registry, no release or change record**, and `AlertRule.frequency` is a recorded intention whose `help_text` says nothing runs it (the `SlaRule` / `SyncSchedule` / `BackupJob.frequency` precedent — all three already say this in their own docstrings).
- 0.20's **"Unified Admin Dashboard — central command center for users, security, health, and configuration"** must **link to 0.17's health board**, not re-declare health. 0.17's health board is the health leaf for both sidebars; 0.20 aggregates it.
- **Maintenance:** 0.17's `Incident(scheduled_maintenance)` is the **outward-facing notice**; 0.20's maintenance-window/release model is the **change itself** (what ships, when, phased rollout). 0.20 should FK `Incident` to announce a window, not copy it.

**Boundary vs 0.19 License & Subscription Administration.** NavERP.md gives "quota management" to 0.17 bullet 4 **and** "Usage Metering & Quotas — consumption tracking, overage alerts, fair-use limits" to 0.19 bullet 3. **Ruling: 0.19 owns the quota** (it is the commercial limit, and 0.1 already stores the consumption); **0.17 owns the scaling trigger** (`AlertRule.category="capacity"`). Flag this in `NavERP-ERD.md` in the same pass as the build (L36: reconcile the ERD for **both** modules, do not just note the conflict).

**Boundary vs 0.21 / 0.11.** Postmortems → 0.21. Escalation/on-call → 0.11. Error-budget/SLA targets → 0.11's `SlaRule` vocabulary, computed not stored.

**House-style rules the build must not break.**

- **NULL is not 0** (0.16 `Backup.py`): `warning_threshold`, `critical_threshold`, `observed_value`, `threshold_at_fire`, `last_status_at` are nullable *on purpose*, with `*_display` properties rendering `None` as `"—"` / "Not measured" / "Not verified". A `0` that means "not reported" is the most dangerous number an operations board can print.
- **Nothing performs the act** (0.8 / 0.16): no model here evaluates a threshold, probes a service, sends a notification or publishes a status page. Every page built on these four models must say so in the same voice 0.16 uses.
- **L22:** `fired_at`, `acknowledged_at`, `resolved_at`, `last_status_at`, `notified_at` are system-set — **zero editable `DateTimeField`s on the forms** (mirror `tenants.HealthMetric.recorded_at`).
- **L33/L40:** badges are `badge-green` / `badge-red` / `badge-amber` in `theme.css`; use `.detail-label` / `.detail-value` for detail rows. Every badge branch needs an `{% else %}` falling back to `{{ obj.get_field_display }}`.
- **L38/L52:** the docstrings' "nothing runs this" claims must be true at review time. If the build wires anything that *does* evaluate, update the prose in the same commit — do not let prose assert what the code does not do.
- **L28 (clone sweep):** if review finds a per-model defect in the four `Monitoring.py` models, sweep the four `templates/core/<entity>/` triples and the `crud()` URL entries together, not just the offending one.
- **Filter rules:** every list view must pass its own `*_choices` into context (`state_choices`, `status_choices`, `category_choices`, `kind_choices`, `metric_choices`); FK filter params validated before `.filter(fk_id=…)` (L11); paginate after filtering (L9).
- **L43/L51:** claim the migration number before generating, and `makemigrations` is scoped to the app **registry** — check no peer session added a model to `core` in the same checkout.

**Residual risk:** the honest-claim surface here is large — all four models are registers of things that did not happen automatically. The single highest-value review question is therefore *"does any page on these models imply NavERP is watching something it is not watching?"*

### 4.1 Per-relationship ownership (who owns what)

- **The 0.18 seam is one enum value:** `AlertRule.category` includes `security` so 0.18's rules land in
  the same *rule* table and the same board, but every **other** 0.17 model treats a security rule as
  ordinary. 0.18 must **not** add category-scoped columns to `AlertRule` (`threat_level`, `ip_address`,
  `cvss_score`) — those are 0.18 fields on 0.18 models that FK `AlertRule`/`ServiceComponent` if they
  want correlation.
- **Incidents:** 0.17's `Incident` is **service-availability** comms. 0.18's security incident response
  owns a **security** incident; it should either FK `core.Incident` (a breach *is* a service-availability
  event too) or own its own — but it must not expect 0.17 to have modelled breach notification, forensic
  evidence or regulatory timelines. Those are 0.18's fields.
- **Postmortem records** → 0.21 Compliance/Governance (and 0.18 for security incidents).
  `incident_type="postmortem"` is reserved but unused.
- **Status-page public rendering, subscriber email/SMS lists, uptime % history** — 0.12 delivery +
  `tenants.HealthMetric.uptime_pct`.
- **`Incident.Relates to:** FK `tenant`, `service` + M2M `affected_services` → `ServiceComponent`,
  `primary_alert` → `AlertEvent`. **No FK to `core.SlaRule`** (process escalation, 0.11) or
  `EnvironmentInstance` (0.16) — a maintenance notice is a communication about a window someone else owns.
