import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.CapaManagement.CapaInvestigations import CapaInvestigationForm
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "%")):
        return f"'{text}"
    return text


@login_required
def capa_investigation_list(request):
    qs = quality_scope(CapaInvestigation.objects.all(), request).select_related(
        "lead_investigator", "quality_owner", "department"
    ).annotate(
        actions_count=Count("actions", distinct=True),
        pending_actions_count=Count(
            "actions",
            filter=Q(actions__status__in=["pending", "in_progress"]),
            distinct=True,
        ),
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(issue_summary__icontains=q)
            | Q(source_reference__icontains=q)
            | Q(affected_item_code__icontains=q)
            | Q(affected_item_name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    source_filter = request.GET.get("source", "").strip()
    if source_filter:
        qs = qs.filter(source_type=source_filter)

    priority_filter = request.GET.get("priority", "").strip()
    if priority_filter:
        qs = qs.filter(risk_priority=priority_filter)

    base_qs = quality_scope(CapaInvestigation.objects.all(), request)
    today = timezone.now().date()
    stats = base_qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=~Q(status__in=["closed", "voided"])),
        overdue_count=Count(
            "id",
            filter=Q(
                target_closure_date__lt=today,
            )
            & ~Q(status__in=["closed", "voided"]),
        ),
        critical_count=Count("id", filter=Q(risk_priority="critical")),
    )

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "capas": page_obj,
        "total_count": stats["total_count"] or 0,
        "active_count": stats["active_count"] or 0,
        "overdue_count": stats["overdue_count"] or 0,
        "critical_count": stats["critical_count"] or 0,
        "q": q,
        "status_filter": status_filter,
        "source_filter": source_filter,
        "priority_filter": priority_filter,
        "status_choices": CapaInvestigation.STATUS_CHOICES,
        "source_type_choices": CapaInvestigation.SOURCE_TYPE_CHOICES,
        "risk_priority_choices": CapaInvestigation.RISK_PRIORITY_CHOICES,
    }
    return render(request, "quality/capamanagement/capa_investigation/list.html", context)


@login_required
def capa_investigation_detail(request, pk):
    capa = quality_object(
        request,
        CapaInvestigation,
        pk,
        select_related=[
            "lead_investigator",
            "quality_owner",
            "department",
            "design_project",
            "risk_assessment",
            "containment_verified_by",
            "closure_approved_by",
            "formal_closure_signature",
        ],
    )
    rcas = capa.root_cause_analyses.all().select_related("lead_investigator", "verified_by")
    actions = capa.actions.all().select_related("assigned_to", "verified_by", "controlled_document", "change_order")
    reviews = capa.effectiveness_reviews.all().select_related("evaluator", "formal_signature")

    context = {
        "capa": capa,
        "rcas": rcas,
        "actions": actions,
        "reviews": reviews,
    }
    return render(request, "quality/capamanagement/capa_investigation/detail.html", context)


@login_required
def capa_investigation_create(request):
    if request.method == "POST":
        form = CapaInvestigationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            capa = form.save()
            write_audit_log(request.user, capa, "create", tenant=request.tenant)
            messages.success(request, f"CAPA Investigation {capa.number} initialized successfully.")
            return redirect("quality:capa_investigation_detail", pk=capa.pk)
    else:
        form = CapaInvestigationForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "quality/capamanagement/capa_investigation/form.html", context)


@login_required
def capa_investigation_edit(request, pk):
    capa = quality_object(request, CapaInvestigation, pk)
    if capa.status == "closed":
        messages.warning(request, f"CAPA {capa.number} is closed and cannot be directly edited.")
        return redirect("quality:capa_investigation_detail", pk=capa.pk)

    if request.method == "POST":
        form = CapaInvestigationForm(request.POST, instance=capa, tenant=request.tenant)
        if form.is_valid():
            capa = form.save()
            write_audit_log(request.user, capa, "update", tenant=request.tenant)
            messages.success(request, f"CAPA Investigation {capa.number} updated successfully.")
            return redirect("quality:capa_investigation_detail", pk=capa.pk)
    else:
        form = CapaInvestigationForm(instance=capa, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "capa": capa,
    }
    return render(request, "quality/capamanagement/capa_investigation/form.html", context)


@require_POST
@tenant_admin_required
def capa_investigation_delete(request, pk):
    capa = quality_object(request, CapaInvestigation, pk)
    num = capa.number
    write_audit_log(request.user, capa, "delete", tenant=request.tenant)
    capa.delete()
    messages.success(request, f"CAPA Investigation {num} was deleted.")
    return redirect("quality:capa_investigation_list")


@require_POST
@login_required
def capa_investigation_advance_status(request, pk):
    capa = quality_object(request, CapaInvestigation, pk)
    target_status = request.POST.get("target_status", "").strip()

    valid_statuses = [choice[0] for choice in CapaInvestigation.STATUS_CHOICES]
    if target_status not in valid_statuses:
        messages.error(request, "Invalid lifecycle transition requested.")
        return redirect("quality:capa_investigation_detail", pk=capa.pk)

    if capa.status == "closed":
        messages.error(request, "Cannot advance or modify a closed CAPA.")
        return redirect("quality:capa_investigation_detail", pk=capa.pk)

    if target_status == "closed":
        messages.error(request, "Formal closure must be performed via the closure workflow.")
        return redirect("quality:capa_investigation_detail", pk=capa.pk)

    if target_status == "voided" and not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)):
        messages.error(request, "Only tenant administrators can void a CAPA investigation.")
        return redirect("quality:capa_investigation_detail", pk=capa.pk)

    old_status = capa.status
    capa.status = target_status
    capa.save()
    write_audit_log(request.user, capa, "advance", tenant=request.tenant)
    messages.success(request, f"CAPA {capa.number} transitioned from {old_status} to {capa.get_status_display()}.")
    return redirect("quality:capa_investigation_detail", pk=capa.pk)


@require_POST
@tenant_admin_required
def capa_investigation_close(request, pk):
    capa = quality_object(request, CapaInvestigation, pk)
    closure_summary = request.POST.get("closure_summary", "").strip()

    pending_actions = capa.actions.exclude(status__in=["implemented", "verified", "cancelled"]).count()
    if pending_actions > 0:
        messages.error(request, f"Cannot close CAPA: {pending_actions} action item(s) remain incomplete.")
        return redirect("quality:capa_investigation_detail", pk=capa.pk)

    capa.status = "closed"
    capa.closed_at = timezone.now()
    capa.closure_approved_by = request.user
    if closure_summary:
        capa.closure_summary = closure_summary
    capa.save()

    write_audit_log(request.user, capa, "close", tenant=request.tenant)
    messages.success(request, f"CAPA {capa.number} has been formally closed and verified.")
    return redirect("quality:capa_investigation_detail", pk=capa.pk)


@login_required
def capa_investigation_export(request):
    qs = quality_scope(CapaInvestigation.objects.all(), request).select_related(
        "lead_investigator", "quality_owner", "department"
    )

    response = HttpResponse(content_type="text/csv")
    filename = f"CAPA_Investigations_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "CAPA Number",
        "Title",
        "Action Type",
        "Source Type",
        "Source Reference",
        "Risk Priority",
        "Status",
        "Lead Investigator",
        "Quality Owner",
        "Target Closure Date",
        "Containment Implemented",
        "Is Escalated",
        "Created At",
    ])

    for c in qs:
        writer.writerow([
            csv_safe(c.number),
            csv_safe(c.title),
            csv_safe(c.get_action_type_display()),
            csv_safe(c.get_source_type_display()),
            csv_safe(c.source_reference),
            csv_safe(c.get_risk_priority_display()),
            csv_safe(c.get_status_display()),
            csv_safe(c.lead_investigator.username if c.lead_investigator else ""),
            csv_safe(c.quality_owner.username if c.quality_owner else ""),
            csv_safe(c.target_closure_date),
            csv_safe("Yes" if c.containment_implemented else "No"),
            csv_safe("Yes" if c.is_escalated else "No"),
            csv_safe(c.created_at.strftime("%Y-%m-%d %H:%M")),
        ])

    write_audit_log(request.user, CapaInvestigation(), "export", tenant=request.tenant)
    return response
