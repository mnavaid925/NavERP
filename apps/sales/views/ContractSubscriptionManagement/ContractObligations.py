"""Sales 8.15 — ContractObligation views."""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.sales.forms.ContractSubscriptionManagement.ContractObligations import (
    ContractObligationFilterForm,
    ContractObligationForm,
    ObligationBreachForm,
    ObligationFulfillForm,
)
from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import CustomerContract
from apps.sales.models.ContractSubscriptionManagement.CustomerSubscriptions import CustomerSubscription
from apps.sales.models.ContractSubscriptionManagement.ContractObligations import (
    OBLIGATION_STATUS_CHOICES,
    OBLIGATION_TYPE_CHOICES,
    ContractObligation,
)


@login_required
def contract_obligation_list(request):
    tenant = request.tenant
    qs = ContractObligation.objects.filter(tenant=tenant).select_related("contract", "subscription", "assigned_to")

    filter_form = ContractObligationFilterForm(request.GET, tenant=tenant)
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get("q")
        if q:
            qs = qs.filter(
                Q(number__icontains=q)
                | Q(title__icontains=q)
                | Q(contract__title__icontains=q)
                | Q(target_metric__icontains=q)
            )

        obligation_type = filter_form.cleaned_data.get("obligation_type")
        if obligation_type:
            qs = qs.filter(obligation_type=obligation_type)

        status = filter_form.cleaned_data.get("status")
        if status:
            qs = qs.filter(status=status)

        contract = filter_form.cleaned_data.get("contract")
        if contract:
            qs = qs.filter(contract=contract)

        assigned_to = filter_form.cleaned_data.get("assigned_to")
        if assigned_to:
            qs = qs.filter(assigned_to=assigned_to)

    # Aggregates
    all_obligations = ContractObligation.objects.filter(tenant=tenant)
    penalty_exposure = all_obligations.filter(penalty_status__in=["assessed", "credited"]).aggregate(
        total=Sum("penalty_amount")
    )["total"] or Decimal("0.00")
    breached_count = all_obligations.filter(status="breached").count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "obligations": page_obj.object_list,
        "page_obj": page_obj,
        "filter_form": filter_form,
        "status_choices": OBLIGATION_STATUS_CHOICES,
        "type_choices": OBLIGATION_TYPE_CHOICES,
        "penalty_exposure": penalty_exposure,
        "breached_count": breached_count,
    }
    return render(request, "sales/contractsubscriptionmanagement/contractobligation/list.html", context)


@login_required
@transaction.atomic
def contract_obligation_create(request):
    tenant = request.tenant
    if request.method == "POST":
        form = ContractObligationForm(request.POST, tenant=tenant)
        if form.is_valid():
            obl = form.save(commit=False)
            obl.tenant = tenant
            obl.save()
            write_audit_log(
                user=request.user,
                obj=obl,
                action="create",
                tenant=tenant,
            )
            messages.success(request, f"Obligation {obl.number} created successfully.")
            return redirect("sales:contract_obligation_detail", pk=obl.pk)
    else:
        initial = {}
        contract_id = request.GET.get("contract")
        if contract_id and contract_id.isdigit():
            contract = CustomerContract.objects.filter(tenant=tenant, pk=contract_id).first()
            if contract:
                initial["contract"] = contract

        sub_id = request.GET.get("subscription")
        if sub_id and sub_id.isdigit():
            sub = CustomerSubscription.objects.filter(tenant=tenant, pk=sub_id).first()
            if sub:
                initial["subscription"] = sub
                if not initial.get("contract"):
                    initial["contract"] = sub.contract

        form = ContractObligationForm(tenant=tenant, initial=initial)

    context = {
        "form": form,
        "obligation": None,
        "obj": None,
        "is_edit": False,
    }
    return render(request, "sales/contractsubscriptionmanagement/contractobligation/form.html", context)


@login_required
def contract_obligation_detail(request, pk):
    tenant = request.tenant
    obligation = get_object_or_404(
        ContractObligation.objects.filter(tenant=tenant).select_related(
            "contract", "subscription", "assigned_to", "contract__account"
        ),
        pk=pk,
    )

    context = {
        "obligation": obligation,
        "obj": obligation,
        "fulfill_form": ObligationFulfillForm(),
        "breach_form": ObligationBreachForm(initial={"penalty_amount": obligation.penalty_amount}),
    }
    return render(request, "sales/contractsubscriptionmanagement/contractobligation/detail.html", context)


@login_required
@transaction.atomic
def contract_obligation_edit(request, pk):
    tenant = request.tenant
    obligation = get_object_or_404(ContractObligation.objects.filter(tenant=tenant), pk=pk)
    if request.method == "POST":
        form = ContractObligationForm(request.POST, instance=obligation, tenant=tenant)
        if form.is_valid():
            obl = form.save()
            write_audit_log(
                user=request.user,
                obj=obl,
                action="update",
                tenant=tenant,
            )
            messages.success(request, f"Obligation {obl.number} updated successfully.")
            return redirect("sales:contract_obligation_detail", pk=obl.pk)
    else:
        form = ContractObligationForm(instance=obligation, tenant=tenant)

    context = {
        "form": form,
        "obligation": obligation,
        "obj": obligation,
        "is_edit": True,
    }
    return render(request, "sales/contractsubscriptionmanagement/contractobligation/form.html", context)


@login_required
@require_POST
@transaction.atomic
def contract_obligation_delete(request, pk):
    tenant = request.tenant
    obligation = get_object_or_404(ContractObligation.objects.filter(tenant=tenant), pk=pk)
    number = obligation.number
    write_audit_log(
        user=request.user,
        obj=obligation,
        action="delete",
        tenant=tenant,
    )
    obligation.delete()
    messages.success(request, f"Obligation {number} deleted successfully.")
    return redirect("sales:contract_obligation_list")


@login_required
@require_POST
@transaction.atomic
def contract_obligation_fulfill(request, pk):
    tenant = request.tenant
    obligation = get_object_or_404(ContractObligation.objects.filter(tenant=tenant), pk=pk)
    form = ObligationFulfillForm(request.POST)
    if form.is_valid():
        obligation.status = "fulfilled"
        obligation.fulfilled_at = timezone.now()
        obligation.fulfillment_evidence = form.cleaned_data["fulfillment_evidence"]
        obligation.save(update_fields=["status", "fulfilled_at", "fulfillment_evidence", "updated_at"])
        write_audit_log(
            user=request.user,
            obj=obligation,
            action="update",
            tenant=tenant,
        )
        messages.success(request, f"Obligation {obligation.number} marked fulfilled.")
    else:
        messages.error(request, "Fulfillment evidence is required.")
    return redirect("sales:contract_obligation_detail", pk=obligation.pk)


@login_required
@require_POST
@transaction.atomic
def contract_obligation_breach(request, pk):
    tenant = request.tenant
    obligation = get_object_or_404(ContractObligation.objects.filter(tenant=tenant), pk=pk)
    form = ObligationBreachForm(request.POST)
    if form.is_valid():
        obligation.status = "breached"
        obligation.penalty_amount = form.cleaned_data["penalty_amount"]
        obligation.penalty_status = form.cleaned_data["penalty_status"]
        obligation.save(update_fields=["status", "penalty_amount", "penalty_status", "updated_at"])
        write_audit_log(
            user=request.user,
            obj=obligation,
            action="update",
            tenant=tenant,
        )
        messages.success(request, f"Obligation {obligation.number} marked breached with penalty assessment.")
    else:
        messages.error(request, "Penalty amount must be greater than zero.")
    return redirect("sales:contract_obligation_detail", pk=obligation.pk)
