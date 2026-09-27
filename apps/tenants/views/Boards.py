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
from datetime import timedelta

from django.db.models import Count, Q, Sum

from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    LicenseAssignment,
    Subscription,
    Tenant,
    UsageQuota,
    UsageRecord,
)

#: How many rows `renewal_board` RENDERS. The board is a roll-up, not a register — the paginated
#: register is `subscription_list`. The cap is here so the view and the page prose quote the same
#: number, and so it is one edit if the number is wrong.
RENEWAL_BOARD_ROW_CAP = 200


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

    Two queries become ONE (I9): a single `values("status")` group carries the three status
    counts, the total and `expired` as a filtered aggregate. `expired` is `status == "active"`
    AND `expires_on` in the past, so it lives naturally inside the `active` group's row — nothing
    ever writes `status="expired"` ([RULING] 5), which is exactly why a bare status group cannot
    produce it, and why the DISPLAYED state has to be counted rather than grouped.

    The `user__tenant` clause lives on ONE queryset, so it cannot be applied to one number and
    forgotten on another. The shipped code applied it to the ACTIVE count only, so for a row
    holding a null-tenant user the five numbers rendered side by side on the seat detail page
    disagreed with each other: `total` counted the row, `active` did not, and the register the
    page links to did show it. `accounts.User.tenant` is nullable (the superuser has tenant=None
    by design) and the Django admin is not tenant-scoped, so that row is constructible. Ninety-nine
    percent of workspaces never see it, which is exactly why it needed saying.
    """
    today = timezone.localdate()
    by_status = {
        row["status"]: row
        for row in LicenseAssignment.objects.filter(tenant=tenant, user__tenant=tenant)
                                     .values("status")
                                     .annotate(
                                         n=Count("id"),
                                         expired=Count(
                                             "id",
                                             filter=Q(expires_on__lt=today),
                                         ),
                                     )
    }
    active = by_status.get("active", {"n": 0, "expired": 0})
    return {
        "active": active["n"],
        "reclaimed": by_status.get("reclaimed", {}).get("n", 0),
        "revoked": by_status.get("revoked", {}).get("n", 0),
        # Inside the `active` group, so every row counted here is a row `active` counts too.
        "expired": active["expired"],
        "total": sum(row["n"] for row in by_status.values()),
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
        # I3: `metric_choices` and `action_choices` are GONE, not unused. The board has no filter
        # bar, and every headline number above is computed over the UNFILTERED row set, so a
        # filter would print "2 marked as breached" above a table holding zero breached rows. The
        # board's value is that the number and the row are the same fact. The decision is written
        # down in the template's own header comment.
    })



@tenant_admin_required
def renewal_board(request):
    """Renewal & expiry: ONE aggregate query for the headline numbers, one capped fetch for the rows.

    `Subscription.days_left()` is still PREFERRED over re-deriving the arithmetic in the view for
    the ROWS (it is a pure method on an already-loaded row), but the four stat cards are database
    AGGREGATES, not `len()` of what was rendered. `days_left()` returns `None` when `renews_on` is
    unset, so the template must guard it with `{% if row.days_left is not None %}`; a bare
    `{{ row.days_left }}` would print `None` on screen.

    **The cap and the counts are two different facts, and the page says so.** The table renders at
    most `RENEWAL_BOARD_ROW_CAP` rows; the tiles count every subscription in the workspace. That is
    deliberate — deriving the tiles from the visible rows would make them report the cap, which is
    the confident lie this project refuses to ship — but it is only honest while the reader is
    told, so `rows_truncated` is passed and the template states the cap whenever it is true.

    `auto_renew` and `grace_ends_on` are RECORDED commercial terms with nothing behind them: no
    scheduler exists (0.20 owns it), no renewal is executed, no card is charged, and no expiry
    email is sent. Both are read with `getattr(..., default)` in the row loop so this board renders
    against a `Subscription` that does not yet carry the two columns rather than raising
    AttributeError.
    """
    today = timezone.localdate()
    plan_labels = dict(Tenant.PLAN_CHOICES)
    status_labels = dict(Subscription.STATUS_CHOICES)

    base = Subscription.objects.filter(tenant=request.tenant)
    # I8: the four headline counts are AGGREGATES over the whole workspace, NOT `len()` of the
    # rows this page happens to render. Capping the rows and leaving `len()` in place would be
    # worse than doing nothing: the stat cards would quietly start reporting the cap instead of
    # the workspace, which is the confident lie this project refuses to ship. The count and the
    # row must be the same fact, so a subscription past its date counts as expired whether or not
    # it made it into the first 200 rows - and the page says the cap out loud.
    counts = base.aggregate(
        # 0 <= days_left <= 30, i.e. renews_on between today and today+30. NULL renews_on is
        # excluded by the comparison, matching the row loop's `days_left is not None` guard.
        expiring=Count("id", filter=Q(renews_on__gte=today, renews_on__lte=today + timedelta(days=30))),
        expired=Count("id", filter=Q(renews_on__lt=today)),
        in_grace=Count("id", filter=Q(grace_ends_on__isnull=False, grace_ends_on__gte=today)),
        auto_renew=Count("id", filter=Q(auto_renew=True)),
        # The untruncated size of the workspace, so the page can state the cap honestly.
        total=Count("id"),
    )

    # The rows themselves ARE capped, because `Subscription` only ever grows and this board is
    # a roll-up, not a register - the register is `subscription_list`, which paginates.
    subscriptions = base.order_by("renews_on", "id")[:RENEWAL_BOARD_ROW_CAP]
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
        "expiring_count": counts["expiring"],
        "in_grace_count": counts["in_grace"],
        "expired_count": counts["expired"],
        "auto_renew_count": counts["auto_renew"],
        # I8, honesty half: the stat cards are computed over the WHOLE workspace, the table is
        # capped. The page must therefore say so, or a reader counts 200 rows against a tile
        # reading 214 and concludes the board is broken. `rows_truncated` is the one condition
        # under which the two numbers legitimately differ, and the template only mentions the
        # cap when it is true.
        "renewal_total": counts["total"],
        "row_cap": RENEWAL_BOARD_ROW_CAP,
        "rows_truncated": counts["total"] > len(rows),
        # I3: `plan_choices` is GONE, not unused. The board has no filter bar, and every headline
        # number is computed over the UNFILTERED set, so a filter would split the stat cards from
        # the rows beneath them. The decision is written down in the template's header comment.
    })

