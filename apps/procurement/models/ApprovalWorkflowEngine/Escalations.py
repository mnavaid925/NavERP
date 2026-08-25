"""Procurement 6.3 Approval Workflow Engine — Escalation Management.

**Escalation Management** bullet: "Automated escalation to a backup approver or
manager if an approval sits idle." Two halves, honestly separated:

* ``EscalationPolicy`` is the tenant's ONE standing knob — the idle window (a
  routing rule may override it per queue) and the backup approver raised alerts
  are assigned to (blank raises to the team, the 6.1 alert posture).
* :func:`escalation_candidates` / :func:`run_escalations` are the engine. There is
  deliberately NO scheduler in this codebase, so "automated" means one idempotent
  Run action on the escalation board that anyone on the tenant can fire; it raises
  a ``ProcurementAlert`` (kind=approval) per idle chain — exactly what 6.1's alert
  docstring promised this sub-module would do — and skips requisitions that
  already have an open escalation alert (the dedupe guard; MariaDB cannot express
  the partial unique that rule would want).
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from apps.core.utils import write_audit_log

from apps.procurement.models._base import *  # noqa: F401,F403

#: Cap on how many pending chains one evaluation loads — a review aid, not an export.
ESCALATION_CANDIDATE_CAP = 100


class EscalationPolicy(TenantOwned):
    """The tenant's standing escalation configuration (one row per workspace)."""

    idle_hours = models.PositiveIntegerField(
        default=48,
        help_text="A pending approval idle longer than this escalates; a routing rule "
                  "may override per queue")
    escalate_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_escalations_received",
        help_text="Backup approver escalation alerts are assigned to; blank = raised to the team")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"Escalate after {self.idle_hours}h → {self.escalate_to or 'team'}"

    @classmethod
    def for_tenant(cls, tenant):
        """The workspace's singleton policy, created on first touch."""
        obj, _created = cls.objects.get_or_create(tenant=tenant)
        return obj

    def clean(self):
        super().clean()
        if (self.escalate_to is not None
                and self.escalate_to.tenant_id != self.tenant_id):
            raise ValidationError(
                {"escalate_to": "That record belongs to another workspace."})


def _alert_link(requisition_pk):
    """The exact internal path escalation alerts carry (6.1 renders hrefs from these)."""
    return f"/scm/requisitions/{requisition_pk}/"


def escalation_candidates(tenant, policy=None, *, rules=None, limit=ESCALATION_CANDIDATE_CAP):
    """Pending approval chains with their idle clock — longest-idle first.

    One flat pass: pending requisitions, their existing decisions (one grouped
    query), and each chain's resolved routing rule (the caller may preload once).
    Idle-from is the LAST signature's moment (or the requisition's creation when
    nobody has signed); the effective window is the routing rule's own
    ``escalation_hours`` — where 0 is a legitimate "escalate immediately", so only
    ``None`` falls back to the policy — and each row carries ``escalated`` (an open
    kind=approval alert already points at this requisition) plus a display-ready
    ``idle_hours_f``. ``limit=None`` evaluates EVERY pending chain: the Run verb
    passes it so chains beyond the board's rendering cap still escalate.
    """
    from apps.procurement.models import (
        ApprovalRoutingRule,
        ProcurementAlert,
        RequisitionApproval,
        resolve_routing,
    )
    from apps.scm.models import PurchaseRequisition

    if policy is None:
        policy = EscalationPolicy.for_tenant(tenant)
    if rules is None:
        rules = list(ApprovalRoutingRule.objects.filter(
            tenant=tenant, is_active=True).select_related("org_unit"))

    pending_qs = (PurchaseRequisition.objects.filter(tenant=tenant,
                                                     status="pending_approval")
                  .select_related("requester", "org_unit").order_by("created_at"))
    pending = list(pending_qs[:limit] if limit else pending_qs)
    last_signature = dict(
        RequisitionApproval.objects.filter(
            tenant=tenant, requisition_id__in=[r.pk for r in pending])
        .values_list("requisition_id")
        .annotate(last=Max("decided_at")))
    open_alert_links = set(
        ProcurementAlert.objects.filter(
            tenant=tenant, kind="approval",
            status__in=ProcurementAlert.OPEN_STATUSES,
            link_url__in=[_alert_link(r.pk) for r in pending])
        .values_list("link_url", flat=True))

    now = timezone.now()
    rows = []
    for req in pending:
        rule, _reason = resolve_routing(req, rules=rules)
        hours = (rule.escalation_hours
                 if rule is not None and rule.escalation_hours is not None
                 else policy.idle_hours)
        anchor = last_signature.get(req.pk) or req.created_at
        idle_for = now - anchor
        rows.append({
            "requisition": req,
            "rule": rule,
            "idle_hours_effective": hours,
            "window_is_rule": rule is not None and rule.escalation_hours is not None,
            "anchor": anchor,
            "idle_for": idle_for,
            "idle_hours_f": round(idle_for.total_seconds() / 3600, 1),
            "is_idle": idle_for > timedelta(hours=hours),
            "escalated": _alert_link(req.pk) in open_alert_links,
        })
    rows.sort(key=lambda row: (-row["idle_for"].total_seconds(),
                               row["requisition"].id))
    return rows


def run_escalations(tenant, user, policy=None, *, candidates=None):
    """Raise one alert per idle, not-yet-escalated chain. Idempotent by the
    open-alert probe inside the caller's atomic block — and the caller holds the
    policy row lock, which serializes concurrent Runs per tenant. Evaluates EVERY
    pending chain (``limit=None``), not just the board's rendering cap. Returns
    the summary dict."""
    from apps.procurement.models import ProcurementAlert

    if candidates is None:
        candidates = escalation_candidates(tenant, policy, limit=None)
    elif policy is None:
        policy = EscalationPolicy.for_tenant(tenant)
    now = timezone.now()
    raised = skipped_open = 0
    for row in candidates:
        if not row["is_idle"]:
            continue
        if row["escalated"]:
            skipped_open += 1
            continue
        req = row["requisition"]
        ProcurementAlert.objects.create(
            tenant=tenant, kind="approval", severity="warning", status="open",
            title=f"Approval idle: {req.number}",
            message=(f"{req.number} '{req.title}' has sat in approval for "
                     f"{int(row['idle_for'].total_seconds() // 3600)}h "
                     f"(window {row['idle_hours_effective']}h). "
                     f"Signed so far: see the approval history."),
            link_url=_alert_link(req.pk),
            assigned_to=policy.escalate_to,
            created_by=user)
        write_audit_log(user, policy, "escalation_raise",
                        {"requisition": req.number})
        raised += 1
    summary = {"checked": len(candidates), "raised": raised,
               "skipped_open": skipped_open}
    write_audit_log(user, policy, "escalation_run", summary)
    return summary
