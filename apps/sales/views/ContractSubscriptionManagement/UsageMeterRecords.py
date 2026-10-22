"""Sales 8.15 — UsageMeterRecord views."""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.sales.forms.ContractSubscriptionManagement.UsageMeterRecords import (
    UsageMeterRecordFilterForm,
    UsageMeterRecordForm,
)
from apps.sales.models.ContractSubscriptionManagement.CustomerSubscriptions import CustomerSubscription
from apps.sales.models.ContractSubscriptionManagement.UsageMeterRecords import (
    USAGE_STATUS_CHOICES,
    UsageMeterRecord,
)


@login_required
def usage_meter_record_list(request):
    tenant = request.tenant
    qs = UsageMeterRecord.objects.filter(tenant=tenant).select_related("subscription", "subscription__account")

    filter_form = UsageMeterRecordFilterForm(request.GET, tenant=tenant)
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get("q")
        if q:
            qs = qs.filter(
                Q(number__icontains=q)
                | Q(meter_name__icontains=q)
                | Q(subscription__subscription_name__icontains=q)
            )

        status = filter_form.cleaned_data.get("status")
        if status:
            qs = qs.filter(status=status)

        subscription = filter_form.cleaned_data.get("subscription")
        if subscription:
            qs = qs.filter(subscription=subscription)

    # Aggregates
    all_meters = UsageMeterRecord.objects.filter(tenant=tenant)
    total_overage_charge = all_meters.filter(status="calculated").aggregate(total=Sum("overage_total_charge"))["total"] or Decimal("0.00")
    unbilled_count = all_meters.filter(status__in=["metering", "calculated"]).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "usage_records": page_obj.object_list,
        "page_obj": page_obj,
        "filter_form": filter_form,
        "status_choices": USAGE_STATUS_CHOICES,
        "total_overage_charge": total_overage_charge,
        "unbilled_count": unbilled_count,
    }
    return render(request, "sales/contractsubscriptionmanagement/usagemeterrecord/list.html", context)


@login_required
def usage_meter_record_create(request):
    tenant = request.tenant
    if request.method == "POST":
        form = UsageMeterRecordForm(request.POST, tenant=tenant)
        if form.is_valid():
            meter = form.save(commit=False)
            meter.tenant = tenant
            meter.calculate_charges()
            meter.save()
            write_audit_log(
                user=request.user,
                obj=meter,
                action="create",
                tenant=tenant,
            )
            messages.success(request, f"Usage record {meter.number} created successfully.")
            return redirect("sales:usage_meter_record_detail", pk=meter.pk)
    else:
        initial = {}
        sub_id = request.GET.get("subscription")
        if sub_id and sub_id.isdigit():
            sub = CustomerSubscription.objects.filter(tenant=tenant, pk=sub_id).first()
            if sub:
                initial["subscription"] = sub
                initial["billing_period_start"] = sub.current_term_start
                initial["billing_period_end"] = sub.current_term_end
        form = UsageMeterRecordForm(tenant=tenant, initial=initial)

    context = {
        "form": form,
        "usage_record": None,
        "obj": None,
        "is_edit": False,
    }
    return render(request, "sales/contractsubscriptionmanagement/usagemeterrecord/form.html", context)


@login_required
def usage_meter_record_detail(request, pk):
    tenant = request.tenant
    meter = get_object_or_404(
        UsageMeterRecord.objects.filter(tenant=tenant).select_related(
            "subscription", "subscription__account", "subscription__currency"
        ),
        pk=pk,
    )

    context = {
        "usage_record": meter,
        "obj": meter,
    }
    return render(request, "sales/contractsubscriptionmanagement/usagemeterrecord/detail.html", context)


@login_required
def usage_meter_record_edit(request, pk):
    tenant = request.tenant
    meter = get_object_or_404(UsageMeterRecord.objects.filter(tenant=tenant), pk=pk)
    if request.method == "POST":
        form = UsageMeterRecordForm(request.POST, instance=meter, tenant=tenant)
        if form.is_valid():
            meter = form.save(commit=False)
            meter.calculate_charges()
            meter.save()
            write_audit_log(
                user=request.user,
                obj=meter,
                action="update",
                tenant=tenant,
            )
            messages.success(request, f"Usage record {meter.number} updated successfully.")
            return redirect("sales:usage_meter_record_detail", pk=meter.pk)
    else:
        form = UsageMeterRecordForm(instance=meter, tenant=tenant)

    context = {
        "form": form,
        "usage_record": meter,
        "obj": meter,
        "is_edit": True,
    }
    return render(request, "sales/contractsubscriptionmanagement/usagemeterrecord/form.html", context)


@login_required
@require_POST
def usage_meter_record_delete(request, pk):
    tenant = request.tenant
    meter = get_object_or_404(UsageMeterRecord.objects.filter(tenant=tenant), pk=pk)
    number = meter.number
    write_audit_log(
        user=request.user,
        obj=meter,
        action="delete",
        tenant=tenant,
    )
    meter.delete()
    messages.success(request, f"Usage record {number} deleted successfully.")
    return redirect("sales:usage_meter_record_list")


@login_required
@require_POST
def usage_meter_record_calculate(request, pk):
    tenant = request.tenant
    meter = get_object_or_404(UsageMeterRecord.objects.filter(tenant=tenant), pk=pk)
    meter.calculate_charges()
    meter.status = "calculated"
    meter.save(update_fields=["billable_overage_units", "overage_total_charge", "status", "updated_at"])
    write_audit_log(
        user=request.user,
        obj=meter,
        action="update",
        tenant=tenant,
    )
    messages.success(request, f"Calculated overage charge ${meter.overage_total_charge} for {meter.number}.")
    return redirect("sales:usage_meter_record_detail", pk=meter.pk)


@login_required
@require_POST
def usage_meter_record_invoice(request, pk):
    tenant = request.tenant
    meter = get_object_or_404(UsageMeterRecord.objects.filter(tenant=tenant), pk=pk)
    meter.status = "invoiced"
    meter.invoiced_at = timezone.now()
    meter.save(update_fields=["status", "invoiced_at", "updated_at"])
    write_audit_log(
        user=request.user,
        obj=meter,
        action="update",
        tenant=tenant,
    )
    messages.success(request, f"Usage record {meter.number} marked invoiced.")
    return redirect("sales:usage_meter_record_detail", pk=meter.pk)
