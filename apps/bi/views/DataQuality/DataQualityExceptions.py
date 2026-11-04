from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.DataQuality.DataQualityExceptionForms import (
    DataQualityExceptionForm,
    DataQualityExceptionRemediationForm,
)
from apps.bi.models.DataQuality.DataQualityExceptions import DataQualityException
from apps.bi.models.DataQuality.DataQualityRules import DataQualityRule
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def data_quality_exception_list(request):
    queryset = (
        bi_scope(DataQualityException.objects.all(), request)
        .select_related("rule", "profile", "warehouse_table", "semantic_model", "assigned_steward")
    )

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(record_identifier__icontains=q)
            | Q(number__icontains=q)
            | Q(target_column__icontains=q)
            | Q(invalid_value__icontains=q)
            | Q(expected_condition__icontains=q)
            | Q(resolution_notes__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    severity_filter = request.GET.get("severity", "").strip()
    if severity_filter:
        queryset = queryset.filter(severity=severity_filter)

    exception_type_filter = request.GET.get("exception_type", "").strip()
    if exception_type_filter:
        queryset = queryset.filter(exception_type=exception_type_filter)

    rule_filter = request.GET.get("rule", "").strip()
    if rule_filter.isdigit():
        queryset = queryset.filter(rule_id=rule_filter)

    steward_filter = request.GET.get("assigned_steward", "").strip()
    if steward_filter.isdigit():
        queryset = queryset.filter(assigned_steward_id=steward_filter)

    stat_counts = bi_scope(DataQualityException.objects.all(), request).aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status__in=["open", "investigating"])),
        remediated=Count("id", filter=Q(status="remediated")),
        critical=Count("id", filter=Q(severity__in=["critical", "fatal"])),
    )
    total_count = stat_counts["total"]
    open_count = stat_counts["open"]
    remediated_count = stat_counts["remediated"]
    critical_count = stat_counts["critical"]

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    rules = bi_scope(DataQualityRule.objects.only("id", "name"), request).order_by("name")
    stewards = get_user_model().objects.filter(tenant=request.tenant, is_active=True).only("id", "first_name", "last_name", "username").order_by("first_name", "username")

    context = {
        "page_obj": page_obj,
        "exceptions": page_obj,
        "status_choices": DataQualityException.STATUS_CHOICES,
        "severity_choices": DataQualityException.SEVERITY_CHOICES,
        "exception_type_choices": DataQualityException.EXCEPTION_TYPE_CHOICES,
        "rules": rules,
        "stewards": stewards,
        "total_count": total_count,
        "open_count": open_count,
        "remediated_count": remediated_count,
        "critical_count": critical_count,
    }
    return render(request, "bi/data_quality/data_quality_exception/list.html", context)


@login_required
def data_quality_exception_detail(request, pk):
    exception = bi_object(
        request,
        DataQualityException,
        pk,
        select_related=["rule", "profile", "warehouse_table", "semantic_model", "assigned_steward", "resolved_by"],
    )
    remediation_form = DataQualityExceptionRemediationForm(instance=exception, tenant=request.tenant)

    context = {
        "exception": exception,
        "remediation_form": remediation_form,
    }
    return render(request, "bi/data_quality/data_quality_exception/detail.html", context)


@login_required
def data_quality_exception_create(request):
    if request.method == "POST":
        form = DataQualityExceptionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            exc = form.save(commit=False)
            exc.tenant = request.tenant
            exc.save()
            write_audit_log(request.user, exc, "create", tenant=request.tenant)
            messages.success(request, f"Quality exception '{exc.number}' created successfully.")
            return redirect("bi:data_quality_exception_detail", pk=exc.pk)
    else:
        form = DataQualityExceptionForm(tenant=request.tenant)

    context = {
        "form": form,
        "exception": None,
        "is_edit": False,
    }
    return render(request, "bi/data_quality/data_quality_exception/form.html", context)


@login_required
def data_quality_exception_edit(request, pk):
    exception = bi_object(request, DataQualityException, pk)
    if request.method == "POST":
        form = DataQualityExceptionForm(request.POST, instance=exception, tenant=request.tenant)
        if form.is_valid():
            exception = form.save(commit=False)
            if exception.status == "remediated":
                if not exception.resolved_at:
                    exception.resolved_by = request.user
                    exception.resolved_at = timezone.now()
            else:
                exception.resolved_by = None
                exception.resolved_at = None
            exception.save()
            write_audit_log(request.user, exception, "update", tenant=request.tenant)
            messages.success(request, f"Quality exception '{exception.number}' updated successfully.")
            return redirect("bi:data_quality_exception_detail", pk=exception.pk)
    else:
        form = DataQualityExceptionForm(instance=exception, tenant=request.tenant)

    context = {
        "form": form,
        "exception": exception,
        "is_edit": True,
    }
    return render(request, "bi/data_quality/data_quality_exception/form.html", context)


@login_required
@require_POST
def data_quality_exception_delete(request, pk):
    exception = bi_object(request, DataQualityException, pk)
    exc_number = exception.number
    write_audit_log(request.user, exception, "delete", tenant=request.tenant)
    exception.delete()
    messages.success(request, f"Quality exception '{exc_number}' deleted successfully.")
    return redirect("bi:data_quality_exception_list")


@login_required
@require_POST
def data_quality_exception_remediate(request, pk):
    exception = bi_object(request, DataQualityException, pk)
    form = DataQualityExceptionRemediationForm(request.POST, instance=exception, tenant=request.tenant)
    if form.is_valid():
        exc = form.save(commit=False)
        if exc.status == "remediated":
            if not exc.resolved_at:
                exc.resolved_by = request.user
                exc.resolved_at = timezone.now()
        else:
            exc.resolved_by = None
            exc.resolved_at = None
        exc.save()

        write_audit_log(
            request.user,
            exc,
            "remediate",
            changes={"status": exc.status, "remediation_action": exc.remediation_action},
            tenant=request.tenant,
        )
        messages.success(request, f"Remediation update saved for exception '{exc.number}'.")
    else:
        err_msg = "; ".join(f"{f}: {', '.join(e)}" for f, e in form.errors.items())
        messages.error(request, f"Failed to update exception remediation: {err_msg}")
    return redirect("bi:data_quality_exception_detail", pk=exception.pk)
