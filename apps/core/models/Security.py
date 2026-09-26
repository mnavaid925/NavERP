"""0.18 — Threat Protection & Security Operations.

**The posture, stated once and obeyed by every page in this file.** A row here is
**a report that something was observed, or a policy somebody wrote down.** NavERP has
**no IDS/IPS agent, no packet capture, no anomaly engine, no vulnerability scanner, no
dependency/CI scanner, no WAF, no CAPTCHA library, no SIEM client, no log pipeline, no
scheduler and no API gateway** anywhere in this repository. Nothing in this module
detects, blocks, remediates or notifies on its own:

* an `IpAccessRule` is **written down, not enforced** — no edge evaluates it, so
  `action="block"` records the operator's intent, not a block that happened;
* a `SecurityThreat` is a **declared finding** — nothing correlates logins, probes the
  network or watches a ruleset to produce it;
* a `VulnerabilityFinding` is a **hand-entered published advisory** — NavERP runs no
  scan, so `scan_frequency` is a *declared cadence*, not a schedule;
* a `SecurityIncident` is a **response record with a legal clock displayed on it** — the
  72-hour Art. 33 deadline is computed and shown, and NavERP files nothing with any
  authority.

This is the L52 discipline the whole repo runs on: a permanently-empty column is a lie
by omission, so every field here is either written by an operator or by an explicit POST
action, and the seeders create **zero** `SecurityThreat`, `SecurityIncident` and
`IpAccessRule` rows — seeding one would fabricate a breach that never happened.

**Ownership (L36 — what this file deliberately does NOT re-declare).**
`core.RateLimitPolicy` (0.13, `apps/core/models/Integration.py`) owns the limit itself —
the number, the window and the credential scope. 0.18 **extends it by FK** and never
edits that file: a limit is a *configuration*, and the observation that it was crossed
is a *fact about the world*, so it belongs here, on `SecurityThreat.rate_limit_policy`.
`core.AlertRule` / `AlertEvent` / `Incident` / `ServiceComponent` (0.17) own alerting and
incident communication. `AlertRule.CATEGORY_CHOICES` already carries `("security",
"Security")` and a committed test — `test_monitoring_security_is_the_018_seam` — names
that value as **the** 0.18 seam, so this file adds **no column to any 0.17 model** and
declares **no** `SecurityAlert` table, **no** second incident lifecycle and **no** second
board. `core.AuditLog` is *who changed which row*; a security finding is *what an adversary
did* — for that reason there is no second audit log and no second tamper-evidence
mechanism here (`procurement.AuditSeal`, 6.17, already chains SHA-256 over a range of
`AuditLog` ids; the incident detail page points at it in prose rather than re-implementing
it). `accounts` owns identity, authentication and login-attempt recording; 0.18 declares no
`accounts` row, and the brute-force board **reads** those rows rather than duplicating
them. `procurement` 6.17 owns *supplier* compliance — 0.18 owns *platform* security, so
the two compliance spines stay separate.

**Known, documented limitation — do not try to close it here.** `TenantConsistentMixin`
walks `ForeignKey`/`OneToOneField` only, so `SecurityIncident.affected_services` (an
**M2M**) is not tenant-checked on the **admin** path. `TenantModelForm` *does* narrow
M2M querysets, so the form path is covered when `tenant is not None`. Same posture 0.16
and 0.17 recorded for **C7 (escalated, not fixed)**. Do **not** change
`TenantModelForm`; it would break committed tests in three other apps.
"""
from datetime import timedelta
import ipaddress

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone

from apps.core.models._base import *  # noqa: F401,F403
# The tenant-consistency model edge (I2), defined in `Backup.py` and imported one-way by every
# module since. `Backup.py` does not import this module, so the graph stays cycle-free.
from apps.core.models.Backup import TenantConsistentMixin
# Reuse-by-REFERENCE (L36) — assign the object, never rebuild the tuple. `SEVERITY_CHOICES` is
# literally 0.17's list, so a severity an operator picks on a threat is the same severity they
# would pick on the alert that fired it. The tests assert `is` identity: a pasted copy that
# happens to be equal today forks silently the first time 0.17 adds a value.
from apps.core.models.Integration import RateLimitPolicy, SyncSchedule
from apps.core.models.Monitoring import AlertEvent, AlertRule, Incident, ServiceComponent

#: Reuse-by-reference: 0.17's firing severity, as a module constant so a model can expose it
#: without each one re-deriving it.
SEVERITY_CHOICES = AlertRule.SEVERITY_CHOICES
#: Reuse-by-reference: 0.13's schedule vocabulary, borrowed as a *declared* scan cadence.
#: 0.20 owns the scheduler that would actually read it.
SCAN_FREQUENCY_CHOICES = SyncSchedule.FREQUENCY_CHOICES

#: GDPR Art. 33(1): a controller notifies "not later than 72 hours after having become aware
#: of it". This is a **recorded and displayed** deadline, never an acted-on one — NavERP runs
#: no scheduler and files nothing with any authority. It is the single most useful thing on
#: the incident page precisely because nothing will chase it.
NOTIFICATION_WINDOW_HOURS = 72

#: A remediation SLA by CVSS band. A **policy somebody writes down**; no scheduler reads it
#: (the `SyncSchedule.frequency` / `AlertRule.frequency` / `BackupJob.frequency` precedent —
#: 0.20 owns the scheduler). Days from `first_seen_at` to `due_on` when nobody overrides.


REMEDIATION_SLA_DAYS = {
    "none": None,
    "low": 180,
    "medium": 90,
    "high": 30,
    "critical": 7,
}


def validate_ip_or_cidr(value):
    """Accept one bare IPv4/IPv6 address, or one address plus a prefix length.

    A field-level validator, so it protects the **admin** path too — which is the whole
    reason it is not just a form `clean()`. `CharField` rather than
    `GenericIPAddressField` because the latter cannot hold `203.0.113.0/24`, and every
    real allow/deny list is full of CIDR blocks; a bare address is read as a host route
    (`/32` or `/128`).
    """
    text = (value or "").strip()
    if not text:
        raise ValidationError("An address or CIDR block is required.")
    try:
        ipaddress.ip_network(text, strict=False)
    except ValueError as exc:
        raise ValidationError(
            "%(value)s is not an IP address or CIDR block (e.g. 203.0.113.7 or "
            "203.0.113.0/24) - %(detail)s",
            code="invalid",
            params={"value": text, "detail": exc},
        )


class IpAccessRule(TenantConsistentMixin, models.Model):
    """An address that is allowed, or is not. **Written down; nothing enforces it.**

    The allow/deny list every WAF and every API gateway has, minus the gateway. This is
    the operator's *intent*, recorded: no edge in this repository reads it, so
    `action="block"` describes what should happen to a packet NavERP never sees. That is
    the honest shape, and `action` defaults to `log` for the same reason `AlertEvent` has
    no payload column — a rule that claims to block when nothing blocks is a lie the
    operator reads back as a control that works.
    """

    DIRECTION_CHOICES = [
        ("allow", "Allow"),
        ("deny", "Deny"),
    ]
    #: Cloudflare's IP Access action names, verbatim, so a rule imported from a real
    #: console keeps its meaning. `log` is the **default** — see the class docstring.
    ACTION_CHOICES = [
        ("allow", "Allow"),
        ("block", "Block"),
        ("challenge", "Challenge"),
        ("managed_challenge", "Managed challenge"),
        ("non_interactive_challenge", "Non-interactive challenge"),
        ("interactive_challenge", "Interactive challenge"),
        ("log", "Log only"),
    ]
    #: Mirrors `RateLimitPolicy.credential`'s nullable scoping, so the two read the same way.
    SCOPE_CHOICES = [
        ("workspace", "Whole workspace"),
        ("service", "One service"),
        ("credential", "One API credential"),
    ]
    #: Where the rule came from. **Nothing in NavERP ever chooses this automatically** —
    #: `manual` is the only value a view or the seeder may write. `threat` and
    #: `rate_limit` are recorded by an operator saying "this came out of that finding".
    SOURCE_CHOICES = [
        ("manual", "Entered by hand"),
        ("threat", "From a recorded threat"),
        ("rate_limit", "From a rate-limit finding"),
        ("import", "Imported from elsewhere"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="ip_access_rules", db_index=True)
    cidr = models.CharField(max_length=43, validators=[validate_ip_or_cidr],
                            help_text="An address or CIDR block, e.g. 203.0.113.7 or 203.0.113.0/24.")
    direction = models.CharField(max_length=5, choices=DIRECTION_CHOICES)
    action = models.CharField(max_length=28, choices=ACTION_CHOICES, default="log")
    service = models.ForeignKey("core.ServiceComponent", on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="+")
    credential = models.ForeignKey("core.ApiCredential", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="+")
    #: The limit this rule was written alongside. The policy stays 0.13's; this is the seam.
    rate_limit_policy = models.ForeignKey("core.RateLimitPolicy", on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name="ip_access_rules")
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default="workspace")
    #: Required by `clean()`, not by the column: an unexplained allow/deny is the first
    #: thing an auditor asks about.
    reason = models.TextField(blank=True)
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default="manual")
    expires_at = models.DateTimeField(null=True, blank=True,
                                      help_text="Optional. An allow-list entry with a real expiry is a temporary one.")
    is_active = models.BooleanField(default=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="+")
    #: Snapshot, so the page still names who added the rule after the account is deleted.
    added_by_label = models.CharField(max_length=150, blank=True, editable=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        #: `created_at` is never NULL, so the C5 MariaDB NULL-sorts-last trap cannot apply.
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "cidr", "direction"],
                                    name="core_iprule_tenant_cidr_dir_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "-created_at"], name="iprule_tenant_created_idx"),
            models.Index(fields=["tenant", "direction"], name="iprule_tenant_dir_idx"),
            models.Index(fields=["tenant", "expires_at"], name="iprule_tenant_expires_idx"),
        ]

    def __str__(self):
        return "%s %s" % (self.get_direction_display(), self.cidr)

    @property
    def action_display(self):
        """``Would <action>`` — the wording that keeps the record honest.

        A bare ``"Block"`` badge on a list whose own page says nothing enforces it reads
        as a working control. Prefixing the word is the cheapest possible way to stop a
        reader mistaking the intent for the effect, and it is why `log` is the default.
        """
        return "Would %s" % (self.get_action_display().lower(),)

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    def clean(self):
        super().clean()
        if not (self.reason or "").strip():
            raise ValidationError({"reason": "A reason is required - an unexplained "
                                              "allow/deny rule is the first thing an auditor asks about."})
        if self.scope == "service" and self.service_id is None:
            raise ValidationError({"service": "Scope 'One service' requires a service."})
        if self.scope == "credential" and self.credential_id is None:
            raise ValidationError({"credential": "Scope 'One API credential' requires a credential."})


class SecurityThreat(TenantConsistentMixin, models.Model):
    """A threat, as a **declared finding** — nothing in NavERP detects one.

    The centre of gravity of 0.18, and the half of the rate-limit story that
    `RateLimitPolicy` deliberately left open: a limit nobody has ever watched being
    crossed is a number on a page. This is the record that somebody noticed.

    It correlates to 0.17 by FK (`alert_event`) and to 0.13 by FK
    (`rate_limit_policy`) rather than growing either. The fields 0.17's `AlertEvent`
    cannot hold — `mitre_technique`, a source address, an occurrence count, the WAF rule
    that fired — live here precisely because `Monitoring.py` refuses to widen its own
    models, and because a security finding is a different *kind* of fact from a threshold
    crossing even when the same threshold fired.
    """

    #: A union enum across bullets 1, 4 and 5 — one field, because an operator recording
    #: "this address was crawling the API" should not have to pick a sub-module first.
    THREAT_TYPE_CHOICES = [
        ("brute_force", "Brute force"),
        ("credential_stuffing", "Credential stuffing"),
        ("anomalous_login", "Anomalous login"),
        ("privilege_escalation", "Privilege escalation"),
        ("suspicious_api_activity", "Suspicious API activity"),
        ("data_exfiltration", "Data exfiltration attempt"),
        ("malware", "Malware"),
        ("phishing", "Phishing"),
        ("waf_rule_match", "WAF rule match"),
        ("rate_limit_exceeded", "Rate limit exceeded"),
        ("bot_abuse", "Bot or automated abuse"),
        ("other", "Other"),
    ]
    #: Defender for Cloud Apps' acknowledge / resolve / suppress / dismiss shape, mapped to
    #: a lifecycle this repo can actually hold and display.
    STATUS_CHOICES = [
        ("new", "New"),
        ("triaged", "Triaged"),
        ("investigating", "Investigating"),
        ("contained", "Contained"),
        ("resolved", "Resolved"),
        ("false_positive", "False positive"),
        ("ignored", "Ignored"),
    ]
    #: A **recorded posture**, not an enforcement — no ruleset exists here to carry the value.
    WAF_ACTION_CHOICES = [
        ("none", "None"),
        ("log", "Log"),
        ("block", "Block"),
        ("challenge", "Challenge"),
        ("managed_challenge", "Managed challenge"),
        ("interactive_challenge", "Interactive challenge"),
    ]
    #: The bot/abuse mitigation posture: which challenge, if any, a surface is behind.
    #: Cloudflare Turnstile's three modes and Imperva/F5's scoring vocabulary, flattened.
    DEFENSE_MODE_CHOICES = [
        ("none", "None"),
        ("captcha", "CAPTCHA"),
        ("challenge", "Challenge"),
        ("rate_limit", "Rate limit"),
        ("block", "Block"),
        ("waf", "WAF"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="security_threats", db_index=True)
    #: The 0.17 seam: a finding that raised an alert points at the firing, so the threat
    #: board and `core:firing_board` are two views of one event rather than two events.
    alert_event = models.ForeignKey("core.AlertEvent", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="+")
    #: The rate-limit seam. The policy is 0.13's and untouched; this records that the limit
    #: was crossed. A row here says *a limit was exceeded* — no middleware counts requests
    #: in this repo, so the count is one an operator read off something else.
    rate_limit_policy = models.ForeignKey("core.RateLimitPolicy", on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name="security_threats")
    service = models.ForeignKey("core.ServiceComponent", on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="+")
    #: Snapshot of the service name, so the finding still names what was hit after the
    #: component is retired. Written by `SecurityThreatForm.save()` only when a service
    #: IS chosen — clearing the service is a legitimate correction.
    service_label = models.CharField(max_length=150, blank=True, editable=False)
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="+")
    target_credential = models.ForeignKey("core.ApiCredential", on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name="+")
    title = models.CharField(max_length=200)
    threat_type = models.CharField(max_length=30, choices=THREAT_TYPE_CHOICES, default="other")
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="warning")
    #: Free text on purpose (e.g. ``T1110.001``). A taxonomy table would go stale against
    #: MITRE's own release cycle, and the technique is a *label* here, never a filter that
    #: must join to something.
    mitre_technique = models.CharField(max_length=20, blank=True)
    mitre_tactic = models.CharField(max_length=50, blank=True)
    rule_reference = models.CharField(max_length=120, blank=True)
    waf_action = models.CharField(max_length=30, choices=WAF_ACTION_CHOICES, blank=True, default="")
    defense_mode = models.CharField(max_length=20, choices=DEFENSE_MODE_CHOICES, blank=True, default="")
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    detected_at = models.DateTimeField(default=timezone.now)
    occurrence_count = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    summary = models.TextField(blank=True)
    detail = models.TextField(blank=True)
    evidence = models.TextField(blank=True)
    status = models.CharField(max_length=14, choices=STATUS_CHOICES, default="new")
    #: The allow/deny rule somebody wrote in response — the one place 0.18 records a
    #: mitigation that another 0.18 model owns.
    mitigated_by = models.ForeignKey("core.IpAccessRule", on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="mitigated_threats")
    #: Stamped by the POST-only `_resolve` action, never by the form (L22).
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="+")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        #: **No `updated_at`** — a finding is a point-in-time report; its history lives in
        #: `core.AuditLog` and in the lifecycle stamps, not in a column that moves on edit.
        ordering = ["-detected_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "-detected_at"], name="secthreat_tenant_detected_idx"),
            models.Index(fields=["tenant", "status"], name="secthreat_tenant_status_idx"),
            models.Index(fields=["tenant", "threat_type"], name="secthreat_tenant_type_idx"),
            models.Index(fields=["tenant", "source_ip"], name="secthreat_tenant_source_idx"),
        ]

    def __str__(self):
        return "%s - %s" % (self.title, self.get_status_display())

    @property
    def is_open(self):
        """The board's "live" test. `false_positive` and `ignored` are decisions, not open items."""
        return self.status not in ("resolved", "false_positive", "ignored")

    def clean(self):
        super().clean()
        if self.status == "resolved" and self.resolved_at is None:
            raise ValidationError({"resolved_at": "A resolved threat needs the moment it was resolved."})
        if self.status == "resolved" and self.resolved_by_id is None:
            raise ValidationError({"resolved_by": "A resolved threat needs who resolved it."})
        if self.resolved_at and self.status != "resolved":
            raise ValidationError({"status": "This threat is stamped resolved but its status says "
                                             "%(status)s.", "params": {"status": self.get_status_display()}})
        if self.threat_type == "rate_limit_exceeded" and self.rate_limit_policy_id is None:
            raise ValidationError({"rate_limit_policy": "A rate-limit finding must name the limit that "
                                                        "was crossed."})
        if self.source_ip:
            try:
                ipaddress.ip_address(self.source_ip)
            except ValueError:
                raise ValidationError({"source_ip": "%(ip)s is not a valid IP address.",
                                       "params": {"ip": self.source_ip}})


class VulnerabilityFinding(TenantConsistentMixin, models.Model):
    """A known weakness, and what was done about it. **Hand-entered; NavERP scans nothing.**

    The register every scanner's console produces, minus the scanner. `evidence` says
    where the advisory came from, and the honest seeded row carries a real published
    advisory id with `evidence` stating that NavERP ran no scanner — the same honesty
    `DisposalRecord` (0.8) is seeded for, and for the same reason: a register with nothing
    in it renders as "clean", which is a claim nobody in this repository can support.

    **This `severity` is a CVSS band and is deliberately NOT `AlertRule.SEVERITY_CHOICES`.**
    They are different facts — how badly a system is scored versus how loudly a threshold
    fired — and the same reasoning that let `AlertRule.metric_key` overlap
    `HealthMetric.METRIC_CHOICES` by string apply: a similar word is not the same concept.
    This is the one place a second severity list is correct, and it is called out here so
    the next agent does not "fix" the duplication by pointing this at the alert vocabulary.
    """

    FINDING_SOURCE_CHOICES = [
        ("dependency", "Software dependency"),
        ("operating_system", "Operating system"),
        ("application", "Application"),
        ("configuration", "Configuration"),
        ("third_party", "Third-party service"),
        ("misconfiguration", "Misconfiguration"),
    ]
    #: Snyk's `fixAvailable` made explicit. "No fix exists" and "we have not got round to
    #: it" must never render as the same word; NULL is the third state, "nobody determined it".
    FIX_AVAILABLE_CHOICES = [
        ("yes", "Yes"),
        ("no", "No"),
        ("partial", "Partial"),
    ]
    #: Every terminal value is a **decision somebody made**, not an absence of data.
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "Remediation in progress"),
        ("fixed", "Fixed"),
        ("risk_accepted", "Risk accepted"),
        ("false_positive", "False positive"),
        ("not_applicable", "Not applicable"),
    ]
    #: The CVSS band. See the class docstring on why this is not the alert severity list.
    SEVERITY_BAND_CHOICES = [
        ("none", "None"),
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="vulnerability_findings", db_index=True)
    title = models.CharField(max_length=200)
    advisory_id = models.CharField(max_length=40, db_index=True)
    finding_source = models.CharField(max_length=20, choices=FINDING_SOURCE_CHOICES)
    #: Nullable on purpose: a vulnerable *dependency* has no service, and forcing a choice
    #: would push the operator to invent one.
    component = models.ForeignKey("core.ServiceComponent", on_delete=models.SET_NULL, null=True,
                                  blank=True, related_name="+")
    package_name = models.CharField(max_length=150, blank=True)
    installed_version = models.CharField(max_length=60, blank=True)
    severity = models.CharField(max_length=8, choices=SEVERITY_BAND_CHOICES, default="medium")
    cvss_score = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                     validators=[MinValueValidator(0), MaxValueValidator(10)])
    epss_score = models.DecimalField(max_digits=6, decimal_places=5, null=True, blank=True,
                                     validators=[MinValueValidator(0), MaxValueValidator(1)])
    fix_available = models.CharField(max_length=8, choices=FIX_AVAILABLE_CHOICES,
                                     null=True, blank=True, default=None)
    fixed_in_version = models.CharField(max_length=60, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    accepted_reason = models.TextField(blank=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="+")
    #: Back-filled by the form, once, when `accepted_by` is first set — a later edit must not
    #: rewrite when the risk was accepted.
    accepted_at = models.DateTimeField(null=True, blank=True)
    #: **Never defaulted to today.** NULL means "no remediation deadline has been set", which
    #: is a different statement from "due today" and renders as an em dash.
    due_on = models.DateField(null=True, blank=True)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    remediation_note = models.TextField(blank=True)
    evidence = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    #: A **declared** cadence. Nothing in NavERP runs a scan, and the help text says so.
    scan_frequency = models.CharField(max_length=8, choices=SCAN_FREQUENCY_CHOICES, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-first_seen_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="vulfind_tenant_status_idx"),
            models.Index(fields=["tenant", "severity"], name="vulfind_tenant_severity_idx"),
            models.Index(fields=["tenant", "advisory_id"], name="vulfind_tenant_advisory_idx"),
            models.Index(fields=["tenant", "-first_seen_at"], name="vulfind_tenant_firstseen_idx"),
        ]

    def __str__(self):
        return "%s - %s" % (self.advisory_id, self.title)

    @property
    def is_open(self):
        """Terminal statuses are decisions. `open` and `in_progress` are the live set."""
        return self.status in ("open", "in_progress")

    @property
    def days_overdue(self):
        """None when there is no deadline set. Never 0 for "not yet due"."""
        if not self.due_on:
            return None
        return (timezone.now().date() - self.due_on).days

    def suggested_due_on(self):
        """The `REMEDIATION_SLA_DAYS` deadline for this finding's band, or None.

        Displayed on the page as *what the written policy would say* — the column itself is
        only ever set by a person, because a defaulted deadline is a deadline nobody chose.
        """
        days = REMEDIATION_SLA_DAYS.get(self.severity)
        if days is None:
            return None
        return self.first_seen_at.date() + timedelta(days=days)

    def clean(self):
        super().clean()
        if self.status == "risk_accepted":
            # An accepted risk with no stated reason is an unowned risk. The Tenable
            # exception discipline, kept on the finding rather than in a second table.
            if not (self.accepted_reason or "").strip():
                raise ValidationError({"accepted_reason": "An accepted risk needs a stated reason."})
            if self.accepted_by_id is None:
                raise ValidationError({"accepted_by": "An accepted risk needs an owner."})
        if self.status == "fixed" and self.fix_available == "no":
            # A finding with no fix is not a finding that is fixed.
            raise ValidationError({"fix_available": "This advisory has no fix available, so it "
                                                    "cannot be marked fixed."})
        if (self.fixed_in_version or "").strip() and self.fix_available == "no":
            raise ValidationError({"fixed_in_version": "No fix is available for this advisory, so "
                                                       "there is no version it is fixed in."})
        if self.last_seen_at and self.first_seen_at and self.last_seen_at < self.first_seen_at:
            raise ValidationError({"last_seen_at": "Last seen cannot be earlier than first seen."})
        if self.due_on and self.first_seen_at and self.due_on < self.first_seen_at.date():
            raise ValidationError({"due_on": "A remediation deadline cannot precede the date the "
                                             "finding was first seen."})


class SecurityIncident(TenantConsistentMixin, models.Model):
    """The response, with a legal clock displayed on it. **Nothing here files anything.**

    The NIST SP 800-61r2 lifecycle, and the GDPR Article 33/34 record that goes with it.
    Its reason for existing is `regulatory_deadline`: a derived, always-visible 72-hour
    clock from the moment the organisation became aware, which is the number an
    organisation is actually judged on and the one nobody in a spreadsheet notices moving.

    `status` is **deliberately not** 0.17's `Incident.status` union. `core.Incident` is the
    availability/comms artifact and its statuses include `scheduled` and `monitoring`,
    which a breach never passes through; forcing this row into that enum would be the L36
    bug pointed the other way. The two rows are joined by `incident` — one incident with two
    faces, not two incidents.

    **No `save()` override, no hash, no seal column and no FK to `core.AuditLog`.**
    `procurement.AuditSeal` (6.17) already chains SHA-256 over a range of `AuditLog` ids;
    a second tamper-evidence mechanism is a parallel schema for the same concept.
    `forensic_log` is a **narrative** — what was found, what was preserved, what remains to
    be collected — and the detail page points at procurement's seal register in prose.
    """

    INCIDENT_CLASS_CHOICES = [
        ("security_incident", "Security incident"),
        ("data_breach", "Personal data breach"),
        ("unauthorized_access", "Unauthorised access"),
        ("malware", "Malware"),
        ("phishing", "Phishing"),
        ("insider_threat", "Insider threat"),
        ("policy_violation", "Policy violation"),
        ("denial_of_service", "Denial of service"),
        ("other", "Other"),
    ]
    #: NIST SP 800-61r2. Not 0.17's union — see the class docstring.
    STATUS_CHOICES = [
        ("detected", "Detected"),
        ("triage", "Triage"),
        ("investigating", "Investigating"),
        ("contained", "Contained"),
        ("eradicated", "Eradicated"),
        ("recovered", "Recovered"),
        ("closed", "Closed"),
        ("false_positive", "False positive"),
    ]
    #: Art. 34(3)'s three exemptions, named as the Article names them, because the
    #: exemption is the defensible part of the record and an auditor asks for it first.
    SUBJECT_EXEMPTION_CHOICES = [
        ("none", "No exemption claimed"),
        ("technical_measures", "Technical measures protect the rights of data subjects"),
        ("subsequent_measures", "Subsequent measures undo the adverse consequences"),
        ("disproportionate_effort", "Disproportionate effort"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="security_incidents", db_index=True)
    #: The 0.17 seam: a breach is also an availability event, so one incident can carry
    #: both faces rather than being recorded twice under two lifecycles.
    incident = models.ForeignKey("core.Incident", on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="security_incidents")
    primary_threat = models.ForeignKey("core.SecurityThreat", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="security_incidents")
    title = models.CharField(max_length=200)
    incident_class = models.CharField(max_length=20, choices=INCIDENT_CLASS_CHOICES,
                                      default="security_incident")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="detected")
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="warning")
    #: The anchor for every legal clock on this row. A **form field**, because awareness
    #: genuinely is a human judgement and a discovered date that silently moves is worse
    #: than one an operator types.
    discovered_at = models.DateTimeField(default=timezone.now)
    #: The four lifecycle stamps below are system-set, one writer each (the POST-only
    #: `_contain` / `_eradicate` / `_recover` / `_close` actions), never form fields (L22).
    contained_at = models.DateTimeField(null=True, blank=True)
    eradicated_at = models.DateTimeField(null=True, blank=True)
    recovered_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    #: NULL = "nobody has decided yet" — a third and very common state, and exactly the
    #: situation the 72-hour clock exists to pressure. It is why the form renders a
    #: three-state `NullBooleanField` rather than a checkbox.
    is_notifiable = models.BooleanField(null=True, blank=True)
    notifiable_reason = models.TextField(blank=True)
    authority_notified_at = models.DateTimeField(null=True, blank=True)
    #: The human-typed filing reference. A **form field**: the act of typing it is the
    #: operator asserting it happened, which is the only place that claim is recorded.
    authority_reference = models.CharField(max_length=150, blank=True)
    subjects_notified = models.BooleanField(null=True, blank=True)
    subjects_notified_at = models.DateTimeField(null=True, blank=True)
    subject_exemption = models.CharField(max_length=28, choices=SUBJECT_EXEMPTION_CHOICES,
                                         default="none")
    #: Art. 33(3)(a) asks for **approximate numbers**, so both are nullable — an unknown
    #: count is not a zero count, and a zero here reads as "nobody was affected".
    data_subjects_affected = models.PositiveIntegerField(null=True, blank=True,
                                                        validators=[MinValueValidator(1)])
    records_affected = models.PositiveIntegerField(null=True, blank=True,
                                                  validators=[MinValueValidator(1)])
    #: Art. 33(3)(b).
    dpo_contact = models.CharField(max_length=200, blank=True)
    #: Art. 33(3)(c).
    likely_consequences = models.TextField(blank=True)
    #: Art. 33(3)(d).
    measures_taken = models.TextField(blank=True)
    measures_proposed = models.TextField(blank=True)
    #: The forensic **narrative**: what was found, what was preserved, what remains to be
    #: collected, in what order, by whom. Not a log pipeline — NavERP acquires nothing.
    forensic_log = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    lessons_learned = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                              blank=True, related_name="+")
    #: Snapshot of the owner's name, so the record still names a responder afterwards.
    owner_label = models.CharField(max_length=150, blank=True, editable=False)
    #: A real M2M. The auto-generated through table is not a hand-declared model, so this
    #: does not break the four-model cap. See the file docstring for the admin-path caveat.
    affected_services = models.ManyToManyField("core.ServiceComponent", blank=True,
                                               related_name="security_incidents")
    evidence = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-discovered_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "-discovered_at"], name="secinc_tenant_discovered_idx"),
            models.Index(fields=["tenant", "status"], name="secinc_tenant_status_idx"),
            models.Index(fields=["tenant", "incident_class"], name="secinc_tenant_class_idx"),
            models.Index(fields=["tenant", "is_notifiable"], name="secinc_tenant_notifiable_idx"),
        ]

    def __str__(self):
        return "%s - %s" % (self.title, self.get_status_display())

    @property
    def regulatory_deadline(self):
        """Art. 33(1)'s 72 hours, derived — **a property, never a column**.

        A stored deadline can drift from its anchor the moment somebody edits
        `discovered_at`; a property cannot. Displayed, never acted on: NavERP runs no
        scheduler and files nothing with any authority.
        """
        if not self.discovered_at:
            return None
        return self.discovered_at + timedelta(hours=NOTIFICATION_WINDOW_HOURS)

    @property
    def hours_remaining(self):
        """Negative once the window has passed. None when there is no anchor."""
        deadline = self.regulatory_deadline
        if deadline is None:
            return None
        return (deadline - timezone.now()).total_seconds() / 3600.0

    @property
    def is_overdue(self):
        hours = self.hours_remaining
        return hours is not None and hours < 0

    @property
    def deadline_display(self):
        """An em dash when there is nothing to show — never "due today" for a NULL anchor."""
        deadline = self.regulatory_deadline
        if deadline is None:
            return "—"
        return deadline.strftime("%Y-%m-%d %H:%M")

    @property
    def is_open(self):
        return self.status not in ("closed", "false_positive")

    def clean(self):
        super().clean()
        # You may not close a breach without having decided whether it is notifiable.
        if self.status == "closed" and self.is_notifiable is None:
            raise ValidationError({"is_notifiable": "A closed incident needs a decision on whether "
                                                    "it is notifiable to the supervisory authority."})
        if self.authority_notified_at and self.is_notifiable is not True:
            raise ValidationError({"is_notifiable": "An authority-notification stamp is recorded, so "
                                                    "this incident must be marked notifiable."})
        # The exemption is the reason you did NOT notify, so it cannot coexist with a
        # notification, and a recorded "no" needs a stated reason.
        if self.subjects_notified is True and self.subject_exemption != "none":
            raise ValidationError({"subject_exemption": "Data subjects are recorded as notified, so no "
                                                       "Art. 34(3) exemption can be claimed."})
        if self.subjects_notified is False and self.subject_exemption == "none":
            raise ValidationError({"subject_exemption": "Recording that data subjects were not "
                                                       "notified requires a stated exemption."})
