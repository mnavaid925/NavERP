"""core — 0.18 views (threat protection & security operations).

**The posture every view here takes, inherited from 0.17 (`apps/core/views/Monitoring.py`)
and 0.16 (`apps/core/views/Backup.py`):**

NavERP has **no IDS/IPS agent, no packet capture, no anomaly engine, no vulnerability
scanner, no dependency/CI scanner, no WAF, no CAPTCHA library, no SIEM client, no log
pipeline, no scheduler, no API gateway, no lockout and no mailer** anywhere in this
repository. Nothing in this module performs the act it describes: a `SecurityThreat` is a
report a human wrote, an `IpAccessRule` is a policy nobody enforces, a
`VulnerabilityFinding` is a hand-entered published advisory, and a `SecurityIncident` is a
response record with a legal clock *displayed* on it. The pages say so in `notes`
(`SECURITY_NOTES`) and every success message says **"recorded"** — never "detected",
"blocked", "scanned", "enforced", "shipped" or "notified".

**The zero rule (0.8), which is the whole point of every board here.** The seeder creates
**zero** `SecurityThreat`, `SecurityIncident` and `IpAccessRule` rows on purpose: a
fabricated "we detected a brute-force attack" or "we blocked an address" is a recorded
event that did not happen (L52), and on a security register that lie is worse than an
empty one. So a fresh seed leaves these boards empty and the templates say **"No threats
have been recorded"** — never `0` in a green badge, because a quiet board here means
*nobody has written anything down*, not *nothing is happening*.

**Every delete and every action is POST-only with `@require_POST` ABOVE the role gate**
(the 0.7 / 0.17 pattern): decorators apply bottom-up, so the outermost runs first. With
the role gate outermost a member's GET would be answered 403 before the method check ran,
and the house standard is 405 for a wrong method regardless of role.

**Every action's guard lives in the VIEW, not only in a hidden button**, so a hand-made
POST cannot reach it and the audit row is not written either — the `backup_job_verify`
rule. `AuditLog.action` is `varchar(10)`, so the verb goes in `changes` (the
`views/Localization.py` pattern).

**Ownership (L36).** `core.RateLimitPolicy` (0.13) owns the limit itself and is extended
by FK only; there is no `core:rate_limit_detail` route, so anything linking a policy uses
`core:rate_limit_edit` with the pk. `AlertRule` / `AlertEvent` / `Incident` /
`ServiceComponent` (0.17) own alerting and incident communication, and are read/extended
by FK — never re-declared. `accounts.LoginAttempt` is **read** by `brute_force_board` and
never written by 0.18.
"""
from datetime import timedelta

from django.contrib import messages
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.utils import write_audit_log
from apps.core.models import (
    NOTIFICATION_WINDOW_HOURS,
    REMEDIATION_SLA_DAYS,
    AlertRule,
    IpAccessRule,
    SecurityIncident,
    SecurityThreat,
    ServiceComponent,
    VulnerabilityFinding,
)
from apps.core.forms import (
    IpAccessRuleForm,
    SecurityIncidentForm,
    SecurityThreatForm,
    VulnerabilityFindingForm,
)


#: The honest-limit lines the overview, the five boards and all sixteen register pages print
#: VERBATIM. A module-level constant so a page and its board cannot disagree about what this
#: application can and cannot do — the same reason 0.16 has `BACKUP_NOTES` and 0.17 has
#: `MONITORING_NOTES`. No view invents its own prose.
SECURITY_NOTES = [
    "This is a register of claims a person wrote, not a security system. NavERP has no IDS/IPS "
    "agent, no packet capture, no anomaly engine, no vulnerability scanner, no dependency/CI "
    "scanner, no WAF, no CAPTCHA library, no SIEM client, no log pipeline, no scheduler, no API "
    "gateway and no lockout - so nothing here detects, blocks, scans, enforces, ships or "
    "notifies anything. A row is a record of what somebody reported.",
    "A threat is a declared finding, an allow/deny rule is a policy nobody evaluates, a "
    "vulnerability finding is a published advisory entered by hand, and an incident is a "
    "response record with the 72-hour GDPR Art. 33 clock displayed on it. Recording any of them "
    "does not make it true, and the seeder creates none of them for exactly that reason.",
    "Where a figure cannot be determined these pages print an em dash or the reason, never a 0: a "
    "zero that means 'cannot tell' is the most dangerous number a security board can show, and a "
    "quiet board here means nobody has written anything down rather than that nothing is wrong.",
]

#: A finding is a point-in-time report, so a threat is SETTLED once an analyst has decided
#: something about it. Declared here rather than read off `STATUS_CHOICES` order, because the
#: board's "live" test is set membership, not a position in a list.
THREAT_SETTLED = ("resolved", "false_positive", "ignored")
#: Same discipline on the incident spine: `false_positive` is a decision, not an open incident.
INCIDENT_SETTLED = ("closed", "false_positive")
#: The vulnerability register's live set. Every other value in `STATUS_CHOICES` is a terminal
#: DECISION somebody made, which is why the board counts only these two as open.
FINDING_OPEN = ("open", "in_progress")

#: Display cap for the three row-listing boards. A board that must render every open row ever
#: recorded is a board that eventually stops rendering; the `open_total` keys are what tell the
#: page when the list it is showing is not the whole truth.
BOARD_ROW_CAP = 200
#: The source-address tables are a "who is talking to us" top-N, not a register, so the cap is
#: tight and the ordering puts the noisiest address first.
TOP_IP_CAP = 50


def _age_days(moment):
    """Whole days from `moment` to now; `None` when there is no anchor.

    `SecurityThreat.detected_at` and `VulnerabilityFinding.first_seen_at` are never NULL (both
    default to `timezone.now`), so this is always a number for them — but the helper returns
    `None` rather than guessing, because a `0` for "no anchor" is a lie.
    """
    if moment is None:
        return None
    return (timezone.now() - moment).days


def _threat_age_days(threat):
    """How long this finding has been sitting on the board."""
    return _age_days(threat.detected_at)


def _source_ip_display(source_ip):
    """A source address, or an em dash. Never a blank cell, never a fabricated address."""
    return source_ip or "—"


def _expires_display(expires_at):
    """`expires_at` NULL -> "permanent". **Never today's date** — a defaulted expiry is an
    expiry nobody chose, and a temporary block is the common case."""
    if expires_at is None:
        return "permanent"
    return expires_at.strftime("%Y-%m-%d %H:%M")


def _sla_days(finding):
    """The `REMEDIATION_SLA_DAYS` figure for this finding's CVSS band, or `None`.

    A **policy somebody wrote down**; no scheduler reads it (0.20 owns the scheduler), which
    is why the page prints it as the policy the finding is judged against rather than as a
    deadline anything will chase.
    """
    return REMEDIATION_SLA_DAYS.get(finding.severity)


def _finding_is_overdue(finding):
    """Past `due_on` AND still open.

    A finding somebody already fixed, accepted or dismissed is never overdue, however late its
    deadline was — the deadline is about the work, not the queue. `False` when no deadline is
    set at all, which is a different statement from "not yet due".
    """
    if finding.due_on is None or not finding.is_open:
        return False
    return finding.due_on < timezone.localdate()


def _is_fixable(finding):
    """True when a fix exists. NULL is the third state — "nobody determined it" — and is
    deliberately neither True nor False here."""
    return finding.fix_available in ("yes", "partial")


def _cvss_display(finding):
    """`cvss_score` NULL -> an em dash. **Never `0`** — a 0.0 CVSS is a real score and a
    completely different statement from "nobody scored this"."""
    if finding.cvss_score is None:
        return "—"
    return str(finding.cvss_score)



def _incident_deadline_display(discovered_at):
    """Art. 33(1)'s 72-hour deadline as a string, or an em dash when there is no anchor.

    The same wording `SecurityIncident.deadline_display` uses, recomputed here from the one
    scalar the view read. An em dash for a NULL anchor, never "due today".
    """
    if discovered_at is None:
        return "—"
    return (discovered_at + timedelta(hours=NOTIFICATION_WINDOW_HOURS)).strftime("%Y-%m-%d %H:%M")


def _incident_hours_remaining(discovered_at):
    """Hours left in the Art. 33 window. Negative once it has passed, `None` with no anchor.

    `None` is a distinct third state from `0` and from a negative number: "nobody recorded when
    the organisation became aware" is not "the deadline is right now", and the breach board's
    whole point is that the undecided rows are the ones nobody has looked at.
    """
    if discovered_at is None:
        return None
    deadline = discovered_at + timedelta(hours=NOTIFICATION_WINDOW_HOURS)
    return (deadline - timezone.now()).total_seconds() / 3600.0


def _tenant_or_home(request, what):
    """The `tenant is None` guard every board and the overview shares.

    Each of these pages queries a tenant-scoped model and `request.tenant` is None for the
    superuser, so without this a tenant-less user gets a board of silent empties and no
    explanation — the 0.16 "live sidebar over a page that renders nothing" failure. The
    `monitoring_overview` pattern, verbatim.
    """
    if request.tenant is None:
        messages.info(request, "%s apply to a tenant workspace." % what)
        return False
    return True


def _choice_rows(counts, choices):
    """Zip a `{value: count}` mapping against a CHOICES list into `(value, label, count)`.

    Zipped HERE, not in the template: a Django template cannot index a dict by a loop
    variable, so `{{ counts[value] }}` printed the whole dict after every label instead of that
    label's own count — the exact bug 0.17's health board and firing board both carry a comment
    about. The raw VALUE travels beside the label so a badge ladder keys off the stored value
    like every other badge in this sub-module; keying off the display label means one relabel
    silently greys out one card while the rest stay correct.

    Every CHOICES value is present even at zero, so the template can loop the whole vocabulary
    without a `.get` and without inventing a key the model does not declare.
    """
    return [(value, label, counts.get(value, 0)) for value, label in choices]


def _count_list(rows):
    """The parallel list of counts from `_choice_rows`, so a template can read either."""
    return [count for _value, _label, count in rows]


def _grouped_counts(qs, field):
    """`{field_value: count}` straight from the database.

    Grouped `Count` rather than a Python loop over fetched rows: this stays one pass at any
    table size, where counting in Python means loading every row ever written to count them.
    """
    return {row[field]: row["n"] for row in qs.values(field).annotate(n=Count("id"))}



# ================================================================ SecurityThreat
@tenant_admin_required
def securitythreat_list(request):
    """The declared-findings register. **Nothing produced any of these rows.**

    `?type=` is the GET param for the `threat_type` COLUMN — the same deliberate split as 0.17's
    `?metric=` / `metric_key`, and the template dropdown must say so too. `?waf=` and
    `?defense=` exist so `waf_action_choices` and `defense_mode_choices` back a real dropdown;
    a `*_choices` key with no filter behind it is a key the template reads for nothing (the
    L7 defect in its dropdown form).

    `crud_list` already refuses a junk enum, a junk pk and a junk boolean itself
    (`_enum_values` / `as_db_int` / the ValidationError guard), so this view adds **no** second
    parser of its own — one parser, fixed once, is the whole point of the helper.
    """
    return crud_list(
        request,
        SecurityThreat.objects.filter(tenant=request.tenant).select_related(
            # `mitigated_by` was missing and the list template reads `obj.mitigated_by.cidr` inside
            # the row loop — measured 10 queries -> 25 (+1 per rendered row) once rows had a
            # mitigation, the same N+1 shape 0.17 fixed on its incident create page.
            "service", "alert_event", "rate_limit_policy", "mitigated_by"),
        "core/securitythreat/list.html",
        search_fields=["title", "mitre_technique", "mitre_tactic", "source_ip", "summary",
                       "evidence", "notes"],
        filters=[("status", "status", False), ("type", "threat_type", False),
                 ("severity", "severity", False), ("service", "service_id", True),
                 ("waf", "waf_action", False), ("defense", "defense_mode", False)],
        extra_context={
            "status_choices": SecurityThreat.STATUS_CHOICES,
            "threat_type_choices": SecurityThreat.THREAT_TYPE_CHOICES,
            # 0.17's firing severity BY REFERENCE (L36), so a severity an analyst picks here is
            # the same severity they would pick on the alert that raised the finding.
            "severity_choices": AlertRule.SEVERITY_CHOICES,
            "waf_action_choices": SecurityThreat.WAF_ACTION_CHOICES,
            "defense_mode_choices": SecurityThreat.DEFENSE_MODE_CHOICES,
            "services": ServiceComponent.objects.filter(tenant=request.tenant).order_by("name"),
            "notes": SECURITY_NOTES,
        })


@tenant_admin_required
def securitythreat_create(request):
    return crud_create(request, form_class=SecurityThreatForm,
                       template="core/securitythreat/form.html",
                       success_url="core:securitythreat_list",
                       extra_context={"notes": SECURITY_NOTES})


@tenant_admin_required
def securitythreat_detail(request, pk):
    """One declared finding, plus the two 0.18 relationships worth reading in place.

    The rate-limit link is `core:rate_limit_edit` with the pk, **not** `rate_limit_detail`:
    `core/urls.py` registers only `_list` / `_create` / `_edit` / `_delete` for
    `RateLimitPolicy`, and a `{% url %}` on a missing name is a hard 500 on this page.

    `crud_detail` renders the object, so the two derived scalars the template needs are read
    from one narrow `.values()` query rather than by fetching the whole row a second time just
    to call a property on it. `first()` rather than `get()` on purpose: this runs BEFORE
    `crud_detail` does its own tenant-scoped `get_object_or_404`, so a missing or
    cross-tenant pk must fall through to *that* 404 rather than raise `DoesNotExist` here.
    """
    scalars = (SecurityThreat.objects.filter(tenant=request.tenant, pk=pk)
               .values("detected_at", "source_ip").first() or {})
    return crud_detail(
        request, model=SecurityThreat, pk=pk, template="core/securitythreat/detail.html",
        select_related=("service", "alert_event__rule", "rate_limit_policy", "mitigated_by",
                        "target_user", "target_credential"),
        extra_context={
            "incident_count": SecurityIncident.objects.filter(
                tenant=request.tenant, primary_threat_id=pk).count(),
            "age_days": _age_days(scalars.get("detected_at")),
            "source_ip_display": _source_ip_display(scalars.get("source_ip")),
            "notes": SECURITY_NOTES,
        })


@tenant_admin_required
def securitythreat_edit(request, pk):
    # `reverse(...)` and not the bare name: `crud_edit` calls `redirect(success_url)` with no
    # arguments, so a pk-taking route passed as a string raises `NoReverseMatch` AFTER the row is
    # saved and the operator sees a 500 for a write that succeeded. House convention
    # (views/Monitoring.py:154, views/Backup.py:137).
    return crud_edit(
        request, model=SecurityThreat, pk=pk, form_class=SecurityThreatForm,
        template="core/securitythreat/form.html",
        success_url=reverse("core:securitythreat_detail", args=[pk]),
        extra_context={"notes": SECURITY_NOTES})


@require_POST
@tenant_admin_required
def securitythreat_delete(request, pk):
    return crud_delete(request, model=SecurityThreat, pk=pk,
                       success_url="core:securitythreat_list")

@require_POST
@tenant_admin_required
def securitythreat_triage(request, pk):
    """Record that an analyst picked this finding up.

    Guarded on `status == "new"`, because only a new finding is waiting on somebody. Re-triage
    is refused rather than silently restamped: a second POST would imply a second analyst
    looked at it, and the whole value of the stamp is that somebody did.

    The message is the point. Triaging a threat does not triage an *attack* — nothing in NavERP
    investigated anything; this records that a person read the row.
    """
    obj = get_object_or_404(SecurityThreat, pk=pk, tenant=request.tenant)
    if obj.status != "new":
        messages.error(request, "This finding is already %s, so triaging it again would imply a "
                                "second look that may not have happened."
                       % obj.get_status_display())
        return redirect("core:securitythreat_detail", pk=obj.pk)
    obj.status = "triaged"
    obj.save(update_fields=["status"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "securitythreat_triage", "status": obj.status})
    messages.success(request, "Triaged. This records that somebody looked at it — NavERP did not "
                              "detect anything and investigated nothing.")
    return redirect("core:securitythreat_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def securitythreat_resolve(request, pk):
    """Record that somebody declared this finding resolved.

    Guarded on the settled set, refusing a re-resolve: the lifecycle stamps (`resolved_at`,
    `resolved_by`) are the only history a finding carries, so overwriting them destroys the
    record of the first decision. `SecurityThreat.clean()` requires both stamps on a resolved
    row, which is why they are written together here.

    The `resolution_note` comes from `request.POST` and is **truncated to the column's 255 width
    before it is written** — an untruncated string raises `DataError` inside the driver and the
    operator sees a 500 for a write that had already half-happened. It is written to its own
    column rather than appended to `notes`, so the closing statement is a field the schema knows
    about and `notes` stays what the analyst typed when they first recorded the finding.
    """
    obj = get_object_or_404(SecurityThreat, pk=pk, tenant=request.tenant)
    if obj.status in THREAT_SETTLED:
        messages.error(request, "This finding is already %s. Recording a second resolution would "
                                "overwrite who settled it and when."
                       % obj.get_status_display())
        return redirect("core:securitythreat_detail", pk=obj.pk)
    now = timezone.now()
    note = (request.POST.get("resolution_note") or "").strip()[:255]
    obj.status = "resolved"
    obj.resolved_at = now
    obj.resolved_by = request.user
    if note:
        obj.resolution_note = note
    obj.save(update_fields=["status", "resolved_at", "resolved_by", "resolution_note"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "securitythreat_resolve", "status": obj.status,
                             "resolved_at": now.isoformat(), "resolution_note": note})
    messages.success(request, "Resolution recorded. NavERP did not fix anything — this records that "
                              "somebody said it was fixed.")
    return redirect("core:securitythreat_detail", pk=obj.pk)


# ==================================================================== IpAccessRule
class _IpAccessRuleCreateForm(IpAccessRuleForm):
    """`IpAccessRuleForm` plus the two authorship stamps, on CREATE only.

    `added_by` / `added_by_label` are L22 system-set stamps: they are deliberately absent from
    `Meta.fields`, because a person typing "I added this" is inventing provenance. The form has
    no `request`, so the **view** is the only layer that can supply the actor — which is why
    this subclass lives here rather than in `forms/Security.py`, where it would have had
    nothing to read.

    `actor` arrives as an ordinary constructor keyword, which is how `crud_create`'s
    `form_kwargs` hands it over on both the GET and the POST branch. It is popped before
    `super().__init__` so the model form machinery never sees it.
    """

    def __init__(self, *args, **kwargs):
        self.actor = kwargs.pop("actor", None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.actor is not None and getattr(self.actor, "is_authenticated", False):
            obj.added_by = self.actor
            # The snapshot, so the rule still names who wrote it after the account is deleted.
            obj.added_by_label = self.actor.get_username()
        if commit:
            obj.save()
            self.save_m2m()
        return obj


@tenant_admin_required
def ipaccessrule_list(request):
    """The allow/deny register. **Written down; nothing evaluates it.**

    `?scope=` and `?source=` were added so `scope_choices` and `source_choices` back real
    dropdowns — a `*_choices` key with no filter behind it is a key the template reads for
    nothing. `?active=` maps to `is_active` and takes the literal strings `"True"` / `"False"`,
    which `crud_list`'s boolean mapping already handles.
    """
    return crud_list(
        request,
        IpAccessRule.objects.filter(tenant=request.tenant).select_related(
            "service", "credential", "rate_limit_policy"),
        "core/ipaccessrule/list.html",
        search_fields=["cidr", "reason", "source", "notes"],
        filters=[("direction", "direction", False), ("action", "action", False),
                 ("active", "is_active", False), ("service", "service_id", True),
                 ("scope", "scope", False), ("source", "source", False)],
        extra_context={
            "direction_choices": IpAccessRule.DIRECTION_CHOICES,
            "action_choices": IpAccessRule.ACTION_CHOICES,
            "scope_choices": IpAccessRule.SCOPE_CHOICES,
            "source_choices": IpAccessRule.SOURCE_CHOICES,
            "services": ServiceComponent.objects.filter(tenant=request.tenant).order_by("name"),
            "notes": SECURITY_NOTES,
        })


@tenant_admin_required
def ipaccessrule_create(request):
    """`crud_create` plus the authorship stamps only the view can supply."""
    return crud_create(request, form_class=_IpAccessRuleCreateForm,
                       template="core/ipaccessrule/form.html",
                       success_url="core:ipaccessrule_list",
                       form_kwargs={"actor": request.user},
                       extra_context={"notes": SECURITY_NOTES})


@tenant_admin_required
def ipaccessrule_detail(request, pk):
    """One policy, and the threats somebody says it mitigates.

    `mitigated_threat_count` is the number the template needs to introduce that list; the list
    itself is read in the template through `obj.mitigated_threats.all` (the reverse side of
    `SecurityThreat.mitigated_by`), so no extra context key is invented for it.

    `crud_detail` owns the row, so the two expiry scalars are derived from one narrow
    `.values()` query rather than by fetching the whole rule a second time just to call a
    property on it. `first()`, not `get()`: this runs BEFORE `crud_detail`'s own tenant-scoped
    `get_object_or_404`, so a missing or cross-tenant pk must fall through to *that* 404 rather
    than raise `DoesNotExist` here.
    """
    row = IpAccessRule.objects.filter(tenant=request.tenant, pk=pk).values("expires_at").first()
    expires_at = row["expires_at"] if row else None
    return crud_detail(
        request, model=IpAccessRule, pk=pk, template="core/ipaccessrule/detail.html",
        select_related=("service", "rate_limit_policy", "added_by"),
        extra_context={
            "mitigated_threat_count": SecurityThreat.objects.filter(
                tenant=request.tenant, mitigated_by_id=pk).count(),
            "is_expired": bool(expires_at and expires_at <= timezone.now()),
            "expires_display": _expires_display(expires_at),
            "notes": SECURITY_NOTES,
        })


@tenant_admin_required
def ipaccessrule_edit(request, pk):
    return crud_edit(
        request, model=IpAccessRule, pk=pk, form_class=IpAccessRuleForm,
        template="core/ipaccessrule/form.html",
        success_url=reverse("core:ipaccessrule_detail", args=[pk]),
        extra_context={"notes": SECURITY_NOTES})


@require_POST
@tenant_admin_required
def ipaccessrule_delete(request, pk):
    return crud_delete(request, model=IpAccessRule, pk=pk, success_url="core:ipaccessrule_list")



# =========================================================== VulnerabilityFinding
@tenant_admin_required
def vulnerabilityfinding_list(request):
    """The advisory register. **Hand-entered; NavERP runs no scanner.**

    **The `severity` here is a CVSS band, deliberately NOT `AlertRule.SEVERITY_CHOICES`** — how
    badly a system is scored is a different fact from how loudly a threshold fired, so the two
    dropdowns are built from two different constants and must never share a context key by
    accident. `?source=` maps to the `finding_source` COLUMN, and the `?component=` dropdown
    reads `components` (so it is plural — the contract names that key) with its options compared
    against `|stringformat:"d"`.
    """
    return crud_list(
        request,
        VulnerabilityFinding.objects.filter(tenant=request.tenant).select_related("component"),
        "core/vulnerabilityfinding/list.html",
        search_fields=["title", "advisory_id", "package_name", "installed_version",
                       "remediation_note", "evidence", "notes"],
        filters=[("status", "status", False), ("severity", "severity", False),
                 ("source", "finding_source", False), ("component", "component_id", True),
                 ("fix", "fix_available", False)],
        extra_context={
            "status_choices": VulnerabilityFinding.STATUS_CHOICES,
            "severity_choices": VulnerabilityFinding.SEVERITY_BAND_CHOICES,
            "finding_source_choices": VulnerabilityFinding.FINDING_SOURCE_CHOICES,
            "fix_available_choices": VulnerabilityFinding.FIX_AVAILABLE_CHOICES,
            "components": ServiceComponent.objects.filter(tenant=request.tenant).order_by("name"),
            # The whole mapping, so the page prints the policy the findings are judged against
            # rather than a single number. `none` -> None means "no SLA for this band", which
            # the template must render as a reason and never as 0 days.
            "sla_days": REMEDIATION_SLA_DAYS,
            "notes": SECURITY_NOTES,
        })


@tenant_admin_required
def vulnerabilityfinding_create(request):
    return crud_create(request, form_class=VulnerabilityFindingForm,
                       template="core/vulnerabilityfinding/form.html",
                       success_url="core:vulnerabilityfinding_list",
                       extra_context={"notes": SECURITY_NOTES})


@tenant_admin_required
def vulnerabilityfinding_detail(request, pk):
    """One advisory, with the SLA policy it is measured against.

    `due_on` NULL means **"no remediation deadline has been set"**, which is a different
    statement from "due today" and must never be defaulted; `days_overdue` is `None` for the
    same reason, and the template is expected to print the reason rather than a `0`.

    `crud_detail` owns the row, so the derived scalars come from one narrow `.values()` query.
    `first()`, not `get()`: this runs BEFORE `crud_detail`'s tenant-scoped `get_object_or_404`,
    so a missing or cross-tenant pk must fall through to *that* 404.
    """
    row = (VulnerabilityFinding.objects.filter(tenant=request.tenant, pk=pk)
           .values("severity", "status", "due_on", "cvss_score", "fix_available").first() or {})
    due_on = row.get("due_on")
    is_open = row.get("status") in FINDING_OPEN
    return crud_detail(
        request, model=VulnerabilityFinding, pk=pk,
        template="core/vulnerabilityfinding/detail.html",
        select_related=("component", "accepted_by"),
        extra_context={
            "sla_days": REMEDIATION_SLA_DAYS.get(row.get("severity")),
            # Open AND past the deadline. A finding somebody already fixed or accepted is never
            # overdue, however late its deadline was.
            "is_overdue": bool(due_on and is_open and due_on < timezone.localdate()),
            # `None` (no deadline set) is deliberately distinct from `0` (due today) — the same
            # discipline the model property carries.
            "days_overdue": (timezone.localdate() - due_on).days
            if (due_on and is_open and due_on <= timezone.localdate()) else None,
            # NULL `fix_available` is the third state, "nobody determined it", so it is neither.
            "is_fixable": row.get("fix_available") in ("yes", "partial"),
            "cvss_display": "—" if row.get("cvss_score") is None else str(row["cvss_score"]),
            "notes": SECURITY_NOTES,
        })


@tenant_admin_required
def vulnerabilityfinding_edit(request, pk):
    return crud_edit(
        request, model=VulnerabilityFinding, pk=pk, form_class=VulnerabilityFindingForm,
        template="core/vulnerabilityfinding/form.html",
        success_url=reverse("core:vulnerabilityfinding_detail", args=[pk]),
        extra_context={"notes": SECURITY_NOTES})


@require_POST
@tenant_admin_required
def vulnerabilityfinding_delete(request, pk):
    return crud_delete(request, model=VulnerabilityFinding, pk=pk,
                       success_url="core:vulnerabilityfinding_list")



# ============================================================== SecurityIncident
@tenant_admin_required
def securityincident_list(request):
    """The response register, with the notification decisions beside it.

    `?class=` is the GET param for the `incident_class` COLUMN (the same deliberate split as
    `?type=` / `threat_type` and 0.17's `?metric=` / `metric_key`).

    **`?notifiable=` is a THREE-state filter and the third state is the point.** `is_notifiable`
    is a nullable Boolean: NULL means *nobody has decided yet*, which is precisely the state the
    72-hour Art. 33 clock exists to pressure. `crud_list` maps the literal strings `"True"` /
    `"False"` to the booleans and ignores anything else, so `?notifiable=` cannot express NULL
    and the template's blank "Not decided" option correctly means "no filter", not "NULL only".

    `?exemption=` was added so `subject_exemption_choices` backs a real dropdown — Art. 34(3)'s
    three exemptions are a filter an investigator actually reaches for.
    """
    return crud_list(
        request,
        SecurityIncident.objects.filter(tenant=request.tenant).select_related(
            "incident", "primary_threat", "owner").prefetch_related("affected_services"),
        "core/securityincident/list.html",
        search_fields=["title", "notifiable_reason", "authority_reference", "root_cause",
                       "lessons_learned", "notes"],
        filters=[("status", "status", False), ("class", "incident_class", False),
                 ("severity", "severity", False), ("notifiable", "is_notifiable", False),
                 ("exemption", "subject_exemption", False)],
        extra_context={
            "status_choices": SecurityIncident.STATUS_CHOICES,
            "incident_class_choices": SecurityIncident.INCIDENT_CLASS_CHOICES,
            # 0.17's firing severity by reference again — the same list the threat list uses,
            # because both describe how loudly something happened, not how badly a system scored.
            "severity_choices": AlertRule.SEVERITY_CHOICES,
            "subject_exemption_choices": SecurityIncident.SUBJECT_EXEMPTION_CHOICES,
            "notes": SECURITY_NOTES,
        })


@tenant_admin_required
def securityincident_create(request):
    return crud_create(request, form_class=SecurityIncidentForm,
                       template="core/securityincident/form.html",
                       success_url="core:securityincident_list",
                       extra_context={"notes": SECURITY_NOTES})


@tenant_admin_required
def securityincident_detail(request, pk):
    """One incident, with the Art. 33 clock **displayed**.

    `regulatory_deadline` is a **property, never a column**: a stored deadline drifts from its
    anchor the moment somebody edits `discovered_at`, and a property cannot. It is shown, never
    acted on — NavERP runs no scheduler and files nothing with any authority.

    The `affected_services` M2M is read in the template through `obj.affected_services.all`
    (prefetched by the list queryset; on this page it is a single extra query, which is why no
    context key is invented for it). The notification block renders only when
    `obj.incident_class == "data_breach"`, so nothing here keys off it.

    `crud_detail` owns the row, so the three clock scalars are derived from ONE narrow
    `.values("discovered_at")` query rather than by re-fetching the incident three times to call
    three properties on it. `first()`, not `get()`: this runs BEFORE `crud_detail`'s
    tenant-scoped `get_object_or_404`, so a missing or cross-tenant pk falls through to *that*.
    """
    discovered_at = (SecurityIncident.objects.filter(tenant=request.tenant, pk=pk)
                     .values_list("discovered_at", flat=True).first())
    hours_remaining = _incident_hours_remaining(discovered_at)
    return crud_detail(
        request, model=SecurityIncident, pk=pk, template="core/securityincident/detail.html",
        select_related=("incident", "primary_threat", "owner"),
        extra_context={
            # An em dash when there is no anchor, never "due today" for a NULL `discovered_at` —
            # the same discipline `deadline_display` carries on the model.
            "deadline_display": _incident_deadline_display(discovered_at),
            "hours_remaining": hours_remaining,
            # `None` (no anchor) is NOT overdue. A clock that never started has not been missed.
            "is_overdue": hours_remaining is not None and hours_remaining < 0,
            # The policy, not a per-row number, so the page shows what it is judged against.
            "window_hours": NOTIFICATION_WINDOW_HOURS,
            "notes": SECURITY_NOTES,
        })


@tenant_admin_required
def securityincident_edit(request, pk):
    return crud_edit(
        request, model=SecurityIncident, pk=pk, form_class=SecurityIncidentForm,
        template="core/securityincident/form.html",
        success_url=reverse("core:securityincident_detail", args=[pk]),
        extra_context={"notes": SECURITY_NOTES})


@require_POST
@tenant_admin_required
def securityincident_delete(request, pk):
    return crud_delete(request, model=SecurityIncident, pk=pk,
                       success_url="core:securityincident_list")



# ------------------------------------------- the NIST SP 800-61r2 lifecycle verbs
# Four POST-only verbs, ONE stamp each, each guarded on its legal predecessor. Every message
# says "recorded" — these record that somebody said a step happened, and NavERP contained,
# eradicated, recovered, closed, filed and notified nothing.


def _incident_refuse(request, obj, message):
    """The shared refusal path: an error message, a redirect, and **no write and no audit row**.

    A refused action must leave no trace, or the audit trail claims a containment that was
    refused — which is worse than no audit trail, because it is a false one.
    """
    messages.error(request, message)
    return redirect("core:securityincident_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def securityincident_contain(request, pk):
    """Record that somebody says this incident was contained.

    Two guards. The **legal predecessor** is triage: an incident cannot be contained before
    anybody has looked at it, and a `detected` row somebody jumps straight to containing is a
    response nobody assessed. And `contained_at` being unset, so a second POST cannot rewrite
    the first containment's timestamp and imply the incident came back and was handled twice.
    """
    obj = get_object_or_404(SecurityIncident, pk=pk, tenant=request.tenant)
    if obj.status in INCIDENT_SETTLED:
        # `INCIDENT_SETTLED` is consulted for the first time. The guard used to test only
        # `status == "detected"`, so a `false_positive` — a DECISION somebody made, and the whole
        # reason this set is declared — could still be stamped contained. Probed, not predicted.
        return _incident_refuse(
            request, obj,
            "This incident is %s, which is a decision somebody recorded. Stamping a containment on "
            "it would rewrite that decision." % obj.get_status_display().lower())
    if obj.status == "detected":
        return _incident_refuse(
            request, obj,
            "This incident is still only detected. Triage it first - an incident cannot be "
            "contained before somebody has assessed it.")
    if obj.contained_at is not None:
        return _incident_refuse(
            request, obj,
            "Containment was already recorded on %s. A second POST would overwrite the first "
            "moment." % obj.contained_at.strftime("%b %d, %Y %H:%M"))
    now = timezone.now()
    obj.contained_at = now
    obj.save(update_fields=["contained_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "securityincident_contain", "contained_at": now.isoformat()})
    messages.success(request, "Containment recorded. NavERP contained nothing - it has no IDS/IPS "
                              "agent and blocks no traffic. This records that somebody says it was.")
    return redirect("core:securityincident_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def securityincident_eradicate(request, pk):
    """Record that somebody says the cause was removed.

    Legal predecessor: `contained_at` set. Eradication before containment is a claim about a
    root cause nobody established, which is the single most expensive mistake on this page.
    """
    obj = get_object_or_404(SecurityIncident, pk=pk, tenant=request.tenant)
    if obj.contained_at is None:
        return _incident_refuse(
            request, obj,
            "Record containment first. Eradication is a claim about a root cause, and there is "
            "no containment on this incident to have established one.")
    if obj.eradicated_at is not None:
        return _incident_refuse(
            request, obj,
            "Eradication was already recorded on %s. A second POST would overwrite the first "
            "moment." % obj.eradicated_at.strftime("%b %d, %Y %H:%M"))
    now = timezone.now()
    obj.eradicated_at = now
    obj.save(update_fields=["eradicated_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "securityincident_eradicate", "eradicated_at": now.isoformat()})
    messages.success(request, "Eradication recorded. NavERP removed nothing - it patched no "
                              "system and closed no port. This records that somebody says it was.")
    return redirect("core:securityincident_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def securityincident_recover(request, pk):
    """Record that somebody says service was restored.

    Legal predecessor: `eradicated_at` set. Recovering before the cause is gone is how an
    incident comes back, and the stamp is what tells the next responder it did.
    """
    obj = get_object_or_404(SecurityIncident, pk=pk, tenant=request.tenant)
    if obj.eradicated_at is None:
        return _incident_refuse(
            request, obj,
            "Record eradication first. Recovering before the cause was removed is how an "
            "incident returns.")
    if obj.recovered_at is not None:
        return _incident_refuse(
            request, obj,
            "Recovery was already recorded on %s. A second POST would overwrite the first "
            "moment." % obj.recovered_at.strftime("%b %d, %Y %H:%M"))
    now = timezone.now()
    obj.recovered_at = now
    obj.save(update_fields=["recovered_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "securityincident_recover", "recovered_at": now.isoformat()})
    messages.success(request, "Recovery recorded. NavERP restored nothing - it runs no failover "
                              "and no deployment. This records that somebody says it was.")
    return redirect("core:securityincident_detail", pk=obj.pk)



@require_POST
@tenant_admin_required
def securityincident_close(request, pk):
    """Record that somebody closed this incident.

    Three guards. `recovered_at` set, because an incident is not closed while it is still
    running. `is_notifiable is not None`, which is the readable version of the model's
    `clean()` rule — a closed incident with an undecided notification status is refused here
    rather than 500-ing on a form submit, and the refusal names the missing decision. And
    `closed_at` unset, so a second POST cannot rewrite the closure.
    """
    obj = get_object_or_404(SecurityIncident, pk=pk, tenant=request.tenant)
    if obj.status in INCIDENT_SETTLED:
        # Checked BEFORE the legal-predecessor test, for the same reason `contain` does it: a
        # `false_positive` is a decision, and closing it would overwrite that decision with
        # "closed". The probe found `close` already refused here, but only incidentally.
        return _incident_refuse(
            request, obj,
            "This incident is %s, which is a decision somebody recorded. Closing it would rewrite "
            "that decision." % obj.get_status_display().lower())
    if obj.recovered_at is None:
        return _incident_refuse(
            request, obj,
            "Record recovery first. An incident is not closed while it is still running.")
    if obj.is_notifiable is None:
        return _incident_refuse(
            request, obj,
            "Decide whether this incident is notifiable to the supervisory authority before "
            "closing it. \"Not yet decided\" is not the same answer as \"no\", and Art. 33 does "
            "not let a closed record leave the question open.")
    if obj.closed_at is not None:
        return _incident_refuse(
            request, obj,
            "This incident was already closed on %s. A second POST would overwrite the first "
            "closure." % obj.closed_at.strftime("%b %d, %Y %H:%M"))
    now = timezone.now()
    obj.closed_at = now
    obj.status = "closed"
    obj.save(update_fields=["closed_at", "status", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "securityincident_close", "closed_at": now.isoformat(),
                             "status": obj.status, "is_notifiable": obj.is_notifiable})
    messages.success(request, "Closure recorded. NavERP closed nothing and notified no authority "
                              "- it has no mailer and files nothing. This records that somebody "
                              "closed the record elsewhere.")
    return redirect("core:securityincident_detail", pk=obj.pk)



@require_POST
@tenant_admin_required
def securityincident_notify_authority(request, pk):
    """Record that somebody says a supervisory authority was notified.

    Guarded on `is_notifiable is True` first: a stamp on an incident somebody decided is **not**
    notifiable would assert a filing the record itself contradicts, and the model's `clean()`
    already refuses that pair. Then `authority_notified_at is None`, so a second POST cannot
    restamp a notice and imply a second filing.

    NavERP **sends nothing to any authority** — there is no regulator integration, no mailer and
    no webhook anywhere in this repository — so this writes a timestamp, and the message says
    so rather than letting the button read as a filing.
    """
    obj = get_object_or_404(SecurityIncident, pk=pk, tenant=request.tenant)
    if obj.is_notifiable is not True:
        return _incident_refuse(
            request, obj,
            "This incident is not marked notifiable, so recording an authority notification "
            "would contradict the decision above. Mark it notifiable first, with a reason.")
    if obj.authority_notified_at is not None:
        return _incident_refuse(
            request, obj,
            "An authority notification was already recorded on %s. A second POST would imply a "
            "second filing of the same breach."
            % obj.authority_notified_at.strftime("%b %d, %Y %H:%M"))
    now = timezone.now()
    obj.authority_notified_at = now
    obj.save(update_fields=["authority_notified_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "securityincident_notify_authority",
                             "authority_notified_at": now.isoformat()})
    messages.success(request, "This records that somebody says a filing was made. NavERP sends "
                              "nothing to any authority - it has no regulator integration, no "
                              "mailer and no webhook.")
    return redirect("core:securityincident_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def securityincident_notify_subjects(request, pk):
    """Record that somebody says the data subjects were told (Art. 34).

    Guarded on `subject_exemption == "none"` first, and that guard is the whole point of the
    field: an Art. 34(3) exemption is **the reason you did NOT notify**, so a recorded
    notification coexisting with a claimed exemption is a contradiction, and the model's
    `clean()` refuses that pair too. Then `subjects_notified is not True`, so a second POST
    cannot restamp.

    NavERP **told no data subject anything** — no mailer, no SMS gateway, no webhook.
    """
    obj = get_object_or_404(SecurityIncident, pk=pk, tenant=request.tenant)
    if obj.subject_exemption != "none":
        return _incident_refuse(
            request, obj,
            "This incident claims the \"%s\" exemption, which is a reason the data subjects were "
            "NOT notified. Recording a notification beside it would contradict the exemption."
            % obj.get_subject_exemption_display())
    if obj.subjects_notified is True:
        return _incident_refuse(
            request, obj,
            "Data subjects were already recorded as notified on %s. A second POST would imply they "
            "were told twice."
            % (obj.subjects_notified_at.strftime("%b %d, %Y %H:%M")
               if obj.subjects_notified_at else "an earlier date"))
    now = timezone.now()
    obj.subjects_notified = True
    obj.subjects_notified_at = now
    obj.save(update_fields=["subjects_notified", "subjects_notified_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "securityincident_notify_subjects",
                             "subjects_notified_at": now.isoformat()})
    messages.success(request, "This records that somebody says the data subjects were told. "
                              "NavERP notified nobody - it has no mailer, no SMS gateway and no "
                              "webhook.")
    return redirect("core:securityincident_detail", pk=obj.pk)



# ===================================================== the overview hub and the boards
@tenant_admin_required
def security_overview(request):
    """COMPUTED landing page for 0.18 — stores nothing, measures nothing.

    **One aggregate per model, not a count per figure.** The I3 lesson from 0.16: a second
    `COUNT(*)` for each headline figure is what took that page from 11 queries to 20, and a
    filtered `Count` inside `aggregate` is the supported way to ask for exactly these columns
    in one pass.

    Every figure here is a count over a real column, so a `0` is a legitimate figure and not a
    stand-in for "cannot tell" — which is why the template can print them bare. What a `0` does
    NOT mean is "secure": with the seeder creating no rows on purpose, a fresh workspace shows
    zeros because **nobody has written anything down**, and the template's empty states say so.
    """
    tenant = request.tenant
    if not _tenant_or_home(request, "The security overview"):
        return redirect("dashboard:home")

    threat_totals = SecurityThreat.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        open=Count("id", filter=~Q(status__in=THREAT_SETTLED)),
        new=Count("id", filter=Q(status="new")),
    )
    rule_totals = IpAccessRule.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        # "Deny" is the operator's INTENT, not an enforcement - so the figure is a count of
        # recorded deny policies, and the template must not label it "blocks".
        active_deny=Count("id", filter=Q(is_active=True, direction="deny")),
    )
    today = timezone.localdate()
    finding_totals = VulnerabilityFinding.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status__in=FINDING_OPEN)),
        # Open AND past the deadline. A finding somebody already fixed or accepted is never
        # overdue, however late its deadline was.
        overdue=Count("id", filter=Q(status__in=FINDING_OPEN, due_on__lt=today)),
    )
    incident_totals = SecurityIncident.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        open=Count("id", filter=~Q(status__in=INCIDENT_SETTLED)),
        # **The breach board's whole point.** An open incident nobody has decided about is a
        # 72-hour clock that is running with nobody watching it.
        undecided=Count("id", filter=~Q(status__in=INCIDENT_SETTLED, is_notifiable__isnull=False)),
    )

    return render(request, "core/securityoverview.html", {
        "threat_count": threat_totals["total"],
        "open_threat_count": threat_totals["open"],
        "new_threat_count": threat_totals["new"],
        "ip_rule_count": rule_totals["total"],
        "active_deny_count": rule_totals["active_deny"],
        "vulnerability_count": finding_totals["total"],
        "open_vulnerability_count": finding_totals["open"],
        "overdue_vulnerability_count": finding_totals["overdue"],
        "incident_count": incident_totals["total"],
        "open_incident_count": incident_totals["open"],
        "breach_undecided_count": incident_totals["undecided"],
        # The policy every incident on this sub-module is judged against.
        "window_hours": NOTIFICATION_WINDOW_HOURS,
        "notes": SECURITY_NOTES,
    })



@tenant_admin_required
def threat_board(request):
    """The declared-findings board. **The zero rule is the whole point of this page.**

    An empty board must never render as "secure" or "all clear". It is empty because **nothing
    in NavERP watches for threats**, and a green "0 open" here would be the precise false
    all-clear 0.8 refuses — so no green badge appears anywhere on this page.

    `open_total` is the UNTRUNCATED count beside the capped list, so a truncated list is never
    mistaken for a quiet one.
    """
    tenant = request.tenant
    if not _tenant_or_home(request, "The threat board"):
        return redirect("dashboard:home")

    base = SecurityThreat.objects.filter(tenant=tenant)
    open_qs = base.filter(~Q(status__in=THREAT_SETTLED))
    # Bounded for display; `open_total` below is what tells the page when the list it is showing
    # is not the whole truth. Ordered `-detected_at`, never a nullable column: MariaDB sorts
    # NULLs LAST under `DESC`, which is the C5 trap that hid 0.16's queued backups.
    open_threats = list(open_qs.select_related("service", "rate_limit_policy")
                        .order_by("-detected_at", "-id")[:BOARD_ROW_CAP])

    state_rows = _choice_rows(_grouped_counts(base, "status"), SecurityThreat.STATUS_CHOICES)
    severity_rows = _choice_rows(_grouped_counts(base, "severity"), AlertRule.SEVERITY_CHOICES)
    type_rows = _choice_rows(_grouped_counts(base, "threat_type"),
                             SecurityThreat.THREAT_TYPE_CHOICES)
    # Top source addresses, grouped and counted in the database. Rows with a NULL `source_ip`
    # are excluded rather than bucketed under a blank key: "no address recorded" is not an
    # address, and a pseudo-bucket would imply one.
    top_source_ips = list(
        base.exclude(source_ip=None).values("source_ip")
        .annotate(threats=Count("id"), last_seen=Max("detected_at"))
        .order_by("-threats", "-last_seen")[:TOP_IP_CAP])

    return render(request, "core/threatboard.html", {
        "open_threats": [{"threat": t, "age_days": _threat_age_days(t),
                          "mitigation": t.mitigated_by_id,
                          "source_ip_display": _source_ip_display(t.source_ip)}
                         for t in open_threats],
        "open_count": len(open_threats),
        "open_total": open_qs.count(),
        "state_rows": state_rows,
        "state_counts": _count_list(state_rows),
        "severity_rows": severity_rows,
        "severity_counts": _count_list(severity_rows),
        "type_rows": type_rows,
        "type_counts": _count_list(type_rows),
        "top_source_ips": top_source_ips,
        # Open findings with no allow/deny rule recorded against them: a count of GAPS in the
        # register, NOT a count of attacks that got through.
        "unmitigated_count": open_qs.filter(mitigated_by__isnull=True).count(),
        # The 0.17 seam made visible: how many of these were raised against a real firing.
        "correlated_alert_count": open_qs.filter(alert_event__isnull=False).count(),
        "notes": SECURITY_NOTES,
    })



@tenant_admin_required
def vulnerability_board(request):
    """The aging / overdue board for the advisory register. **NavERP scans nothing.**

    `sla_days` is the WHOLE `REMEDIATION_SLA_DAYS` mapping, so the page prints the policy the
    findings are judged against rather than a single number. `none -> None` means "no SLA for
    this band", which the template must render as a reason and never as "0 days".

    `oldest` is `None` when there is no open finding — never a fabricated placeholder object,
    because a placeholder row on a security board reads as a real finding.
    """
    tenant = request.tenant
    if not _tenant_or_home(request, "The vulnerability board"):
        return redirect("dashboard:home")

    base = VulnerabilityFinding.objects.filter(tenant=tenant)
    open_qs = base.filter(status__in=FINDING_OPEN)
    today = timezone.localdate()
    # The single oldest OPEN finding, ordered `first_seen_at` ASCENDING — the opposite direction
    # from every other ordering on this sub-module, because "oldest" is the whole question.
    oldest_finding = open_qs.order_by("first_seen_at", "id").first()
    oldest = None
    if oldest_finding is not None:
        oldest = {"finding": oldest_finding, "age_days": _age_days(oldest_finding.first_seen_at),
                  "sla_days": _sla_days(oldest_finding),
                  "suggested_due": oldest_finding.suggested_due_on(),
                  "days_overdue": oldest_finding.days_overdue}

    band_rows = _choice_rows(_grouped_counts(base, "severity"),
                             VulnerabilityFinding.SEVERITY_BAND_CHOICES)
    status_rows = _choice_rows(_grouped_counts(base, "status"),
                               VulnerabilityFinding.STATUS_CHOICES)
    source_rows = _choice_rows(_grouped_counts(base, "finding_source"),
                               VulnerabilityFinding.FINDING_SOURCE_CHOICES)

    return render(request, "core/vulnerabilityboard.html", {
        "band_rows": band_rows,
        "band_counts": _count_list(band_rows),
        "status_rows": status_rows,
        "status_counts": _count_list(status_rows),
        "source_rows": source_rows,
        "source_counts": _count_list(source_rows),
        "open_total": open_qs.count(),
        "overdue_count": open_qs.filter(due_on__lt=today).count(),
        # Open findings whose advisory says no fix exists. These are the ones no amount of
        # patching will clear, so they are the register's permanent residue.
        "no_fix_count": open_qs.filter(fix_available="no").count(),
        # Every accepted risk, open or not: a decision somebody made and owns, which is a
        # different thing from a finding nobody looked at.
        "accepted_count": base.filter(status="risk_accepted").count(),
        # `cvss_score IS NULL` — "nobody scored this", which is NOT the same as a score of 0.
        "unscored_count": base.filter(cvss_score__isnull=True).count(),
        "sla_days": REMEDIATION_SLA_DAYS,
        "oldest": oldest,
        "notes": SECURITY_NOTES,
    })



@tenant_admin_required
def breach_clock_board(request):
    """The GDPR Art. 33 clock board — **the most useful page in this sub-module, precisely
    because nothing will chase the deadline.**

    `undecided` is the `is_notifiable is None` subset of open incidents, and it is this board's
    whole point: an open personal-data breach nobody has decided about is a 72-hour clock
    running with nobody watching it. `is_notifiable` is a nullable Boolean precisely so that
    third state exists, and this page exists to make it visible.

    `hours_remaining` is `None` when `discovered_at` is NULL, which is a distinct third state
    from `0` and from a negative number — a clock that never started has not been missed, and
    the template must not print it as overdue.

    **NavERP files nothing with any authority and tells no data subject anything.** The rows
    here display a legal deadline; they do not discharge one.
    """
    tenant = request.tenant
    if not _tenant_or_home(request, "The breach clock"):
        return redirect("dashboard:home")

    base = SecurityIncident.objects.filter(tenant=tenant)
    open_qs = base.filter(~Q(status__in=INCIDENT_SETTLED))
    open_incidents = list(open_qs.order_by("-discovered_at", "-id")[:BOARD_ROW_CAP])
    # The clock is computed ONCE per row and reused: the list, the `undecided` subset and the
    # tallies all read the same dict, so the page can never show a row whose "hours remaining"
    # disagrees with the board's own overdue count.
    clocks = [{"incident": i,
               "hours_remaining": _incident_hours_remaining(i.discovered_at),
               "deadline": _incident_deadline_display(i.discovered_at)}
              for i in open_incidents]
    for clock in clocks:
        hours = clock["hours_remaining"]
        # `None` (no `discovered_at`) is NOT overdue: a clock that never started has not been
        # missed, and counting it as overdue would be a deadline nobody was ever given.
        clock["overdue"] = hours is not None and hours < 0

    undecided = [c for c in clocks if c["incident"].is_notifiable is None]
    return render(request, "core/breachclock.html", {
        "open_incidents": clocks,
        "undecided": undecided,
        # UNTRUNCATED, from the database rather than from the capped list: this is the figure the
        # board exists to report, so it must not shrink silently at the display cap.
        "undecided_count": open_qs.filter(is_notifiable__isnull=True).count(),
        "overdue_count": open_qs.filter(discovered_at__lt=timezone.now()
                                        - timedelta(hours=NOTIFICATION_WINDOW_HOURS)).count(),
        "notifiable_count": open_qs.filter(is_notifiable=True).count(),
        "not_notifiable_count": open_qs.filter(is_notifiable=False).count(),
        "notified_authority_count": open_qs.filter(authority_notified_at__isnull=False).count(),
        "subjects_notified_count": open_qs.filter(subjects_notified=True).count(),
        "window_hours": NOTIFICATION_WINDOW_HOURS,
        # UNTRUNCATED, so a capped list is never read as a quiet board.
        "open_total": open_qs.count(),
        "notes": SECURITY_NOTES,
    })



@tenant_admin_required
def brute_force_board(request):
    """A *query* over `accounts.LoginAttempt`. **This board declares no 0.18 table and writes no
    `accounts` row** — 0.4 owns identity and login-attempt recording, and re-recording attempts
    here would be a second copy of the same evidence (L36). It also adds **no lockout**: nothing
    on this page blocks an address, challenges an identifier or expires a session.

    **`LoginAttempt.tenant` is NULLABLE**, so attempts against an unknown identifier are recorded
    with no tenant and are therefore **excluded** from every figure here. The board counts the
    attempts it can attribute and says so on the page: a `0` means "no attributable failures
    recorded", **not** "no attacks". An aggregate that silently dropped un-attributable rows
    while reading as a total would be the 0.16 lie one level up.

    Grouping and counting happen in the database (`Count` / `Max` over a grouped `.values`),
    which stays one pass at any table size; counting in Python would mean loading every failed
    attempt ever recorded to count them.
    """
    tenant = request.tenant
    if not _tenant_or_home(request, "The brute-force correlation board"):
        return redirect("dashboard:home")
    # Read, never re-declared: the step-up threshold belongs to `accounts.security` (0.4). A
    # copy here would be a second definition of the same policy that drifts the moment 0.4
    # changes it, and this board's whole claim is that it adds nothing to that module.
    from apps.accounts.models import LoginAttempt
    from apps.accounts.security import RISK_STEP_UP_THRESHOLD

    failed = LoginAttempt.objects.filter(tenant=tenant, success=False, ip__isnull=False)
    # `identifiers` is a DISTINCT count of the usernames tried from that address — the number that
    # separates one stubborn user from a spray across many accounts. It is counted in the
    # database because the alternative is loading every failed attempt to deduplicate in Python.
    failed_addresses = list(
        failed.values("ip")
        .annotate(failures=Count("id"),
                  identifiers=Count("identifier", distinct=True, filter=~Q(identifier="")),
                  max_risk=Max("risk_score"),
                  last_seen=Max("created_at"))
        .order_by("-failures", "-last_seen")[:TOP_IP_CAP])

    return render(request, "core/bruteforceboard.html", {
        "failed_addresses": failed_addresses,
        # UNTRUNCATED, so a capped table is never read as a quiet one.
        "failed_total": failed.count(),
        # The policy this board is read against, not a re-declaration of it.
        "step_up_threshold": RISK_STEP_UP_THRESHOLD,
        # Attempts that DID reach an MFA challenge. This is the closest thing on the page to a
        # countermeasure, and it is still 0.4's doing — nothing here issued a challenge.
        "mfa_challenged_total": LoginAttempt.objects.filter(
            tenant=tenant, mfa_challenged=True).count(),
        "notes": SECURITY_NOTES,
    })
