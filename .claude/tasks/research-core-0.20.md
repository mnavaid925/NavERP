# Research — Sub-module 0.20: Admin Console & System Operations (Module 0 — Core / Foundation, `apps/core`)

**Scope (verbatim from `NavERP.md` lines 266–271, the five bullets, and nothing else):**

1. **Unified Admin Dashboard** — Central command center for users, security, health, and configuration.
2. **Job Scheduler & Background Tasks** — Cron jobs, queue management, and batch-process monitoring.
3. **Maintenance & Release Management** — Maintenance windows, phased feature rollout, and change management.
4. **Bulk Operations & Data Tools** — Mass updates, recalculations, and data-fix utilities.
5. **Self-Service Support & Help Center** — In-app help, knowledge base, and support-ticket integration.

---

## Repo state checked first

### `LIVE_LINKS` — module 0 built so far (read at run time from `apps/core/navigation.py`)

Present keys: **`0.1` 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 0.10 0.11 0.12 0.13 0.14 0.15 0.16 0.17 0.18 0.19**.
**`0.20` has NO entry** — it is the lowest unbuilt sub-module in module 0. (0.21 Compliance is next after it.)

### Spine entities — recursive grep, verbatim evidence

Command run over `apps\*\models\**\*.py` + `apps\*\models\*.py` (models are **packages**, never `models.py` — L28):

**EXIST (with file):**

| Class | File |
|---|---|
| `SyncSchedule` | `apps/core/models/Integration.py:219` |
| `FeatureFlag` | `apps/core/models/FeatureFlag.py:14` |
| `EnvironmentInstance` | `apps/core/models/Backup.py:511` |
| `BackupJob` | `apps/core/models/Backup.py:97` |
| `DataArchive` | `apps/core/models/Backup.py:273` |
| `LegalHold` | `apps/core/models/LegalHold.py:36` |
| `ServiceComponent` | `apps/core/models/Monitoring.py:98` |
| `AlertRule` | `apps/core/models/Monitoring.py:203` (and `apps/inventory/models/AlertsNotifications/AlertRules.py:17` — a second app's own) |
| `AlertEvent` | `apps/core/models/Monitoring.py:401` |
| `Incident` | `apps/core/models/Monitoring.py:545` |
| `NotificationChannel` / `NotificationTemplate` / `NotificationRule` / `NotificationPreference` | `apps/core/models/Notification.py:32 / 62 / 92 / 150` |
| `AuditLog` | `apps/core/models/AuditLog.py:5` |
| `Activity` | `apps/core/models/Activity.py:5` |
| `SettingDefinition` / `SettingValue` | `apps/core/models/Setting.py:16 / 52` |
| `NumberingScheme` | `apps/core/models/NumberingScheme.py:15` |
| `ConnectorDefinition` / `MappingTemplate` / `ApiCredential` / `RateLimitPolicy` | `apps/core/models/Integration.py:143 / 185 / 35 / 114` |
| `Tenant` | `apps/core/models/Tenant.py:17` |
| `Party` / `PartyRole` | `apps/core/models/Party.py:5` / `PartyRole.py:5` |
| `OrgUnit` | `apps/core/models/OrgUnit.py:5` |
| `Case` / `CaseComment` / `SlaPolicy` | `apps/crm/models/CustomerService/Cases.py:5 / 120`, `SlaPolicies.py:10` |
| `KbCategory` | `apps/crm/models/CustomerService/KbCategories.py:5` |
| `HelpdeskCategory` / `HelpdeskTicket` | `apps/hrm/models/Helpdesk/Helpdeskcategory.py:5`, `Helpdeskticket.py:7` |
| `KnowledgeArticle` | `apps/crm/models/CustomerService/KnowledgeBase.py:5` **and** `apps/hrm/models/Helpdesk/Knowledgearticle.py:5` — two distinct classes, two distinct `app_label`s |

**DO NOT EXIST as classes (verified absent):**

- **`KnowledgeBase`** — there is a *file* `apps/crm/models/CustomerService/KnowledgeBase.py`, but the class it defines is **`KnowledgeArticle`** (prefix `KB`). Do not "reuse `core.KnowledgeBase`"; it does not exist.
- **`User` / `Role` / `Permission`** — they live in **`apps/accounts/models.py`** (flat module), not in `apps/core/models/`. Import as `settings.AUTH_USER_MODEL` / `"accounts.Role"`.
- No class anywhere in the repo is named `JobDefinition`, `JobRun`, `MaintenanceWindow`, `ChangeRequest`, `BulkOperation`, `HelpTopic`, `AdminTask`, `CommandLog` or `Runbook` — every name 0.20 might want is free.
- `HelpdeskSLAPolicy` also exists at `apps/hrm/models/Helpdesk/Helpdeskslapolicy.py:18` (prefix `HSLA`), separate from `crm.SlaPolicy` (prefix `SLA`).


### The four reconciliations that decide 0.20

**(a) Bullet 2 — the scheduler is a REGISTER, not a runner. `requirements.txt` proves it.**
Full dependency list: `Django==5.1.15`, `PyMySQL`, `python-dotenv`, `stripe`, `Pillow`, `cryptography`, `pdfplumber`, `pytest`, `pytest-django`, `python-barcode`, `qrcode`. **No Celery, no RQ, no APScheduler, no huey, no django-q, no dramatiq.** `config/settings.py::INSTALLED_APPS` contains only the 12 NavERP apps plus the six `django.contrib` ones — **no `django_celery_beat`** (the single repo-wide hit for that string is a *string inside a skip tuple* at `apps/core/views/privacy.py:66`, not an installed app).
`core.SyncSchedule`'s own docstring (`Integration.py:220`) reads verbatim: *"A recorded sync intention. **Nothing runs it** — the repo has no scheduler."* — **confirmed.**
The identical posture is already committed three more times: `AlertRule.frequency`, `BackupJob.frequency` and `Security.VulnerabilityFinding.due_on` each carry a docstring saying no scheduler reads them, and `research-core-0.18.md:199` explicitly hands the scheduler to 0.20.
**Therefore: 0.20 EXTENDS `core.SyncSchedule` by FK and adds a job-definition + run register, exactly the way 0.16's `BackupJob` and 0.17's `AlertEvent` are already "registers of recorded firings." Nothing here executes anything; a POST-only "Run now" action writes a `JobRun` row and nothing else. Do NOT propose adding a dependency** — it is out of scope for this build.

**(b) Bullet 3 — extend by FK, own the CHANGE/CAB + RELEASE register.**
`core.FeatureFlag` (0.10) is the per-tenant toggle; `core.EnvironmentInstance` (0.16 bullet 5, `Backup.py:511`) is the dev/test/staging/sandbox target; `core.Incident` (`Monitoring.py:545`) already carries `incident_type = "scheduled_maintenance"` with `scheduled_for` / `scheduled_until` — and its own `clean()` says, verbatim: *"This is the notice, not the change record (**0.20 owns that**)."* That is an as-built instruction, not a doc guess. 0.20 FKs all three and adds the change/release register beside them.

**(c) Bullet 4 — there IS bulk/mass-update precedent, and it is deliberately non-executing.**
`core.BusinessRule` + `core.BusinessRuleLog` (`apps/core/models/BusinessRule.py:23 / 72`) is the closest thing in the repo: `BusinessRule.condition` is a JSON predicate, `evaluate_rules()` returns matching rules **in priority order** with a recommended action, and the module docstring is blunt — *"It does NOT execute the action. There is no cross-module action executor here, and building one would mean this app reaching into 71 approval engines and mutating their rows — the L36 mistake at the largest scale."* `BusinessRuleLog.action_taken` is free text because *the caller* performs the action and reports back. `core.CustomFieldValue` (`CustomField.py:61`) is the second precedent: a value store that can be bulk-written but is not itself a bulk tool. 0.20's bulk model must follow this posture: **declare the target set, declare the mutation, record what the caller did.**


**(d) Bullet 5 — THE BIGGEST DUPLICATION TRAP. Two knowledge bases and two ticket tables already exist.**
- `crm.Case` (`CASE-`), `crm.CaseComment`, `crm.SlaPolicy` (`SLA-`), `crm.KbCategory`, `crm.KnowledgeArticle` (`KB-`, with `kb_category` FK, `visibility`, `status`, `views_count`/`helpful_count`/`not_helpful_count`, `public_token`) — **CRM 1.4, already built.**
- `hrm.HelpdeskTicket` (`TKT-`, with `category` FK, `assignee`, `sla_policy` FK, `first_response_due`, `resolution_due`, `satisfaction_rating`), `hrm.HelpdeskCategory`, `hrm.KnowledgeArticle` (`KBA-`), `hrm.HelpdeskSLAPolicy` (`HSLA-`) — **HRM 3.x, already built.**
**0.20 must NOT create a third ticket table or a third knowledge base (L29/L36).** Bullet 5 is served by a **computed board that reads the four existing tables** and links to their existing list/detail pages, plus — at most — a thin *routing* register. This is load-bearing: two `KnowledgeArticle` classes already exist in two apps, and a naive "add `core.HelpArticle`" is exactly the mistake the lessons file exists to prevent.

**(e) Bullet 1 — the "unified" page is a NEW roll-up that LINKS existing boards. It replaces nothing.**
`templates/core/` already contains, verified by directory listing: `configoverview.html`, `securityoverview.html`, `healthboard.html`, `monitoringoverview.html`, `backupboard.html`, `threatboard.html`, `vulnerabilityboard.html`, `breachclock.html`, `bruteforceboard.html`, `capacityboard.html`, `firingboard.html`, `deliveryboard.html`, `integrationoverview.html`, `integrationboard.html`, `settingsoverview.html`, `numberingboard.html`, `retentionboard.html`, `localizationboard.html`, `calendarboard.html`, `workflowoverview.html`, `notificationoverview.html`, `privacyoverview.html`, `consentmatrix.html`, `accessmatrix.html`. Their url names are all live in `apps/core/urls.py` (`health_board`, `threat_board`, `vulnerability_board`, `breach_clock_board`, `brute_force_board`, `capacity_board`, `firing_board`, `backup_board`, `config_overview`, `settings_overview`, `security_overview`, `monitoring_overview`, `integration_overview`, `notification_overview`, `retention_board`, `numbering_board`, `workflow_overview`, `localization_board`, `delivery_board`, `privacy_overview`, `access_matrix`, `consent_matrix`, `calendar_board`). 0.20 adds a `core:admin_board` that **aggregates and links** them; it re-declares no health, no security, no backup and no config logic.

### Structural constraints the `todo` agent must honour

- **Backend rule 9:** `apps/core` is a Module-0 foundation app with **no sub-module level**. Entity files sit FLAT at the package root: `apps/core/models/SystemOps.py`, `apps/core/forms/SystemOps.py`, `apps/core/views/SystemOps.py` — and each must be re-exported from the package `__init__.py`.
- **Template rule 4:** templates stay flat under `templates/core/<entity>/`. A board is a **standalone page at `templates/core/<name>.html`** (rule 6), not inside an entity folder.
- **`core` has NO `TenantNumbered` base.** Core models are plain `models.Model` with an explicit `tenant` FK. If 0.20 needs auto-numbers, the established in-repo pattern is `tenants.EntitlementFeature` / `UsageQuota` / `LicenseAssignment`: a `number = models.CharField(..., editable=False)` minted in `save()` via `next_number(Model, self.tenant, "JOB")`, **plus an entry in `apps/core/settings_engine.py::LITERAL_PREFIX_MODELS`** or `prefix_usage()` will report the prefix as unused on the reconciliation board.
- **Prefix availability, grep-verified against every `NUMBER_PREFIX = "…"` in the repo:** `JOB` **FREE**, `RUN` **FREE**, `MNTW` **FREE**, `CHG` **FREE**, `BULK` **FREE** (the only `BULK` hits are test-fixture *arguments*, not prefixes). **TAKEN and to be avoided:** `REL`, `OPS` (used as a free-text `evidence="OPS-1041"` string in `seed_core.py:869`, so it already reads as an ops ticket number), `SYNC` is technically free but is 0.13's word and would invite a second-sync-table reading, `SCR` (four different models already collide on it), `TASK`, `TSK`, `TRC`.
- **Tenant-consistency edge:** the last four core entity groups (`Backup`, `Monitoring`, `Security`, `LegalHold`) inherit `TenantConsistentMixin` from `apps/core/models/Backup.py:53`. 0.20's models should too — it walks every FK at `clean()` time and is enforced on the form, the admin **and** the seeder.


---

## Leaders surveyed (with source links)

The sub-module's domain is the **admin console / system-operations plane of a large multi-tenant application** — not observability generally, not ITSM generally. Nine products, each read for its slice:

1. **Apache Airflow** — the reference open-source batch orchestrator; DAG schedules, run objects, pools, backfill — https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html · https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dag-run.html · https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/backfill.html · https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/pools.html
2. **LaunchDarkly** — feature-flag management and release tooling (progressive rollout, approvals, scheduled changes) — https://launchdarkly.com/docs/home/releases/ · https://launchdarkly.com/docs/home/releases/release-management/ · https://launchdarkly.com/docs/home/releases/scheduled-changes · https://launchdarkly.com/docs/home/releases/approvals
3. **PagerDuty** — on-call scheduling and maintenance windows (the canonical "planned silence" model) — https://support.pagerduty.com/main/docs/maintenance-windows · https://support.pagerduty.com/docs/schedules
4. **Datadog** — monitors, scheduled downtimes with tag/group scope, and a status page with component impact precedence — https://docs.datadoghq.com/monitors/ · https://docs.datadoghq.com/monitors/downtimes/ · https://docs.datadoghq.com/service_management/status_pages/
5. **Grafana** — alert rules (query + condition + interval + duration), the notification policy tree, silences and mute timings — https://grafana.com/docs/grafana/latest/alerting/ · https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rules/ · https://grafana.com/docs/grafana/latest/alerting/fundamentals/notifications/
6. **Freshservice** — ITSM with change management, knowledge management, self-service portal, SLA management and a **sandbox** for testing changes without touching live — https://www.freshworks.com/freshservice/features/ · https://www.freshworks.com/freshservice/
7. **Atlassian Jira Service Management** — request/incident/problem/**change**/asset/knowledge management with risk-aware change rollout and self-service knowledge — https://www.atlassian.com/software/jira/service-management/features
8. **New Relic** — alert notification integrations, message templates, and *temporarily mute your notifications* as a first-class lifecycle verb — https://docs.newrelic.com/docs/alerts/get-notified/notification-integrations/
9. **Zendesk Guide** — the help-center content model in detail: articles inside sections inside categories, draft state, labels, permission groups, user segments, votes — https://developer.zendesk.com/api-reference/help_center/help-center-api/articles/ · https://developer.zendesk.com/api-reference/help_center/help-center-api/sections/

---

## Feature catalog (this sub-module only)

### Bullet 1 — Unified Admin Dashboard

- **Single roll-up page that links, never re-derives** — one page carrying a health tile, a security tile, a jobs tile, a changes tile and a config tile, each tile linking to the board that already owns that answer (`core:health_board`, `core:security_overview`, `core:backup_board`, `core:config_overview`, `core:settings_overview`, `core:threat_board`, `core:capacity_board`, `core:integration_board`). · seen in: Datadog (Governance Console + Status Pages), Grafana (one consolidated view), Freshservice (unified ServiceOps) · priority: **table-stakes** · spine: **new computed board page `templates/core/adminboard.html`, zero new models** — every tile counts a verified-existing table (`core.ServiceComponent`, `core.AlertEvent`, `core.Incident`, `core.BackupJob`, `accounts.User`, `core.SettingValue`, `tenants.LicenseAssignment`, `tenants.UsageQuota`) · buildable now.
- **"Everything needs attention" count strip** — a single number per surface (open alerts, overdue vulnerabilities, breached SLAs, failing jobs, upcoming maintenance windows, seats over quota) so an admin can triage without opening six pages. · seen in: Freshservice (Freddy Insights ticket trends), Grafana · priority: **common** · spine: computed from verified tables, no new model · buildable now.
- **Drill-through rather than duplication** — a rule the whole sub-module obeys: every tile is a link. The `LIVE_LINKS` comments for 0.17/0.18/0.19 already enforce "5 bullets over 5 **distinct** targets" so the sidebar never highlights two labels on one page; 0.20 must keep that discipline. · priority: **table-stakes** · spine: `apps/core/navigation.py` · buildable now.
- **Config drift summary** — settings whose `SettingValue` disagrees with the `SettingDefinition` default, plus `NumberingScheme` prefixes no model mints. · seen in: Grafana, Odoo-style admin consoles · priority: **common** · spine: reuses **`core.SettingDefinition` / `core.SettingValue`** and **`core.NumberingScheme`** via `settings_engine.prefix_usage()` — adds no table · buildable now.
- **NOT in scope:** building a new health/availability calculation. 0.17's `health_board` already owns it (L36: 0.17 declares no scheduler, no job registry, and hands both to 0.20 — the reverse direction does not apply).


### Bullet 2 — Job Scheduler & Background Tasks

- **Job definition register** — one row per scheduled unit of work: a name, the module it belongs to, a **schedule expression** (cron or interval), a **handler target** (module path + callable), a timeout, a priority, an enabled flag, and last/next *recorded* run timestamps. · seen in: Airflow (a DAG holds `schedule`, `tasks`, callbacks, retries, timeouts), Grafana (an alert rule holds an **interval** and a **duration**), Odoo `ir.cron` (model + method + interval + `nextcall`) · priority: **table-stakes** · spine: **new `JobDefinition`**; **FK to the verified `core.SyncSchedule`** so a 0.13 integration schedule is *referenced* by a job rather than re-declared (L29/L36) · buildable now.
- **Job run register** — one row per execution attempt: a FK to the job, a **trigger kind** (`scheduled` / `manual` / `backfill` / `retry`), a status (`queued`/`running`/`success`/`failed`/`skipped`/`cancelled`), start/finish timestamps, duration, rows-affected, and a free-text error. · seen in: Airflow (`DagRun` is "an object representing an instantiation of the Dag in time"; status derives from the leaf tasks; every execution creates one), Grafana (firing/resolved instances) · priority: **table-stakes** · spine: **new `JobRun`**, child of `JobDefinition` in the same entity file; `triggered_by` → `settings.AUTH_USER_MODEL` · buildable now.
- **Manual "Run now" that records rather than executes** — a POST-only action that opens a `JobRun`, stamps a started/finished pair from the request, and writes the result. It performs no background work, and the page says so in the same register-honest tone `SyncSchedule` already uses. · seen in: Airflow (manual trigger from UI/CLI creates a run alongside scheduled ones) · priority: **common** · spine: view action only, no model · buildable now.
- **Backfill / catch-up as a declared range** — record a from/to window and a reprocessing policy (`missing_only` / `missing_and_failed` / `all`) rather than firing it. · seen in: Airflow (backfill by date range, three reprocessing behaviours, `max_active_runs`, dry run, run-backwards) · priority: **common** · spine: fields on `JobRun` / `JobDefinition`, no new table · buildable now.
- **Queue / concurrency pool** — a named capacity that bounds how many jobs may run at once, with queued-vs-running shown per job. · seen in: Airflow Pools (named pools of worker slots; a task occupies `pool_slots`; once capacity is reached runnable tasks show as **queued**; a default pool always exists) · priority: **common** · spine: **fields on `JobDefinition`** (`pool_name`, `pool_slots`, `max_active_runs`) — Airflow's *whole point* is that a pool is a named slot count, so a table would be over-modelling · buildable now (as declaration).
- **Deadline / overdue detection** — how long a job has been overdue relative to its own schedule, and which jobs have missed consecutive runs. · seen in: Airflow Deadline Alerts (a time threshold on a run with a callback when exceeded, referenced to queue time or start time), Airflow auto-pause after N consecutive failures · priority: **common** · spine: **computed on the board** from `JobRun` + `JobDefinition.next_run_at`; auto-pause is a recorded `max_consecutive_failures` + a status, not an action · buildable now.
- **⚠️ DECLINE — an actual scheduler.** No Celery / RQ / APScheduler / django-q in `requirements.txt`, and no worker app in `INSTALLED_APPS`. The `next_run_at` column is a **recorded intent**; nothing advances it. The docstrings of `SyncSchedule`, `AlertRule`, `BackupJob` and `VulnerabilityFinding.due_on` already say exactly this, and `research-tenants-0.19.md:104` explicitly declined automatic renewal execution *because* 0.20 was unbuilt. 0.20 closes that by being the register, and the register is still a register.
- **⚠️ DECLINE — a queue broker table / `QueueDepth` time series.** Airflow's pool *is* the queue-management surface; NavERP has no broker, so a depth table would be permanently empty (L52 — a permanently-empty field is a lie by omission).
- **⚠️ DECLINE — a worker/agent fleet table.** There is no worker process to register.


### Bullet 3 — Maintenance & Release Management

- **Maintenance window with an explicit start and end** — a planned window with a start, an end, a recurrence, and a stated purpose; one-ended windows are invalid. · seen in: PagerDuty Maintenance Windows (create/update, **End Now** to finish early, delete only *future* windows because **past ones are kept as history**, indefinite "disable a service" mode, recurring windows created through the API) · priority: **table-stakes** · spine: **new `MaintenanceWindow`**, with FK to the verified **`core.ServiceComponent`** (what is affected) and FK to **`core.EnvironmentInstance`** (which env is down) · buildable now.
- **Planned silence / mute scope** — what a window suppresses and what it does not: alerts for the named services, notification delivery, and (declared) job execution. · seen in: Datadog Downtimes (scope by monitor name **or** by tag, an extra group-scope filter with its own query syntax, a **Preview affected monitors** step, and the rule that a monitor created or edited *after* the downtime is scheduled is automatically included if it matches), Grafana (notification-policy tree with **mute timings** and **silences**), New Relic (temporarily mute notifications) · priority: **table-stakes** · spine: fields on `MaintenanceWindow`; the "what it silences" set references the verified **`core.AlertRule`** / **`core.NotificationRule`** by FK or M2M, and the page states that **nothing consults it** — the 0.17 `Incident(scheduled_maintenance)` row remains the outward-facing notice · buildable now.
- **Outward notice linked, not copied** — the window points at the `core.Incident` of type `scheduled_maintenance` that announces it, so 0.20 owns the change and 0.17 owns the communication. · seen in: Datadog Status Pages (a Maintenance notice is a *separate* status from Major/Partial Outage/Degraded/Operational, and it does **not** count as downtime in the uptime percentage) · priority: **table-stakes** · spine: **FK to the verified `core.Incident`**; the reverse is deliberately not created (0.17's docstring says *"Incident has no FK to EnvironmentInstance — a maintenance notice is a communication about a window somebody else owns"*) · buildable now.
- **Change advisory / change request register** — the change itself: a title, a **change type** (standard / normal / emergency), a **risk** and an **impact** assessment, a requester and an approver, a target environment, a planned window, a status lifecycle, a rollback plan, and a post-implementation review note. · seen in: Freshservice change management (assess impact with real service context, identify risks early, roll out with confidence, plus **change success rate** reporting), Jira Service Management change management (richer contextual information from development tools so teams make better decisions and minimise risk) · priority: **table-stakes** · spine: **new `ChangeRequest`**, FK to the verified **`core.EnvironmentInstance`**, FK to **`MaintenanceWindow`**, FK to **`accounts.User`** for requester/approver, inheriting `TenantConsistentMixin` · buildable now.

- **Phased feature rollout** — serving a feature to a widening slice: a percentage or cohort, a start and an end date, and the flag being rolled. · seen in: LaunchDarkly (**percentage rollouts** fixed share of contexts, **progressive rollouts** that increase the share automatically over time, **guarded rollouts** that watch a metric and can roll back on regression, **experiments** that compare variations; plus **scheduled flag changes** so a rollout can be planned in steps — internal testing, then a beta segment, then 100%) · priority: **common** · spine: **a `FeatureRollout` child of `ChangeRequest`** (same entity file) carrying the **FK to the verified `core.FeatureFlag`**; `core.FeatureFlag` already resolves per-tenant / per-plan / per-role, so 0.20 does **not** re-declare a targeting engine — it records the *plan* for flipping one · buildable now (as a recorded plan).
- **Flag-change approval gate** — a proposed change that must be approved before it applies, with the approver and the decision recorded. · seen in: LaunchDarkly approvals (a change to a flag's targeting or variations can be put up for review, the request appears in an approvals dashboard, and Enterprise customers can *require* approval per environment) · priority: **common** · spine: fields on `ChangeRequest` / `FeatureRollout` (requested/approved/rejected + approver + decided_at). The repo's own approval machinery is `core.WorkflowDefinition` / `core.ApprovalLimit` (verified) — 0.20 records the decision, it does not build a second approval engine · buildable now.
- **Required comment / confirmation before a risky change** — a checkbox and a justification that must be present before a change can be marked approved. · seen in: LaunchDarkly (required comments, required confirmation) · priority: **common** · spine: fields on `ChangeRequest` (`change_note`, `confirmed_at`) · buildable now.
- **Environment promotion path** — which environment a change moves through on its way to production. · seen in: Freshservice **sandbox** ("set up sandbox environments to test changes and train users safely without disrupting your live setup") · priority: **common** · spine: FK to the verified **`core.EnvironmentInstance`**, whose `KIND_CHOICES` already carry `development`/`test`/`staging`/`sandbox`/`preview`/`production` and whose `source_environment` self-FK already models "cloned from" · buildable now.
- **⚠️ DECLINE — a build/deploy pipeline or artifact store.** NavERP ships no build artifacts; a deployment pipeline would be a table of nothing.
- **⚠️ DECLINE — automatic flag flipping at a scheduled time.** No scheduler (see bullet 2). `FeatureRollout` records the plan; the docstring says nothing fires it.
- **⚠️ DECLINE — automatic rollback on a metric regression.** No metric pipeline, no scheduler. A guarded rollout is recorded as an *intent to watch*, with the metric named in free text.


### Bullet 4 — Bulk Operations & Data Tools

- **Declared bulk operation with a target and a filter** — a saved, reviewable description of a mass change: the **target model**, the **filter** (as JSON, inspectable in the DB), the **fields to set**, a **dry-run** flag, and an **estimated/actual affected count**. · seen in: Salesforce-style mass update / Data Loader (mass operations are a distinct admin surface from ordinary record editing) · priority: **common** · spine: **new `BulkOperation`**; the filter reuses the **same JSON predicate shape as the verified `core.BusinessRule.condition`** (`{"all": [{"field", "op", "value"}]}`) so one mental model covers rules and bulk ops · buildable now.
- **Operation kind vocabulary** — `mass_update` / `recalculate` / `reprocess` / `archive` / `data_fix`, so "recalculation" and "data-fix utilities" are named rows rather than prose. · seen in: Odoo server actions (one model, several kinds of automation), Airflow (one DAG model serving many workloads) · priority: **table-stakes** · spine: `KIND_CHOICES` on the new model · buildable now.
- **Pre-flight preview before commit** — show the matching row count and a sample before anything is written. · seen in: Airflow backfill **dry run** (prints the dates that *would* be created), Datadog downtime **Preview affected monitors** · priority: **common** · spine: a view that evaluates the JSON filter and reports a count; **writes nothing** · buildable now.
- **Caller-reported outcome, not an executor** — the row records the **rows affected**, the outcome status, and a free-text "what the calling module did", exactly like `BusinessRuleLog.action_taken`. · seen in: `apps/core/models/BusinessRule.py` (docstring: *"this app never performs it, so it cannot know more than it is told"*) · priority: **table-stakes** · spine: **reuse the verified `core.BusinessRuleLog` posture verbatim** — this is the L36 pattern already committed in this very app · buildable now.
- **Reversibility / undo reference** — a pointer to the batch a corrective action belongs to, and whether the operation declared itself reversible. · seen in: Grafana (alert-rule versions), Airflow (clear/re-run task instances) · priority: **common** · spine: `reverses` self-FK + `is_reversible` on the new model; a full undo journal is deferred · buildable now (as a declaration).
- **Approval for a wide-reaching bulk change** — an affected-count threshold above which the operation needs a second pair of eyes. · seen in: Freshservice (change approvals), LaunchDarkly (required approvals for sensitive changes) · priority: **common** · spine: fields on the new model, reusing the `core.ApprovalLimit` vocabulary by reference · buildable now.
- **⚠️ DECLINE — an actual mass-update executor.** `BusinessRule`'s docstring already rejects one in this exact app: reaching across 71 approval engines to mutate their rows "is the L36 mistake at the largest scale, and a silent data change nobody asked for." 0.20 records the intent; the calling module acts and reports.
- **Deferred — import/export data tools.** A CSV importer is a data-model question, not an admin-console one; it belongs with whichever module owns the target entity.


### Bullet 5 — Self-Service Support & Help Center

- **⚠️ THE DUPLICATION TRAP — verified, and load-bearing.** `crm.Case` + `crm.CaseComment` + `crm.SlaPolicy` + `crm.KbCategory` + `crm.KnowledgeArticle` (CRM 1.4) **and** `hrm.HelpdeskTicket` + `hrm.HelpdeskCategory` + `hrm.KnowledgeArticle` + `hrm.HelpdeskSLAPolicy` (HRM 3.x) all exist today, with priorities, statuses, assignees, SLA due-dates, satisfaction ratings, satisfaction comments, categories, article visibility, draft status, view counts and helpful/not-helpful counts already modelled. **A `core.HelpArticle`, a `core.SupportTicket` or a `core.KnowledgeBase` would be the third of each.** Do not build one.
- **Unified support inbox board** — one page that reads all four existing tables and shows open counts by status, priority and age, each row linking to the owning app's existing list/detail page (`crm:case_list`, `hrm:helpdesk_ticket_list`, `crm:knowledgearticle_list`, `hrm:knowledgearticle_list`). · seen in: Freshservice (omnichannel support with a unified view across channels), Zendesk (one request object surfaced through every channel) · priority: **table-stakes** · spine: **new computed board, ZERO new models** — reads the verified `crm.Case` / `hrm.HelpdeskTicket` / `crm.KnowledgeArticle` / `hrm.KnowledgeArticle` · buildable now.
- **In-app help content model (for reference, not for duplication)** — articles carry a draft/published state, a **category** and **section** hierarchy, **labels/tags**, a **visibility** scope, a **vote** signal, and a **view count**. · seen in: Zendesk Guide (articles live in sections, sections live in categories; a `draft` flag per locale; `label_names` filtering; permission groups and user segments restrict who sees an article; votes and badges) · priority: **common** · spine: **all of these attributes already exist** — `crm.KnowledgeArticle.status`/`.kb_category`/`.visibility`/`.views_count`/`.helpful_count`/`.not_helpful_count` and `hrm.KnowledgeArticle.status`/`.category`/`.tags`/`.views_count`. 0.20 adds **no help-content table**; it may only *link* · buildable now (as links).
- **Suggested-article / deflection reporting** — which articles were viewed before a ticket was raised, i.e. whether self-service actually deflected. · seen in: Zendesk (suggested articles surfaced in the chat widget), Freshservice (centralised knowledge base that "reduces agent load", with usage insights) · priority: **common** · spine: **computed on the board** from the verified view counts and the existing ticket rows; a proper deflection join needs a ticket↔article link that does not exist — **defer** rather than invent a join table · buildable now as a count, deferred as a join.
- **Support routing register** — which system owns which kind of request (a customer case vs. an internal employee ticket), and the category/SLA each routes to. · seen in: Freshservice (service catalog routes a request to the right team, SLA policies auto-escalate by priority, intelligent routing by agent skills) · priority: **common** · spine: a **thin `SupportRoute` model carrying FKs to the verified `crm.KbCategory`, `hrm.HelpdeskCategory`, `crm.SlaPolicy`, `hrm.HelpdeskSLAPolicy`** — it points at the owners, it stores no ticket and no article body. This is the *only* new model bullet 5 could justify · buildable now.
- **⚠️ DECLINE — a new ticket queue, escalation ladder or macro library.** `core.SlaRule` (verified, `Workflow.py:122`), `crm.SlaPolicy` and `hrm.HelpdeskSLAPolicy` already own SLA vocabulary; 0.11 owns escalation; 0.12 owns notification delivery. 0.20 builds none of them.

### Beyond the bullets (strong, and 0.20-shaped)

- **Scheduled-action / self-service audit view** — who changed a flag, a setting, a maintenance window or a bulk operation, and when. · seen in: LaunchDarkly (approvals surface every requested change), Grafana (alert-rule version history) · priority: **common** · spine: **read-only over the verified `core.AuditLog`** (which already carries `content_type` + `GenericForeignKey` + `changes` JSON + `user` + `at`) — **no new audit table**; 0.20's writes should flow through the same `AuditLog` so the trail is one trail · buildable now.
- **Operational notification on a job failure / window opening** — reuse the existing channel and rule vocabulary. · seen in: Airflow (a missed deadline triggers a callback to a notifier), New Relic (notification destinations and message templates) · priority: **common** · spine: **FK to the verified `core.NotificationRule` / `core.NotificationChannel`**; 0.20 records *that a notice is due* — 0.12 owns delivery and there is still no dispatcher · buildable now (as a recorded intent), delivery deferred.
- **Cross-tenant IDOR discipline on every new FK** — the admin console is the most tempting place to leak another workspace's row. · priority: **table-stakes** · spine: inherit **`TenantConsistentMixin`** (verified, `Backup.py:53`) and filter every list by `tenant=request.tenant` · buildable now.


---

## Recommended build scope (this pass — 4 models)

> All four live flat at the `apps/core/models/` package root (backend rule 9), each re-exported from `apps/core/models/__init__.py`, each inheriting `TenantConsistentMixin`.

### 1. `JobDefinition` — prefix **`JOB-`** (verified FREE; `REL`, `OPS`, `SYNC`, `SCR` taken or misleading)

Justified by: job-definition register · schedule expression + handler target · queue/pool declaration · deadline/overdue detection · backfill declaration · manual "run now" target · and by the *pointer* at 0.13's `SyncSchedule`.

| Field / choice | Justified by |
|---|---|
| `number` (`editable=False`, `next_number(..., "JOB")` in `save()` + a `settings_engine.LITERAL_PREFIX_MODELS` entry) | in-app reference for an operator; the `tenants.UsageQuota` / `LicenseAssignment` pattern |
| `name`, `module_slug` | which module owns the work; one admin console, many modules |
| `job_type` ∈ `scheduled_task`, `integration_sync`, `bulk_operation`, `report`, `cleanup`, `maintenance` | one model, several workloads (Airflow/Odoo shape) |
| `schedule_kind` (reuses **`core.SyncSchedule.FREQUENCY_CHOICES` by reference** — L36, never a second pasted list) + `cron_expression` + `interval_minutes` | Airflow `schedule`; Grafana `interval`; Odoo `ir.cron` |
| `handler_path` (module + callable, free text) | the declared target — nothing imports or calls it |
| `is_active`, `priority`, `timeout_seconds`, `max_active_runs` | Grafana rule fields; Airflow retry/timeout |
| `pool_name`, `pool_slots` | Airflow Pools, as declaration |
| `max_consecutive_failures`, `auto_pause_after` | Airflow auto-pause, as a recorded policy |
| `last_run_at`, `next_run_at` | **recorded intent — nothing advances them** |
| **FK `sync_schedule` → `core.SyncSchedule`** (SET_NULL, nullable) | **the L29/L36 reconciliation: 0.13's schedule is referenced, not re-declared** |
| **FK `environment` → `core.EnvironmentInstance`** (SET_NULL, nullable) | which env the job runs in (0.16's vocabulary) |
| `is_muted`, `notes` | a maintenance window silences a job (Datadog downtime scope) |
| inherits `TenantConsistentMixin` | the model edge every core entity group since 0.16 uses |

### 2. `JobRun` — prefix **`RUN-`** (verified FREE) — same entity file as `JobDefinition`

Justified by: the run register · trigger kind · status lifecycle · backfill as a declared range · the outcome record.

| Field / choice | Justified by |
|---|---|
| `FK job` → `JobDefinition` (CASCADE) | Airflow `DagRun` belongs to its DAG |
| `FK triggered_by` → `settings.AUTH_USER_MODEL` (SET_NULL) | who pressed Run now |
| `trigger_kind` ∈ `scheduled`, `manual`, `backfill`, `retry` | Airflow distinguishes scheduled from externally triggered runs |
| `status` ∈ `queued`, `running`, `success`, `failed`, `skipped`, `cancelled` | Airflow's terminal-state set; Grafana firing/resolved |
| `started_at`, `finished_at`, `duration_seconds` | Grafana's `duration`; Airflow's start reference |
| `rows_affected` | the number a batch process is actually judged on |
| `error_text`, `log_reference` | free text — the register does not own logs (0.17 explicitly declined a log store) |
| `reprocess_behaviour`, `backfill_from`, `backfill_to` | Airflow's three reprocessing behaviours, recorded not executed |
| `is_dry_run` | Airflow backfill dry run; Datadog "Preview affected monitors" |
| `notes` | free text |


### 3. `MaintenanceWindow` — prefix **`MNTW-`** (verified FREE; `MNT` also free, `MNTW` is unambiguous) — `apps/core/models/Maintenance.py`

Justified by: maintenance windows · planned silence / mute scope · the outward-notice link.

| Field / choice | Justified by |
|---|---|
| `number` (`next_number(..., "MNTW")` + `LITERAL_PREFIX_MODELS` entry) | operator reference; `MNTW-00001` |
| `title`, `purpose` | PagerDuty windows have a scheduled purpose |
| `starts_at`, `ends_at`, `recurrence` (`once`/`daily`/`weekly`/`monthly`), `timezone_label` | PagerDuty (one-off + recurring), Grafana active-time windows. **`clean()` requires both ends and `ends_at >= starts_at`** — a one-ended window is not a window (the `core.Incident.window_valid` precedent) |
| `M2M affected_services` → **`core.ServiceComponent`** | Datadog downtime scope by name; PagerDuty windows attach to services |
| `M2M suppressed_alert_rules` → **`core.AlertRule`**, `M2M suppressed_notification_rules` → **`core.NotificationRule`** | Grafana mute timings; Datadog "what to silence". **The page states nothing consults these** — 0.17's `Incident(scheduled_maintenance)` stays the notice |
| `FK incident` → **`core.Incident`** (SET_NULL, nullable) | **0.20 owns the change; 0.17 owns the communication** |
| `FK environment` → **`core.EnvironmentInstance`** (SET_NULL, nullable) | "staging is down 02:00–04:00" |
| `FK change_request` → `ChangeRequest` (SET_NULL, nullable, reverse accessor) | one change, one window (Freshservice shape) |
| `status` ∈ `draft`, `scheduled`, `active`, `ended_early`, `completed`, `cancelled`; `ended_at` | PagerDuty: **End Now**; past windows are **kept as history** and only *future* ones are deletable |
| `suppresses_jobs` (bool), `blocks_admin_writes` (bool) | the two consequences an operator must be able to *state*; recorded, not enforced (0.19's tenant-suspension lockout was parked here and stays a flag) |
| inherits `TenantConsistentMixin` | the model edge |

### 4. `ChangeRequest` — prefix **`CHG-`** (verified FREE) — `apps/core/models/Change.py`, with `FeatureRollout` as its child class in the same file

Justified by: change advisory / change request register · risk & impact · approvals · phased feature rollout · environment promotion · post-implementation review.

| Field / choice | Justified by |
|---|---|
| `number` (`next_number(..., "CHG")` + `LITERAL_PREFIX_MODELS` entry) | operator reference; `CHG-00001` |
| `title`, `summary`, `change_type` ∈ `standard`, `normal`, `emergency` | Freshservice / Jira Service Management change classes |
| `risk_level` ∈ `low`/`medium`/`high`, `impact_level` ∈ `minor`/`moderate`/`major` | "assess impact with real service context, identify risks early" |
| `FK environment` → **`core.EnvironmentInstance`**; `FK maintenance_window` → `MaintenanceWindow` | Freshservice sandbox / change calendar; the promotion path (0.16 already models `source_environment` and the 7 `KIND_CHOICES`) |
| `status` ∈ `draft`, `submitted`, `approved`, `rejected`, `scheduled`, `in_progress`, `verifying`, `completed`, `rolled_back`, `closed` | the union of the CAB lifecycle and the maintenance lifecycle 0.17 already had to union for `Incident` |
| `FK requested_by` / `FK approved_by` → `settings.AUTH_USER_MODEL` (SET_NULL) | the approver is a person, not a flag |
| `approval_required` (bool), `change_note` (text), `confirmed_at` | LaunchDarkly required comments + required confirmation + required approvals |
| `rollback_plan`, `rollback_at` | every real change register has one; a recorded plan, not an automatic rollback |
| `post_review_notes`, `success_rating` | Freshservice change success rate / post-implementation review |
| **`FeatureRollout` child**: `FK feature_flag` → **`core.FeatureFlag`**, `rollout_kind` ∈ `percentage`, `cohort`, `progressive`, `experiment`; `rollout_pct`, `cohort_label`, `planned_start_at`, `planned_end_at`, `rollback_metric` (free text), `FK approved_by` | LaunchDarkly percentage / progressive / guarded rollouts and experiments; **`core.FeatureFlag` already resolves per-tenant / per-plan / per-role, so 0.20 records the *plan*, never a second targeting engine** |
| inherits `TenantConsistentMixin` | the model edge |


### Also in this pass, with **no model at all**

- `templates/core/adminboard.html` + `core:admin_board` — the bullet-1 roll-up, linking `core:health_board`, `core:security_overview`, `core:threat_board`, `core:vulnerability_board`, `core:breach_clock_board`, `core:brute_force_board`, `core:capacity_board`, `core:firing_board`, `core:backup_board`, `core:config_overview`, `core:settings_overview`, `core:integration_board`, `core:notification_overview`, `core:retention_board`, `core:numbering_board`, plus `tenants:quota_board` and `tenants:renewal_board`.
- `templates/core/supportboard.html` + `core:support_board` — the bullet-5 unified inbox, reading `crm.Case`, `hrm.HelpdeskTicket`, `crm.KnowledgeArticle`, `hrm.KnowledgeArticle` and linking out to them. **Zero new tables.**
- `templates/core/bulkboard.html` + a `core:bulk_preview` POST action — the bullet-4 pre-flight count, evaluating the stored JSON filter and writing nothing.
- One `LIVE_LINKS["0.20"]` block, **5 bullets over 5 distinct targets**, each key copied **byte-identically** from `NavERP.md`, with extras (Job Runs, Change Register, Rollouts, Admin Board) appended after the bullets per the 0.17/0.18/0.19 pattern.

---

## Belongs to sibling sub-modules (parked, not scoped here)

| Feature | Goes to |
|---|---|
| Real health/availability computation, uptime %, SLOs | **0.17** (`core:health_board` already owns it) |
| Alert thresholds, recorded firings, incident lifecycle, the `scheduled_maintenance` **notice** | **0.17** (`core.AlertRule` / `core.AlertEvent` / `core.Incident`) |
| Threat / brute-force / IP rules, vulnerability findings, `due_on` remediation dates, security incidents | **0.18** (`core.SecurityThreat`, `VulnerabilityFinding`, `IpAccessRule`, `SecurityIncident`) |
| Seat allocation, plan entitlements, quotas, renewal & expiry | **0.19** (`tenants:LicenseAssignment`, `PlanEntitlement`, `UsageQuota`, `tenants:renewal_board`) |
| Backup, restore, drills, archives, legal holds, **sandbox/environment provisioning** | **0.16** (`core:BackupJob`, `RestoreRecord`, `RecoveryDrill`, `DataArchive`, `LegalHold`, `EnvironmentInstance`) |
| Notification **delivery**, channels, templates, dispatch | **0.12** (`core.NotificationRule` / `NotificationChannel` / `NotificationTemplate`) — 0.20 records *that a notice is due* |
| Escalation ladders, approval thresholds | **0.11** (`core.SlaRule`, `core.ApprovalLimit`, `BusinessRule`) |
| Configuration & setting definitions, numbering schemes, feature flags | **0.10** (`core.SettingDefinition`, `core.SettingValue`, `core.NumberingScheme`, `core.FeatureFlag`) |
| **The real scheduler / worker runtime** | **nobody in NavERP** — no dependency is being added |
| **Control frameworks, policy authoring, risk register, audit evidence, data residency** | **0.21** |
| Genuine tenant **suspension / read-only lockout** on a lapsed subscription (parked by `research-tenants-0.19.md:126`) | 0.20 records the *intent* as `MaintenanceWindow.blocks_admin_writes`; the **enforcement** is 0.21's policy-management territory and is **not** built here |
| Customer-facing ticket lifecycle, KB authoring, SLA policy authoring | **CRM 1.4** / **HRM 3.x** — 0.20 only links |


## Deferred (later passes / integrations)

- **A real scheduler runtime** (Celery beat / APScheduler / cron) — no dependency is added by this pass; `next_run_at` stays a recorded intent. Revisit only as an explicit, separate decision.
- **`BulkOperation` itself** — bullet 4 ships this pass as the board, the JSON-filter preview action and the `BusinessRuleLog` posture; the saved `BulkOperation` table is the *next* 0.20 pass, so this pass does not carry five new models.
- **A notification dispatcher** — 0.20 records the intent (`NotificationRule` FK); 0.12 owns delivery and no dispatcher exists yet.
- **A queue broker / worker fleet / `QueueDepth` table** — no broker exists; a depth table would be permanently empty (L52).
- **An actual bulk-update executor** — refused on purpose, matching `core.BusinessRule`'s own documented stance.
- **Ticket ↔ article deflection join** — needs a link table between `crm.Case`/`hrm.HelpdeskTicket` and the two `KnowledgeArticle` classes that neither app owns. Deferred rather than invented.
- **A build/deploy pipeline, artifact store, or environment promotion *automation*** — recorded as a change plan; nothing promotes anything.
- **A unified cross-app support inbox with a single ticket identity** — genuinely desirable, genuinely a cross-module refactor of CRM 1.4 + HRM 3.x. Deferred to a dedicated reconciliation pass, not smuggled into 0.20.
- **Community forums / suggested-article ML / AI triage** — Freshservice's differentiators; integration-tier, not this pass.
- **`SupportRoute`** — the thin routing register bullet 5 could justify; deferred so this pass stays at four models and links the existing categories/SLAs instead.

---

## The one-paragraph version for the `todo` agent

0.20 adds **four tenant-scoped models to `apps/core`**, flat at the package root, each with an auto-number minted in `save()` and registered in `settings_engine.LITERAL_PREFIX_MODELS`: **`JobDefinition` (`JOB-`)**, **`JobRun` (`RUN-`)**, **`MaintenanceWindow` (`MNTW-`)**, **`ChangeRequest` + its `FeatureRollout` child (`CHG-`)**. Every one of them is a **register of recorded intent** — there is no scheduler, no worker and no bulk executor anywhere in this repo (`requirements.txt` proves it) and each docstring must say so in the same tone `SyncSchedule`, `AlertRule`, `BackupJob` and `VulnerabilityFinding.due_on` already use. `JobDefinition` **FKs the existing `core.SyncSchedule`** rather than declaring a second schedule table; `MaintenanceWindow` **FKs `core.Incident`** (0.17's notice) and `core.ServiceComponent`; `ChangeRequest` **FKs `core.EnvironmentInstance`** and its child **FKs `core.FeatureFlag`**. Bullet 1 (unified dashboard) and bullet 5 (help center) ship as **computed boards with zero new tables** — the board links the twenty-plus existing `core:*_board` / `*_overview` pages, and the support board reads `crm.Case`, `hrm.HelpdeskTicket`, `crm.KnowledgeArticle` and `hrm.KnowledgeArticle` and links out to them. **Never build a third ticket table or a third knowledge base.**

