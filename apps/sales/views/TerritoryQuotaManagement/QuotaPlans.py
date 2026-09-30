"""Sales 8.7 — the quota-plan views: how a CRM quota target was derived, and its approval verbs.

**8.7 does not define a quota.** The amount lives on `crm.SalesQuota`, is edited in CRM's form
under CRM's permission set, and is only ever READ here (§0.3). A `QuotaPlan` is the derivation: the
method, the allocation basis, the growth and attrition percentages, the phasing, and the `parameters`
that make the number reproducible. The two `derived_*` figures on the detail page are therefore
COMPUTED IN PYTHON in this view, never stored and never an `F()` expression (§10.5).

The status is ACTION-DRIVEN. `status` is off the form by decision, not by `editable=False`, and only
the four POST verbs below move it: `draft -> submitted -> approved | rejected -> locked`. Each
transition re-checks the state server-side before writing, so a hidden button is never the guard.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.crud import as_db_int
from apps.core.utils import write_audit_log
from apps.sales.forms.TerritoryQuotaManagement.QuotaPlans import QuotaPlanForm
from apps.sales.models.SalesForecasting.ForecastPeriods import ForecastPeriod
from apps.sales.models.TerritoryQuotaManagement.QuotaPlans import QuotaPlan
from apps.sales.views._common import *
from apps.sales.views.TerritoryQuotaManagement.TerritoryBoards import tenant_territories
from apps.sales.views._helpers import is_tenant_admin

LIST_TEMPLATE = "sales/territoryquotamanagement/quotaplan/list.html"
DETAIL_TEMPLATE = "sales/territoryquotamanagement/quotaplan/detail.html"
FORM_TEMPLATE = "sales/territoryquotamanagement/quotaplan/form.html"

PAGE_SIZE = 15

HUNDRED = Decimal("100")
CENTS = Decimal("0.01")

ACTIVE_CHOICES = [("active", "Active"), ("inactive", "Inactive")]

#: The `parameters` key a top-down / bottom-up plan states its baseline in. Read only when it
#: parses as a money figure; a value that does not is reported, never coerced to zero.
CUSTOM_BASELINE_KEY = "custom_baseline"


def _plan_queryset(request):
    return (
        QuotaPlan.objects.filter(tenant=request.tenant)
        .select_related("quota_ref", "forecast_period", "owner", "territory", "submitted_by", "approved_by")
    )


def _choice_context():
    return {
        "status_choices": QuotaPlan.STATUS_CHOICES,
        "method_choices": QuotaPlan.METHOD_CHOICES,
        "allocation_basis_choices": QuotaPlan.ALLOCATION_BASIS_CHOICES,
        "baseline_source_choices": QuotaPlan.BASELINE_SOURCE_CHOICES,
        "target_type_choices": QuotaPlan.TARGET_TYPE_CHOICES,
        "phasing_choices": QuotaPlan.PHASING_CHOICES,
    }


def _form_context(request):
    return {
        **_choice_context(),
        "territories": tenant_territories(request.tenant),
        "owners": User.objects.filter(tenant=request.tenant, is_active=True).order_by("username"),
        "periods": ForecastPeriod.objects.filter(tenant=request.tenant).order_by(
            "-period_year", "-period_number", "period_type"
        ),
    }


def derive_baseline(plan):
    """The figure the plan's target was built FROM, as a ``Decimal`` in Python.

    The contract pins that this is a Python ``Decimal`` and never a stored column, and leaves the
    arithmetic here (§17 item 7). The reading that is honest about what a plan records:

    * a ``custom`` baseline STATES it, in ``parameters["custom_baseline"]``;
    * every other source (``previous_period`` / ``previous_year``) is back-solved from the target
      and the two percentages that moved it, because the plan is exactly the sentence "this target,
      this growth, this attrition relief" and the baseline is what makes that sentence check out.

    Returns ``(value, caveat)``; ``(None, str)`` when the arithmetic has no answer.
    """
    if plan.baseline_source == "custom":
        raw = (plan.parameters or {}).get(CUSTOM_BASELINE_KEY)
        try:
            return Decimal(str(raw)).quantize(CENTS, rounding=ROUND_HALF_UP), ""
        except Exception:
            return None, (
                f"This plan says its baseline is custom but carries no readable "
                f"{CUSTOM_BASELINE_KEY!r} figure, so the baseline cannot be shown."
            )
    # target = baseline x (1 + growth% - attrition relief%)
    multiplier = (
        HUNDRED
        + Decimal(plan.growth_target_pct or 0)
        - Decimal(plan.attrition_relief_pct or 0)
    ) / HUNDRED
    if multiplier == 0:
        return None, (
            "Growth and attrition relief cancel exactly, so the baseline behind this target is not "
            "recoverable from it."
        )
    return (Decimal(plan.quota_ref.target_amount or 0) / multiplier).quantize(
        CENTS, rounding=ROUND_HALF_UP
    ), ""


def derive_stretch_amount(plan):
    """The stretch figure, as a ``Decimal`` in Python: a percentage UPLIFT on the CRM money number,
    never a second money column on the plan."""
    if plan.stretch_target_pct is None:
        return None, ""
    if not plan.uplift_allowed:
        return None, "A stretch target is set without uplift allowed, so none is derived."
    amount = Decimal(plan.quota_ref.target_amount or 0) * (
        HUNDRED + Decimal(plan.stretch_target_pct)
    ) / HUNDRED
    return amount.quantize(CENTS, rounding=ROUND_HALF_UP), ""


@login_required
def quota_plan_list(request):
    queryset = _plan_queryset(request)
    status = request.GET.get("status", "")
    if status in dict(QuotaPlan.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    method = request.GET.get("method", "")
    if method in dict(QuotaPlan.METHOD_CHOICES):
        queryset = queryset.filter(method=method)
    allocation_basis = request.GET.get("allocation_basis", "")
    if allocation_basis in dict(QuotaPlan.ALLOCATION_BASIS_CHOICES):
        queryset = queryset.filter(allocation_basis=allocation_basis)
    baseline_source = request.GET.get("baseline_source", "")
    if baseline_source in dict(QuotaPlan.BASELINE_SOURCE_CHOICES):
        queryset = queryset.filter(baseline_source=baseline_source)
    target_type = request.GET.get("target_type", "")
    if target_type in dict(QuotaPlan.TARGET_TYPE_CHOICES):
        queryset = queryset.filter(target_type=target_type)
    phasing = request.GET.get("phasing", "")
    if phasing in dict(QuotaPlan.PHASING_CHOICES):
        queryset = queryset.filter(phasing=phasing)
    territory_id = as_db_int(request.GET.get("territory"))
    if territory_id:
        queryset = queryset.filter(territory_id=territory_id)
    owner_id = as_db_int(request.GET.get("owner"))
    if owner_id:
        queryset = queryset.filter(owner_id=owner_id)
    forecast_period_id = as_db_int(request.GET.get("forecast_period"))
    if forecast_period_id:
        queryset = queryset.filter(forecast_period_id=forecast_period_id)
    active = request.GET.get("active", "")
    if active == "active":
        queryset = queryset.filter(is_active=True)
    elif active == "inactive":
        queryset = queryset.filter(is_active=False)

    base = _plan_queryset(request)
    stats = {
        "total": base.count(),
        "draft": base.filter(status="draft").count(),
        "in_approval": base.filter(status="submitted").count(),
        "approved": base.filter(status="approved").count(),
        "frozen": base.filter(status__in=sorted(QuotaPlan.FROZEN_STATES)).count(),
    }
    return crud_list(
        request,
        queryset,
        LIST_TEMPLATE,
        search_fields=[
            "number", "notes", "quota_ref__number", "quota_ref__notes", "owner__username",
        ],
        extra_context={
            "page_size": PAGE_SIZE,
            **_choice_context(),
            "active_choices": ACTIVE_CHOICES,
            "territories": tenant_territories(request.tenant),
            "owners": User.objects.filter(tenant=request.tenant, is_active=True).order_by("username"),
            "periods": ForecastPeriod.objects.filter(tenant=request.tenant).order_by(
                "-period_year", "-period_number", "period_type"
            ),
            "stats": stats,
            "status": status,
            "method": method,
            "allocation_basis": allocation_basis,
            "baseline_source": baseline_source,
            "target_type": target_type,
            "phasing": phasing,
            "territory_id": territory_id or "",
            "owner_id": owner_id or "",
            "forecast_period_id": forecast_period_id or "",
            "active": active,
        },
        per_page=PAGE_SIZE,
    )


@login_required
def quota_plan_create(request):
    return crud_create(
        request,
        form_class=QuotaPlanForm,
        template=FORM_TEMPLATE,
        success_url=reverse("sales:quota_plan_list"),
        extra_context=_form_context(request),
    )


@login_required
def quota_plan_detail(request, pk):
    obj = get_object_or_404(_plan_queryset(request), pk=pk)
    derived_baseline, baseline_caveat = derive_baseline(obj)
    derived_stretch_amount, stretch_caveat = derive_stretch_amount(obj)
    caveats = [caveat for caveat in (baseline_caveat, stretch_caveat) if caveat]
    if obj.is_frozen:
        caveats.append("This plan is frozen; its fields can no longer be edited.")
    if obj.status == "submitted" and obj.submitted_at is None:
        caveats.append("This plan is in approval but carries no submission stamp.")
    if obj.territory_id is None and obj.quota_ref.territory_id is None:
        caveats.append("Neither the plan nor the quota it annotates names a territory.")
    if obj.phasing == "seasonal" and not (obj.parameters or {}).get("seasonal_weights"):
        caveats.append("This plan phases seasonally but carries no weights, so the phasing has no shape.")
    caveats.append(
        "The target amount itself is edited on the CRM quota. 8.7 records how it was derived and "
        "never writes the number."
    )
    return render(request, DETAIL_TEMPLATE, {
        "obj": obj,
        **_choice_context(),
        "quota_ref": obj.quota_ref,
        "forecast_period": obj.forecast_period,
        "is_frozen": obj.is_frozen,
        "can_approve": is_tenant_admin(request.user),
        "derived_baseline": derived_baseline,
        "derived_stretch_amount": derived_stretch_amount,
        "caveats": caveats,
    })


@login_required
def quota_plan_edit(request, pk):
    obj = get_object_or_404(_plan_queryset(request), pk=pk)
    if obj.is_frozen:
        # The form disables its own fields in a frozen state; this is the SERVER-side re-check, so
        # the widgets are never the only guard (research §5.5 R9).
        messages.error(
            request,
            f"This plan is {obj.get_status_display()} and can no longer be edited.",
        )
        return redirect("sales:quota_plan_detail", pk=obj.pk)
    return crud_edit(
        request,
        model=QuotaPlan,
        pk=pk,
        form_class=QuotaPlanForm,
        template=FORM_TEMPLATE,
        success_url=reverse("sales:quota_plan_detail", args=[pk]),
        extra_context=_form_context(request),
    )


@require_POST
@login_required
def quota_plan_submit(request, pk):
    """``draft -> submitted``, stamping the frozen submission evidence."""
    obj = get_object_or_404(_plan_queryset(request), pk=pk)
    if obj.status != "draft":
        messages.error(request, f"Only a draft plan can be submitted; this one is {obj.get_status_display()}.")
        return redirect("sales:quota_plan_detail", pk=obj.pk)
    with transaction.atomic():
        locked = QuotaPlan.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        locked.status = "submitted"
        locked.submitted_by = request.user
        locked.submitted_at = timezone.now()
        locked.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
        write_audit_log(
            request.user, locked, "update",
            {"action": "quota_plan_submit", "status": locked.status, "quota_ref_id": locked.quota_ref_id},
            tenant=request.tenant,
        )
    messages.success(request, "Quota plan submitted for approval.")
    return redirect("sales:quota_plan_detail", pk=obj.pk)


@require_POST
@login_required
@tenant_admin_required
def quota_plan_approve(request, pk):
    """``submitted -> approved``, stamping the frozen approval evidence. Tenant-admin only."""
    obj = get_object_or_404(_plan_queryset(request), pk=pk)
    if obj.status != "submitted":
        messages.error(request, f"Only a submitted plan can be approved; this one is {obj.get_status_display()}.")
        return redirect("sales:quota_plan_detail", pk=obj.pk)
    with transaction.atomic():
        locked = QuotaPlan.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        locked.status = "approved"
        locked.approved_by = request.user
        locked.approved_at = timezone.now()
        locked.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        write_audit_log(
            request.user, locked, "update",
            {"action": "quota_plan_approve", "status": locked.status, "quota_ref_id": locked.quota_ref_id},
            tenant=request.tenant,
        )
    messages.success(request, "Quota plan approved. Its fields are now frozen.")
    return redirect("sales:quota_plan_detail", pk=obj.pk)


@require_POST
@login_required
@tenant_admin_required
def quota_plan_reject(request, pk):
    """``submitted -> rejected``. A rejection is never silent: the plan goes back for rework."""
    obj = get_object_or_404(_plan_queryset(request), pk=pk)
    if obj.status != "submitted":
        messages.error(request, f"Only a submitted plan can be rejected; this one is {obj.get_status_display()}.")
        return redirect("sales:quota_plan_detail", pk=obj.pk)
    with transaction.atomic():
        locked = QuotaPlan.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        locked.status = "rejected"
        locked.save(update_fields=["status", "updated_at"])
        write_audit_log(
            request.user, locked, "update",
            {"action": "quota_plan_reject", "status": locked.status, "quota_ref_id": locked.quota_ref_id},
            tenant=request.tenant,
        )
    messages.success(request, "Quota plan rejected. Edit it and submit it again.")
    return redirect("sales:quota_plan_detail", pk=obj.pk)


@require_POST
@login_required
@tenant_admin_required
def quota_plan_lock(request, pk):
    """``approved -> locked``. The terminal state: the plan is a record, not a proposal."""
    obj = get_object_or_404(_plan_queryset(request), pk=pk)
    if obj.status != "approved":
        messages.error(request, f"Only an approved plan can be locked; this one is {obj.get_status_display()}.")
        return redirect("sales:quota_plan_detail", pk=obj.pk)
    with transaction.atomic():
        locked = QuotaPlan.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        locked.status = "locked"
        locked.save(update_fields=["status", "updated_at"])
        write_audit_log(
            request.user, locked, "update",
            {"action": "quota_plan_lock", "status": locked.status, "quota_ref_id": locked.quota_ref_id},
            tenant=request.tenant,
        )
    messages.success(request, "Quota plan locked.")
    return redirect("sales:quota_plan_detail", pk=obj.pk)


@require_POST
@login_required
@tenant_admin_required
def quota_plan_delete(request, pk):
    obj = get_object_or_404(_plan_queryset(request), pk=pk)
    with transaction.atomic():
        locked = QuotaPlan.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        write_audit_log(
            request.user, locked, "delete",
            {"action": "quota_plan", "quota_ref_id": locked.quota_ref_id, "status": locked.status},
            tenant=request.tenant,
        )
        locked.delete()
    messages.success(request, "Quota plan deleted. The CRM quota it annotated is untouched.")
    return redirect("sales:quota_plan_list")
