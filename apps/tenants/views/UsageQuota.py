"""tenants — UsageQuota views (0.19, the commercial ceiling) + the mark-breached verb.

`metric_choices` is `UsageQuota.METRIC_CHOICES` — the SAME OBJECT as `UsageRecord.METRIC_CHOICES`,
assigned by reference ([RULING] 7). There is no `metric` queryset and building one would be a fifth
metric list, the exact duplication the research rejects.
"""
from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    Subscription,
    UsageQuota,
)
from apps.tenants.forms import (
    UsageQuotaForm,
)


@tenant_admin_required
def usagequota_list(request):
    qs = UsageQuota.objects.filter(tenant=request.tenant).select_related("subscription")
    # `breached_at` is a DateTimeField, NOT a boolean, so it CANNOT go in the `filters` spec:
    # `?breached=True` would reach `.filter(breached_at="True")`, raise ValueError inside the
    # filter, and be silently skipped by `crud.py:176` — the dropdown would render, appear selected,
    # and do nothing. The lens is therefore applied HERE, on the `usagerecord_list` `?billed=yes|no`
    # precedent. This is the ONE place a 0.19 view filters outside `crud_list`; the comment is the
    # reason, so the next reader does not "simplify" it back into the filter spec and silently break
    # the dropdown. Values stay the literal "True"/"False" the template compares against.
    breached = request.GET.get("breached", "").strip()
    if breached in ("True", "False"):
        qs = qs.filter(breached_at__isnull=(breached == "False"))
    return crud_list(
        request, qs, "tenants/usagequota/list.html",
        search_fields=["notes"],
        filters=[("metric", "metric", False),
                 ("subscription", "subscription_id", True),
                 ("action", "action_on_breach", False),
                 ("period", "period", False)],
        extra_context={
            "metric_choices": UsageQuota.METRIC_CHOICES,
            "action_choices": UsageQuota.ACTION_CHOICES,
            "period_choices": UsageQuota.PERIOD_CHOICES,
            "subscription_choices": Subscription.objects
                                          .filter(tenant=request.tenant).order_by("-created_at"),
            "breached_choices": [("True", "Breached"), ("False", "Not breached")],
        },
    )


@tenant_admin_required
def usagequota_create(request):
    return crud_create(request, form_class=UsageQuotaForm,
                       template="tenants/usagequota/form.html",
                       success_url="tenants:usagequota_list")


@tenant_admin_required
def usagequota_detail(request, pk):
    obj = get_object_or_404(UsageQuota, pk=pk, tenant=request.tenant)
    # `consumption` is the {metric: Decimal} map for THIS subscription, taken from the board helper
    # rather than re-queried here — a row-dict contract is a second contract: read the PRODUCER of
    # the rows, not the view that forwards them.
    from apps.tenants.views.Boards import _consumption_by_subscription
    return crud_detail(
        request, model=UsageQuota, pk=pk,
        template="tenants/usagequota/detail.html",
        extra_context={
            "consumption": _consumption_by_subscription(request.tenant).get(obj.subscription_id, {}),
        },
    )


@tenant_admin_required
def usagequota_edit(request, pk):
    return crud_edit(request, model=UsageQuota, pk=pk, form_class=UsageQuotaForm,
                     template="tenants/usagequota/form.html",
                     success_url="tenants:usagequota_list")


@require_POST
@tenant_admin_required
def usagequota_delete(request, pk):
    """`require_POST` OUTSIDE the role gate — 405 for a wrong method regardless of role. See
    `entitlementfeature_delete` for the full decorator-order rationale."""
    return crud_delete(request, model=UsageQuota, pk=pk,
                       success_url="tenants:usagequota_list")


@require_POST
@tenant_admin_required
def usagequota_mark_breached(request, pk):
    """The SOLE writer of `UsageQuota.breached_at`. See the decorator-order note above.

    This does NOT enforce `action_on_breach`. That value (`alert` / `charge` / `block`) is a recorded
    policy with NO interceptor: marking a quota breached writes a timestamp and an audit row, and
    nothing else happens — no alert is raised, no charge is computed, no request is blocked. It also
    does not require consumption to exist; this is the operator recording a commercial fact, not a
    system measuring one.
    """
    obj = get_object_or_404(UsageQuota, pk=pk, tenant=request.tenant)
    # Idempotence guard, the `usagerecord_mark_billed` shape: a double-click must not stamp twice.
    if obj.breached_at is not None:
        messages.info(request, "That quota is already marked as breached.")
        return redirect("tenants:usagequota_detail", pk=obj.pk)

    obj.breached_at = timezone.now()
    # `update_fields` is mandatory: it makes the verb's write surface auditable by reading the code.
    obj.save(update_fields=["breached_at"])
    # AuditLog.action is varchar(10), so the verb goes in `changes`, not in `action` (L41).
    write_audit_log(request.user, obj, "update", changes={"verb": "usagequota_mark_breached"})
    messages.success(request, "Quota marked as breached.")
    # The detail page, not the list, so the operator sees the evidence stamp they just created.
    return redirect("tenants:usagequota_detail", pk=obj.pk)
