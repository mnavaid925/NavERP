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
from apps.quality.forms.CapaManagement.CapaActions import CapaActionForm
from apps.quality.models.CapaManagement.CapaActions import CapaAction
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "%")):
        return f"'{text}"
    return text


@login_required
def capa_action_list(request):
    qs = quality_scope(CapaAction.objects.all(), request).select_related(
        "capa", "assigned_to", "department", "verified_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(capa__number__icontains=q)
        )

    action_type_filter = request.GET.get("type", "").strip()
    if action_type_filter:
        qs = qs.filter(action_type=action_type_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    capa_filter = request.GET.get("capa", "").strip()
    if capa_filter.isdigit():
        qs = qs.filter(capa_id=int(capa_filter))

    base_qs = quality_scope(CapaAction.objects.all(), request)
    today = timezone.now().date()
    stats = base_qs.aggregate(
        total_count=Count("id"),
        pending_count=Count("id", filter=Q(status__in=["pending", "in_progress"])),
        overdue_count=Count(
            "id",
            filter=Q(due_date__lt=today)
            & ~Q(status__in=["implemented", "verified", "cancelled"]),
        ),
    )

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "actions": page_obj,
        "total_count": stats["total_count"] or 0,
        "pending_count": stats["pending_count"] or 0,
        "overdue_count": stats["overdue_count"] or 0,
        "q": q,
        "action_type_filter": action_type_filter,
        "status_filter": status_filter,
        "capa_filter": capa_filter,
        "action_type_choices": CapaAction.ACTION_TYPE_CHOICES,
        "status_choices": CapaAction.STATUS_CHOICES,
    }
    return render(request, "quality/capamanagement/capa_action/list.html", context)


@login_required
def capa_action_detail(request, pk):
    action = quality_object(
        request,
        CapaAction,
        pk,
        select_related=[
            "capa",
            "root_cause",
            "assigned_to",
            "department",
            "controlled_document",
            "change_order",
            "design_project",
            "verified_by",
        ],
    )
    context = {"action": action}
    return render(request, "quality/capamanagement/capa_action/detail.html", context)


@login_required
def capa_action_create(request):
    initial = {}
    capa_param = request.GET.get("capa", "").strip()
    if capa_param.isdigit():
        initial["capa"] = int(capa_param)
    rca_param = request.GET.get("rca", "").strip()
    if rca_param.isdigit():
        initial["root_cause"] = int(rca_param)

    if request.method == "POST":
        form = CapaActionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            action = form.save()
            write_audit_log(request.user, action, "create", tenant=request.tenant)
            messages.success(request, f"CAPA Action Item {action.number} created successfully.")
            return redirect("quality:capa_action_detail", pk=action.pk)
    else:
        form = CapaActionForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "quality/capamanagement/capa_action/form.html", context)


@login_required
def capa_action_edit(request, pk):
    action = quality_object(request, CapaAction, pk)
    if action.status == "verified":
        messages.warning(request, f"Action {action.number} has been verified and cannot be directly modified.")
        return redirect("quality:capa_action_detail", pk=action.pk)

    if request.method == "POST":
        form = CapaActionForm(request.POST, instance=action, tenant=request.tenant)
        if form.is_valid():
            action = form.save()
            write_audit_log(request.user, action, "update", tenant=request.tenant)
            messages.success(request, f"CAPA Action {action.number} updated successfully.")
            return redirect("quality:capa_action_detail", pk=action.pk)
    else:
        form = CapaActionForm(instance=action, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "action": action,
    }
    return render(request, "quality/capamanagement/capa_action/form.html", context)


@require_POST
@tenant_admin_required
def capa_action_delete(request, pk):
    action = quality_object(request, CapaAction, pk)
    if action.status == "verified":
        messages.error(request, "Cannot delete a verified CAPA action item.")
        return redirect("quality:capa_action_detail", pk=action.pk)
    if action.capa.status == "closed":
        messages.error(request, "Cannot delete actions belonging to a closed CAPA.")
        return redirect("quality:capa_action_detail", pk=action.pk)
    num = action.number
    capa_pk = action.capa_id
    write_audit_log(request.user, action, "delete", tenant=request.tenant)
    action.delete()
    messages.success(request, f"CAPA Action {num} was deleted.")
    return redirect("quality:capa_investigation_detail", pk=capa_pk)


@require_POST
@login_required
def capa_action_mark_completed(request, pk):
    action = quality_object(request, CapaAction, pk)

    if action.status in ["verified", "cancelled"]:
        messages.warning(request, f"Action item is already {action.get_status_display()} and cannot be marked implemented.")
        return redirect("quality:capa_action_detail", pk=action.pk)

    notes = request.POST.get("implementation_notes", "").strip()

    action.status = "implemented"
    action.completion_date = timezone.now().date()
    if notes:
        action.implementation_notes = notes
    action.save()

    write_audit_log(request.user, action, "complete", tenant=request.tenant)
    messages.success(request, f"Action {action.number} marked as implemented.")
    return redirect("quality:capa_action_detail", pk=action.pk)


@require_POST
@login_required
def capa_action_verify(request, pk):
    action = quality_object(request, CapaAction, pk)

    if action.status == "verified":
        messages.warning(request, "Action item is already verified.")
        return redirect("quality:capa_action_detail", pk=action.pk)

    if action.status != "implemented":
        messages.error(request, "Only implemented actions can be verified.")
        return redirect("quality:capa_action_detail", pk=action.pk)

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
    if action.assigned_to and request.user == action.assigned_to and not is_admin:
        messages.error(request, "Separation of duties required: the assignee cannot verify their own action item.")
        return redirect("quality:capa_action_detail", pk=action.pk)

    evidence = request.POST.get("verification_evidence", "").strip()

    action.status = "verified"
    action.verified_by = request.user
    action.verified_on = timezone.now().date()
    if evidence:
        action.verification_evidence = evidence
    action.save()

    write_audit_log(request.user, action, "verify", tenant=request.tenant)
    messages.success(request, f"Action {action.number} verified by Quality.")
    return redirect("quality:capa_action_detail", pk=action.pk)


@login_required
def capa_action_export(request):
    qs = quality_scope(CapaAction.objects.all(), request).select_related(
        "capa", "assigned_to", "department", "verified_by"
    )

    response = HttpResponse(content_type="text/csv")
    filename = f"CAPA_Actions_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Action Number",
        "CAPA Number",
        "Action Type",
        "Title",
        "Assigned To",
        "Due Date",
        "Completion Date",
        "Status",
        "Verified By",
        "Verified On",
        "Created At",
    ])

    for a in qs:
        writer.writerow([
            csv_safe(a.number),
            csv_safe(a.capa.number if a.capa else ""),
            csv_safe(a.get_action_type_display()),
            csv_safe(a.title),
            csv_safe(a.assigned_to.username if a.assigned_to else ""),
            csv_safe(a.due_date),
            csv_safe(a.completion_date),
            csv_safe(a.get_status_display()),
            csv_safe(a.verified_by.username if a.verified_by else ""),
            csv_safe(a.verified_on),
            csv_safe(a.created_at.strftime("%Y-%m-%d %H:%M")),
        ])

    write_audit_log(request.user, CapaAction(), "export", tenant=request.tenant)
    return response
