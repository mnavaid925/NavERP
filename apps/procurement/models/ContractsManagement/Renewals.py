"""Procurement 6.8 Contract Management — Renewal & Expiration alert engine.

**Renewal & Expiration Alerts** bullet: "Automated notifications for upcoming
contract expirations or auto-renewals." There is deliberately NO scheduler in this
codebase (the 6.3 escalation ruling), so "automated" means one idempotent Run action
on the renewal board: it scans the SCM-owned agreement spine for agreements inside
their own notice window and raises a ``ProcurementAlert`` (6.1's inbox, kind
``contract``) per contract — skipping contracts that already have an OPEN alert so
double-Runs stay silent (the escalation-engine dedupe posture).

The window is PER CONTRACT: ``renewal_notice_days`` before ``end_date``. Auto-renewing
agreements get the same heads-up — the point is that a human decides before the
mechanical renewal lands, not that the contract dies.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.utils import write_audit_log


def _alert_link(contract_pk):
    """The exact internal path alerts carry (6.1 renders hrefs from these)."""
    return f"/scm/contracts/{contract_pk}/"


def expiring_contracts(tenant, *, on=None):
    """Agreements whose renewal/expiration decision window is open, soonest first.

    A contract enters its window when ``end_date - renewal_notice_days <= today``
    and it is still live (active/expiring per the spine's own vocabulary). Contracts
    with no end date never expire, so they never appear.
    """
    from apps.scm.models import SupplierContract

    today = (on or timezone.localdate())
    qs = (SupplierContract.objects
          .filter(tenant=tenant, status__in=("active", "expiring"))
          .exclude(end_date__isnull=True)
          .select_related("party", "owner")
          .order_by("end_date", "id"))
    rows = []
    for contract in qs:
        window_start = contract.end_date - timedelta(days=contract.renewal_notice_days)
        if today >= window_start:
            rows.append({
                "contract": contract,
                "days_left": (contract.end_date - today).days,
                "auto_renews": contract.auto_renew,
            })
    return rows


def run_renewal_alerts(tenant, user):
    """Raise one alert per in-window contract; idempotent against OPEN duplicates.

    Returns ``{"raised": n, "skipped_open": n}`` like the 6.3 engine. Severity:
    critical once the end date is within 7 days or already past, warning otherwise.
    """
    from apps.procurement.models import ProcurementAlert
    from apps.scm.models import SupplierContract

    raised = skipped = 0
    for row in expiring_contracts(tenant):
        contract = row["contract"]
        # Dedupe is check-then-create — two concurrent Runs could both find no open
        # alert and both raise. Taking the CONTRACT row lock makes one contract's
        # check+create sequential against every other Run scanning that agreement.
        with transaction.atomic():
            locked = SupplierContract.objects.select_for_update().get(pk=contract.pk)
            if ProcurementAlert.objects.filter(
                    tenant=tenant, kind="contract",
                    link_url=_alert_link(locked.pk),
                    status__in=("open", "acknowledged")).exists():
                skipped += 1
                continue
            days = row["days_left"]
            action = ("auto-renews" if row["auto_renews"] else "expires")
            ProcurementAlert.objects.create(
                tenant=tenant,
                kind="contract",
                severity="critical" if days <= 7 else "warning",
                status="open",
                title=f"{locked.number} {action} on {locked.end_date:%d %b %Y}",
                message=(f"{locked.title} with {locked.party.name} {action} in {days} day(s) "
                         f"(notice window {locked.renewal_notice_days}d). Decide: renew, "
                         f"renegotiate via an amendment, or let it lapse."),
                link_url=_alert_link(locked.pk),
                due_at=None,
            )
            raised += 1
    return {"raised": raised, "skipped_open": skipped}


@transaction.atomic
def run_renewal_alerts_audited(tenant, user):
    """Transactional wrapper used by the view verb: runs the scan + writes the audit row."""
    summary = run_renewal_alerts(tenant, user)
    write_audit_log(user, None, "contract_renewals_run",
                    {"raised": summary["raised"], "skipped_open": summary["skipped_open"]})
    return summary
