"""tenants — UsageRecord views (0.1 "Subscription & Billing — usage metering")."""
from django.db.models import Sum

from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    PLAN_ALLOWANCES,
    Subscription,
    UsageRecord,
)
from apps.tenants.forms import (
    UsageRecordForm,
)


def _usage_summary(tenant):
    """Unbilled usage per metric, with the plan allowance and the derived overage.

    Computed in the VIEW off one grouped query rather than per-row model properties: a derived
    property calling `.filter()` bypasses any prefetch cache and re-queries per render. The
    allowance table is read once for the tenant's newest subscription, so this stays at a
    constant number of queries regardless of how many metrics the tenant is metered on.
    """
    totals = (
        UsageRecord.objects.filter(tenant=tenant, is_billed=False)
        .values("metric")
        .annotate(total=Sum("quantity"))
        .order_by("metric")
    )
    subscription = Subscription.objects.filter(tenant=tenant).order_by("-created_at").first()
    allowances = PLAN_ALLOWANCES.get(subscription.plan, {}) if subscription else {}

    labels = dict(UsageRecord.METRIC_CHOICES)
    rows = []
    for row in totals:
        total = row["total"] or Decimal("0.00")
        allowance = allowances.get(row["metric"])
        overage = Decimal("0.00")
        if allowance is not None:
            overage = max(Decimal("0.00"), total - Decimal(allowance))
        rows.append({
            "metric": row["metric"],
            "label": labels.get(row["metric"], row["metric"]),
            "total": total,
            "allowance": allowance,
            "overage": overage,
        })
    return rows, subscription


# ============================================================ Usage metering
@tenant_admin_required
def usagerecord_list(request):
    qs = (
        UsageRecord.objects.filter(tenant=request.tenant)
        .select_related("subscription", "subscription_invoice")
    )
    # `is_billed` is a boolean, and crud_list's filter spec passes the raw GET string to the ORM,
    # where "yes"/"no" is not a valid BooleanField value — so the billed lens is applied here.
    billed = request.GET.get("billed", "").strip()
    if billed in ("yes", "no"):
        qs = qs.filter(is_billed=(billed == "yes"))

    summary, subscription = _usage_summary(request.tenant)
    return crud_list(
        request, qs,
        "tenants/usagerecord/list.html",
        search_fields=["metric", "notes"],
        filters=[("metric", "metric", False)],
        extra_context={
            "metric_choices": UsageRecord.METRIC_CHOICES,
            "billed_choices": [("yes", "Billed"), ("no", "Unbilled")],
            "usage_summary": summary,
            "subscription": subscription,
        },
    )


@tenant_admin_required
def usagerecord_create(request):
    return crud_create(request, form_class=UsageRecordForm, template="tenants/usagerecord/form.html",
                       success_url="tenants:usagerecord_list")


@tenant_admin_required
def usagerecord_detail(request, pk):
    obj = get_object_or_404(
        UsageRecord.objects.select_related("subscription", "subscription_invoice"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "tenants/usagerecord/detail.html", {"obj": obj})


@tenant_admin_required
def usagerecord_edit(request, pk):
    # A billed row is the evidence the invoice stands on, so it is frozen — the same discipline
    # the project applies to approved baselines and posted expenses. The form cannot express this
    # (crud_edit has no guard hook), so the check lives here.
    obj = get_object_or_404(UsageRecord, pk=pk, tenant=request.tenant)
    if obj.is_billed:
        messages.error(request, "Billed usage is frozen evidence and cannot be edited.")
        return redirect("tenants:usagerecord_detail", pk=obj.pk)
    return crud_edit(request, model=UsageRecord, pk=pk, form_class=UsageRecordForm,
                     template="tenants/usagerecord/form.html", success_url="tenants:usagerecord_list")


@require_POST
@tenant_admin_required
def usagerecord_delete(request, pk):
    """`require_POST` sits ABOVE `tenant_admin_required` on purpose.

    Decorators apply bottom-up, so the OUTERMOST runs first. With the role gate outermost, a
    non-admin member's GET would be answered 403 by the role check before the method check ever
    ran; the house standard (7.7's ruling) is 405 for a wrong method regardless of role. The
    older tenants verbs (`encryptionkey_rotate`, `subscription_mark_paid`) still carry the
    pre-7.7 order — this one does not copy it.
    """
    obj = get_object_or_404(UsageRecord, pk=pk, tenant=request.tenant)
    if obj.is_billed:
        messages.error(request, "Billed usage is frozen evidence and cannot be deleted.")
        return redirect("tenants:usagerecord_detail", pk=obj.pk)
    return crud_delete(request, model=UsageRecord, pk=pk, success_url="tenants:usagerecord_list")


@require_POST
@tenant_admin_required
def usagerecord_mark_billed(request, pk):
    """The ONLY writer of `is_billed` / `billed_at`. See the decorator-order note above.

    Requires a linked invoice first: the point of marking usage billed is that it went onto a
    specific invoice, so a row marked billed with nothing to point at is not evidence.
    """
    obj = get_object_or_404(UsageRecord, pk=pk, tenant=request.tenant)
    if obj.is_billed:
        messages.info(request, "That usage is already marked as billed.")
        return redirect("tenants:usagerecord_detail", pk=obj.pk)
    if obj.subscription_invoice_id is None:
        messages.error(request, "Link an invoice before marking this usage as billed.")
        return redirect("tenants:usagerecord_edit", pk=obj.pk)

    obj.is_billed = True
    obj.billed_at = timezone.now()
    obj.save(update_fields=["is_billed", "billed_at"])
    # AuditLog.action is varchar(10), so the verb goes in `changes`, not in `action` (L41).
    write_audit_log(request.user, obj, "update", changes={"verb": "usagerecord_mark_billed"})
    messages.success(request, "Usage marked as billed.")
    return redirect("tenants:usagerecord_detail", pk=obj.pk)
