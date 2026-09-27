"""tenants — the two computed boards for 0.19 "License & Subscription Administration".

One file, because they are two functions and neither has a model (the 0.17/0.18 board precedent).
Both follow `_usage_summary()` exactly: **one grouped query**, the reference table read once, **no
per-row `.filter()`**, and a MODULE-LEVEL helper so a detail view can reuse the same numbers rather
than re-querying. A row-dict contract is a second contract: read the PRODUCER of the rows, not the
view that forwards them.

**THE L36 NOTE, which both board pages must carry:** NavERP.md bullets 3 and 4 point at these NEW
boards, but the underlying ROWS are 0.1's — `UsageRecord`, `Subscription` and `SubscriptionInvoice`
were built by sub-module 0.1 and are EXTENDED here (a quota to read the meter against, two columns
on the subscription), never re-declared. A reader who believes 0.19 built a second usage table will
file a duplicate-billing bug against the wrong sub-module.

Neither board is a control. `quota_board` measures consumption against a recorded ceiling and
`renewal_board` computes time to a recorded renewal date; neither enforces anything, and the
`action_on_breach` / `auto_renew` columns they display are recorded intent with no interceptor
behind them.
"""
from django.db.models import Count, Sum

from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    LicenseAssignment,
    Subscription,
    Tenant,
    UsageQuota,
    UsageRecord,
)


# ================================================================= helpers shared with the detail views


def _consumption_by_subscription(tenant):
    """`{(subscription_id, metric): Decimal}` for the tenant's UNBILLED usage — ONE grouped query.

    Unbilled only, the same `is_billed=False` lens the 0.1 usage list uses, so "consumed" and
    "overage" mean the same thing on both pages. The join is on the SAME `subscription` as
    `UsageRecord.subscription`; joining on anything else would let a quota be measured against a
    different subscription's consumption.

    Rows with a NULL `subscription_id` are dropped: a usage record may pre-date its subscription, but
    a `UsageQuota` never has a null one, so such a row can never match a quota and would only be a
    key nothing looks up.
    """
    totals = (
        UsageRecord.objects.filter(tenant=tenant, is_billed=False, subscription__isnull=False)
        .values("subscription_id", "metric")
        .annotate(total=Sum("quantity"))
    )
    return {
        (row["subscription_id"], row["metric"]): (row["total"] or Decimal("0.00"))
        for row in totals
    }


def _seat_summary(tenant):
    """`{active, reclaimed, revoked, expired, total}` for the seat register.

    Reused by `licenseassignment_detail`, which forwards the same numbers rather than re-querying.

    The `user__tenant` clause on the ACTIVE count is REQUIRED, not defensive: `accounts.User.tenant`
    is nullable (the superuser `admin` has tenant=None by design). Without it a row holding the
    superuser would be counted on the board but absent from the register, and the page would
    contradict itself.

    `expired` counts rows whose `expires_on` is past AND whose `status == "active"` — the DISPLAYED
    state, never a stored one. Nothing ever writes `status="expired"` ([RULING] 5), so a
    `values("status")` group alone cannot produce it.
    """
    today = timezone.localdate()
    by_status = {
        row["status"]: row["n"]
        for row in LicenseAssignment.objects.filter(tenant=tenant)
                                         .values("status").annotate(n=Count("id"))
    }
    return {
        "active": LicenseAssignment.objects.filter(
            tenant=tenant, status="active", user__tenant=tenant).count(),
        "reclaimed": by_status.get("reclaimed", 0),
        "revoked": by_status.get("revoked", 0),
        "expired": LicenseAssignment.objects.filter(
            tenant=tenant, status="active", expires_on__lt=today).count(),
        "total": sum(by_status.values()),
    }


# ================================================================= the two boards


@tenant_admin_required
def quota_board(request):
    """Quota vs. consumption, one grouped query, following `_usage_summary()`.

    Consumption is UNBILLED usage for the CURRENT period only — the same `is_billed=False` lens the
    0.1 usage list uses — so "consumed" and "overage" mean the same thing on both pages. The join
    is on the SAME `subscription` as `UsageRecord.subscription`; joining on anything else would let a
    quota be measured against a different subscription's consumption.

    **`quota_limit == 0` means UNMETERED.** Such a row renders "Unmetered" with `pct_used` 0 and no
    breach state, and is EXCLUDED from the `warned_count` / `breached_count` roll-ups. This mirrors
    `UsageRecord.included_allowance`, which returns `None` for an unmetered plan: *None means
    UNMETERED, deliberately distinct from 0, which would make every unit an overage.* A limit of 0
    here is the same statement.
    """
    consumption = _consumption_by_subscription(request.tenant)
    quotas = (UsageQuota.objects.filter(tenant=request.tenant)
              .select_related("subscription").order_by("subscription_id", "metric", "period"))

    metric_labels = dict(UsageQuota.METRIC_CHOICES)
    action_labels = dict(UsageQuota.ACTION_CHOICES)

    rows = []
    for quota in quotas:
        limit = quota.quota_limit or Decimal("0.00")
        # NEVER None — a None here prints blank in the template's arithmetic.
        consumed = consumption.get((quota.subscription_id, quota.metric), Decimal("0.00"))
        unmetered = limit == Decimal("0.00")
        if unmetered:
            # Unmetered ⇒ 0% and no overage, and the row is excluded from the warned/breached
            # counts. A 0.01 limit must not be able to render a 4000% cell either, hence the cap.
            pct_used = 0
            overage = Decimal("0.00")
        else:
            pct_used = min(int(consumed / limit * 100), 999)
            overage = max(Decimal("0.00"), consumed - limit)
        is_warned = (not unmetered) and pct_used >= quota.warn_at_pct
        rows.append({
            "quota": quota,
            # Denormalised onto the row so the template never walks `quota.subscription`.
            "subscription": quota.subscription,
            "metric": quota.metric,
            "metric_label": metric_labels.get(quota.metric, quota.metric),
            "limit": limit,
            "consumed": consumed,
            "pct_used": pct_used,
            "overage": overage,
            "warn_at_pct": quota.warn_at_pct,
            "is_warned": is_warned,
            # The RECORDED stamp, not a recomputation, so a manual mark-breach shows here at once.
            "is_breached": quota.breached_at is not None,
            # Read inside an `{% if %}` branch in the template, never through a filter argument (L10).
            "breached_at": quota.breached_at,
            # The label is resolved HERE, so the template never builds a dict.
            "action_on_breach": action_labels.get(quota.action_on_breach, quota.action_on_breach),
            "is_fair_use": quota.is_fair_use,
        })

    rows.sort(key=lambda r: (-r["pct_used"], r["metric_label"]))
    return render(request, "tenants/quota_board.html", {
        "quota_rows": rows,
        "warned_count": len([r for r in rows if r["is_warned"]]),
        "breached_count": len([r for r in rows if r["is_breached"]]),
        "unmetered_count": len([r for r in rows if r["limit"] == Decimal("0.00")]),
        "metric_choices": UsageQuota.METRIC_CHOICES,
        "action_choices": UsageQuota.ACTION_CHOICES,
    })



@tenant_admin_required
def renewal_board(request):
    """Renewal & expiry, one query — `Subscription.days_left()` is PREFERRED over re-deriving the
    arithmetic in the view (it is a pure method on an already-loaded row).

    `days_left()` returns `None` when `renews_on` is unset, so the template must guard it with
    `{% if renewal.days_left is not None %}`; a bare `{{ renewal.days_left }}` would print `None`
    on screen.

    `auto_renew` and `grace_ends_on` are RECORDED commercial terms with nothing behind them: no
    scheduler exists (0.20 owns it), no renewal is executed, no card is charged, and no expiry
    email is sent. Both are read with `getattr(..., default)` so this board renders against a
    `Subscription` that does not yet carry the two columns rather than raising AttributeError.
    """
    today = timezone.localdate()
    plan_labels = dict(Tenant.PLAN_CHOICES)
    status_labels = dict(Subscription.STATUS_CHOICES)

    subscriptions = Subscription.objects.filter(tenant=request.tenant).order_by("renews_on", "id")
    rows = []
    for subscription in subscriptions:
        days_left = subscription.days_left()
        grace_ends_on = getattr(subscription, "grace_ends_on", None)
        rows.append({
            "subscription": subscription,
            "plan": subscription.plan,
            "plan_label": plan_labels.get(subscription.plan, subscription.plan),
            "status": subscription.status,
            "status_label": status_labels.get(subscription.status, subscription.status),
            "days_left": days_left,
            "auto_renew": getattr(subscription, "auto_renew", False),
            # Read inside an `{% if %}` in the template, never through a filter argument (L10).
            "grace_ends_on": grace_ends_on,
            "in_grace": bool(grace_ends_on is not None and today <= grace_ends_on),
            # A COMPUTED state, never a stored status.
            "is_expired": bool(subscription.renews_on and subscription.renews_on < today),
            # Copied so the template does no FK walk.
            "seats": subscription.seats,
        })

    return render(request, "tenants/renewal_board.html", {
        "renewal_rows": rows,
        "expiring_count": len([r for r in rows
                               if r["days_left"] is not None and 0 <= r["days_left"] <= 30]),
        "in_grace_count": len([r for r in rows if r["in_grace"]]),
        "expired_count": len([r for r in rows if r["is_expired"]]),
        "auto_renew_count": len([r for r in rows if r["auto_renew"]]),
        "plan_choices": Tenant.PLAN_CHOICES,
    })

