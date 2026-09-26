# Build Plan — Module 0 · 0.17 Monitoring, Logging & Observability


### 11.3 Phase 6 — tests, serial

- [ ] **Step 1, one agent, owns the contract:** write `.claude/tasks/test-contract-core-0.17.md` pinning the
      exact model / form / url / context names, then `apps/core/tests/__init__.py` and the shared
      `conftest.py` additions. **`conftest.py` is owned by this step alone** — no later step may edit it
      without re-running the full suite.
- [ ] Fixtures use the **`mon_` prefix** (`mon_component_a`, `mon_rule_a`, `mon_event_b`, `mon_incident_b`),
      following 0.16's `bkp_` precedent, so a later `test_writing_*` agent appending nearby cannot shadow
      them. `conftest.py` already provides `tenant_a` / `tenant_b` — **reuse them, do not redefine**.
- [ ] **Step 2, one `test-writer` agent per file, one after another**, each committed on its own as it lands:
      `test_monitoring_models.py` → `test_monitoring_forms.py` → `test_monitoring_views.py` →
      `test_monitoring_security.py`. Every test function is `test_monitoring_*`; every module-level
      helper `_monitoring_*`.
- [ ] The four modules must cover, at minimum: the two **reuse-by-reference** assertions
      (`AlertRule.COMPARATORS is BusinessRule.OPERATORS`,
      `AlertRule.FREQUENCY_CHOICES is SyncSchedule.FREQUENCY_CHOICES`) · the **NULL-is-not-0** rendering of
      every nullable numeric · the **zero editable `DateTimeField`s** rule · the action **guards** (§10.3) ·
      **seeder idempotency** (the test 0.16 recorded as missing) · **cross-tenant 404** on all eight routes ·
      the **empty-firing-board** prose.
- [ ] **Step 3: the full UNFILTERED `apps/core/tests` suite, run to green.** Never `-k` filtered — a filter
      excludes exactly the tests a shared-file change can break (L47). This run must also include the
      pre-existing `test_crud_enum_guard.py` and `test_navigation_active.py`, which walk the new `choices`
      tuples and the new sidebar entries respectively.
- [ ] Run that suite **once without `--nomigrations`** — the only run that proves `0015_*` applies to a clean
      database (§9's final gate).

### 11.4 Phase 7 — skill + docs, one file per commit

- [ ] `.claude/skills/core/SKILL.md` — append the 0.17 section: the four models with their key fields and
      choices, the **28 url names**, the 16 template paths, the seeder rows **and the two deliberate
      non-seeds**, and the `LIVE_LINKS["0.17"]` entry. Record the **ownership ruling** explicitly, because
      the next agent to touch `core` is the one most likely to "helpfully" add a log table. **Append — never
      rewrite**; the file is shared with every earlier `core` sub-module.
- [ ] **`README.md` line 1193** — the Module 0 row: `16 of 21 sub-modules built (0.1–0.16)` →
      **`17 of 21 sub-modules built (0.1–0.17)`**, and update the trailing pointer so it names the four
      that remain (0.18–0.21) rather than the five it names now.
- [ ] **`NavERP.md`** — the Module 0 counter line: `16 of 21 built — 0.1–0.16 (5 remain: 0.17–0.21)` →
      **`17 of 21 built — 0.1–0.17 (4 remain: 0.18–0.21)`**.
      WARNING: **this is the file `parse_catalog()` reads.** Re-run Gate 2 check 1 after editing it — a
      botched heading or bullet here silently changes sidebar labels across the whole app.
- [ ] Commit each of the three files separately. Never bundle them.

### 11.5 Discipline reminders (the three that actually get broken)

- [ ] **One file per commit**, `git add '<path>'; git commit -m '...'` — `;`, never `&&` (PowerShell 5.x).
      No exceptions, including for three templates in one entity folder.
- [ ] **Never `git push`.** Stop at `git commit`.
- [ ] **L45 — the tree was dirty at this session's start** (`.claude/tasks/todo.md`, `apps/sales/tests/*`,
      `templates/projects/reporting/*`, plus the 8.4 sales files). Those are **not yours**. Do not stage
      them, do not revert them, and do not let a `git add -A` sweep them into a 0.17 commit.
- [ ] **Re-append this plan into `.claude/tasks/todo.md` once that file is clean** (see the placement note
      at the top). It is dirty with another session's uncommitted work; committing it would misattribute
      their work under a message you wrote. Until its owner commits it, **this file is the plan of record**
      and the build session must read *this* file, not `todo.md`.
- [ ] `.claude/tasks/plan-core-0.17.md` is committed **on its own**, as the last file of Phase 2.
---


# Build Plan — Module 0 · 0.17 Monitoring, Logging & Observability

**Phase 2 (todo agent) output. Source of truth:** `.claude/tasks/research-core-0.17.md` (Phase 1 — read
it first; this plan executes its L36 boundary rulings rather than re-litigating them).

**Status: COMPLETE — §0 … §11, the whole sub-module.** Execute **top to bottom, strictly serially**;
nothing here may be reordered or parallelised. The spine of the plan is: §0 the ownership call (what
0.17 must **not** build) → §1–§7 the build → §8–§9 the integration → §10 the four verify gates →
§11 the Phase 4/5/6/7 close-out. **§0 is not background reading — a build that skips it will build one of
the deferred tables and the review will not catch it in time.**

> ### 📌 Placement note — read this before anything else
>
> The house Phase-2 rule says *"append the plan block to `.claude/tasks/todo.md`"*. **I did not append
> it, and this is a deliberate, documented deviation.**
>
> `todo.md` is **dirty in the working tree at session start** with the **0.16 session's uncommitted
> close-out note** (verified: `git status --porcelain` → ` M .claude/tasks/todo.md`, +32/−5, all 0.16
> final-gate and "Not ours" prose). Under **L45** that file is not mine to commit, and under **L43** I must
> not stage a shared file another session is mid-edit on. Committing it would sweep their work into my
> history under a message I wrote — the exact misattribution L45 exists to prevent.
>
> **Therefore this plan lives in its own file.** When `todo.md` is clean, **re-append the whole
> "Build Plan" block below into `todo.md` in a single append and commit it as one file** — after 0.16's
> note has been committed by its owner, never before. Until then this file is the plan of record and the
> build session must read *this* file, not `todo.md`.

---
| | |
|---|---|
| **App** | `core` — Module 0 foundation. Entity files sit **FLAT at the package root** (backend rule 9); `urls.py` stays a **flat file**; templates are **flat** at `templates/core/<entity>/` (template rule 4). |
| **New files** | 1 model file · 1 form file · 1 view file · 16 templates |
| **Shared files touched** | `models/__init__.py`, `forms/__init__.py`, `views/__init__.py`, `urls.py`, `admin.py`, `navigation.py`, `seed_core.py`, `temp/audit_integrity.py`, one new migration |
| **Migration** | `core.0015_*` (core is at `0014_dataarchive_darch_tenant_at_idx_and_more.py`) — **agree before generating (L43)** |
| **Test subslug** | `monitoring` → `test_monitoring_{models,forms,views,security}.py`, fixtures prefixed `mon_*` |
| **DB writer** | Single main session only: migrations, seeder, `navigation.py`, `urls.py`, the three `__init__.py` re-export blocks, `conftest.py`. Never delegated. |
| **The posture in one line** | **Four registers of things that did not happen automatically.** Nothing here probes, evaluates, notifies, ships a log, or publishes a status page. |

---

## 0. The ownership call (L36) — what 0.17 deliberately does NOT build

The most important section. Every "do not build" row is **carried forward from the Phase-1 research** and
written here as an explicit instruction, so a later session cannot quietly reinvent it.

| Deferred | Why (research §3 / §4) | Who owns it instead |
|---|---|---|
| **A centralized log store** — `LogEntry`, `ErrorLog`, `AccessLog`, `SystemLog`, log shipping, log-level thresholds, scrubbing | `settings.LOGGING` writes to console handlers; there is **no collector, shipper or index**. A log table would be a second log store *and* an empty one — both the `AuditLog` L36 violation and the 0.16 "reports success while nothing happened" lie. | Nothing. Bullet 2 is **partial by design** and the pages say so. |
| **A second metric / time-series table** — `MetricSample`, `TimeSeries`, `HealthReading` | `tenants.HealthMetric` **owns readings** (0.1). A second sample table is the parallel-schema bug (L36 / SCM L37 posture). | `tenants.HealthMetric` — the health board **reads** it. |
| **A second usage/quota table** — allowance, overage, fair-use | `tenants.UsageRecord.included_allowance` stores consumption; 0.19 bullet 3 owns the **commercial limit**. NavERP.md genuinely overlaps. | `tenants.UsageRecord` + **0.19**. 0.17 keeps the **scaling trigger** (`AlertRule.category="capacity"`). |
| **Distributed tracing** — `Trace`, `Span`, `trace_id`/`span_id`/parent | No OpenTelemetry SDK, no collector, no instrumentation anywhere in the repo. `Span` rows with no spans are fiction. | **Deferred until an OTel pipeline is actually deployed.** |
| **APM span store, continuous profiler, session replay, flame graphs** | Same; and readings already live in 0.1. | `tenants.HealthMetric` |
| **Notification channels, routing tree, receivers, contact points, on-call schedules, escalation policies** | 0.12 `Notification.py` owns delivery; 0.11 `SlaRule`/`ApprovalLimit` owns escalation. | 0.12 / 0.11. `AlertRule.notification_rule` is the **single seam**. |
| **A mute DSL, matcher expressions, inhibition rules** (Alertmanager) | A feature nothing enforces; a matcher DSL would be a 5th model. | The scalar `AlertEvent.muted_until` is the honest minimum. |
| **Synthetic probe execution + a heartbeat table** (Uptime Kuma, PRTG) | There is no prober process. `ServiceComponent.current_status` is **hand-set** and the page must label it a claim. | Nothing. **No auto-set `last_checked_at`** — a field claiming a check nothing performs is fiction (L52). |
| **Error grouping by fingerprint as a stored issue** (Sentry) | Would be a 5th model. | A board filter over `AlertEvent` (metric + time window). |
| **An SLO / error-budget table** (Datadog) | Would duplicate 0.11's SLA vocabulary. | A computed page over `AlertEvent` + `ServiceComponent`. |
| **The incident update timeline** (`incident_updates`) | Deferred to stay at 4 models. **Trigger to add it:** when an incident needs more than `public_note` + `updated_at` to be defensible, add `IncidentUpdate` as a 5th model *then*. | — |
| **Postmortems** | → **0.21** (and 0.18 for security incidents). | 0.21. `Incident.incident_type="postmortem"` is **reserved and unused** — the value exists, the model does not. |
| **Status-page public rendering, subscriber lists, uptime-% history** | 0.12 delivery + `tenants.HealthMetric.uptime_pct`. | 0.12 / 0.1 |
| **A scheduler, job/queue registry, release or change record** | 0.20 owns them. **This is why `AlertRule.frequency` is a recorded intention whose `help_text` says nothing runs it** — the `SlaRule` / `SyncSchedule` / `BackupJob.frequency` precedent, all three of which already say this in their own docstrings. | 0.20 |
| **A maintenance/change record** | `Incident(scheduled_maintenance)` is the **outward-facing notice**; 0.20's window/release model is **the change itself** (what ships, when, phased rollout). | 0.20 — it should FK `Incident` to announce a window, not copy it. |
| **A connector-health model** | 0.13's `core:integration_board` already answers "are the connectors well?". | 0.13 |

---

### 0.1 The L36 rulings that are easy to get wrong

- **`AlertRule` does not FK `AuditLog`, `BusinessRule`, `BusinessRuleLog`, `RateLimitPolicy` or
  `UsageRecord`.** `AuditLog` answers *"who changed which row"*; an `AlertEvent` answers *"a threshold was
  crossed"* — different subject, different evidence. `BusinessRule` evaluates a **condition over a record**;
  an `AlertRule` bounds a **measured value**. Different question. (L36, research §4.1)
- **The two constant REUSEs are reuse-by-REFERENCE, not copies** — restated at each site and asserted in
  the verify list (§10).

### 0.2 The 0.18 / 0.19 / 0.20 / 0.21 seams — encode all four in the ERD in the same pass (L36)

- **0.18** watches *threats*, not availability. The seam is **one enum value**: `AlertRule.category`
  includes `security`, so 0.18's rules land in the same rule table and the same board. **0.18 must NOT add
  category-scoped columns to `AlertRule`** (`threat_level`, `ip_address`, `cvss_score`) — those are 0.18
  fields on 0.18 models that FK `AlertRule`/`ServiceComponent` if they want correlation. Every *other* 0.17
  model treats a security rule as ordinary.
- **0.19** owns the **quota**; 0.17 owns the **scaling trigger**. Rewrite **both** modules' ERD rows in one
  change — do not merely note the conflict.
- **0.20** aggregates 0.17's health board; it must **link to** it, not re-declare health.
- **0.21** owns postmortems; 0.11 owns escalation and the `SlaRule` vocabulary (computed, not stored).

---

## 1. Models — 4 in ONE file, `apps/core/models/Monitoring.py`

**All four inherit `TenantConsistentMixin`** — `from apps.core.models.Backup import TenantConsistentMixin`
(exactly as `LegalHold.py` does; the import is one-way and cycle-free because `Backup.py` does not import
`Monitoring.py`). That mixin walks every `ForeignKey` and refuses one pointing into another workspace, and
it is what makes "the seeder *and the admin* get it too" true — the Django admin uses a plain
`ModelForm` with no queryset narrowing at all.

Header of the file: `from apps.core.models._base import *  # noqa: F401,F403` (the verbatim house import
block), plus `from django.core.exceptions import ValidationError`,
`from django.core.validators import MaxValueValidator, MinValueValidator` and
`from django.utils import timezone` where used.

**⚠️ Known, documented limitation — do NOT try to close it here.** `TenantConsistentMixin` walks
`ForeignKey`/`OneToOneField` only. `Incident.affected_services` is an **M2M**, so the mixin does not
tenant-check it. `TenantModelForm` *does* narrow M2M querysets (`ModelMultipleChoiceField` subclasses
`ModelChoiceField`), so the form path is covered **when `tenant is not None`**; the admin path is not. This
is the same posture 0.16 recorded for **C7 (escalated, not fixed)** — record it in `SKILL.md` at close-out.
Do **not** change `TenantModelForm`; it would break committed tests across three other apps.

### 1.1 `ServiceComponent` — *the thing that can go down*

Serves bullet 1 (service-status monitoring) and bullet 5 (the status-page component). Every researched
product separates the *monitored entity* from the *measurement*; NavERP has the measurement half
(`tenants.HealthMetric`) and **no entity half** — nothing in the repo can say "the payments API is
degraded".

| field | type | null / default | why |
|---|---|---|---|
| `tenant` | `ForeignKey("core.Tenant", on_delete=CASCADE, related_name="service_components", db_index=True)` | no | house spine |
| `name` | `CharField(max_length=150)` | no | the label on the board and the status page |
| `code` | `CharField(max_length=40, blank=True)` | blank | short slug for URLs/tickets. **Free text, not a `SlugField`** — it is a claim somebody types, not a generated identifier. |
| `kind` | `CharField(max_length=20, choices=KIND_CHOICES, default="web_service")` | no | Statuspage component groups / Dynatrace entities |
| `description` | `TextField(blank=True)` | blank | what this is |
| `owner_role` | `ForeignKey("accounts.Role", on_delete=SET_NULL, null=True, blank=True, related_name="owned_service_components")` | null | who is paged. Same shape as `NotificationRule.audience_role`. `related_name` is **not** `"+"` — the role's page links back to what it owns. |
| `is_public` | `BooleanField(default=False)` | | Statuspage's public/private page split |
| `is_critical` | `BooleanField(default=False)` | | a failure here tints the whole board |
| `display_order` | `PositiveIntegerField(default=0)` | | Statuspage `position` |
| `current_status` | `CharField(max_length=20, choices=STATUS_CHOICES, default="unknown", help_text="A hand-set claim. Nothing in NavERP probes this component.")` | | **a claim, never a reading** |
| `last_status_at` | `DateTimeField(null=True, blank=True)` | **null** | `NULL` = "not reported" ≠ epoch, and never coerced to 0. **System-set — out of the form (L22).** |
| `notes` | `TextField(blank=True)` | blank | |
| `is_active` | `BooleanField(default=True)` | | retired components stop counting toward the roll-up |
| `created_at` | `DateTimeField(auto_now_add=True)` | | |
| `updated_at` | `DateTimeField(auto_now=True)` | | |

```python
KIND_CHOICES = [
    ("web_service", "Web service"),
    ("api", "API"),
    ("database", "Database"),
    ("background_job", "Background job"),
    ("queue", "Queue"),
    ("integration", "Integration"),
    ("storage", "Storage"),
    ("external_dependency", "External dependency"),
    ("infrastructure", "Infrastructure"),
    ("other", "Other"),
]
STATUS_CHOICES = [
    ("operational", "Operational"),
    ("degraded", "Degraded"),
    ("partial_outage", "Partial outage"),
    ("major_outage", "Major outage"),
    ("maintenance", "Maintenance"),
    ("unknown", "Unknown"),
]
```

`Meta`:
- `ordering = ["display_order", "name"]`
- `indexes = [models.Index(fields=["tenant", "current_status"], name="svccomp_tenant_status_idx"), models.Index(fields=["tenant", "is_public"], name="svccomp_tenant_public_idx")]`
  — both ≤ 30 chars, both serve a real list filter. **Deliberately no index on the ordering columns:**
  this is a per-tenant *catalogue* of tens of rows, not a 5,000-row register, so the I5 finding that forced
  `-archived_at` / `-performed_at` indexes in 0.16 does not apply. Say so in a comment so a reviewer does
  not read the omission as an oversight.

`__str__` → `f"{self.name} ({self.get_current_status_display()})"`
Properties: `last_status_display` (`"—"` when `None`), `status_age_days` (`None` when never reported).
**No `save()` override on this model** — `last_status_at` is stamped by the edit view (§3.1), which is
where the knowledge that "a person just changed the status" lives.

**No `verbose_name` on any field.** A `verbose_name` is cosmetic and forces a migration for it — use form
`Meta.labels` instead (I11, and the `EnvironmentInstanceForm` precedent in `forms/Backup.py`).

---

### 1.2 `AlertRule` — *the threshold, recorded*

Serves bullets 1, 2, 3 and 4 simultaneously: a capacity ceiling, a latency p95, an error-rate burn and an
uptime floor are the same row with a different `metric_key`. NavERP has threshold-shaped *process* rules
(`SlaRule`, `BusinessRule`) and *quota* rules (`RateLimitPolicy`, `UsageRecord.included_allowance`) but
**no metric-threshold rule** — nothing can say "raise an alert if p95 latency exceeds 800 ms for 5 minutes".

| field | type | null / default | why |
|---|---|---|---|
| `tenant` | `ForeignKey("core.Tenant", CASCADE, related_name="alert_rules", db_index=True)` | no | |
| `service` | `ForeignKey("core.ServiceComponent", CASCADE, related_name="alert_rules")` | no | **CASCADE is right** — a threshold on a component that no longer exists is meaningless. Contrast `AlertEvent.rule`, which is `SET_NULL`. |
| `name` | `CharField(max_length=150)` | no | |
| `module_slug` | `CharField(max_length=40, blank=True)` | blank | the NavERP module it guards; the `BusinessRule.module_slug` precedent |
| `metric_key` | `CharField(max_length=24, choices=METRIC_CHOICES, default="uptime_pct")` | no | the measured quantity — see the overlap warning below |
| `comparator` | `CharField(max_length=10, choices=COMPARATOR_CHOICES, default="gte")` | no | see **REUSE RULING 1** |
| `warning_threshold` | `DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)` | **null** | two tiers (PRTG warning/downtime, Dynatrace). `NULL` = "this tier is unset", **never `0`**. |
| `critical_threshold` | `DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)` | **null** | same |
| `must_persist_seconds` | `PositiveIntegerField(default=0)` | | Grafana's *duration* — the "how long before it counts" that stops flap. `0` is truthful here (no persistence window), which is why this one is **not** nullable. |
| `frequency` | `CharField(max_length=10, choices=FREQUENCY_CHOICES, default="manual", help_text="A recorded intention. Nothing in NavERP runs it.")` | no | see **REUSE RULING 2** |
| `severity` | `CharField(max_length=10, choices=SEVERITY_CHOICES, default="warning")` | no | `info`/`warning`/`critical` **deliberately overlap `tenants.HealthMetric.STATUS_CHOICES`' `warning`/`critical` strings** so the boards cross-reference cleanly |
| `category` | `CharField(max_length=16, choices=CATEGORY_CHOICES, default="availability")` | no | the taxonomy that keeps 0.18 out — `security` is the whole seam |
| `no_data_action` | `CharField(max_length=12, choices=NO_DATA_CHOICES, default="ignore")` | no | Grafana's *error and no-data handling*, folded in as a choice rather than a table. Makes the NULL-is-not-0 discipline **structural**: a metric that stopped reporting is a distinct state from "fine". |
| `notification_rule` | `ForeignKey("core.NotificationRule", SET_NULL, null=True, blank=True, related_name="+")` | null | **the single seam to 0.12.** `related_name="+"` — nothing lists rules by notification rule. |
| `is_active` | `BooleanField(default=True)` | | |
| `notes` | `TextField(blank=True)` | blank | |
| `created_at` / `updated_at` | `DateTimeField(auto_now_add=True)` / `DateTimeField(auto_now=True)` | | |

```python
SEVERITY_CHOICES = [("info", "Info"), ("warning", "Warning"), ("critical", "Critical")]
CATEGORY_CHOICES = [
    ("availability", "Availability"), ("error", "Error"), ("performance", "Performance"),
    ("capacity", "Capacity"), ("security", "Security"),
]
NO_DATA_CHOICES = [
    ("fire", "Fire on no data"), ("ignore", "Ignore no data"), ("ok", "Treat no data as OK"),
]
METRIC_CHOICES = [
    ("uptime_pct", "Uptime %"),
    ("storage_mb", "Storage (MB)"),
    ("latency_p95_ms", "Latency p95 (ms)"),
    ("throughput_rps", "Throughput (requests/sec)"),
    ("error_rate_pct", "Error rate %"),
    ("slow_query_ms", "Slow query (ms)"),
    ("cpu_pct", "CPU utilisation %"),
    ("memory_pct", "Memory utilisation %"),
    ("disk_usage_pct", "Disk usage %"),
    ("db_connection_pct", "DB connection pool %"),
    ("queue_depth", "Queue depth (items)"),
    ("job_failures", "Job failures (count)"),
]
```

**⚠️ The `metric_key` overlap — the file docstring MUST say this or the next agent will "fix" it (L52).**
`uptime_pct` and `storage_mb` appear in **both** `tenants.HealthMetric.METRIC_CHOICES` and this list, and
they **mean different things**: there a reading is *tenant consumption*; here it is a *platform bound*.
0.17's vocabulary is a **strict superset** — the other ten keys are **threshold vocabulary only and have no
stored reading anywhere in the repo**. That is correct: a threshold is not a reading.

#### 🔁 REUSE RULING 1 — `COMPARATORS` IS `BusinessRule.OPERATORS`, by reference

```python
from apps.core.models.BusinessRule import BusinessRule

#: Reuse-by-REFERENCE, not a copy: the same public constant, the same operator vocabulary. A pasted
#: second list is the parallel-schema bug (L36), and it would drift the first time 0.11 adds an operator.
COMPARATORS = BusinessRule.OPERATORS        # identity holds: AlertRule.COMPARATORS is BusinessRule.OPERATORS
#: `BusinessRule.OPERATORS` is a flat tuple of strings, not (value, label) pairs, so the CHOICES are
#: DERIVED from it at import time. Derived, never hand-written — that is what keeps the two in step.
COMPARATOR_CHOICES = tuple((op, op.replace("_", " ").title()) for op in COMPARATORS)
```

`BusinessRule.OPERATORS` is `("eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains", "is_set",
"is_empty")` → the derived labels are `Eq, Ne, Gt, Gte, Lt, Lte, In, Not In, Contains, Is Set, Is Empty`.
**Do not hand-write that tuple.** If someone edits `COMPARATOR_CHOICES` directly the reuse is broken —
assert it at runtime in the verify list.

#### 🔁 REUSE RULING 2 — `FREQUENCY_CHOICES` IS `SyncSchedule.FREQUENCY_CHOICES`, by reference

```python
from apps.core.models.Integration import SyncSchedule

#: Reuse-by-REFERENCE. 0.13 owns the schedule vocabulary. 0.16 copied it into a private
#: `_SCHEDULE_FREQUENCY_CHOICES` (`models/Backup.py:45`) which is a second copy that can drift — do NOT
#: repeat that here. Assign the object; never mutate it, never rebuild the list.
FREQUENCY_CHOICES = SyncSchedule.FREQUENCY_CHOICES   # manual / hourly / daily / weekly
```

Both rulings get a one-line comment naming what is reused and why, in the house voice of
`Backup.py:42-44`. Both are asserted at runtime in §10.

`Meta`:
- `ordering = ["name"]`
- `unique_together = ("tenant", "name")` → **this requires a `clean_name` guard on the form** (§2.2).
- `indexes = [("tenant", "category") → "alertrule_tenant_cat_idx", ("tenant", "severity") → "alertrule_tenant_sev_idx", ("tenant", "name") → "alertrule_tenant_name_idx"]`
  — the third exists for the `ORDER BY name`; the I5 lesson applied up front rather than after review.

`clean()` — the 0.16 `RecoveryDrill` shape (`if self.outcome != "not_run" and self.performed_at is None`),
so it is enforced in `_post_clean` and therefore by the seeder **and** the admin too:

```python
def clean(self):
    super().clean()
    if self.is_active and self.warning_threshold is None and self.critical_threshold is None:
        raise ValidationError(
            {"warning_threshold": "An active rule with no bound can never fire. Set a warning or a "
                                  "critical threshold, or mark the rule inactive."})
```

`__str__` → `f"{self.name} ({self.get_metric_display()} {self.get_comparator_display()})"`
Properties: `is_bounded` (either threshold set), `threshold_display` (both tiers, `"—"` for `None`),
`tier_count` (1 or 2 — a one-tier rule is normal; two tiers is the richer one).

---

### 1.3 `AlertEvent` — *one firing, as evidence*

The read side of every alert. This is the **hand-written-evidence posture** of `DisposalRecord` /
`RestoreRecord` / `BackupJob` applied to alerting: nothing in NavERP evaluates a threshold (no scheduler),
so each row is *a report that a threshold was crossed*.

| field | type | null / default | why |
|---|---|---|---|
| `tenant` | `ForeignKey("core.Tenant", CASCADE, related_name="alert_events", db_index=True)` | no | |
| `rule` | `ForeignKey("core.AlertRule", SET_NULL, null=True, blank=True, related_name="events")` | null | **SET_NULL, copying `BusinessRuleLog.rule`'s exact reasoning** (`BusinessRule.py:77-78`): the event is the evidence a rule fired and must survive the rule being retired. |
| `service` | `ForeignKey("core.ServiceComponent", SET_NULL, null=True, blank=True, related_name="alert_events")` | null | same reason, plus the snapshot below |
| `service_label` | `CharField(max_length=150, blank=True)` | blank | **denormalised snapshot**, written by the form's `save()` from the chosen service, so the row still reads after the component is deleted. **Not a form field.** |
| `state` | `CharField(max_length=12, choices=STATE_CHOICES, default="firing")` | no | **written only by the three POST-only actions.** Not a form field. |
| `severity_at_fire` | `CharField(max_length=10, choices=SEVERITY_CHOICES, default="warning")` | no | **a snapshot, not a join** — the rule's severity may be edited later and the historical record must not move. Form field (a person records the severity they saw). |
| `observed_value` | `DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)` | **null** | the reading that crossed. `NULL` = **not measured**, rendered `"—"` — never `0`. |
| `threshold_at_fire` | `DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)` | **null** | the bound that was crossed, as it stood. `NULL` = not recorded. |
| `message` | `CharField(max_length=255)` | no | a firing with no message is unreadable |
| `detail` | `TextField(blank=True)` | blank | |
| `occurrence_count` | `PositiveIntegerField(default=1)` | | Sentry's *count*. **Not a form field** — NavERP cannot count recurrences it did not observe, so only the `recur` action increments it. |
| `first_seen_at` | `DateTimeField(null=True, blank=True)` | null | written by the create view as `fired_at` when blank |
| `last_seen_at` | `DateTimeField(null=True, blank=True)` | null | written by the `recur` action |
| `fired_at` | `DateTimeField(default=timezone.now)` | no | the reported moment of the crossing. **System-set, `default=now`, out of the form (L22).** |
| `acknowledged_at` | `DateTimeField(null=True, blank=True)` | null | written by the `acknowledge` action |
| `acknowledged_by` | `ForeignKey(AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` | null | actor, set from `request.user`. **Never a form field** — otherwise a user can attribute an acknowledgement to somebody else, and attribution is the act an audit exists for. |
| `resolved_at` | `DateTimeField(null=True, blank=True)` | null | written by the `resolve` action |
| `resolved_by` | `ForeignKey(AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name="+")` | null | as `acknowledged_by` |
| `resolution_note` | `CharField(max_length=255, blank=True)` | blank | written by the `resolve` action from `request.POST` |
| `muted_until` | `DateTimeField(null=True, blank=True)` | null | Alertmanager *silence* / Datadog *downtime*, as a **recorded** mute — **nothing enforces it** |
| `evidence` | `CharField(max_length=255, blank=True)` | blank | **the same field shape** as `BackupJob.evidence` / `DisposalRecord.evidence` — the ticket/runbook ref that makes the claim defensible. Form field. |
| `created_at` | `DateTimeField(auto_now_add=True)` | | |

```python
STATE_CHOICES = [
    ("firing", "Firing"),
    ("acknowledged", "Acknowledged"),
    ("resolved", "Resolved"),
    ("expired", "Expired"),
    ("no_data", "No data"),
]
```

**`muted_until` IS a form field, and that is deliberate — do not "fix" it.** L22 targets *system-set*
timestamps. `muted_until` is a **forward-declared boundary a human types**, exactly like
`BackupJob.retain_until`, which **is** in 0.16's form. The three stamps L22 actually names here
(`fired_at`, `acknowledged_at`, `resolved_at`) are all written by system/actions and are all out. The list
and detail label it *"a recorded mute. Nothing in NavERP silences an alert."*

**Explicitly absent — do not add them (L52: a permanently-empty field is a lie by omission):** stack
trace, log line, request/response body, raw payload, trace id. NavERP does not collect them.

`Meta`:
- `ordering = ["-fired_at", "-id"]`
- `indexes = [("tenant", "-fired_at") → "alertevent_tenant_fired_idx", ("tenant", "state") → "alertevent_tenant_state_idx", ("tenant", "service", "-fired_at") → "alertevent_tenant_svc_idx"]`
  — all ≤ 30 chars; the third serves both the `?service=` filter and the per-service board roll-up.

**⚠️ C5 note that must appear as a comment.** `fired_at` is `default=timezone.now` and therefore **never
NULL** — so `ORDER BY -fired_at` cannot hit the MariaDB "NULLs sort LAST under DESC" trap that sank
`BackupJob` (see the C5 finding in `views/Backup.py`). **If anyone ever makes `fired_at` nullable, this
index and this ordering must be revisited together.** This is L52 rule 2: prefer an invariant a grep can
confirm.

`__str__` → `f"{self.rule or 'ad-hoc alert'} · {self.get_state_display()}"`
Properties: `observed_value_display` / `threshold_at_fire_display` (`"—"` when `None`);
`is_open` (`state in {"firing", "acknowledged"}`); `is_muted` (`muted_until` in the future);
`age_days`.

---

### 1.4 `Incident` — *the comms artifact*

Every status-page product's core is *component* + *incident*, and an incident has a **different lifecycle
and a different audience** from an alert. NavERP has neither.

| field | type | null / default | why |
|---|---|---|---|
| `tenant` | `ForeignKey("core.Tenant", CASCADE, related_name="incidents", db_index=True)` | no | |
| `service` | `ForeignKey("core.ServiceComponent", SET_NULL, null=True, blank=True, related_name="primary_incidents")` | null | the component this notice is about. SET_NULL — a notice outlives the catalogue entry. **`related_name` must differ from the M2M's.** |
| `affected_services` | `ManyToManyField("core.ServiceComponent", blank=True, related_name="affected_incidents")` | blank | a **real M2M** — the auto-generated through table is not a hand-declared model, so this does not break the 4-model cap |
| `primary_alert` | `ForeignKey("core.AlertEvent", SET_NULL, null=True, blank=True, related_name="+")` | null | lets a firing *become* a comms incident without a second store, and gives the status page a "why" link |
| `title` | `CharField(max_length=200)` | no | |
| `incident_type` | `CharField(max_length=24, choices=INCIDENT_TYPE_CHOICES, default="incident")` | no | Statuspage's own variant set. **`postmortem` is RESERVED and unused** — the value exists, the postmortem model does not (→ 0.21). |
| `status` | `CharField(max_length=16, choices=STATUS_CHOICES, default="investigating")` | no | a **union** enum, because one list renders both an incident and a scheduled maintenance |
| `impact` | `CharField(max_length=12, choices=IMPACT_CHOICES, default="minor")` | no | Statuspage's; the field that drives `ServiceComponent.current_status` in the **roll-up (derived, never stored — SCM L37 posture)** |
| `public_note` | `TextField(blank=True)` | blank | the public status-page text |
| `internal_note` | `TextField(blank=True)` | blank | internal-only text. **Never rendered on a public page** — 0.17 has no public page at all. |
| `progress_pct` | `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])` | **null** | `NULL` = **not tracked**, rendered "not tracked", never `0%` |
| `started_at` | `DateTimeField(null=True, blank=True)` | null | form field (a human reports when it started) |
| `resolved_at` | `DateTimeField(null=True, blank=True)` | null | **model-stamped, out of the form (L22)** — see `save()` below |
| `scheduled_for` | `DateTimeField(null=True, blank=True)` | null | maintenance notice window start. **This is the NOTICE, not the change** (0.20 owns the change). |
| `scheduled_until` | `DateTimeField(null=True, blank=True)` | null | window end |
| `notified_at` | `DateTimeField(null=True, blank=True)` | null | **system-set, out of the form (L22)** — written only by the `notify` action |
| `is_active` | `BooleanField(default=True)` | | |
| `notes` | `TextField(blank=True)` | blank | |
| `created_at` / `updated_at` | `DateTimeField(auto_now_add=True)` / `DateTimeField(auto_now=True)` | | |

```python
INCIDENT_TYPE_CHOICES = [
    ("incident", "Incident"),
    ("scheduled_maintenance", "Scheduled maintenance"),
    ("postmortem", "Postmortem (reserved — 0.21)"),
]
STATUS_CHOICES = [
    ("scheduled", "Scheduled"),
    ("investigating", "Investigating"),
    ("identified", "Identified"),
    ("in_progress", "In progress"),
    ("monitoring", "Monitoring"),
    ("verifying", "Verifying"),
    ("resolved", "Resolved"),
    ("completed", "Completed"),
]
IMPACT_CHOICES = [
    ("none", "No impact"),
    ("minor", "Minor"),
    ("major", "Major"),
    ("critical", "Critical"),
]
```


`Meta`:
- `ordering = ["-created_at", "-id"]` — **deliberately NOT `-started_at`.** `created_at` is `auto_now_add`
  and therefore never `NULL`, so this dodges the C5 MariaDB NULL-sort trap outright, and insertion order
  is what "newest notice" means for a register. Note the reason in a comment.
- `indexes = [("tenant", "-created_at") → "incident_tenant_created_idx", ("tenant", "status") → "incident_tenant_status_idx", ("tenant", "impact") → "incident_tenant_impact_idx"]`
  — all ≤ 30 chars; the first is the ordering index, the other two serve real list filters.

`clean()`:
```python
def clean(self):
    super().clean()
    if self.scheduled_for and self.scheduled_until and self.scheduled_until < self.scheduled_for:
        raise ValidationError({"scheduled_until": "The maintenance window cannot end before it starts."})
    if self.incident_type == "scheduled_maintenance" and not self.scheduled_for:
        raise ValidationError({"scheduled_for": "A maintenance notice must say when the window opens. "
                                                 "This is the notice, not the change record (0.20 owns that)."})
```

`save()` — **one override, one rule, reachable from the form AND the admin AND the seeder:**
```python
def save(self, *args, **kwargs):
    # `resolved_at` is system-set (L22) and nothing performs the resolution, so it is DERIVED from the
    # recorded status rather than typed. One-way: moving back to an in-progress status does not erase
    # the fact that this incident was once resolved.
    if self.status in {"resolved", "completed"} and self.resolved_at is None:
        self.resolved_at = timezone.now()
    super().save(*args, **kwargs)
```

`__str__` → `f"{self.title} · {self.get_status_display()}"`
Properties: `progress_display` (`"not tracked"` when `None`), `is_open`, `is_scheduled`, `window_valid`.

**No FK to `core.SlaRule`** (process escalation, 0.11) and **none to `EnvironmentInstance`** (0.16) — a
maintenance notice is a *communication about a window somebody else owns*.

### 1.5 Model-file close-out checks (grep these; do not eyeball them)

- [ ] `grep -c "TenantConsistentMixin, models.Model" apps/core/models/Monitoring.py` → **4**
- [ ] `grep -c "ManyToManyField" apps/core/models/Monitoring.py` → **1**, in `Incident`
- [ ] `grep -n 'ForeignKey("tenants\.\|ForeignKey("core.AuditLog"\|ForeignKey("core.BusinessRule\|ForeignKey("core.RateLimitPolicy' apps/core/models/Monitoring.py` → **no matches**
- [ ] `AlertRule.COMPARATORS is BusinessRule.OPERATORS` and `AlertRule.FREQUENCY_CHOICES is SyncSchedule.FREQUENCY_CHOICES` — assert at runtime, do not verify by reading
- [ ] Every index `name=` is **≤ 30 characters** (Django's limit; `svccomp_tenant_status_idx` is 24, the longest here)
- [ ] `grep -n "verbose_name" apps/core/models/Monitoring.py` → **no matches** (cosmetic; use form `Meta.labels` — I11)
- [ ] After the migration is generated, `makemigrations core --check --dry-run` → "No changes detected"

---

## 2. Forms — 4 in `apps/core/forms/Monitoring.py`

All four subclass `TenantModelForm` (from `apps.core.forms._common` via `import *`), exactly as
`forms/Backup.py` does. All are **`Meta`-only** apart from two deliberate exceptions called out below —
`ModelForm._post_clean` already calls `instance.full_clean()`, so every `clean()` in §1 is enforced on
every form, the seeder **and** the admin. One rule, one place.

**Zero editable `DateTimeField`s on these forms, with exactly one named exception** (L22, mirroring
`tenants.HealthMetric.recorded_at`). The exception is `AlertEventForm.muted_until`, argued at §1.3.

### 2.1 `ServiceComponentForm`

```python
class ServiceComponentForm(TenantModelForm):
    class Meta:
        model = ServiceComponent
        fields = ["name", "code", "kind", "description", "owner_role", "is_public", "is_critical",
                  "display_order", "current_status", "notes", "is_active"]
        labels = {"owner_role": "Owning role",
                  "current_status": "Current status (hand-set — nothing probes this)"}
```
- **Excluded:** `tenant` (never a form field), `last_status_at` (**system-set, L22**), `created_at`,
  `updated_at` (auto columns).
- `current_status` **is** editable — it is the claim. The *label* is what makes it honest, and the detail
  page repeats it.

### 2.2 `AlertRuleForm` — the one form that needs a `clean_*`

```python
class AlertRuleForm(TenantModelForm):
    class Meta:
        model = AlertRule
        fields = ["name", "service", "module_slug", "metric_key", "comparator", "warning_threshold",
                  "critical_threshold", "must_persist_seconds", "frequency", "severity", "category",
                  "no_data_action", "notification_rule", "is_active", "notes"]
        labels = {"must_persist_seconds": "Must persist (seconds)",
                  "no_data_action": "When there is no data",
                  "notification_rule": "Notify via (0.12 rule)"}

    def clean_name(self):
        # `(tenant, name)` is `unique_together`, but `tenant` is not a `Meta.fields` member, so Django
        # DROPS the whole tuple from validation (`Model._get_unique_checks()` discards a
        # `unique_together` containing an excluded field) and a duplicate name reaches the DB as an
        # `IntegrityError` 500 on both create and edit. Enforce it here, scoped to this tenant — the
        # same guard `StatutoryRuleForm.clean_name` already ships (`forms/Localization.py`).
        name = self.cleaned_data.get("name")
        if name and self.tenant is not None:
            qs = AlertRule.objects.filter(tenant=self.tenant, name=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "An alert rule with this name already exists in this workspace — edit the existing "
                    "one or choose a different name.")
        return name
```
- **Excluded:** `tenant`, `created_at`, `updated_at`. **No `DateTimeField` on this form at all.**


### 2.3 `AlertEventForm`

```python
class AlertEventForm(TenantModelForm):
    class Meta:
        model = AlertEvent
        fields = ["rule", "service", "severity_at_fire", "observed_value", "threshold_at_fire",
                  "message", "detail", "muted_until", "evidence"]
        labels = {"severity_at_fire": "Severity at fire (snapshot)",
                  "threshold_at_fire": "Threshold at fire"}

    def save(self, commit=True):
        # `service_label` is a DENORMALISED SNAPSHOT, not a form field: a person cannot type it, and it
        # must not be able to disagree with the service they picked. Written here so the row still
        # reads after the component is deleted.
        obj = super().save(commit=False)
        obj.service_label = obj.service.name if obj.service_id else ""
        if commit:
            obj.save()
            self.save_m2m()
        return obj
```
- **Excluded and why** (each exclusion is a rule, not an omission):
  `tenant` · `service_label` (snapshot, written above) · `state` (only the POST-only actions write it) ·
  `occurrence_count` (NavERP cannot count recurrences it did not observe — only `recur` increments it) ·
  `first_seen_at` / `last_seen_at` / `fired_at` (**L22 — system/action-set**) ·
  `acknowledged_at` / `acknowledged_by` / `resolved_at` / `resolved_by` / `resolution_note`
  (**L22 + actor fields are never editable — the actor is the request user**) · `created_at`.
- **The one `DateTimeField` that IS present is `muted_until`** — a forward-declared mute boundary, the
  0.16 `BackupJob.retain_until` precedent. If a reviewer flags it, the answer is in §1.3, not "remove it".

### 2.4 `IncidentForm`

```python
class IncidentForm(TenantModelForm):
    class Meta:
        model = Incident
        fields = ["title", "service", "affected_services", "primary_alert", "incident_type", "status",
                  "impact", "public_note", "internal_note", "progress_pct", "started_at",
                  "scheduled_for", "scheduled_until", "is_active", "notes"]
        labels = {"affected_services": "Also affecting",
                  "primary_alert": "Originating alert",
                  "progress_pct": "Progress (%)",
                  "public_note": "Public note (what a status page would show)",
                  "internal_note": "Internal note (never public)"}
```
- **Excluded and why:** `tenant` · `resolved_at` (**model-stamped in `save()` — L22**) ·
  `notified_at` (**written only by the POST-only `notify` action — L22**) · `created_at` · `updated_at`.
- `affected_services` is the M2M; `crud_create` calls `form.save_m2m()` and `crud_edit` calls
  `form.save()`, so the through table is written on both paths with no extra code.
- `started_at` / `scheduled_for` / `scheduled_until` **are** editable. They are not system-set — they
  are the *schedule a person is declaring*, and the alternative (a form that cannot say when a maintenance
  window opens) makes `scheduled_maintenance` unusable. The anti-L22 argument that applies to
  `fired_at`/`acknowledged_at` — "a date-only widget truncates the time component" — is already solved for
  every `DateTimeField` in this repo: `TenantModelForm.__init__` installs a `datetime-local` widget with
  matching `input_formats` (`["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]`). Rely on that
  base class; do not re-declare a widget.

### 2.5 Form close-out checks

- [ ] `grep -c "class .*TenantModelForm" apps/core/forms/Monitoring.py` → **4**
- [ ] `grep -n "tenant" apps/core/forms/Monitoring.py` → appears only in `clean_name` and the docstrings, never inside a `fields` list
- [ ] `grep -n "DateTimeField\|DateTimeInput" apps/core/forms/Monitoring.py` → **no matches** (the base class supplies the widgets)
- [ ] `AlertRuleForm` has `clean_name`; `grep -c "def clean_" apps/core/forms/Monitoring.py` → **exactly 1**
- [ ] `IncidentForm` has **no** `save()` override (no snapshot to write) — confirm before adding one

---

## 3. Views — `apps/core/views/Monitoring.py`

**Shared preamble, mirroring `views/Backup.py`:**
- `from apps.core.views._common import *  # noqa: F401,F403` (this supplies `crud_list`, `crud_create`,
  `crud_detail`, `crud_edit`, `crud_delete`, `require_POST`, `User`, `redirect`, `render`,
  `get_object_or_404`, `messages`, `timezone`) — plus `from django.db.models import Count, Q` and
  `from django.urls import reverse`.
- Import models from `apps.core.models` and forms from `apps.core.forms` (absolute imports only,
  backend rule 4). Import `accounts.models.Role` **lazily inside the function that needs it** — 0.16's
  seeder does the same, because `core` is imported before `accounts` at startup.
- Every view is `@tenant_admin_required` (from `apps.core.decorators`, re-exported by `_common`) — 0.17 is
  platform administration, exactly as 0.13–0.16 are.

**A module-level `MONITORING_NOTES` constant** — the honest-limit lines the overview and all three boards
print verbatim, so a page and a board cannot disagree about what this application can and cannot do.
`Backup.py` has the same shape (`BACKUP_NOTES`):

```python
MONITORING_NOTES = [
    "This is a register of claims a person wrote, not a monitoring system. NavERP has no probe, no "
    "collector, no log pipeline and no scheduler — nothing here measures, evaluates, notifies or "
    "publishes anything.",
    "A component's status is hand-set. An alert event is a report that a threshold was crossed. Neither "
    "is a measurement NavERP took, and recording either does not make it true.",
    "Where a figure cannot be determined the boards say so and print —, never a 0: a zero that means "
    "'cannot tell' is the most dangerous number an operations board can show.",
]
```

### 3.1 `ServiceComponent` — 5 views, and one field stamped by the form

| view | decorator | helper |
|---|---|---|
| `service_component_list` | `@tenant_admin_required` | `crud_list` |
| `service_component_create` | `@tenant_admin_required` | `crud_create`, `success_url="core:service_component_list"` |
| `service_component_detail` | `@tenant_admin_required` | `crud_detail`, `select_related=("owner_role",)` |
| `service_component_edit` | `@tenant_admin_required` | `crud_edit` |
| `service_component_delete` | `@require_POST` **above** `@tenant_admin_required` | `crud_delete` — 405 on GET regardless of role (7.7) |

**`last_status_at` is stamped in the FORM, not the view**, so the admin gets it too:
```python
# in ServiceComponentForm
def save(self, commit=True):
    # `last_status_at` is system-set (L22). Nobody probes this component, so the honest reading of
    # "last status change" is "when a person last changed the status by hand" — which is exactly when
    # somebody edited this form. Needs `from django.utils import timezone` in the forms file.
    obj = super().save(commit=False)
    if obj.pk:
        before = ServiceComponent.objects.filter(pk=obj.pk).values_list("current_status", flat=True).first()
        if before != obj.current_status:
            obj.last_status_at = timezone.now()
    if commit:
        obj.save()
        self.save_m2m()
    return obj
```
This is **one extra query per edit POST** — not per list render. Do not hoist it anywhere else.


**`service_component_list` — the exact contract (L7/L8):**
```python
qs = ServiceComponent.objects.filter(tenant=request.tenant).select_related("owner_role")
crud_list(request, qs, "core/servicecomponent/list.html",
          search_fields=["name", "code", "description"],
          filters=[("kind", "kind", False), ("status", "current_status", False),
                   ("owner_role", "owner_role_id", True), ("public", "is_public", False)],
          extra_context={
              "kind_choices": ServiceComponent.KIND_CHOICES,
              "status_choices": ServiceComponent.STATUS_CHOICES,
              "owner_roles": Role.objects.filter(tenant=request.tenant).order_by("name"),
              "unreported_count": ServiceComponent.objects.filter(
                  tenant=request.tenant, last_status_at__isnull=True).count(),
              "notes": MONITORING_NOTES,
          })
```
> ⚠️ Pin exactly: `?q=`, `?kind=`, `?status=`, `?owner_role=`, `?public=`. The GET param for the status
> filter is **`status`** while the ORM lookup is `current_status`. `?public=` maps to the `is_public`
> boolean and `crud_list`'s string→bool map (`"True"`/`"False"`) handles it.
> `unreported_count` is a real, readable count (one nullable column) so `0` is legitimate here.
> **Do not add a `critical_count`** — it is derivable by the reader from the `is_critical` column and
> adds a query for nothing.

**`service_component_detail` extra_context (every key pinned, L8):**
`rule_count` (int) · `open_event_count` (int) · `incident_count` (int) · `notes`.
- `rule_count` = `AlertRule.objects.filter(tenant=…, service_id=pk).count()`
- `open_event_count` = `AlertEvent.objects.filter(tenant=…, service_id=pk, state__in=["firing", "acknowledged"]).count()`
- `incident_count` = `Incident.objects.filter(tenant=…, Q(service_id=pk) | Q(affected_services=pk)).distinct().count()`

### 3.2 `AlertRule` — 5 views

`alert_rule_{list,create,detail,edit,delete}`, the same decorator set (delete is `@require_POST` above the
role gate). `alert_rule_create` uses `success_url="core:alert_rule_list"`. `alert_rule_detail` uses
`select_related=("service", "notification_rule")`.

**`alert_rule_list` contract:**
```python
qs = AlertRule.objects.filter(tenant=request.tenant).select_related("service")
crud_list(request, qs, "core/alertrule/list.html",
          search_fields=["name", "module_slug", "metric_key", "notes"],
          filters=[("category", "category", False), ("severity", "severity", False),
                   ("metric", "metric_key", False), ("service", "service_id", True),
                   ("active", "is_active", False)],
          extra_context={
              "category_choices": AlertRule.CATEGORY_CHOICES,
              "severity_choices": AlertRule.SEVERITY_CHOICES,
              "metric_choices": AlertRule.METRIC_CHOICES,
              "no_data_choices": AlertRule.NO_DATA_CHOICES,
              "services": ServiceComponent.objects.filter(tenant=request.tenant).order_by("name"),
              "notes": MONITORING_NOTES,
          })
```
> Pin the GET params: `?category=`, `?severity=`, `?metric=`, `?service=` (int, L11-guarded by
> `crud_list`), `?active=`, `?q=`. `comparator_choices` is **not** passed because there is no comparator
> filter — do not add the key without also adding the dropdown.
> **No `unbounded_count` key.** The model's `clean()` refuses an active rule with no bound, so such a
> count is structurally always `0` — a tautological number that teaches the reader nothing (0.8's zero
> rule applied to a tautology).

**`alert_rule_detail` extra_context:** `event_count` (int) · `open_event_count` (int) ·
`latest_event` (`AlertEvent | None`) · `notes`. `latest_event` is
`AlertEvent.objects.filter(tenant=…, rule_id=pk).order_by("-fired_at").first()` — ordering by
`-fired_at`, which is never NULL in this model, so the C5 MariaDB NULL-sort trap cannot apply.


### 3.3 `AlertEvent` — 5 views + 3 POST-only actions

`alert_event_{list,create,detail,edit,delete}` plus `alertevent_acknowledge`, `alertevent_resolve`,
`alertevent_recur`. **All three actions are `@require_POST` ABOVE `@tenant_admin_required`** — a wrong
method is 405 regardless of role.

`alert_event_create` sets `first_seen_at` in the **form's** `save()` alongside the `service_label`
snapshot, so the admin gets it too:
```python
if obj.fired_at and not obj.first_seen_at:
    obj.first_seen_at = obj.fired_at
```

**The three action views — exact behaviour:**

| view | route suffix | guard (refuse, with a message + redirect) | writes | success message |
|---|---|---|---|---|
| `alertevent_acknowledge` | `<int:pk>/acknowledge/` | `state != "firing"` | `state="acknowledged"`, `acknowledged_at=now()`, `acknowledged_by=request.user` | "Acknowledged. This records that somebody looked at it — it does not silence the alert." |
| `alertevent_resolve` | `<int:pk>/resolve/` | `state in {"resolved", "expired"}`; `resolution_note` read from `request.POST`, truncated to 255 | `state="resolved"`, `resolved_at=now()`, `resolved_by=request.user`, `resolution_note` | "Resolution recorded. NavERP did not fix anything." |
| `alertevent_recur` | `<int:pk>/recur/` | `state in {"resolved", "expired"}` | `occurrence_count = F("occurrence_count") + 1`, `last_seen_at = now()` | "Recurrence recorded. Nothing is counting this automatically." |

Each writes `write_audit_log(request.user, obj, "update", changes={"verb": "<view_name>", …})` —
`AuditLog.action` is `varchar(10)`, so the verb stays short and the detail goes in `changes` (the
`views/Localization.py` pattern). **The guard is in the VIEW, not only a hidden button**, so the action
cannot be reached by a hand-made POST and the audit row is not written either — the `backup_job_verify`
rule.

**`alert_event_list` contract:**
```python
qs = AlertEvent.objects.filter(tenant=request.tenant).select_related("rule", "service")
crud_list(request, qs, "core/alertevent/list.html",
          search_fields=["message", "detail", "evidence", "service_label"],
          filters=[("state", "state", False), ("severity", "severity_at_fire", False),
                   ("rule", "rule_id", True), ("service", "service_id", True)],
          extra_context={
              "state_choices": AlertEvent.STATE_CHOICES,
              "severity_choices": AlertEvent.SEVERITY_CHOICES,
              "services": ServiceComponent.objects.filter(tenant=request.tenant).order_by("name"),
              "firing_count": AlertEvent.objects.filter(tenant=request.tenant, state="firing").count(),
              "unmeasured_count": AlertEvent.objects.filter(
                  tenant=request.tenant, observed_value__isnull=True).count(),
              "notes": MONITORING_NOTES,
          })
```
> Pin the GET params: `?state=`, `?severity=` (ORM lookup `severity_at_fire`), `?rule=` (int),
> `?service=` (int), `?q=`.
> `unmeasured_count` = firings where nobody wrote down what the reading was. **The single most useful
> number on this page** — the register's own honesty score — and a real count, so `0` is legitimate.

**`alert_event_detail` extra_context:** `incident_count` (int) · `related_incidents` (list) · `notes`.
`related_incidents` = `list(Incident.objects.filter(tenant=…, primary_alert_id=pk))`. **The three POST-only
action buttons live on this page**, each a `<form method="post">` with `{% csrf_token %}` and
`onsubmit="return confirm(...)"`, rendered only when the guard would allow it.

### 3.4 `Incident` — 5 views + 1 POST-only action

`incident_{list,create,detail,edit,delete}` plus `incident_notify` (`@require_POST` above the role gate).
`incident_notify` writes `notified_at = now()` and **refuses if `notified_at` is already set** ("this
notice was already recorded as published"). Message: "Publication recorded. NavERP published nothing — it
has no status page and sends nothing."

**`incident_list` contract:**
```python
qs = (Incident.objects.filter(tenant=request.tenant)
      .select_related("service", "primary_alert").prefetch_related("affected_services"))
crud_list(request, qs, "core/incident/list.html",
          search_fields=["title", "public_note", "internal_note"],
          filters=[("status", "status", False), ("impact", "impact", False),
                   ("type", "incident_type", False), ("service", "service_id", True),
                   ("active", "is_active", False)],
          extra_context={
              "status_choices": Incident.STATUS_CHOICES,
              "impact_choices": Incident.IMPACT_CHOICES,
              "type_choices": Incident.INCIDENT_TYPE_CHOICES,
              "services": ServiceComponent.objects.filter(tenant=request.tenant).order_by("name"),
              "active_count": Incident.objects.filter(tenant=request.tenant, is_active=True).count(),
              "notes": MONITORING_NOTES,
          })
```
> Pin the GET params: `?status=`, `?impact=`, `?type=` (ORM lookup `incident_type` — the GET param is
> **`type`**, not `incident_type`), `?service=` (int), `?active=`, `?q=`.

**`incident_detail` extra_context:** `affected` (list of `ServiceComponent`) · `alert_events` (list) ·
`notes`. `alert_events` = `list(AlertEvent.objects.filter(tenant=…, service__in=affected_ids)
.order_by("-fired_at")[:10])`.


### 3.5 `monitoring_overview` — the landing page (COMPUTED hub, stores nothing)

The `backup_overview` shape: redirect to `dashboard:home` when `request.tenant is None`, with
`messages.info(request, "Monitoring applies to a tenant workspace.")`.

**One query per model, then derive in Python** (the I3 lesson 0.16 recorded — a second `COUNT(*)` per
figure is what took that landing page from 11 queries to 20). Fetch once each, `.select_related()` their
FKs, and order every one of them **`-id`** (the C5 rule: never window over an `ORDER BY` on a nullable
column — MariaDB sorts NULLs LAST under `DESC`, which is what hid 0.16's queued backups):
`components` · `rules` · `events` · `incidents`, and
`metrics = list(HealthMetric.objects.filter(tenant=tenant).order_by("-id")[:20])`
(`HealthMetric` is imported from `apps.tenants.models`).

**Context keys (every one pinned):**
| key | value |
|---|---|
| `component_total` | `len(components)` |
| `operational_count` | count of `c.current_status == "operational"` |
| `unreported_count` | count of `c.last_status_at is None` |
| `rule_total` / `active_rule_count` | ints |
| `firing_count` / `open_event_count` / `unmeasured_count` | ints |
| `active_incident_count` | int |
| `latest_metrics` | the most recent `HealthMetric` rows |
| `notes` | `MONITORING_NOTES` |

**The zero rule on this page:** with **no components at all**, the page must say *"No components are
registered, so there is no status to report"* — never render a green "0 unreported" all-clear.
`unreported_count` is readable from one column, so a literal `0` is legitimate **only when
`component_total > 0`**; when `component_total == 0` render "not applicable".

### 3.6 `health_board` — the **health** board (bullet 1)

Template `core/healthboard.html`, url name `core:health_board`. **Computed; no table.**
Redirect to `dashboard:home` on `request.tenant is None`.

Content: every `ServiceComponent` with its `current_status`, `is_critical`, `is_public`, `last_status_at`
and an open-alert count; the latest `tenants.HealthMetric` readings beside them (**read, never copied**);
and the **roll-up** — one degraded service tints the whole board.

**Context keys (pinned):**
| key | value |
|---|---|
| `components` | list of dicts `{"component": c, "open_alerts": <int>, "note": <str>}` — the note is the per-row honest text (e.g. *"Status hand-set 12 days ago"*, *"Never reported"*) |
| `component_total`, `critical_count`, `public_count` | ints |
| `status_counts` | dict keyed by **every** `ServiceComponent.STATUS_CHOICES` value → int, all keys present defaulting to 0, so the template can loop the choices without a `.get` |
| `unreported_count` | int (readable, so `0` is legitimate **only when `component_total > 0`**) |
| `open_alert_count` | int |
| `latest_metrics` | list of `HealthMetric` rows, newest first per metric |
| `rollup_status` | the worst status across active components, or the string `"unknown"` when there are none — **never `"operational"` by default** |
| `notes` | `MONITORING_NOTES` |

**`rollup_status` — the derivation, pinned exactly** (worst wins; `"unknown"` is *not* worse than a real
outage, it is the absence of a claim, and it must not mask a real outage):
```python
_ORDER = ["major_outage", "partial_outage", "degraded", "maintenance", "unknown", "operational"]
rollup = "operational"
for c in components:                      # already fetched once — no second query
    if c.is_active and _ORDER.index(c.current_status) < _ORDER.index(rollup):
        rollup = c.current_status
if not any(c.is_active for c in components):
    rollup = "unknown"
```
**This is DERIVED, never stored** (SCM L37 posture): there is no `tenant.uptime` column and no roll-up
field. 0.18 may FK `ServiceComponent`; 0.20 must **link to** this board, not re-derive health.


### 3.7 `firing_board` — the **firing** board (bullet 2)

Template `core/firingboard.html`, url name `core:firing_board`. **The zero rule is the whole point of this
page:** *an empty board must not render as "healthy"*. If nothing is firing because **nothing evaluates
thresholds**, the page says so in those words.

**Context keys (pinned):**
| key | value |
|---|---|
| `open_events` | list of dicts `{"event": e, "age_days": <int>, "muted": <bool>, "note": <str>}` for `state__in=["firing", "acknowledged"]`, newest first |
| `open_count` | `len(open_events)` |
| `acknowledged_count` / `muted_count` | ints |
| `state_counts` | dict keyed by **every** `AlertEvent.STATE_CHOICES` value → int, all keys present |
| `rule_total` | int — **the denominator that makes the empty board honest** |
| `unattributed_count` | int of open events whose `rule_id` is `None` (fired against a rule nobody registered) |
| `severity_counts` | dict keyed by **every** `AlertEvent.SEVERITY_CHOICES` value → int |
| `notes` | `MONITORING_NOTES` |

**The empty-board rule, pinned as template logic:**
- `open_count == 0` **and** `rule_total == 0` → *"No alert rules are registered, so nothing can be
  evaluated. This is not an all-clear."* (`badge-slate`, never `badge-green`)
- `open_count == 0` **and** `rule_total > 0` → *"No firing has been recorded. NavERP does not evaluate
  these rules — a quiet board is an unmonitored one, not a healthy one."*
- **`badge-green` is never used on this board.** A green "0 firing" would be the exact false all-clear
  0.8's `retention_board` refuses to print.

### 3.8 `capacity_board` — the **capacity** board (bullet 4)

Template `core/capacityboard.html`, url name `core:capacity_board`. Computed over
**`tenants.UsageRecord`** (0.19 owns the commercial limit) against the **`AlertRule`** bound on that metric.
**0.17 contributes the trigger, not the quota** — the page says exactly that.

**Context keys (pinned):**
| key | value |
|---|---|
| `usage_rows` | list of dicts, one per metered metric: `{"metric": <str>, "quantity": <Decimal>, "included": <Decimal\|None>, "overage": <Decimal\|None>, "note": <str>}` — `included is None` means **unmetered on this plan** and the note says so; it is never `0` |
| `capacity_rules` | the `AlertRule` rows with `category="capacity"`, each as `{"rule": r, "headroom": <Decimal\|None>, "note": <str>}` — `headroom is None` when either side of the comparison is missing, and the note says which |
| `rule_count` / `over_threshold_count` | ints. `over_threshold_count == 0` is printed **with the caveat** *"no capacity rule is bound to this metric"* when the denominator is `0` |
| `unmetered_count` | int |
| `notes` | `MONITORING_NOTES` |

**The 0.19 handoff is visible on this page**, verbatim: *"Quota allowances, overage and fair-use limits
are 0.19's. This page shows a scaling trigger a person declared, not a quota the system enforces."*
**Do not recompute `overage` here** — `UsageRecord` already derives it and this page **reads** that value.
Recomputing it is the second-copy bug L36 forbids.

### 3.9 View close-out checks

- [ ] `grep -n "^def " apps/core/views/Monitoring.py` returns **24** functions by name: the 20 CRUD verbs (`{service_component,alert_rule,alert_event,incident}_{list,create,detail,edit,delete}`) + `alertevent_acknowledge` / `alertevent_resolve` / `alertevent_recur` / `incident_notify` + `monitoring_overview` / `health_board` / `firing_board` / `capacity_board`. **Verify by name, not by count.**
- [ ] `grep -n -B1 "def .*_delete" apps/core/views/Monitoring.py` → every delete is preceded by `@require_POST`
- [ ] Every `crud_list` call passes `search_fields`, `filters` **and** `extra_context` — no template may read a key its view did not pass (L8)
- [ ] Every `*_choices` key a list template loops over is present in that view's `extra_context`
- [ ] No view returns a bare `0` for a figure it could not determine (§3.5 / §3.6 / §3.7)
- [ ] `grep -c "MONITORING_NOTES" apps/core/views/Monitoring.py` → **1 definition + 1 use per view that renders a page** (no view invents its own honest-limit prose)

---

## 4. URLs — surgical `Edit` to the flat `apps/core/urls.py`

**One edit, appended at the very end of `urlpatterns`,** immediately after the 0.16 block and before the
closing `)`. Nothing existing is rewritten (L43: never full-rewrite a shared file; another session may be
building 8.x in this same checkout).

`core` keeps a **flat `urls.py` deliberately** (backend rule 10 — the `crud()` factory is 37 lines and
expanding it into per-entity `urlpatterns` would replace a good abstraction with ~20 duplicated `path()`
lines). **Do not convert it to a package.** The 0.17 block mirrors 0.16's shape exactly.

```python
    # ===================== 0.17 Monitoring, Logging & Observability =====================
    # Literal segments BEFORE the `crud()` groups below, and the four POST-only action routes AFTER
    # the group that owns them — the 0.16 ordering, for the same reason (a greedy `<int:pk>` route
    # declared first would shadow `add/`).
    + [
        path("monitoring/", views.monitoring_overview, name="monitoring_overview"),
        path("monitoring/health/", views.health_board, name="health_board"),
        path("monitoring/firing/", views.firing_board, name="firing_board"),
        path("monitoring/capacity/", views.capacity_board, name="capacity_board"),
    ]
    + crud("monitoring/components", "service_component")
    + crud("monitoring/rules", "alert_rule")
    + crud("monitoring/events", "alert_event")
    + [
        # POST-only verbs, declared after the literal `add/` route above so it cannot shadow it.
        path("monitoring/events/<int:pk>/acknowledge/", views.alertevent_acknowledge,
             name="alertevent_acknowledge"),
        path("monitoring/events/<int:pk>/resolve/", views.alertevent_resolve, name="alertevent_resolve"),
        path("monitoring/events/<int:pk>/recur/", views.alertevent_recur, name="alertevent_recur"),
    ]
    + crud("monitoring/incidents", "incident")
    + [
        path("monitoring/incidents/<int:pk>/notify/", views.incident_notify, name="incident_notify"),
    ]
```

**⚠️ The URL prefix is `monitoring/…` while the templates are flat `core/<entity>/`.** That asymmetry is
intentional and matches 0.16 (`backup/jobs` routes ↔ `templates/core/backupjob/`) — the route namespace
groups 0.17's pages in the URL bar; the template folder is flat because Module 0 has no sub-module level
(backend rule 9 / template rule 4). **Do not "fix" it by creating `templates/core/monitoring/`.**

**The resulting url names, verbatim (28 in all):**

| from | url names |
|---|---|
| `crud("monitoring/components", "service_component")` | `core:service_component_list`, `core:service_component_create`, `core:service_component_detail`, `core:service_component_edit`, `core:service_component_delete` |
| `crud("monitoring/rules", "alert_rule")` | `core:alert_rule_list`, `core:alert_rule_create`, `core:alert_rule_detail`, `core:alert_rule_edit`, `core:alert_rule_delete` |
| `crud("monitoring/events", "alert_event")` | `core:alert_event_list`, `core:alert_event_create`, `core:alert_event_detail`, `core:alert_event_edit`, `core:alert_event_delete` |
| `crud("monitoring/incidents", "incident")` | `core:incident_list`, `core:incident_create`, `core:incident_detail`, `core:incident_edit`, `core:incident_delete` |
| the literal `path()`s | `core:monitoring_overview`, `core:health_board`, `core:firing_board`, `core:capacity_board`, `core:alertevent_acknowledge`, `core:alertevent_resolve`, `core:alertevent_recur`, `core:incident_notify` |

- [ ] Reverse **all 28** by name in a throwaway `temp/` script (`audit_integrity.py` check 3 does this, but
      read its output rather than trusting a summary line).
- [ ] `grep -n "monitoring" apps/core/urls.py` shows the new block only — no existing line changed.
- [ ] **No `config/urls.py` or `config/settings.py` edit is needed.** `apps.core` is already installed and
      already mounted. This is the L12 trap avoided by construction: there is no new app to register.

---


## 5. Templates — 16 new files, all flat under `templates/core/`

Module 0 is a **foundation app**, so templates are **flat at the app root** (CLAUDE.md template rule 4) —
`templates/core/<entity>/{list,detail,form}.html`, **never** `templates/core/monitoring/<entity>/…`.

### 5.1 The twelve entity templates

| path | context keys it may read |
|---|---|
| `templates/core/servicecomponent/list.html` | `object_list`, `page_obj`, `q`, `kind_choices`, `status_choices`, `owner_roles`, `unreported_count`, `notes` |
| `templates/core/servicecomponent/detail.html` | `obj`, `rule_count`, `open_event_count`, `incident_count`, `notes` |
| `templates/core/servicecomponent/form.html` | `form`, `is_edit`, `notes` |
| `templates/core/alertrule/list.html` | `object_list`, `page_obj`, `q`, `category_choices`, `severity_choices`, `metric_choices`, `no_data_choices`, `services`, `notes` |
| `templates/core/alertrule/detail.html` | `obj`, `event_count`, `open_event_count`, `latest_event`, `notes` |
| `templates/core/alertrule/form.html` | `form`, `is_edit`, `notes` |
| `templates/core/alertevent/list.html` | `object_list`, `page_obj`, `q`, `state_choices`, `severity_choices`, `services`, `firing_count`, `unmeasured_count`, `notes` |
| `templates/core/alertevent/detail.html` | `obj`, `incident_count`, `related_incidents`, `notes` |
| `templates/core/alertevent/form.html` | `form`, `is_edit`, `notes` |
| `templates/core/incident/list.html` | `object_list`, `page_obj`, `q`, `status_choices`, `impact_choices`, `type_choices`, `services`, `active_count`, `notes` |
| `templates/core/incident/detail.html` | `obj`, `affected`, `alert_events`, `notes` |
| `templates/core/incident/form.html` | `form`, `is_edit`, `notes` |

Every list template carries, in this order: `{% extends "base.html" %}` → page header with breadcrumb and
page-actions → a `.text-muted` honest line → the `{% for note in notes %}` block → the filter bar → the
table → the pagination partial. Copy `templates/core/backupjob/list.html` as the structural template; it is
the most recently reviewed one.

### 5.2 The four computed pages

| path | view | the one thing it must get right |
|---|---|---|
| `templates/core/monitoringoverview.html` | `monitoring_overview` | the landing page; links to all three boards and all four registers |
| `templates/core/healthboard.html` | `health_board` | the roll-up banner and the per-component status badge |
| `templates/core/firingboard.html` | `firing_board` | **the empty state (§3.7) — never `badge-green`** |
| `templates/core/capacityboard.html` | `capacity_board` | `included is None` renders "unmetered", never `0` |

### 5.3 Template rules that are not optional

- [ ] **Badge classes are COLOUR-named** (L33): only `badge-green`, `badge-red`, `badge-amber`, `badge-info`,
      `badge-muted`, `badge-slate`. **Verify:** `grep -c "badge-success\|badge-warning\|badge-danger" templates/core/*/[ldf]*.html` → **0**.
      The exact ternaries to mirror (copied from `templates/core/legalhold/detail.html`):
      - `ServiceComponent.current_status`: `operational → badge-green` · `degraded → badge-amber` ·
        `partial_outage` / `major_outage → badge-red` · `maintenance → badge-info` ·
        `{% else %}<span class="badge badge-slate">{{ obj.get_current_status_display }}</span>{% endif %}`
        — **every branch ends in an `{% else %}`** (filter rule 5).
      - `AlertRule.severity`: `info → badge-info` · `warning → badge-amber` · `critical → badge-red` · `{% else %}…`
      - `AlertEvent.state`: `firing → badge-red` · `acknowledged → badge-amber` · `resolved → badge-green` ·
        `{% else %}<span class="badge badge-slate">{{ obj.get_state_display }}</span>{% endif %}`
      - `Incident.impact`: `none → badge-slate` · `minor → badge-info` · `major → badge-amber` ·
        `critical → badge-red` · `{% else %}…`
- [ ] **Detail rows use the real layout classes** (L40): `<dl class="detail-grid"><div class="detail-item"><dt>…</dt><dd>…</dd></div></dl>`.
      **Never** `detail-label` / `detail-value` — **verify** `grep -c "detail-label\|detail-value" static/css/theme.css` → **0**.
- [ ] **Nullable user/FK display is guarded** (L10):
      `{% if obj.acknowledged_by %}{{ obj.acknowledged_by.get_full_name|default:obj.acknowledged_by.username }}{% else %}<span class="text-muted">—</span>{% endif %}`
      — the bare `…|default:obj.acknowledged_by.username` form **500s** when the FK is `None`.
- [ ] **Pagination is guarded** (L9): `{% if page_obj.has_previous %}{{ page_obj.previous_page_number }}{% else %}1{% endif %}` and the `has_next` equivalent.
- [ ] **Every delete and every action is a POST form** with `{% csrf_token %}` and `onsubmit="return confirm('…')"` (AGENTS.md CRUD rule 2). The four POST-only action buttons are POST forms too.
- [ ] **`{% comment %}` for anything multi-line** (L2) — a multi-line `{# … #}` **leaks as visible text**.
- [ ] **No `{#` or `{% comment` markers survive into the rendered HTML** — assert it in the smoke test (L3).
- [ ] The honest-limit note uses `.text-warn` / `.text-muted`, **not** `.alert-*` (which does not exist in
      `theme.css` — the 0.16 templates already learned this).
- [ ] **The honest claim is on every page, not only the landing one.** Each template renders
      `{% for note in notes %}` with its own one-line version of the boundary, because a reader who lands
      on a detail page from a search result never sees the overview.

---


## 6. Admin — 4 registrations in `apps/core/admin.py`

One edit: add the four names to the existing `from .models import (…)` block, then append four
`@admin.register` classes at the end of the file, after `RecoveryDrillAdmin`. Match the 0.16 block's style
exactly.

```python
@admin.register(ServiceComponent)
class ServiceComponentAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "current_status", "is_critical", "is_public", "last_status_at", "tenant"]
    list_filter = ["kind", "current_status", "is_critical", "is_public", "is_active", "tenant"]
    search_fields = ["name", "code", "description"]
    list_select_related = ["owner_role", "tenant"]
    # `last_status_at` is stamped by the form when a person changes the status; the admin must not let a
    # superuser type it, or the register gains a timestamp nothing can account for.
    readonly_fields = ["last_status_at", "created_at", "updated_at"]


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "service", "metric_key", "comparator", "severity", "category", "is_active", "tenant"]
    list_filter = ["category", "severity", "metric_key", "no_data_action", "is_active", "tenant"]
    search_fields = ["name", "module_slug", "metric_key"]
    list_select_related = ["service", "notification_rule", "tenant"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AlertEvent)
class AlertEventAdmin(admin.ModelAdmin):
    # The actor and the lifecycle stamps are NOT editable anywhere — see the 0.16 `BackupJobAdmin`
    # comment. An admin who could type `acknowledged_by` would attribute an acknowledgement to
    # somebody who did not make it, and attribution is the act an audit exists for.
    list_display = ["message", "rule", "service", "state", "severity_at_fire", "fired_at", "tenant"]
    list_filter = ["state", "severity_at_fire", "tenant"]
    search_fields = ["message", "detail", "evidence", "service_label"]
    list_select_related = ["rule", "service", "acknowledged_by", "resolved_by", "tenant"]
    readonly_fields = ["state", "service_label", "occurrence_count", "first_seen_at", "last_seen_at",
                        "fired_at", "acknowledged_at", "acknowledged_by", "resolved_at", "resolved_by",
                        "resolution_note", "created_at"]


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ["title", "incident_type", "status", "impact", "service", "created_at", "tenant"]
    list_filter = ["incident_type", "status", "impact", "is_active", "tenant"]
    search_fields = ["title", "public_note", "internal_note"]
    list_select_related = ["service", "primary_alert", "tenant"]
    filter_horizontal = ["affected_services"]
    readonly_fields = ["resolved_at", "notified_at", "created_at", "updated_at"]
```

- [ ] `readonly_fields` on `AlertEventAdmin` is the whole point of that class — and the "why" comment must
      be the 0.16 attribution argument, not silence.
- [ ] `IncidentAdmin.resolved_at` is readonly because the model's `save()` derives it; letting the admin
      type it would create a row whose stamp contradicts its own status.

---


## 7. Seeder — `_seed_monitoring(tenant)` in `apps/core/management/commands/seed_core.py`

Add the four model names to the existing `from apps.core.models import (…)` block, and one new method
`_seed_monitoring(self, tenant)`, called **after** `self._seed_backup(tenant)` on line 125 of the per-tenant
loop. **Per-entity guards only — never a tenant-wide `if … .exists()`** (0.16's rule, and the reason its
C5 defect stayed invisible through review).

### 7.1 What MUST be seeded — and why it is not a false claim

| seeded | rows | the honesty argument |
|---|---|---|
| `ServiceComponent` | 3 per tenant | **A catalogue is a declaration, not evidence.** "This workspace has a web front end, a database and a payments gateway" is a true statement about what somebody chose to watch. Seeding it fabricates **no event**. |
| `AlertRule` | 3 per tenant | **A threshold rule is a recorded intention.** `SyncSchedule` (0.13), `SlaRule` (0.11) and `BackupJob.frequency` (0.16) are all seeded on exactly this basis. Seeding a rule fabricates no firing. |

The rows must exercise the states a naive seed omits (the 0.16 lesson, verbatim):
- `ServiceComponent`: one `operational` with a `last_status_at` in the past; one `degraded` that is
  `is_critical=True` (so the health board's roll-up has something to roll **up** from); one with
  `last_status_at=None` (the **unreported** case — without it the board's `unreported_count` is a
  structural `0` and its "not applicable" branch is never exercised by real data).
- `AlertRule`: one two-tier `performance` rule on `latency_p95_ms` with `must_persist_seconds > 0`; one
  one-tier `availability` rule on `uptime_pct` with `critical_threshold` only (`warning_threshold` NULL —
  the one-tier shape); one `category="capacity"` rule on `storage_mb` with **`is_active=False`**, so the
  capacity board has an inactive row and the `?active=` filter is provable. One of the three FKs an existing
  `NotificationRule`, looked up with `.filter(tenant=tenant).first()`. `_seed_notifications(tenant)` at
  line 122 has already run by the time `_seed_monitoring` does — **but write the lookup defensively** and
  allow `None`, so a future reordering cannot crash the seeder.

### 7.2 What MUST NOT be seeded — the L52 ruling, and the audit gate that enforces it

**`AlertEvent` and `Incident` are not seeded. Not one row, in any tenant, ever.**

| not seeded | why, in the voice `audit_integrity.py` already uses |
|---|---|
| `AlertEvent` | "a firing is EVIDENCE that a threshold was crossed; seeding one fabricates an alert that never happened, and its seeded `fired_at` / `observed_value` / `evidence` would be a lie told in the register's own voice (0.17)" |
| `Incident` | "a status-page entry records a communication somebody published; seeding one invents an incident that never happened (0.17)" |

`ServiceComponent.current_status` is a hand-set **claim** — and it *is* seeded. That is the one tension in
this sub-module, and it resolves cleanly: **seeding the claim is fine because the seed row is explicitly
labelled as a starting position, not as a report.** Every seeded `ServiceComponent.notes` must say so, e.g.
`"Seeded starting position. This status is a hand-set claim, not a measurement — nothing in NavERP probes
this component."` A claim honestly labelled is honest; what would be dishonest is seeding a **firing**,
which asserts that something actually happened.

**This is not optional bookkeeping — `temp/audit_integrity.py` check 6 FAILS the build without it.** That
check walks every model in an app and requires each to appear in the app's own seeder **or** in its
`KNOWN_OK` dict, and it *prints the reason* for every exemption precisely so that "an unexplained exemption
is indistinguishable from an oversight, which is the thing this check exists to catch."

- [ ] **Add to `KNOWN_OK` in `temp/audit_integrity.py`**, appended to the existing
      `--- 0.8 / 0.10 / 0.11 (module 0) ---` block. **Append — never rewrite the dict** (L43; a concurrent
      session may have added a 7.x entry):
      ```python
      "AlertEvent": "a firing is EVIDENCE that a threshold was crossed; seeding one fabricates an "
                    "alert that never happened, and the seeded fired_at/observed_value/evidence would "
                    "be a lie in the register's own voice (0.17)",
      "Incident": "a status-page entry records a communication somebody published; seeding one invents "
                  "an incident that never happened (0.17)",
      ```
- [ ] Re-run `venv\Scripts\python.exe temp\audit_integrity.py`; check 6 must still pass **and now name
      these two**, with their reasons printed.

### 7.3 Seeder output line

`self.stdout.write(f"  {tenant.name}: seeded 3 service component(s) and 3 alert rule(s)")`. The
**absence** of events/incidents is deliberate — do not print a line implying they were skipped by accident,
and do not print a count of zero for them (0.8's zero rule: a `0` there would read as an all-clear).

### 7.4 Idempotency (L5-M1)

- [ ] `venv\Scripts\python.exe manage.py seed_core` run **twice**; the second run must add **nothing**.
      Verify by diffing `SELECT COUNT(*)` per table, **not** by eyeballing stdout — 0.16 recorded that no
      test enforces idempotency, so **add the test** in Phase 6.

---


## 8. Navigation — exactly ONE `LIVE_LINKS["0.17"]` entry in `apps/core/navigation.py`

Insert it immediately after the closing `},` of the `"0.16"` block and before the
`# ========================= Module 1 — Customer Relationship Management (CRM)` banner. **Surgical `Edit`
only — never rewrite the dict** (L43; a concurrent 8.x session is in this file).

### 8.1 The five NavERP.md bullet keys must be BYTE-IDENTICAL

`parse_catalog()` in `apps/core/navigation.py` (line 2227) parses NavERP.md with
`_FEATURE_RE = re.compile(r"^\s*-\s+\*\*(.+?)\*\*")` and `resolve_nav` does `live_map.get(name)` — an
**exact string match, case- and punctuation-sensitive, with no normalisation.** A key that differs by one
character renders as a `pill-soon` "On the roadmap" stub beside a fully built page: the 7.10 failure mode,
and **check 5 of `audit_integrity.py` will not catch it** — that check verifies the target *reverses*, not
that the key matched a bullet.

The five bullets, **copied character-for-character** from `NavERP.md`'s
`### 0.17 Monitoring, Logging & Observability` section (read them off the file; do not retype from a plan):

1. `System Health Dashboards` — *"Uptime, resource usage, and service-status monitoring."*
2. `Application & Error Logging` — *"Centralized logs, error tracking, and alert thresholds."*
3. `Performance Metrics & APM` — *"Latency, throughput, slow-query detection, and distributed tracing."*
4. `Capacity & Resource Planning` — *"Usage trends, scaling triggers, and quota management."*
5. `Status Page & Incident Comms` — *"Internal/external status pages and maintenance notices."*

### 8.2 The entry

```python
    # 0.17 Monitoring, Logging & Observability. The five bullet keys below are copied
    # BYTE-IDENTICALLY from `NavERP.md`; `parse_catalog()` matches them by exact string, so a
    # one-character drift renders a built page as a roadmap pill with no error anywhere.
    # Bullets 2, 3 and 4 are PARTIAL or hand-shared, and the comments say which:
    #   b2 "centralized logs" is deferred (no log pipeline exists) — thresholds + the firing register;
    #   b3 distributed tracing is deferred (no OTel SDK) — latency/throughput/slow-query are
    #      THRESHOLD VOCABULARY on AlertRule and a computed board, not an APM product;
    #   b4 quota management is 0.19's; 0.17 keeps the scaling trigger.
    "0.17": {
        "System Health Dashboards": "core:health_board",                 # b1 (the roll-up board)
        "Application & Error Logging": "core:alert_event_list",           # b2 (thresholds + firings)
        "Performance Metrics & APM": "core:alert_rule_list",              # b3 (latency/throughput rules)
        "Capacity & Resource Planning": "core:capacity_board",             # b4 (0.19 owns the quota)
        "Status Page & Incident Comms": "core:incident_list",              # b5
        # Extra built pages that are not NavERP.md bullets. `resolve_nav` appends these AFTER the
        # bullets, so they read as operational leaves rather than as more features.
        "Service Components": "core:service_component_list",               # extra (the entity half)
        "Alert Thresholds": "core:alert_rule_list",                        # extra
        "Alert Events": "core:alert_event_list",                           # extra
        "Firing Board": "core:firing_board",                               # extra (the zero rule)
        "Monitoring Overview": "core:monitoring_overview",                 # extra (landing page)
    },
```


### 8.3 The nav verification — run it, do not read it

- [ ] With `venv\Scripts\python.exe`, assert programmatically that every `NavERP.md` 0.17 bullet is a key
      **and** resolves:
      ```python
      from apps.core.navigation import LIVE_LINKS, parse_catalog
      sub = next(s for m in parse_catalog() for s in m["submodules"] if s["num"] == "0.17")
      keys = LIVE_LINKS["0.17"]
      assert set(sub["features"]) <= set(keys), set(sub["features"]) - set(keys)
      assert all(keys[f] for f in sub["features"])          # every bullet resolves
      ```
- [ ] `venv\Scripts\python.exe temp\audit_integrity.py` — check 1 (CATALOG vs `LIVE_LINKS`) must no longer
      list 0.17 under "catalogued but NOT built"; check 5 (every sidebar target reverses) must pass and the
      reported distinct-target count must grow by exactly 8 (5 bullets collapsing onto 3 distinct routes,
      plus the 5 extras — `alert_rule_list` and `alert_event_list` are each reached twice).
- [ ] **Manual sidebar pass as `admin_acme`** (L30): every 0.17 bullet is **live** (not a "soon" pill) and
      lands on a page that renders real content for the Acme tenant. A bullet still showing "soon" is the
      7.10 failure mode and blocks close-out.
- [ ] `git diff apps/core/navigation.py` shows one added block and **nothing else** — the 8.x session's
      entries are untouched.

---

## 9. Migration — `core.0015_*`, and the L43 agreement

- [ ] **Agree the number before generating** (L43). `core` is at
      `0014_dataarchive_darch_tenant_at_idx_and_more.py` (the I5 index fix 0.16 landed last), so 0.17 takes
      **`0015`**. Re-check `Get-ChildItem apps/core/migrations` immediately before running
      `makemigrations` — a peer session could have taken it. **If `0015_*` now exists, take `0016` and say
      so in the contract.**
- [ ] **Pre-create the placeholder as an empty file at Phase 0 and commit it as its own file** — the 0.16
      move (`00122627` claimed `core.0013` before the build started). That makes the number claim durable
      and visible in `git log`, not a claim in a transcript.
- [ ] Generate with `venv\Scripts\python.exe manage.py makemigrations core` and **read the generated file**
      before applying: 4 `CreateModel`s + the auto-created `core_incident_affected_services` M2M through
      table + `unique_together` on `core_alertrule` + 9 `AddIndex` operations. **The through table is not a
      5th hand-declared model** — confirm the migration did not emit an explicit `CreateModel` for it with
      its own `options` block, and that the index names match §1 byte-for-byte.
- [ ] `venv\Scripts\python.exe manage.py migrate`, then
      `venv\Scripts\python.exe manage.py makemigrations core --check --dry-run` → **"No changes detected."**
- [ ] **The final gate that only catches an unapplied migration:** run the `apps/core/tests` suite
      **without** `--nomigrations`. 0.16 recorded this as its last item and it is the only run that proves
      the migration applies to a clean database — `pytest --nomigrations` builds tables straight from the
      models, so a broken dependency ordering or through-table declaration sails straight past it.
- [ ] Commit the migration as **one file, one commit**:
      `git add 'apps/core/migrations/0015_monitoring_*.py'; git commit -m '…'` (PowerShell-safe: `;`
      never `&&`, and the glob quoted).
---

## 10. Verify — four gates, in this order. Do not start Phase 4 until all four are green.

The whole of 0.17 is a claim about what NavERP is *not* doing, so these gates are weighted toward
**proving the honesty of the prose**, not merely toward `200`s. A page that renders is a weak pass; a page
that renders *and* refuses to imply monitoring is the pass.

### 10.1 Gate 1 — Django's own check

- [ ] `venv\Scripts\python.exe manage.py check` → `System check identified no issues (0 silenced).`
- [ ] `venv\Scripts\python.exe manage.py makemigrations core --check --dry-run` → **`No changes detected.`**
      This is the gate that catches a model field added to the form but not the model, or a `Meta.indexes`
      entry typed into this plan but not the file. **Run it before the migration and again after** — before,
      to prove the models are complete; after, to prove the migration matches them.
- [ ] `venv\Scripts\python.exe manage.py check --deploy` — read-only, informational. Do **not** chase its
      warnings; they are pre-existing Module-0 settings findings, not 0.17 regressions.

### 10.2 Gate 2 — `temp/audit_integrity.py`, all six checks, each with a stated expected result

- [ ] `venv\Scripts\python.exe temp\audit_integrity.py` → `RESULT: all checks passed`
- [ ] **Read all six. Do not read the summary line.** The expected result for each:

| # | check | what 0.17 must produce | what a FAIL means |
|---|---|---|---|
| 1 | CATALOG | 0.17 **disappears** from "catalogued but NOT built"; every one of the five bullets resolves to a real route | a bullet text drifted from the `LIVE_LINKS` key (§8.1) — the 7.10 failure |
| 2 | MIGRATIONS | no pending migration for `core`; the `0015_*` node is applied | §9's final gate was skipped |
| 3 | ROUTES | all **28** new `core:` names reverse (20 CRUD + 4 boards + 4 actions) | a `crud()` slug/name pair or an action route is misspelled |
| 4 | TEMPLATES | each of the **16** new templates is found on disk and is referenced by a 0.17 view | a template with no view, or a view with no template (dead page) |
| 5 | SIDEBAR | every `LIVE_LINKS["0.17"]` target reverses; distinct-target count grows by exactly **8** | a nav entry points at a view that was never created |
| 6 | SEEDERS | still passes, and **now names `AlertEvent` and `Incident`** with their §7.2 reasons printed | the two L52 exemptions were never added |

- [ ] **Check 6 fails silently for the wrong reason.** With `AlertEvent`/`Incident` missing from
      `KNOWN_OK`, check 6 fails with a *seed* complaint. With them present but carrying **no reason string**,
      it passes and the honesty ruling is undocumented. Both are wrong; the second is worse.
- [ ] Confirm the 0.16 and 8.x rows in `KNOWN_OK` are still present and unmodified —
      `git diff temp/audit_integrity.py` shows **additions only**.

### 10.3 Gate 3 — the smoke list: 24 GET pages, asserted for **content**

`manage.py check` cannot see a context-key drift, and neither can a 200. A view that passes
`event_count=None` because the template reads `rule_count` still returns **200 and renders blank** — that is
L8, and it is the most common 0.x defect. Every row below therefore names a **string that must be present in
the body**, not a status code.

- [ ] **First, the fixture problem the seeder deliberately creates.** `AlertEvent` and `Incident` are **not
      seeded** (§7.2), so the Acme tenant has zero rows of each. That is correct and must **not** be "fixed"
      in the seeder. Instead a throwaway `temp/smoke_017.py` creates **one `AlertEvent` and one `Incident`
      for `admin_acme`'s tenant** via the ORM, records their pks, and deletes them in a `finally`.
- [ ] Log in as **`admin_acme`** — a tenant admin, because every 0.17 view is `@tenant_admin_required`. A
      superuser has `tenant=None` and sees empty pages that look exactly like drift.
- [ ] Drive the pages with the Django **test client** inside `temp/smoke_017.py` so the assertions are
      re-runnable; no `runserver` needed.

**The four computed pages — the substantive assertions:**

| url name | must contain, literally |
|---|---|
| `core:monitoring_overview` | the heading, the four register totals, the `{% for note in notes %}` honest-limit block, and `unreported_count == 1` |
| `core:health_board` | every seeded `ServiceComponent` name; the `rollup_status` **word** (degraded — one seeded component is `degraded` + `is_critical`); the literal *"Never reported"* on the component whose `last_status_at is None` |
| `core:firing_board` | with the throwaway event: its `message` and its `age_days`. After deletion: the **empty-board sentence** — and **`badge-green` absent from the whole page** (§3.7), asserted by substring, not by eye |
| `core:capacity_board` | the verbatim 0.19 handoff line (§3.8); a `usage_rows` row; `included is None` rendered as **"unmetered"**, never `0` |

**The four registers — the L7/L8 assertion per page:**

- [ ] `core:service_component_list` — a seeded component name; all three dropdowns render
      (`kind_choices`, `status_choices`, `owner_roles`); `unreported_count` shows.
- [ ] `core:alert_rule_list` — a seeded rule name; `category_choices`, `severity_choices`, `metric_choices`,
      `no_data_choices` all render; `services` is populated.
- [ ] `core:alert_event_list` — the throwaway event's `message`; `state_choices` + `severity_choices`
      render; `unmeasured_count` renders.
- [ ] `core:incident_list` — the throwaway incident's `title`; `status_choices`, `impact_choices`,
      `type_choices` render; `active_count` renders.
- [ ] Each `*_add` page renders **every** field in its form's `Meta.fields` — and **no** `DateTimeField`
      (§2). A `resolved_at` / `fired_at` / `acknowledged_at` input on a form is **L22 and a build defect**,
      not a smoke finding: stop and fix §2.
- [ ] Each `*_detail` page renders the object's own fields **and** every key from its `extra_context`
      (§3.1–§3.4): `rule_count` / `open_event_count` / `incident_count`; `event_count` / `latest_event`;
      `incident_count` / `related_incidents`; `affected` / `alert_events`.
- [ ] Each `*_edit` page renders pre-filled.
- [ ] Each `*_delete` URL on **GET** redirects to its list (it is POST-only). A 200 here is a defect.

**The four POST-only actions — the guard, not the happy path:**

| action | POST on a row that is | expected |
|---|---|---|
| `core:alertevent_acknowledge` | `state="firing"` | 302 to the list; state now `acknowledged`; `acknowledged_at` set; `acknowledged_by` = the user; `AuditLog` row written |
| `core:alertevent_acknowledge` | `state="resolved"` | **refused** — no write, no `AuditLog` row, message explains why |
| `core:alertevent_resolve` | `state="acknowledged"` | 302; `resolved_at` + `resolved_by` + `resolution_note` set |
| `core:alertevent_resolve` | `state="firing"` | **refused** — acknowledge before you resolve; the guard is the point |
| `core:alertevent_recur` | `state="resolved"` | 302; `occurrence_count` incremented by exactly 1; `last_seen_at` set |
| `core:incident_notify` | `notified_at` already set | **refused** — "already recorded as published" |
| `core:incident_notify` | `notified_at is None` | 302; `notified_at` set |
| all four | `GET` | **405**, and no row changed |

- [ ] **Junk params do not 500** (L11) — `?kind=nonsense`, `?status=nonsense`, `?service=999999`,
      `?service=abc`, `?page=9999`, `?q=` on **all four** lists → 200 with the unfiltered set. A
      `ValueError` from `as_db_int`, or a `ValidationError` from a `choices` filter, is a FAIL here.
- [ ] **Page 2 is reachable** (L9). Only 3 components are seeded, so assert the pagination partial renders
      `has_next` false and says so honestly — and force a second page by seeding **throwaway** rows in
      `temp/smoke_017.py` (never in the seeder) so the `?page=2` branch is genuinely exercised. A `?page=2`
      silently returning page 1's objects is the L9 defect.
- [ ] **Cross-tenant IDOR → 404**: an `AlertEvent` and an `Incident` created for `tenant_b`, fetched by pks
      as `admin_acme` → **404 on all eight** CRUD routes (detail, edit, delete, and the three/four actions).
      A 200 or a 500 is a security FAIL, and it is the finding `security-reviewer` would otherwise raise.
- [ ] **The sidebar pass, as `admin_acme`** (L30): all five 0.17 bullets are **live links**, none is a
      "soon" pill, and each lands on a page that rendered real content above.
- [ ] No `{#` or `{% comment` marker survives into any rendered body (L3), and no multi-line `{# ... #}` was
      used anywhere (L2).
- [ ] `temp/smoke_017.py` is **deleted** before close-out. It is a throwaway; leaving it in `temp/` is how
      the next session inherits a script that writes rows it never cleans up.

### 10.4 Gate 4 — the honesty gate (L38 / L52). Run it by hand, once, and read the pages.

- [ ] Read `core:monitoring_overview`, `core:firing_board` and `core:capacity_board` as **a reader who does
      not know the code**, and answer: *does any sentence on any of these 24 pages imply that NavERP is
      watching, probing, evaluating, notifying or publishing something it is not?*
- [ ] If the answer is yes anywhere, the fix is **prose**, in the same commit as the page (L38): the page
      must not assert what the code does not do. Do **not** silence it by deleting the claim's subject.
- [ ] Confirm the reverse direction too — the **0.19 handoff** on the capacity board and the
      *"nothing evaluates these rules"* line on the firing board are **present and verbatim**. A page that
      hedges about what it does not do is correct; a page that hedges about what it *does* do is the
      opposite failure and is just as dishonest.

---

## 11. Close-out

Phases 4→7 run **in order**, one agent in flight at a time, one file per commit. `git push` is **never**
part of any step.

### 11.1 Phase 4 — review (six reviewers, one after another)

- [ ] `BASE` = the sha saved at Phase 0 (`git rev-parse HEAD` before the first 0.17 commit). If it was not
      saved, recover it from `git --no-pager log --oneline` and take the commit before the first 0.17 file —
      **the reviewers need a range**; with no range they read the whole repo and return nothing usable.
- [ ] Run **exactly these six, in this order**, each in its own agent call, each reviewing `BASE...HEAD`:
      `code-reviewer` → `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` →
      `security-reviewer`.
- [ ] The reviewers are **read-only** and **commit nothing**. `qa-smoke-tester` is the only one that may
      touch the DB (migrate + seed + its own throwaway `temp/` script), and its "fix what you find"
      behaviour is **overridden to "report it instead"**.
- [ ] **After each agent reports, append its findings to `.claude/tasks/review-core-0.17.md`** — do not
      carry findings in your head between agents. Findings that live only in the transcript are not findings.
- [ ] When all six have reported: dedupe, sort **Critical → Important → Minor**, assign IDs (`C1`, `I3`,
      `M7`), and commit that file as its own single commit.
- [ ] If a reviewer returns nothing usable, **re-run that one agent**. A missing pass is missing coverage,
      not a clean bill of health.
- [ ] **The lead question for 0.17, given to every reviewer** (research §"Residual risk"): *"Does any page
      on these models imply NavERP is watching something it is not watching?"* All four models are registers
      of things that did not happen automatically, so this is the highest-value question in the sub-module —
      and it is the one a generic reviewer will not think to ask.
- [ ] **L28 clone sweep:** if a per-model defect surfaces, sweep all four `templates/core/<entity>/` triples
      and all four `crud()` entries together, not just the offending entity. They are four instances of one
      pattern; fixing one is how a sub-module ships three copies of the same bug.

### 11.2 Phase 5 — `code-fixer`, one agent

- [ ] Hand it `.claude/tasks/review-core-0.17.md` verbatim. **The main session does not apply findings
      itself** — that is what kept blowing out the context window.
- [ ] It fixes in **ID order** (all Critical, then Important, then Minor), verifies each, and makes **one
      commit per file**, marking each finding `[x] fixed` or `[~] skipped — reason` **in the findings file**.
- [ ] When it reports: **no finding is left `[ ] open`**, and `manage.py check` is still clean.
- [ ] Re-run Gate 1 (§10.1) afterwards. A fixer that "improved" a model and left the migration stale is the
      exact failure `--check` exists to catch.

### 11.3 Phase 6 — tests, serial

- [ ] **Step 1, one agent, owns the contract:** write `.claude/tasks/test-contract-core-0.17.md` pinning the
      exact model / form / url / context names, then `apps/core/tests/__init__.py` and the shared
      `conftest.py` additions. **`conftest.py` is owned by this step alone** — no later step may edit it
      without re-running the full suite.
- [ ] Fixtures use the **`mon_` prefix** (`mon_component_a`, `mon_rule_a`, `mon_event_b`, `mon_incident_b`),
      following 0.16's `bkp_` precedent, so a later `test_writing_*` agent appending nearby cannot shadow
      them. `conftest.py` already provides `tenant_a` / `tenant_b` — **reuse them, do not redefine**.
- [ ] **Step 2, one `test-writer` agent per file, one after another**, each committed on its own as it lands:
      `test_monitoring_models.py` → `test_monitoring_forms.py` → `test_monitoring_views.py` →
      `test_monitoring_security.py`. Every test function is `test_monitoring_*`; every module-level
      helper `_monitoring_*`.
- [ ] The four modules must cover, at minimum: the two **reuse-by-reference** assertions
      (`AlertRule.COMPARATORS is BusinessRule.OPERATORS`,
      `AlertRule.FREQUENCY_CHOICES is SyncSchedule.FREQUENCY_CHOICES`) · the **NULL-is-not-0** rendering of
      every nullable numeric · the **zero editable `DateTimeField`s** rule · the action **guards** (§10.3) ·
      **seeder idempotency** (the test 0.16 recorded as missing) · **cross-tenant 404** on all eight routes ·
      the **empty-firing-board** prose.
- [ ] **Step 3: the full UNFILTERED `apps/core/tests` suite, run to green.** Never `-k` filtered — a filter
      excludes exactly the tests a shared-file change can break (L47). This run must also include the
      pre-existing `test_crud_enum_guard.py` and `test_navigation_active.py`, which walk the new `choices`
      tuples and the new sidebar entries respectively.
- [ ] Run that suite **once without `--nomigrations`** — the only run that proves `0015_*` applies to a clean
      database (§9's final gate).

### 11.4 Phase 7 — skill + docs, one file per commit

- [ ] `.claude/skills/core/SKILL.md` — append the 0.17 section: the four models with their key fields and
      choices, the **28 url names**, the 16 template paths, the seeder rows **and the two deliberate
      non-seeds**, and the `LIVE_LINKS["0.17"]` entry. Record the **ownership ruling** explicitly, because
      the next agent to touch `core` is the one most likely to "helpfully" add a log table. **Append — never
      rewrite**; the file is shared with every earlier `core` sub-module.
- [ ] **`README.md` line 1193** — the Module 0 row: `16 of 21 sub-modules built (0.1–0.16)` →
      **`17 of 21 sub-modules built (0.1–0.17)`**, and update the trailing pointer so it names the four
      that remain (0.18–0.21) rather than the five it names now.
- [ ] **`NavERP.md`** — the Module 0 counter line: `16 of 21 built — 0.1–0.16 (5 remain: 0.17–0.21)` →
      **`17 of 21 built — 0.1–0.17 (4 remain: 0.18–0.21)`**.
      WARNING: **this is the file `parse_catalog()` reads.** Re-run Gate 2 check 1 after editing it — a
      botched heading or bullet here silently changes sidebar labels across the whole app.
- [ ] Commit each of the three files separately. Never bundle them.

### 11.5 Discipline reminders (the three that actually get broken)

- [ ] **One file per commit**, `git add '<path>'; git commit -m '...'` — `;`, never `&&` (PowerShell 5.x).
      No exceptions, including for three templates in one entity folder.
- [ ] **Never `git push`.** Stop at `git commit`.
- [ ] **L45 — the tree was dirty at this session's start** (`.claude/tasks/todo.md`, `apps/sales/tests/*`,
      `templates/projects/reporting/*`, plus the 8.4 sales files). Those are **not yours**. Do not stage
      them, do not revert them, and do not let a `git add -A` sweep them into a 0.17 commit.
- [ ] **Re-append this plan into `.claude/tasks/todo.md` once that file is clean** (see the placement note
      at the top). It is dirty with another session's uncommitted work; committing it would misattribute
      their work under a message you wrote. Until its owner commits it, **this file is the plan of record**
      and the build session must read *this* file, not `todo.md`.
- [ ] `.claude/tasks/plan-core-0.17.md` is committed **on its own**, as the last file of Phase 2.
