"""core — 0.17 views (monitoring, logging & observability).

**The posture every view here takes, inherited from 0.8 (`apps/core/views/Privacy.py`) and 0.16
(`apps/core/views/Backup.py`):**

NavERP has **no probe, no collector, no log pipeline, no scheduler, no status page and no mailer**. So
none of these views performs the act it describes. `alert_event_create` records an alert a human
reported; `incident_notify` records a publication somebody says they made. The pages say so in `notes`
(§ `MONITORING_NOTES`) and the success messages say **"recorded"**, never "detected" or "sent".

**The zero rule, which is the whole point of the firing board.** 0.8's `retention_board` refuses to
print a `0` it cannot justify — *"Reporting 0 here would be a false all-clear."* `firing_board` obeys
the same rule and goes one step further: **`badge-green` never appears on it at all.** A green "0
firing" would be the exact false all-clear, because a quiet board here means *nothing evaluates these
rules*, not *everything is fine*.

**Every delete and every action is POST-only with `@require_POST` ABOVE the role gate** (the 7.7
pattern): decorators apply bottom-up, so the outermost runs first. With the role gate outermost a
member's GET would be answered 403 before the method check ran, and the house standard is 405 for a
wrong method regardless of role.

**Every action's guard lives in the VIEW, not only in a hidden button**, so the action cannot be
reached by a hand-made POST and the audit row is not written either — the `backup_job_verify` rule.
"""
from django.contrib import messages
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.utils import write_audit_log
from apps.core.models import (
    AlertEvent,
    AlertRule,
    Incident,
    ServiceComponent,
)
from apps.core.forms import (
    AlertEventForm,
    AlertRuleForm,
    IncidentForm,
    ServiceComponentForm,
)


#: The honest-limit lines the overview, the boards and every register page print VERBATIM. A
#: module-level constant so a page and its board cannot disagree about what this application can and
#: cannot do — the same reason 0.16 has `BACKUP_NOTES`. No view invents its own prose.
MONITORING_NOTES = [
    "This is a register of claims a person wrote, not a monitoring system. NavERP has no probe, no "
    "collector, no log pipeline and no scheduler - nothing here measures, evaluates, notifies or "
    "publishes anything.",
    "A component's status is hand-set. An alert event is a report that a threshold was crossed. Neither "
    "is a measurement NavERP took, and recording either does not make it true.",
    "Where a figure cannot be determined the boards say so and print an em dash, never a 0: a zero that "
    "means 'cannot tell' is the most dangerous number an operations board can show.",
]


# ====================================================== ServiceComponent
@tenant_admin_required
def service_component_list(request):
    # `Role` is imported LAZILY inside the function: `core` is imported before `accounts` at startup, so
    # a module-level import here is a circular import. The path is `apps.accounts.models` (a package
    # whose __init__ re-exports Role), NOT `accounts.models.Role` - `accounts` is a FLAT app, so that
    # dotted form is a ModuleNotFoundError. Same posture as 0.16's lazy import in the seeder.
    from apps.accounts.models import Role

    return crud_list(
        request,
        ServiceComponent.objects.filter(tenant=request.tenant).select_related("owner_role"),
        "core/servicecomponent/list.html",
        search_fields=["name", "code", "description"],
        # NOTE the asymmetry, pinned by the contract: the GET param is `status` while the ORM lookup is
        # `current_status`. `owner_role` is an int FK and is L11-guarded inside `crud_list`.
        filters=[("kind", "kind", False), ("status", "current_status", False),
                 ("owner_role", "owner_role_id", True), ("public", "is_public", False)],
        extra_context={
            "kind_choices": ServiceComponent.KIND_CHOICES,
            "status_choices": ServiceComponent.STATUS_CHOICES,
            "owner_roles": Role.objects.filter(tenant=request.tenant).order_by("name"),
            # A real count over ONE nullable column, so a literal 0 here is legitimate. Deliberately NO
            # `critical_count`: it is derivable by the reader from the `is_critical` column and would
            # cost a query for nothing.
            "unreported_count": ServiceComponent.objects.filter(
                tenant=request.tenant, last_status_at__isnull=True).count(),
            "notes": MONITORING_NOTES,
        })


@tenant_admin_required
def service_component_create(request):
    return crud_create(request, form_class=ServiceComponentForm,
                       template="core/servicecomponent/form.html",
                       success_url="core:service_component_list",
                       extra_context={"notes": MONITORING_NOTES})


@tenant_admin_required
def service_component_detail(request, pk):
    return crud_detail(
        request, model=ServiceComponent, pk=pk, template="core/servicecomponent/detail.html",
        select_related=("owner_role",),
        extra_context={
            "rule_count": AlertRule.objects.filter(tenant=request.tenant, service_id=pk).count(),
            "open_event_count": AlertEvent.objects.filter(
                tenant=request.tenant, service_id=pk,
                state__in=["firing", "acknowledged"]).count(),
            # `.distinct()` is load-bearing: an incident naming this component as BOTH `service` and in
            # `affected_services` matches on either branch, and without it one incident counts twice.
            "incident_count": Incident.objects.filter(
                Q(service_id=pk) | Q(affected_services=pk), tenant=request.tenant).distinct().count(),
            "notes": MONITORING_NOTES,
        })


@tenant_admin_required
def service_component_edit(request, pk):
    # `reverse(...)` and not the bare name: `crud_edit` calls `redirect(success_url)` with no
    # arguments, so a pk-taking route passed as a string raises `NoReverseMatch` AFTER the row is saved
    # and the operator sees a 500 for a write that succeeded. House convention (views/Backup.py:137).
    return crud_edit(
        request, model=ServiceComponent, pk=pk, form_class=ServiceComponentForm,
        template="core/servicecomponent/form.html",
        success_url=reverse("core:service_component_detail", args=[pk]),
        extra_context={"notes": MONITORING_NOTES})


@require_POST
@tenant_admin_required
def service_component_delete(request, pk):
    return crud_delete(request, model=ServiceComponent, pk=pk,
                       success_url="core:service_component_list")




# ============================================================== AlertRule
@tenant_admin_required
def alert_rule_list(request):
    return crud_list(
        request,
        AlertRule.objects.filter(tenant=request.tenant).select_related("service"),
        "core/alertrule/list.html",
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
            # `comparator_choices` is deliberately NOT passed: there is no comparator filter, and a
            # context key with no dropdown behind it is a key the template reads for nothing.
            # No `unbounded_count` either: `clean()` refuses an active rule with no bound, so that
            # count is structurally always 0 — a tautological number (0.8's zero rule on a tautology).
            "notes": MONITORING_NOTES,
        })


@tenant_admin_required
def alert_rule_create(request):
    return crud_create(request, form_class=AlertRuleForm,
                       template="core/alertrule/form.html",
                       success_url="core:alert_rule_list",
                       extra_context={"notes": MONITORING_NOTES})


@tenant_admin_required
def alert_rule_detail(request, pk):
    return crud_detail(
        request, model=AlertRule, pk=pk, template="core/alertrule/detail.html",
        select_related=("service", "notification_rule"),
        extra_context={
            "event_count": AlertEvent.objects.filter(tenant=request.tenant, rule_id=pk).count(),
            "open_event_count": AlertEvent.objects.filter(
                tenant=request.tenant, rule_id=pk,
                state__in=["firing", "acknowledged"]).count(),
            # Ordered by `-fired_at`, which is never NULL in this model, so the C5 MariaDB NULL-sorts-
            # LAST-under-DESC trap cannot apply (the same reason `BackupJob` had to be fixed).
            "latest_event": AlertEvent.objects.filter(tenant=request.tenant, rule_id=pk)
                                   .order_by("-fired_at").first(),
            "notes": MONITORING_NOTES,
        })


@tenant_admin_required
def alert_rule_edit(request, pk):
    return crud_edit(
        request, model=AlertRule, pk=pk, form_class=AlertRuleForm,
        template="core/alertrule/form.html",
        success_url=reverse("core:alert_rule_detail", args=[pk]),
        extra_context={"notes": MONITORING_NOTES})


@require_POST
@tenant_admin_required
def alert_rule_delete(request, pk):
    return crud_delete(request, model=AlertRule, pk=pk, success_url="core:alert_rule_list")




# ============================================================= AlertEvent
@tenant_admin_required
def alert_event_list(request):
    return crud_list(
        request,
        AlertEvent.objects.filter(tenant=request.tenant).select_related("rule", "service"),
        "core/alertevent/list.html",
        search_fields=["message", "detail", "evidence", "service_label"],
        # `?severity=` maps to the SNAPSHOT column `severity_at_fire`, not to a join on the rule: the
        # rule may have been re-tiered since, and history must not move with it.
        filters=[("state", "state", False), ("severity", "severity_at_fire", False),
                 ("rule", "rule_id", True), ("service", "service_id", True)],
        extra_context={
            "state_choices": AlertEvent.STATE_CHOICES,
            "severity_choices": AlertEvent.SEVERITY_CHOICES,
            "services": ServiceComponent.objects.filter(tenant=request.tenant).order_by("name"),
            # A real count on a real column, so 0 is a legitimate figure on a firing board.
            "firing_count": AlertEvent.objects.filter(tenant=request.tenant, state="firing").count(),
            # THE most useful number on this page: firings where nobody wrote down what the reading
            # actually was. This is the register's own honesty score, and it is a real count too.
            "unmeasured_count": AlertEvent.objects.filter(
                tenant=request.tenant, observed_value__isnull=True).count(),
            "notes": MONITORING_NOTES,
        })


@tenant_admin_required
def alert_event_create(request):
    return crud_create(request, form_class=AlertEventForm,
                       template="core/alertevent/form.html",
                       success_url="core:alert_event_list",
                       extra_context={"notes": MONITORING_NOTES})


@tenant_admin_required
def alert_event_detail(request, pk):
    return crud_detail(
        request, model=AlertEvent, pk=pk, template="core/alertevent/detail.html",
        select_related=("rule", "service", "acknowledged_by", "resolved_by"),
        extra_context={
            "incident_count": Incident.objects.filter(
                tenant=request.tenant, primary_alert_id=pk).count(),
            "related_incidents": list(Incident.objects.filter(tenant=request.tenant,
                                                              primary_alert_id=pk)
                                      .order_by("-created_at")),
            "notes": MONITORING_NOTES,
        })


@tenant_admin_required
def alert_event_edit(request, pk):
    return crud_edit(
        request, model=AlertEvent, pk=pk, form_class=AlertEventForm,
        template="core/alertevent/form.html",
        success_url=reverse("core:alert_event_detail", args=[pk]),
        extra_context={"notes": MONITORING_NOTES})


@require_POST
@tenant_admin_required
def alert_event_delete(request, pk):
    return crud_delete(request, model=AlertEvent, pk=pk, success_url="core:alert_event_list")




# ---- the three POST-only AlertEvent actions --------------------------------
# Each one is an EVENT with a time and an actor, so none of them is a field on the edit form: typing an
# acknowledgement into a form would let the register claim somebody did something they did not do, and
# attribution is the act an audit exists for. Each writes `write_audit_log` with a SHORT verb
# (`AuditLog.action` is `varchar(10)`) and the detail in `changes` — the `views/Localization.py` pattern.


@require_POST
@tenant_admin_required
def alertevent_acknowledge(request, pk):
    """Record that somebody looked at this firing.

    Guarded on `state != "firing"`: an event already acknowledged/resolved/expired has nothing to
    acknowledge, and a hand-made POST that flipped it back would rewrite a settled history.
    """
    obj = get_object_or_404(AlertEvent, pk=pk, tenant=request.tenant)
    if obj.state != "firing":
        messages.error(request, "This event is %s, so there is nothing to acknowledge. Only a firing is "
                                "waiting on a human." % obj.get_state_display())
        return redirect("core:alert_event_detail", pk=obj.pk)
    now = timezone.now()
    obj.state = "acknowledged"
    obj.acknowledged_at = now
    obj.acknowledged_by = request.user
    obj.save(update_fields=["state", "acknowledged_at", "acknowledged_by"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "alertevent_acknowledge", "state": obj.state,
                             "acknowledged_at": now.isoformat()})
    messages.success(request, "Acknowledged. This records that somebody looked at it — it does not "
                              "silence the alert; nothing in NavERP silences anything.")
    return redirect("core:alert_event_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def alertevent_resolve(request, pk):
    """Record that somebody declared this firing resolved.

    Guarded on `state in {"resolved", "expired"}` — refusing to re-resolve a settled event. The
    `resolution_note` comes from `request.POST` and is truncated to the column's 255 chars, because an
    untruncated string raises `DataError` inside the driver on save and the operator sees a 500 for a
    write that half-happened.
    """
    obj = get_object_or_404(AlertEvent, pk=pk, tenant=request.tenant)
    if obj.state in {"resolved", "expired"}:
        messages.error(request, "This event is already %s. Recording a second resolution would "
                                "overwrite the first one." % obj.get_state_display())
        return redirect("core:alert_event_detail", pk=obj.pk)
    now = timezone.now()
    note = (request.POST.get("resolution_note") or "").strip()[:255]
    obj.state = "resolved"
    obj.resolved_at = now
    obj.resolved_by = request.user
    obj.resolution_note = note
    obj.save(update_fields=["state", "resolved_at", "resolved_by", "resolution_note"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "alertevent_resolve", "state": obj.state,
                             "resolved_at": now.isoformat(), "resolution_note": note})
    messages.success(request, "Resolution recorded. NavERP did not fix anything — this records that "
                              "somebody said it was fixed.")
    return redirect("core:alert_event_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def alertevent_recur(request, pk):
    """Record that this firing came back.

    `occurrence_count` is incremented with `F()` so two concurrent POSTs cannot lose one another, and
    `last_seen_at` is stamped because "how long has it been flapping" is the question this board exists
    to answer. Guarded on the settled states for the same reason as resolve.
    """
    obj = get_object_or_404(AlertEvent, pk=pk, tenant=request.tenant)
    if obj.state in {"resolved", "expired"}:
        messages.error(request, "This event is %s, so a recurrence is a new report, not a recurrence of "
                                "this one. Record a new alert event instead."
                                % obj.get_state_display())
        return redirect("core:alert_event_detail", pk=obj.pk)
    now = timezone.now()
    obj.occurrence_count = F("occurrence_count") + 1
    obj.last_seen_at = now
    obj.save(update_fields=["occurrence_count", "last_seen_at"])
    obj.refresh_from_db(fields=["occurrence_count"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "alertevent_recur", "last_seen_at": now.isoformat(),
                             "occurrence_count": obj.occurrence_count})
    messages.success(request, "Recurrence recorded (now %d). Nothing is counting this automatically — "
                              "each recurrence is somebody pressing this button."
                     % obj.occurrence_count)
    return redirect("core:alert_event_detail", pk=obj.pk)




# =============================================================== Incident
@tenant_admin_required
def incident_list(request):
    return crud_list(
        request,
        (Incident.objects.filter(tenant=request.tenant)
         .select_related("service", "primary_alert").prefetch_related("affected_services")),
        "core/incident/list.html",
        search_fields=["title", "public_note", "internal_note"],
        # NOTE: the GET param is `type`, NOT `incident_type`.
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


@tenant_admin_required
def incident_create(request):
    return crud_create(request, form_class=IncidentForm,
                       template="core/incident/form.html",
                       success_url="core:incident_list",
                       extra_context={"notes": MONITORING_NOTES})


@tenant_admin_required
def incident_detail(request, pk):
    obj = get_object_or_404(Incident, pk=pk, tenant=request.tenant)
    affected = list(obj.affected_services.all())
    return render(request, "core/incident/detail.html", {
        "obj": obj,
        "affected": affected,
        # The ten most recent firings against ANY affected component — the "is this notice the whole
        # story" list. Ordered `-fired_at` (never NULL) so the C5 NULL-sort trap cannot apply.
        "alert_events": list(AlertEvent.objects.filter(tenant=request.tenant, service__in=affected)
                             .order_by("-fired_at")[:10]) if affected else [],
        "notes": MONITORING_NOTES,
    })


@tenant_admin_required
def incident_edit(request, pk):
    return crud_edit(
        request, model=Incident, pk=pk, form_class=IncidentForm,
        template="core/incident/form.html",
        success_url=reverse("core:incident_detail", args=[pk]),
        extra_context={"notes": MONITORING_NOTES})


@require_POST
@tenant_admin_required
def incident_delete(request, pk):
    return crud_delete(request, model=Incident, pk=pk, success_url="core:incident_list")


@require_POST
@tenant_admin_required
def incident_notify(request, pk):
    """Record that this notice was published.

    NavERP has **no status page, no subscriber list, no mailer and no webhook**, so this writes a
    timestamp and nothing else — the same posture as 0.16's `backup_job_verify`. Guarded on
    `notified_at` being unset, so a second POST cannot restamp a notice and imply a second publication
    of the same text.
    """
    obj = get_object_or_404(Incident, pk=pk, tenant=request.tenant)
    if obj.notified_at is not None:
        messages.error(request, "This notice was already recorded as published on %s. A second "
                                "publication would need different text — edit the notice first."
                       % obj.notified_at.strftime("%b %d, %Y %H:%M"))
        return redirect("core:incident_detail", pk=obj.pk)
    now = timezone.now()
    obj.notified_at = now
    obj.save(update_fields=["notified_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "incident_notify", "notified_at": now.isoformat()})
    messages.success(request, "Publication recorded. NavERP published nothing — it has no status page "
                              "and sends nothing. This row now claims somebody published it elsewhere.")
    return redirect("core:incident_detail", pk=obj.pk)




# ======================================================== the overview hub
@tenant_admin_required
def monitoring_overview(request):
    """COMPUTED landing page for 0.17 — stores nothing, measures nothing.

    **One query per model, then derive in Python.** A second `COUNT(*)` per figure is what took 0.16's
    equivalent page from 11 queries to 20 (the I3 lesson), so every row is fetched ONCE and every figure
    is counted off the list. Each is ordered **`-id`**, never a nullable column: MariaDB sorts NULLs
    LAST under `DESC`, which is the C5 trap that hid 0.16's queued backups.
    """
    tenant = request.tenant
    if tenant is None:
        messages.info(request, "Monitoring applies to a tenant workspace.")
        return redirect("dashboard:home")
    components = list(ServiceComponent.objects.filter(tenant=tenant)
                      .select_related("owner_role").order_by("-id"))
    rules = list(AlertRule.objects.filter(tenant=tenant).select_related("service").order_by("-id"))
    events = list(AlertEvent.objects.filter(tenant=tenant)
                  .select_related("rule", "service").order_by("-id"))
    incidents = list(Incident.objects.filter(tenant=tenant)
                     .select_related("service").order_by("-id"))
    # 0.1's readings are READ here, never copied into a 0.17 table (L36): a metric that exists in two
    # places is a metric that will disagree with itself.
    from apps.tenants.models import HealthMetric
    metrics = list(HealthMetric.objects.filter(tenant=tenant).order_by("-id")[:20])

    open_events = [e for e in events if e.is_open]
    context = {
        "component_total": len(components),
        "operational_count": sum(1 for c in components if c.current_status == "operational"),
        # Readable from one column, so a literal 0 is legitimate ONLY when there are components at all.
        # The template renders "not applicable" when `component_total == 0` rather than a green zero.
        "unreported_count": sum(1 for c in components if c.last_status_at is None),
        "rule_total": len(rules),
        "active_rule_count": sum(1 for r in rules if r.is_active),
        "firing_count": sum(1 for e in events if e.state == "firing"),
        "open_event_count": len(open_events),
        "unmeasured_count": sum(1 for e in events if e.observed_value is None),
        "active_incident_count": sum(1 for i in incidents if i.is_open),
        "latest_metrics": metrics,
        "notes": MONITORING_NOTES,
    }
    return render(request, "core/monitoringoverview.html", context)


# ============================================================== health board
#: Worst-wins order for the health roll-up. **`unknown` sits just above `operational` deliberately**:
#: "nobody has said" is not worse than a real outage and must not MASK one either, so a board of purely
#: unreported components rolls up to `unknown`, and one known outage rolls up to that outage.
_STATUS_SEVERITY = ["major_outage", "partial_outage", "degraded", "unknown", "operational"]


@tenant_admin_required
def health_board(request):
    """Bullet 1. The roll-up is DERIVED here and never stored (the SCM L37 posture).

    There is no `tenant.uptime` column and no roll-up field: a stored roll-up would freeze one bad hour
    on the workspace forever, and 0.20 must LINK to this board rather than re-derive health.
    """
    tenant = request.tenant
    if tenant is None:
        messages.info(request, "Health monitoring applies to a tenant workspace.")
        return redirect("dashboard:home")
    from apps.tenants.models import HealthMetric

    components = list(ServiceComponent.objects.filter(tenant=tenant, is_active=True)
                      .select_related("owner_role").order_by("display_order", "name"))
    open_alerts = (AlertEvent.objects.filter(tenant=tenant, service_id__in=[c.pk for c in components],
                                             state__in=["firing", "acknowledged"])
                   .values("service_id").annotate(n=Count("id")))
    per_component = {row["service_id"]: row["n"] for row in open_alerts}
    # Newest reading per metric: `HealthMetric.Meta.ordering` is `-created_at` (never NULL), so this
    # keeps the C5 trap out of the "latest per metric" window too.
    metrics = list(HealthMetric.objects.filter(tenant=tenant).order_by("-id")[:40])
    latest_metrics = []
    for m in metrics:
        if m.metric not in [seen.metric for seen in latest_metrics]:
            latest_metrics.append(m)

    # Every STATUS_CHOICES key present, defaulting to 0, so the template can loop the choices without a
    # `.get` and without inventing a key the model does not declare.
    status_counts = {value: 0 for value, _ in ServiceComponent.STATUS_CHOICES}
    for c in components:
        status_counts[c.current_status] = status_counts.get(c.current_status, 0) + 1

    rollup = "operational"
    for c in components:
        if c.is_active and _STATUS_SEVERITY.index(c.current_status) < _STATUS_SEVERITY.index(rollup):
            rollup = c.current_status
    if not components:
        # NEVER "operational" by default: no components means no claim, and an all-green board over an
        # empty register is the false all-clear 0.8 refuses.
        rollup = "unknown"

    return render(request, "core/healthboard.html", {
        "components": [{"component": c, "open_alerts": per_component.get(c.pk, 0),
                        "note": c.status_note()} for c in components],
        "component_total": len(components),
        "critical_count": sum(1 for c in components if c.is_critical),
        "public_count": sum(1 for c in components if c.is_public),
        "status_counts": status_counts,
        "unreported_count": sum(1 for c in components if c.last_status_at is None),
        "open_alert_count": sum(per_component.values()),
        "latest_metrics": latest_metrics,
        "rollup_status": rollup,
        "notes": MONITORING_NOTES,
    })




# ============================================================= firing board
@tenant_admin_required
def firing_board(request):
    """Bullet 2. **The zero rule is the whole point of this page.**

    An empty board must never render as "healthy". If nothing is firing it is because **nothing
    evaluates these rules**, not because everything is fine — and `rule_total` is the denominator that
    makes the empty case honest, so the template can say "no rules registered" instead of "0 firing".
    """
    tenant = request.tenant
    if tenant is None:
        messages.info(request, "Alert firings apply to a tenant workspace.")
        return redirect("dashboard:home")

    events = list(AlertEvent.objects.filter(tenant=tenant)
                  .select_related("rule", "service").order_by("-fired_at", "-id"))
    open_events = [e for e in events if e.is_open]
    state_counts = {value: 0 for value, _ in AlertEvent.STATE_CHOICES}
    severity_counts = {value: 0 for value, _ in AlertEvent.SEVERITY_CHOICES}
    for e in events:
        state_counts[e.state] = state_counts.get(e.state, 0) + 1
        severity_counts[e.severity_at_fire] = severity_counts.get(e.severity_at_fire, 0) + 1

    return render(request, "core/firingboard.html", {
        "open_events": [{"event": e, "age_days": e.age_days, "muted": e.is_muted,
                         "note": e.measure_note()} for e in open_events],
        "open_count": len(open_events),
        "acknowledged_count": sum(1 for e in open_events if e.state == "acknowledged"),
        "muted_count": sum(1 for e in open_events if e.is_muted),
        "state_counts": state_counts,
        "severity_counts": severity_counts,
        # The denominator. Without it, "0 firing" is indistinguishable from "nothing is watching".
        "rule_total": AlertRule.objects.filter(tenant=tenant).count(),
        # Open firings whose rule was retired (or never registered) — nobody owns these.
        "unattributed_count": sum(1 for e in open_events if e.rule_id is None),
        "notes": MONITORING_NOTES,
    })


# =========================================================== capacity board
@tenant_admin_required
def capacity_board(request):
    """Bullet 4. **0.17 contributes the scaling trigger, not the quota.**

    `tenants.UsageRecord` (0.1) owns consumption and derives overage; 0.19 owns the commercial
    allowance. This page READS `UsageRecord.quantity` / `.included_allowance` and sets them beside the
    bound an operator declared on an `AlertRule` — it never recomputes an overage, because a second
    copy of that derivation is the parallel-schema bug L36 forbids.
    """
    tenant = request.tenant
    if tenant is None:
        messages.info(request, "Capacity reporting applies to a tenant workspace.")
        return redirect("dashboard:home")
    from apps.tenants.models import UsageRecord

    usage = list(UsageRecord.objects.filter(tenant=tenant)
                 .select_related("subscription").order_by("-period_start", "-id"))
    # Newest record per metric — one row per metered metric, which is what this board is about.
    usage_rows = []
    seen_metrics = set()
    for u in usage:
        if u.metric in seen_metrics:
            continue
        seen_metrics.add(u.metric)
        included = u.included_allowance
        if included is None:
            note = ("Unmetered on this plan — there is no included allowance, so no overage can be "
                    "computed. This is not a zero allowance.")
        else:
            note = ("Consumption and allowance both come from the usage record; overage is derived "
                    "there and is not recomputed here.")
        usage_rows.append({"metric": u.get_metric_display(), "quantity": u.quantity,
                           "included": included,
                           "overage": u.overage_quantity if included is not None else None,
                           "note": note})

    capacity_rules = list(AlertRule.objects.filter(tenant=tenant, category="capacity")
                          .select_related("service").order_by("name"))
    capacity_rows = []
    over_threshold_count = 0
    for r in capacity_rules:
        bound = r.critical_threshold if r.critical_threshold is not None else r.warning_threshold
        # `get_metric_key_display`, not `get_metric_display`: the FIELD is `metric_key` (Django derives
        # the accessor from the field name), so the shorter name is an AttributeError and this board 500s
        # the moment a capacity rule exists. Caught by the smoke test, not by `manage.py check`.
        matching = [row for row in usage_rows if row["metric"] == r.get_metric_key_display()]
        current = matching[0]["quantity"] if matching else None
        if bound is None or current is None:
            headroom = None
            note = ("Cannot compare: the rule has no bound set, or this workspace has no consumption "
                    "recorded for the metric. Neither side is reported as 0.")
        else:
            headroom = bound - current
            if current > bound:
                over_threshold_count += 1
                note = "Recorded consumption is above the declared bound. Nothing acts on that."
            else:
                note = "Recorded consumption is within the declared bound."
        capacity_rows.append({"rule": r, "headroom": headroom, "note": note,
                              "bound": bound, "current": current})

    unmetered_count = sum(1 for row in usage_rows if row["included"] is None)
    return render(request, "core/capacityboard.html", {
        "usage_rows": usage_rows,
        "capacity_rules": capacity_rows,
        "rule_count": len(capacity_rules),
        "over_threshold_count": over_threshold_count,
        "unmetered_count": unmetered_count,
        "notes": MONITORING_NOTES,
    })

