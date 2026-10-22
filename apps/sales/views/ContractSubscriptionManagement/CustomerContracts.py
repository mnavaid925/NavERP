"""Sales 8.15 — CustomerContract views."""
from decimal import Decimal
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.ContractSubscriptionManagement.CustomerContracts import (
    CustomerContractFilterForm,
    CustomerContractForm,
)
from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import (
    CONTRACT_STATUS_CHOICES,
    CONTRACT_TYPE_CHOICES,
    CustomerContract,
)
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote


@login_required
def customer_contract_list(request):
    tenant = request.tenant
    qs = CustomerContract.objects.filter(tenant=tenant).select_related("account", "owner", "currency")

    filter_form = CustomerContractFilterForm(request.GET, tenant=tenant)
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get("q")
        if q:
            qs = qs.filter(Q(number__icontains=q) | Q(title__icontains=q) | Q(account__name__icontains=q))

        contract_type = filter_form.cleaned_data.get("contract_type")
        if contract_type:
            qs = qs.filter(contract_type=contract_type)

        status = filter_form.cleaned_data.get("status")
        if status:
            qs = qs.filter(status=status)

        owner = filter_form.cleaned_data.get("owner")
        if owner:
            qs = qs.filter(owner=owner)

        account = filter_form.cleaned_data.get("account")
        if account:
            qs = qs.filter(account=account)

    # Aggregates
    all_contracts = CustomerContract.objects.filter(tenant=tenant)
    total_tcv = all_contracts.filter(status="active").aggregate(total=Sum("total_contract_value"))["total"] or Decimal("0.00")
    active_count = all_contracts.filter(status="active").count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "contracts": page_obj.object_list,
        "page_obj": page_obj,
        "filter_form": filter_form,
        "status_choices": CONTRACT_STATUS_CHOICES,
        "type_choices": CONTRACT_TYPE_CHOICES,
        "total_tcv": total_tcv,
        "active_count": active_count,
    }
    return render(request, "sales/contractsubscriptionmanagement/customercontract/list.html", context)


@login_required
@transaction.atomic
def customer_contract_create(request):
    tenant = request.tenant
    if request.method == "POST":
        form = CustomerContractForm(request.POST, tenant=tenant)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.tenant = tenant
            contract.save()
            write_audit_log(
                user=request.user,
                obj=contract,
                action="create",
                tenant=tenant,
            )
            messages.success(request, f"Contract {contract.number} created successfully.")
            return redirect("sales:customer_contract_detail", pk=contract.pk)
    else:
        initial = {}
        if not initial.get("owner"):
            initial["owner"] = request.user
        form = CustomerContractForm(tenant=tenant, initial=initial)

    context = {
        "form": form,
        "contract": None,
        "obj": None,
        "is_edit": False,
    }
    return render(request, "sales/contractsubscriptionmanagement/customercontract/form.html", context)


@login_required
def customer_contract_detail(request, pk):
    tenant = request.tenant
    contract = get_object_or_404(
        CustomerContract.objects.filter(tenant=tenant).select_related(
            "account", "owner", "currency", "originating_quote", "originating_order", "template", "document"
        ),
        pk=pk,
    )
    subscriptions = contract.subscriptions.all().select_related("currency")
    obligations = contract.obligations.all().select_related("assigned_to")

    context = {
        "contract": contract,
        "obj": contract,
        "subscriptions": subscriptions,
        "obligations": obligations,
    }
    return render(request, "sales/contractsubscriptionmanagement/customercontract/detail.html", context)


@login_required
@transaction.atomic
def customer_contract_edit(request, pk):
    tenant = request.tenant
    contract = get_object_or_404(CustomerContract.objects.filter(tenant=tenant), pk=pk)
    if request.method == "POST":
        form = CustomerContractForm(request.POST, instance=contract, tenant=tenant)
        if form.is_valid():
            contract = form.save()
            write_audit_log(
                user=request.user,
                obj=contract,
                action="update",
                tenant=tenant,
            )
            messages.success(request, f"Contract {contract.number} updated successfully.")
            return redirect("sales:customer_contract_detail", pk=contract.pk)
    else:
        form = CustomerContractForm(instance=contract, tenant=tenant)

    context = {
        "form": form,
        "contract": contract,
        "obj": contract,
        "is_edit": True,
    }
    return render(request, "sales/contractsubscriptionmanagement/customercontract/form.html", context)


@login_required
@require_POST
@transaction.atomic
def customer_contract_delete(request, pk):
    tenant = request.tenant
    contract = get_object_or_404(CustomerContract.objects.filter(tenant=tenant), pk=pk)
    number = contract.number
    write_audit_log(
        user=request.user,
        obj=contract,
        action="delete",
        tenant=tenant,
    )
    contract.delete()
    messages.success(request, f"Contract {number} deleted successfully.")
    return redirect("sales:customer_contract_list")


@login_required
@require_POST
@transaction.atomic
def customer_contract_activate(request, pk):
    tenant = request.tenant
    contract = get_object_or_404(CustomerContract.objects.filter(tenant=tenant), pk=pk)
    contract.status = "active"
    if not contract.signed_at:
        contract.signed_at = timezone.now()
    contract.save(update_fields=["status", "signed_at", "updated_at"])
    write_audit_log(
        user=request.user,
        obj=contract,
        action="update",
        tenant=tenant,
    )
    messages.success(request, f"Contract {contract.number} is now active.")
    return redirect("sales:customer_contract_detail", pk=contract.pk)


@login_required
@require_POST
@transaction.atomic
def customer_contract_generate_renewal_quote(request, pk):
    tenant = request.tenant
    contract = get_object_or_404(CustomerContract.objects.filter(tenant=tenant), pk=pk)
    
    # Calculate uplifted price
    uplift_multiplier = Decimal("1.00") + (contract.price_uplift_pct / Decimal("100.00"))
    renewal_amount = (contract.annual_contract_value or contract.total_contract_value) * uplift_multiplier

    quote = CPQQuote.objects.create(
        tenant=tenant,
        account=contract.account,
        name=f"Renewal Quote for {contract.title}",
        status="draft",
        owner=contract.owner or request.user,
        currency=contract.currency,
        subtotal=renewal_amount,
        total=renewal_amount,
        valid_until=timezone.localdate() + timedelta(days=contract.notice_period_days or 30),
        terms_and_conditions=f"Automated renewal quote with {contract.price_uplift_pct}% contractual uplift.",
    )
    write_audit_log(
        user=request.user,
        obj=quote,
        action="create",
        tenant=tenant,
    )
    messages.success(request, f"Renewal quote {quote.number} generated for {contract.number}.")
    return redirect("sales:customer_contract_detail", pk=contract.pk)


@login_required
@require_POST
@transaction.atomic
def customer_contract_execute_auto_renew(request, pk):
    tenant = request.tenant
    contract = get_object_or_404(CustomerContract.objects.filter(tenant=tenant), pk=pk)

    if contract.status != "active":
        messages.error(request, f"Contract {contract.number} cannot be auto-renewed because it is not active.")
        return redirect("sales:customer_contract_detail", pk=contract.pk)

    if not contract.auto_renew:
        messages.error(request, f"Contract {contract.number} does not have auto-renewal enabled.")
        return redirect("sales:customer_contract_detail", pk=contract.pk)

    today = timezone.localdate()
    notice_days = contract.notice_period_days or 30
    if contract.end_date and contract.end_date > today + timedelta(days=notice_days):
        messages.error(request, f"Contract {contract.number} is not within its renewal notice window ({notice_days} days).")
        return redirect("sales:customer_contract_detail", pk=contract.pk)

    months = contract.renewal_term_months or 12
    days = months * 30
    current_end = contract.end_date or today
    contract.end_date = current_end + timedelta(days=days)
    
    # Apply uplift if specified
    if contract.price_uplift_pct > Decimal("0.00"):
        multiplier = Decimal("1.00") + (contract.price_uplift_pct / Decimal("100.00"))
        contract.total_contract_value = (contract.total_contract_value * multiplier).quantize(Decimal("0.01"))
        contract.annual_contract_value = (contract.annual_contract_value * multiplier).quantize(Decimal("0.01"))

    contract.status = "active"
    contract.save(update_fields=["end_date", "total_contract_value", "annual_contract_value", "status", "updated_at"])
    
    write_audit_log(
        user=request.user,
        obj=contract,
        action="update",
        tenant=tenant,
    )
    messages.success(request, f"Contract {contract.number} auto-renewed through {contract.end_date}.")
    return redirect("sales:customer_contract_detail", pk=contract.pk)
