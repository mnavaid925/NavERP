"""core — 0.17 Monitoring, Logging & Observability.

**The rule this file is built around, inherited from 0.8 (`apps/core/models/Retention.py`) and 0.16
(`apps/core/models/Backup.py`):**

> *"'delete' in this codebase does not erase bytes… A 'destruction' feature that reports success while the
> file survives on disk would be actively dishonest."*

Applied here to monitoring. NavERP has **no probe**, **no collector**, **no log pipeline**, **no APM or
tracing SDK** and **no scheduler** — there is no code in this repository that pings a service, samples a
metric, evaluates a threshold, sends a notification or publishes a status page. So every model in this file
is a **register of claims a person wrote**, and every page built on them says so.

Three consequences run through the whole file:

1. **A threshold is not a reading.** `AlertRule.metric_key` is a *vocabulary*, not a store. Ten of its
   twelve keys (`latency_p95_ms`, `throughput_rps`, `error_rate_pct`, `slow_query_ms`, `cpu_pct`,
   `memory_pct`, `disk_usage_pct`, `db_connection_pct`, `queue_depth`, `job_failures`) have **no stored
   reading anywhere in this repository** — NavERP measures none of them. `uptime_pct` and `storage_mb` do
   overlap `tenants.HealthMetric.METRIC_CHOICES`, and that overlap is **deliberate but not a synonym**:
   there a value is *tenant consumption*; here the same word is a *platform bound an operator declares*.
   Do not "fix" the duplication by deleting a key, and do not "fix" it by joining the two models
   together either — they are different facts about different subjects.
2. **`NULL` is not `0`.** `last_status_at`, `observed_value`, `threshold_at_fire`, `progress_pct`,
   `warning_threshold` and `critical_threshold` are nullable **on purpose**. A `0` that means "not
   reported" is the most dangerous number an operations board can print (0.8's `retention_board` and 0.16's
   `backup_board` both refuse exactly this). The `*_display` properties below render `None` as `"—"` and
   never coerce it.
3. **A firing is evidence, not a fact NavERP observed.** `AlertEvent` records *a report that a threshold
   was crossed*, exactly as `DisposalRecord` records *a report that a disposal happened*. Recording one
   does not make it true — which is why the seeder creates **zero** `AlertEvent` and **zero** `Incident`
   rows (see the L52 ruling in `apps/core/management/commands/seed_core.py`).

**Ownership (L36 — what this file deliberately does NOT re-declare):**
`core.AuditLog` (who changed which row — a different subject from "a threshold was crossed");
`core.BusinessRule` / `BusinessRuleLog` and `core.SlaRule` / `ApprovalLimit` (0.11's process rules —
`AlertRule.COMPARATORS` *reuses* `BusinessRule.OPERATORS` as a shared constant and has **no FK** either
way, so the reuse cannot drift into inheritance); `core.NotificationRule` / `Channel` / `Template` (0.12
owns routing — `AlertRule.notification_rule` is the single seam); `core.SyncSchedule` (0.13 owns the
schedule vocabulary, reused **by reference** as `FREQUENCY_CHOICES`); `core.RateLimitPolicy` (0.18's);
`tenants.HealthMetric` and `tenants.UsageRecord` (read by the health and capacity boards, never copied).
`Incident` has **no** FK to `SlaRule` and **no** FK to `EnvironmentInstance` — a maintenance notice is a
communication *about* a window somebody else owns.

**Deferred on purpose, do NOT build:** a centralized log store / `LogEntry` table, log shipping,
distributed tracing (`Trace` / `Span`), a raw metric time-series table, a quota/allowance table,
notification channels or routing, a scheduler or job registry. `AlertEvent` therefore has **no** stack
trace, **no** log line, **no** request/response body and **no** raw payload column: a permanently-empty
field is a lie by omission (L52).

**Known, documented limitation — do not try to close it here.** `TenantConsistentMixin` walks
`ForeignKey`/`OneToOneField` only, so `Incident.affected_services` (an **M2M**) is not tenant-checked on
the **admin** path. `TenantModelForm` *does* narrow M2M querysets, so the form path is covered when
`tenant is not None`. Same posture 0.16 recorded for **C7 (escalated, not fixed)**. Do **not** change
`TenantModelForm`; it would break committed tests in three other apps.
"""
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone

from apps.core.models._base import *  # noqa: F401,F403
# The tenant-consistency model edge (I2), defined in `Backup.py` exactly as `LegalHold.py` imports it.
# One-way and cycle-free: `Backup.py` does not import this module.
from apps.core.models.Backup import TenantConsistentMixin
# Reuse-by-REFERENCE (L36), never a second pasted copy that can drift the first time 0.11 adds an
# operator or 0.13 adds a frequency. The two aliases below are asserted at load time in
# `temp/audit_integrity.py`, so a future edit that rebuilds either list fails loudly instead of quietly
# forking the vocabulary.
from apps.core.models.BusinessRule import BusinessRule
from apps.core.models.Integration import SyncSchedule


#: Reuse-by-REFERENCE: the same public operator constant 0.11 exposes, not a parallel list.
#: `BusinessRule.OPERATORS` is a flat tuple of strings rather than `(value, label)` pairs, so the CHOICES
#: are DERIVED from it at import time. Derived, never hand-written — hand-writing this tuple is exactly
#: the drift the derivation exists to prevent.
COMPARATORS = BusinessRule.OPERATORS
COMPARATOR_CHOICES = tuple((op, op.replace("_", " ").title()) for op in COMPARATORS)

#: Reuse-by-REFERENCE: 0.13 owns the schedule vocabulary. 0.16 copied it into a private
#: `_SCHEDULE_FREQUENCY_CHOICES` (`Backup.py:45`), which is a second copy that can drift — do NOT repeat
#: that here. Assign the object; never mutate it and never rebuild the list. As `SyncSchedule`'s own
#: docstring says of its frequency, a frequency here is a **recorded intention** — nothing runs it either.
FREQUENCY_CHOICES = SyncSchedule.FREQUENCY_CHOICES

#: A firing's severity deliberately OVERLAPS `tenants.HealthMetric.STATUS_CHOICES` on the strings
#: `warning` / `critical`, so the health board and the firing board cross-reference a rule and a reading
#: without a translation table. `info` is the one value 0.1 has no counterpart for. This is a shared
#: vocabulary, not a shared store: `HealthMetric` is never joined to this, and the two are not the same
#: fact — 0.1's `status` is a recorded reading, this is a declared severity.
SEVERITY_CHOICES = [("info", "Info"), ("warning", "Warning"), ("critical", "Critical")]






class ServiceComponent(TenantConsistentMixin, models.Model):
    """The thing that can go down — the entity half NavERP was missing.

    Every status-page product separates the *monitored entity* from the *measurement*. This repo had the
    measurement half (`tenants.HealthMetric`, 0.1) and no entity half, so nothing could say "the payments
    API is degraded". This model is that entity half, and **nothing probes it**: `current_status` is a
    hand-set claim, and the field's own `help_text` says so on the form.
    """

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
    #: **Five values, and `unknown` is the default on purpose** — a newly registered component has no
    #: status and the honest one to hold is "nobody has said". 0.17 declares no `maintenance` value here:
    #: a maintenance window is expressed as an `Incident` of type `scheduled_maintenance` rather than as a
    #: component status, so the health roll-up never has to guess whether a planned window is an outage.
    STATUS_CHOICES = [
        ("operational", "Operational"),
        ("degraded", "Degraded"),
        ("partial_outage", "Partial outage"),
        ("major_outage", "Major outage"),
        ("unknown", "Unknown"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="service_components", db_index=True)
    name = models.CharField(max_length=150)
    #: Short slug for URLs and tickets. **Free text, not a `SlugField`** — this is a label somebody
    #: types, not an identifier the system generates, and a `SlugField` would imply the latter.
    code = models.CharField(max_length=40, blank=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="web_service")
    description = models.TextField(blank=True)
    #: Who is paged. Same shape as `NotificationRule.audience_role`; `related_name` is NOT `"+"` so the
    #: role's own page links back to what it owns.
    owner_role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="owned_service_components")
    is_public = models.BooleanField(default=False)
    #: A failure here tints the whole health board's roll-up.
    is_critical = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    current_status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="unknown",
        help_text="A hand-set claim. Nothing in NavERP probes this component.")
    #: `NULL` = "never reported", which is not the epoch and is never coerced to 0. System-set — stamped
    #: by `ServiceComponentForm.save()` when a person changes the status, and off the form (L22).
    last_status_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    #: A retired component stops counting toward the health roll-up rather than vanishing from it.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]
        indexes = [
            models.Index(fields=["tenant", "current_status"], name="svccomp_tenant_status_idx"),
            models.Index(fields=["tenant", "is_public"], name="svccomp_tenant_public_idx"),
        ]
        # Deliberately NO index on the ordering columns (`display_order`, `name`). The I5 finding that
        # forced `-archived_at` / `-performed_at` indexes in 0.16 applies to unbounded registers; this is
        # a per-tenant *catalogue* of tens of rows, not a 5,000-row log, and an index here would cost a
        # write on every edit for no read win. Saying so beats letting a reviewer read it as oversight.

    def __str__(self):
        return f"{self.name} ({self.get_current_status_display()})"

    # ---- derived (never stored) ----
    @property
    def last_status_display(self):
        """When a person last set this status by hand, or an em dash when nobody ever has."""
        if self.last_status_at is None:
            return "—"
        return self.last_status_at.strftime("%b %d, %Y %H:%M")

    @property
    def status_age_days(self):
        """Days since the hand-set status changed; `None` when it has never been reported."""
        if self.last_status_at is None:
            return None
        return (timezone.now() - self.last_status_at).days

    def status_note(self):
        """The one honest sentence about this row, reused by the board and the detail page.

        Returns `None` — not an empty string — when there is nothing to say, so a template can test it.
        """
        if self.last_status_at is None:
            return "Never reported — nobody has ever set a status on this component."
        age = self.status_age_days
        return f"Hand-set {age} day{'s' if age != 1 else ''} ago. NavERP has not checked it since."

    @property
    def owner_role_name(self):
        return self.owner_role.name if self.owner_role_id else ""


class AlertRule(TenantConsistentMixin, models.Model):
    """The threshold, as a recorded intention. A capacity ceiling, a latency p95, an error-rate burn and
    an uptime floor are the same row with a different `metric_key`.

    NavERP already had threshold-shaped *process* rules (`SlaRule`, `BusinessRule` in 0.11) and *quota*
    rules (`RateLimitPolicy`, `UsageRecord.included_allowance` in 0.18/0.1) but **no metric-threshold
    rule** — nothing could say "raise an alert if p95 latency exceeds 800 ms for 5 minutes". That is this
    model, and **nothing evaluates it**: there is no scheduler, so a rule here is a sentence somebody
    wrote down, exactly as `SyncSchedule.frequency` (0.13) and `SlaRule` (0.11) are.
    """

    #: Reuse-by-REFERENCE, held ON THE CLASS as well as at module scope so the documented assertion
    #: `AlertRule.COMPARATORS is BusinessRule.OPERATORS` reads the way the plan states it. Both names
    #: point at the SAME tuple — this is an alias, not a second list, and the identity is what makes the
    #: reuse real (a `.append()` here would be a bug, and the assertion catches it).
    COMPARATORS = COMPARATORS
    COMPARATOR_CHOICES = COMPARATOR_CHOICES
    FREQUENCY_CHOICES = FREQUENCY_CHOICES
    SEVERITY_CHOICES = SEVERITY_CHOICES

    #: The taxonomy that keeps 0.18 out. `security` is the *entire* seam 0.18 grows through — there is
    #: no second security model here and no rate-limit or lockout vocabulary to duplicate.
    CATEGORY_CHOICES = [
        ("availability", "Availability"),
        ("error", "Error"),
        ("performance", "Performance"),
        ("capacity", "Capacity"),
        ("security", "Security"),
    ]
    #: Grafana's *error and no-data handling*, folded in as a choice rather than a table. It makes the
    #: NULL-is-not-0 discipline STRUCTURAL: a metric that stopped reporting is a distinct state from
    #: "fine", and a naive schema cannot express that distinction at all.
    NO_DATA_CHOICES = [
        ("fire", "Fire on no data"),
        ("ignore", "Ignore no data"),
        ("ok", "Treat no data as OK"),
    ]
    #: A strict SUPERSET of what 0.1 stores (`tenants.HealthMetric.METRIC_CHOICES` = users, storage_mb,
    #: api_calls, db_rows, uptime_pct). The other ten keys are **threshold vocabulary only — there is no
    #: stored reading for any of them anywhere in this repository**, which is correct: a threshold is not
    #: a reading. `uptime_pct` and `storage_mb` overlap 0.1's keys *by string on purpose*, but they mean
    #: something different (a platform bound here, tenant consumption there) — the file docstring says so
    #: so the next agent does not "fix" the duplication (L52).
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



    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="alert_rules", db_index=True)
    #: **CASCADE, unlike every other FK in this file** — a threshold on a component that no longer
    #: exists is meaningless, and keeping it would leave a rule bound to a dead row. Contrast
    #: `AlertEvent.rule`, which is `SET_NULL` because that one IS evidence.
    service = models.ForeignKey("core.ServiceComponent", on_delete=models.CASCADE,
                                related_name="alert_rules")
    name = models.CharField(max_length=150)
    #: The NavERP module this guards — the `BusinessRule.module_slug` precedent.
    module_slug = models.CharField(max_length=40, blank=True)
    metric_key = models.CharField(max_length=24, choices=METRIC_CHOICES, default="uptime_pct")
    comparator = models.CharField(max_length=10, choices=COMPARATOR_CHOICES, default="gte")
    #: Two tiers (PRTG's warning/downtime, Dynatrace's two-stage). **`NULL` = "this tier is unset", never
    #: `0`**: a warning bound of 0 is a different claim from no warning bound, and only one of them is
    #: true of most metrics. A one-tier rule is normal; `tier_count` below names the shape.
    warning_threshold = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    critical_threshold = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    #: Grafana's *duration* — the "how long must this hold before it counts" that stops a flapping alert.
    #: `0` is truthful here (no persistence window demanded), which is exactly why this one is NOT
    #: nullable while the two thresholds above are.
    must_persist_seconds = models.PositiveIntegerField(default=0)
    frequency = models.CharField(
        max_length=10, choices=FREQUENCY_CHOICES, default="manual",
        help_text="A recorded intention. Nothing in NavERP runs it.")
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="warning")
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES, default="availability")
    no_data_action = models.CharField(max_length=12, choices=NO_DATA_CHOICES, default="ignore")
    #: **The single seam to 0.12.** `related_name="+"` — nothing lists alert rules by notification rule,
    #: and a reverse accessor would only invite a second router to be built beside 0.12's.
    notification_rule = models.ForeignKey("core.NotificationRule", on_delete=models.SET_NULL, null=True,
                                          blank=True, related_name="+")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        #: `(tenant, name)` — two rules with the same name in one workspace is a register nobody can
        #: read. NOTE: because `tenant` is deliberately not a `Meta.fields` member, Django drops this
        #: whole tuple from form validation (`_get_unique_checks()` discards a `unique_together` naming
        #: an excluded field), so `AlertRuleForm.clean_name` re-imposes it or a duplicate 500s the DB.
        unique_together = (("tenant", "name"),)
        indexes = [
            models.Index(fields=["tenant", "category"], name="alertrule_tenant_cat_idx"),
            models.Index(fields=["tenant", "severity"], name="alertrule_tenant_sev_idx"),
            # The third index exists for the `ORDER BY name` above — the I5 lesson applied up front
            # rather than after a review raised it.
            models.Index(fields=["tenant", "name"], name="alertrule_tenant_name_idx"),
        ]

    def __str__(self):
        # `get_metric_key_display`, not `get_metric_display`: the FIELD is `metric_key`, so Django
        # derives the accessor from that name. The shorter name raises AttributeError, and because
        # `__str__` is what every ModelChoiceField calls to label a dropdown option, it takes down
        # any form that selects an AlertRule — not just this model's own pages.
        return f"{self.name} ({self.get_metric_key_display()} {self.get_comparator_display()})"

    def clean(self):
        super().clean()
        if self.is_active and self.warning_threshold is None and self.critical_threshold is None:
            raise ValidationError(
                {"warning_threshold": "An active rule with no bound can never fire. Set a warning or a "
                                      "critical threshold, or mark the rule inactive."})

    # ---- derived (never stored) ----
    @property
    def is_bounded(self):
        return self.warning_threshold is not None or self.critical_threshold is not None

    @property
    def tier_count(self):
        """1 or 2. A one-tier rule is normal, not a half-finished one — never render it as a defect."""
        return sum(1 for t in (self.warning_threshold, self.critical_threshold) if t is not None)

    @property
    def threshold_display(self):
        """Both tiers in one string, an em dash where a tier is unset. Never a `0` for "unset"."""
        warning = "—" if self.warning_threshold is None else str(self.warning_threshold)
        critical = "—" if self.critical_threshold is None else str(self.critical_threshold)
        return f"warning {warning} / critical {critical}"

    def bounds_note(self):
        """The sentence the detail page and the capacity board print under a rule's numbers."""
        if not self.is_bounded:
            return ("No bound is set. This rule cannot fire — it is here as a written intention and "
                    "nothing evaluates it.")
        if self.tier_count == 1:
            return ("One tier set. A single bound is a normal shape — this rule warns at one level, not "
                    "at two.")
        return "Both tiers set."




class AlertEvent(TenantConsistentMixin, models.Model):
    """ONE FIRING, as evidence. A report that a threshold was crossed — written by a person.

    The read side of every alert, and the read side inherits the hand-written-evidence posture of
    `DisposalRecord` (0.8) / `BackupJob` / `RestoreRecord` (0.16): NavERP has no scheduler and no
    evaluator, so each row is *somebody's report*, and the page says "recorded", never "detected".

    **Explicitly absent, and not an oversight:** stack trace, log line, request/response body, raw
    payload, trace id. NavERP collects none of them, so a column for any of them would be a field that is
    permanently empty and permanently implies a capability that does not exist (L52: a permanently-empty
    field is a lie by omission).
    """

    STATE_CHOICES = [
        ("firing", "Firing"),
        ("acknowledged", "Acknowledged"),
        ("resolved", "Resolved"),
        ("expired", "Expired"),
        ("no_data", "No data"),
    ]
    #: Reused from `AlertRule` (the same three strings) rather than declared a fourth time: a firing
    #: states the severity the rule declared, and a separate list here could drift from it.
    SEVERITY_CHOICES = SEVERITY_CHOICES

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="alert_events", db_index=True)
    #: **SET_NULL, copying `BusinessRuleLog.rule`'s exact reasoning** (`BusinessRule.py:77-78`): this row
    #: is the evidence that a rule fired, and evidence does not evaporate because somebody retired the
    #: rule. Compare `AlertRule.service`, which CASCADEs — there the rule *is* the configuration, and
    #: configuration should not outlive the thing it configures.
    rule = models.ForeignKey("core.AlertRule", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="events")
    service = models.ForeignKey("core.ServiceComponent", on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="alert_events")
    #: **Denormalised snapshot**, written by `AlertEventForm.save()` from the service that was chosen —
    #: a person cannot type it and it must not be able to disagree with the FK. This is what lets the
    #: row still read after the component is deleted, which is the whole reason the FK is SET_NULL.
    #: NOT a form field.
    service_label = models.CharField(max_length=150, blank=True)
    #: **Written only by the three POST-only actions** (`alertevent_acknowledge` / `_resolve` / `_recur`).
    #: Not a form field: a create form offering `state` would let a person type "resolved" onto a firing
    #: they are recording, and the register would then hold an event that never resolved.
    state = models.CharField(max_length=12, choices=STATE_CHOICES, default="firing")
    #: **A snapshot, not a join.** The rule's severity may be edited tomorrow and the historical record
    #: must not move with it — so this is a copy, deliberately duplicated from `AlertRule.severity`.
    severity_at_fire = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="warning")
    #: The reading that crossed, as somebody read it off a dashboard. **`NULL` = "not measured"**,
    #: rendered "—" and never `0`: a `0` here would say the metric was zero, which is a different and
    #: usually false claim. (The firing board counts these as `unmeasured_count` — the register's own
    #: honesty score.)
    observed_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    #: The bound that was crossed, **as it stood at the moment of the report**. `NULL` = not recorded.
    threshold_at_fire = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    message = models.CharField(max_length=255)
    detail = models.TextField(blank=True)
    #: Sentry's *count*. **Not a form field** — NavERP cannot count recurrences it did not observe, so
    #: only the `recur` action increments it, and it starts at 1 for the report in hand.
    occurrence_count = models.PositiveIntegerField(default=1)
    first_seen_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    #: The reported moment of the crossing. `default=timezone.now` and **never NULL** — which is what
    #: keeps the ordering below off the MariaDB NULL-sorts-LAST-under-DESC trap that sank `BackupJob`
    #: (the C5 finding in `views/Backup.py`). **If anyone ever makes this nullable, the ordering and the
    #: `alertevent_tenant_fired_idx` index must be revisited together** — L52 rule 2: prefer an invariant
    #: a grep can confirm. System-set, out of the form (L22).
    fired_at = models.DateTimeField(default=timezone.now)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    #: Actor, set from `request.user`. **Never a form field** — otherwise a user can attribute an
    #: acknowledgement to somebody else, and attribution is the act an audit exists for.
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                        blank=True, related_name="+")
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="+")
    resolution_note = models.CharField(max_length=255, blank=True)



    #: Alertmanager *silence* / Datadog *downtime*, as a **RECORDED** mute. Nothing enforces it: there
    #: is no mute engine, so a mute here is a note that somebody wrote "do not page me until then" — and
    #: the list and detail pages label it exactly that way. It IS an editable form field, and that is
    #: deliberate: it is a forward-declared boundary a human types (the 0.16 `BackupJob.retain_until`
    #: precedent), not a system-set stamp, so L22 does not apply to it.
    muted_until = models.DateTimeField(null=True, blank=True)
    #: **The same field shape** as `BackupJob.evidence` / `DisposalRecord.evidence` — the ticket or
    #: runbook reference that makes the claim defensible. Free text on purpose: an evidence reference is
    #: a pointer into a system NavERP does not own.
    evidence = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fired_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "-fired_at"], name="alertevent_tenant_fired_idx"),
            models.Index(fields=["tenant", "state"], name="alertevent_tenant_state_idx"),
            # The third serves both the `?service=` list filter and the per-service board roll-up.
            models.Index(fields=["tenant", "service", "-fired_at"], name="alertevent_tenant_svc_idx"),
        ]

    def __str__(self):
        return f"{self.rule or 'ad-hoc alert'} · {self.get_state_display()}"

    # ---- derived (never stored) ----
    @property
    def observed_value_display(self):
        return "—" if self.observed_value is None else str(self.observed_value)

    @property
    def threshold_at_fire_display(self):
        return "—" if self.threshold_at_fire is None else str(self.threshold_at_fire)

    @property
    def is_open(self):
        """Firing or acknowledged. The two states a person still owes an action on."""
        return self.state in {"firing", "acknowledged"}

    @property
    def is_muted(self):
        """True only while a recorded mute is genuinely in the future — a past mute is not a mute."""
        return self.muted_until is not None and self.muted_until > timezone.now()

    @property
    def age_days(self):
        """Days since the reported crossing. `fired_at` is never NULL, so this is always a number."""
        return (timezone.now() - self.fired_at).days

    @property
    def service_display(self):
        """The snapshot first, so a deleted component still names itself; the live FK second."""
        return self.service_label or (self.service.name if self.service_id else "")

    def measure_note(self):
        """What the page says above the numbers, so `—` is never mistaken for zero."""
        if self.observed_value is None:
            return ("No reading was recorded for this firing. The em dashes below mean 'not measured', "
                    "not zero — NavERP did not take this measurement.")
        if self.threshold_at_fire is None:
            return "A reading was recorded; the bound it crossed was not."
        return "Reading and bound are both as they stood when the report was written."




class Incident(TenantConsistentMixin, models.Model):
    """The comms artifact — and the reason this model is not a second `AlertEvent`.

    Every status-page product's core is *component* + *incident*, and an incident has a **different
    lifecycle and a different audience** from an alert: an alert is a machine-to-human operational
    signal about one threshold, an incident is a human-to-human statement about an outage with a public
    and a private version. NavERP had neither, and one list has to be able to render both an outage and
    a planned window, which is why `STATUS_CHOICES` below is a **union** enum.

    **No FK to `core.SlaRule`** (0.11 owns process escalation) **and none to `EnvironmentInstance`** (0.16
    owns the environment): a maintenance notice is a *communication about a window somebody else owns*.

    **And nothing here is published.** NavERP has no status page, no email, no webhook and no
    subscriber list. `notified_at` is a **recorded** publication, written by a POST-only action whose
    success message says so in those words.
    """

    #: Statuspage's own variant set. **`postmortem` is RESERVED and UNUSED** — the value exists so the
    #: enum is the shape 0.21 needs, but there is no postmortem model, no template and no page behind
    #: it. 0.17 must not grow one: a reserved value is a seam, not a half-built feature.
    INCIDENT_TYPE_CHOICES = [
        ("incident", "Incident"),
        ("scheduled_maintenance", "Scheduled maintenance"),
        ("postmortem", "Postmortem (reserved — 0.21)"),
    ]
    #: A **UNION** of the incident lifecycle and the maintenance lifecycle, because one list renders both
    #: and two parallel enums would force a union at query time. `scheduled` → `completed` is a planned
    #: window; `investigating` → `resolved` is an outage; `monitoring` / `verifying` are the shared
    #: "we think it is fixed" middle that both pass through.
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
    #: Statuspage's, and `impact` is the field that would drive `ServiceComponent.current_status` in a
    #: roll-up. That roll-up is **derived on the board, never written back** (the SCM L37 posture): a
    #: stored component status would freeze one incident's impact forever, so a component that recovered
    #: stayed red. 0.17 computes it and labels it.
    IMPACT_CHOICES = [
        ("none", "No impact"),
        ("minor", "Minor"),
        ("major", "Major"),
        ("critical", "Critical"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="incidents", db_index=True)
    #: SET_NULL — a published notice outlives the catalogue entry it was about, and deleting a component
    #: must not silently delete the statement that it was down. `related_name` differs from the M2M's
    #: below because "the one it is about" and "also affecting" are genuinely different facts.
    service = models.ForeignKey("core.ServiceComponent", on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="primary_incidents")
    #: A **real M2M** — a single outage commonly hits several components, and the auto-generated through
    #: table is not a hand-declared model, so this does not break the four-model cap for 0.17.
    affected_services = models.ManyToManyField("core.ServiceComponent", blank=True,
                                               related_name="affected_incidents")
    #: Lets a firing *become* a comms incident without a second store, and gives the status page a
    #: "why" link. `related_name="+"` — the reverse is the `related_incidents` list the alert's own
    #: detail page shows, built explicitly there rather than as an accessor.
    primary_alert = models.ForeignKey("core.AlertEvent", on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name="+")
    title = models.CharField(max_length=200)
    incident_type = models.CharField(max_length=24, choices=INCIDENT_TYPE_CHOICES, default="incident")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="investigating")
    impact = models.CharField(max_length=12, choices=IMPACT_CHOICES, default="minor")
    #: The public status-page text. 0.17 has no public page, so this is a *draft somebody would publish*.
    public_note = models.TextField(blank=True)
    #: Internal-only. **Never rendered on a public page** — there is no public page to render it on, and
    #: the templates label it internal so nobody copies it into one.
    internal_note = models.TextField(blank=True)
    #: `NULL` = **not tracked**, rendered "not tracked" and never `0%`: a fix with no progress figure is
    #: a different statement from a fix that is 0% done.
    progress_pct = models.PositiveSmallIntegerField(null=True, blank=True,
                                                    validators=[MinValueValidator(0),
                                                                MaxValueValidator(100)])
    started_at = models.DateTimeField(null=True, blank=True)
    #: **Model-stamped, out of the form (L22)** — see `save()` below. Nothing resolves an incident, so a
    #: typed date would be an invented event.
    resolved_at = models.DateTimeField(null=True, blank=True)



    #: The **NOTICE window**, not the change itself: this says "we intend to be doing something between
    #: these two times", and 0.20 owns the change record. Both are editable, and that is the answer to
    #: the L22 objection that applies to `fired_at`/`resolved_at` — these are not system-set, they are a
    #: schedule a person is declaring, and a `scheduled_maintenance` notice that cannot say when its
    #: window opens is not a notice. `TenantModelForm` already installs a `datetime-local` widget with
    #: matching `input_formats`, so nothing needs re-declaring here.
    scheduled_for = models.DateTimeField(null=True, blank=True)
    scheduled_until = models.DateTimeField(null=True, blank=True)
    #: **System-set, out of the form (L22)** — written only by the POST-only `incident_notify` action.
    notified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        #: **`-created_at`, deliberately NOT `-started_at`.** Two reasons, and the second is the
        #: important one: `created_at` is `auto_now_add` and therefore never NULL, so this ordering can
        #: never hit the C5 MariaDB trap (NULLs sort LAST under `DESC`) that sank `BackupJob`; and
        #: insertion order is what "newest notice" means in a register, whereas `started_at` is a
        #: nullable fact about an outage and would make the newest-first window non-deterministic.
        ordering = ["-created_at", "-id"]
        indexes = [
            # The ordering index, then two that serve real list filters.
            models.Index(fields=["tenant", "-created_at"], name="incident_tenant_created_idx"),
            models.Index(fields=["tenant", "status"], name="incident_tenant_status_idx"),
            models.Index(fields=["tenant", "impact"], name="incident_tenant_impact_idx"),
        ]

    def __str__(self):
        return f"{self.title} · {self.get_status_display()}"

    def clean(self):
        super().clean()
        if self.scheduled_for and self.scheduled_until and self.scheduled_until < self.scheduled_for:
            raise ValidationError(
                {"scheduled_until": "The maintenance window cannot end before it starts."})
        if self.incident_type == "scheduled_maintenance" and not self.scheduled_for:
            raise ValidationError(
                {"scheduled_for": "A maintenance notice must say when the window opens. This is the "
                                  "notice, not the change record (0.20 owns that)."})

    def save(self, *args, **kwargs):
        # `resolved_at` is system-set (L22) and nothing performs the resolution, so it is DERIVED from
        # the recorded status rather than typed anywhere. One-way on purpose: moving back to an
        # in-progress status does not erase the fact that this incident was once resolved — the same
        # reasoning `LegalHold` applies to a release date, and it is enforced on the form, the admin and
        # the seeder alike because all three go through `save()`.
        if self.status in {"resolved", "completed"} and self.resolved_at is None:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)

    # ---- derived (never stored) ----
    @property
    def progress_display(self):
        """`None` renders "not tracked", never 0% — see the field's own comment."""
        return "not tracked" if self.progress_pct is None else f"{self.progress_pct}%"

    @property
    def is_open(self):
        """The two terminal values of the union enum both close it; everything else is live."""
        return self.status not in {"resolved", "completed"}

    @property
    def is_scheduled(self):
        return self.incident_type == "scheduled_maintenance" or self.status == "scheduled"

    @property
    def window_valid(self):
        """True when both window ends are present and in order. A one-ended window is not valid."""
        return (self.scheduled_for is not None and self.scheduled_until is not None
                and self.scheduled_until >= self.scheduled_for)

    @property
    def notify_display(self):
        return "—" if self.notified_at is None else self.notified_at.strftime("%b %d, %Y %H:%M")


