"""Function-based views for Asset Operating Procedures & LOTO Protocols (11.16)."""

import calendar
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetDocumentKnowledge.AssetOperatingProcedures import (
    AssetOperatingProcedureForm,
)
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetDocumentKnowledge.AssetOperatingProcedures import (
    AssetOperatingProcedure,
)
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.AssetDocumentKnowledge._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    is_asset_document_readable,
    is_tenant_admin_user,
    serve_protected_attachment,
)
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.scm.models.AssetManagement.Assets import Asset


def _add_months(start_date, months):
    """Advance a date by calendar months while clamping day-of-month cleanly."""
    total_months = start_date.month - 1 + max(1, int(months))
    year = start_date.year + total_months // 12
    month = total_months % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _next_proc_revision_label(current_label):
    """Increment SOP revision labels cleanly (Rev 1.0 -> Rev 2.0, else append +1)."""
    raw = (current_label or "").strip()
    if raw.startswith("Rev "):
        tail = raw[4:].strip()
        if "." in tail:
            major, _, minor = tail.partition(".")
            if major.isdigit():
                return f"Rev {int(major) + 1}.{minor}"
        if tail.isdigit():
            return f"Rev {int(tail) + 1}"
    return "Rev 2.0"


def _filter_procedure_queryset(request, base_qs):
    """Apply search and dropdown GET filters to an AssetOperatingProcedure queryset."""
    qs = base_qs.select_related(
        "operational_asset",
        "asset_category",
        "asset_model",
        "org_unit",
        "author",
        "safety_reviewer",
        "approved_by",
        "primary_document",
        "supersedes",
    )
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(required_qualification_code__icontains=search_query)
            | Q(required_ppe__icontains=search_query)
            | Q(revision_label__icontains=search_query)
        )
    qs = apply_choice_filter(
        qs,
        request,
        "procedure_type",
        allowed_values={val for val, _ in AssetOperatingProcedure.PROCEDURE_TYPE_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "safety_level",
        allowed_values={val for val, _ in AssetOperatingProcedure.SAFETY_LEVEL_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values={val for val, _ in AssetOperatingProcedure.STATUS_CHOICES},
    )
    qs = apply_fk_filter(qs, request, "operational_asset")
    qs = apply_fk_filter(qs, request, "asset_category")
    if request.GET.get("loto_only") == "1":
        qs = qs.filter(loto_required=True)
    return qs


_SOP_LINEAGE_FIELDS = (
    "id",
    "tenant_id",
    "number",
    "revision_label",
    "status",
    "supersedes_id",
)


def _build_procedure_detail_context(request, proc):
    """Shared context builder for SOP detail views with bounded lineage queries."""
    seen = {proc.pk}
    ancestors = []
    cur = proc
    for _ in range(25):
        next_id = cur.supersedes_id
        if not next_id or next_id in seen:
            break
        if "supersedes" in cur._state.fields_cache:
            nxt = cur._state.fields_cache["supersedes"]
        else:
            nxt = (
                AssetOperatingProcedure.objects.filter(
                    tenant=request.tenant, pk=next_id
                )
                .only(*_SOP_LINEAGE_FIELDS)
                .first()
            )
        if nxt is None or nxt.pk in seen or nxt.tenant_id != request.tenant.pk:
            break
        seen.add(nxt.pk)
        ancestors.append(nxt)
        cur = nxt

    descendants = []
    frontier_ids = [proc.pk]
    while frontier_ids and len(descendants) < 25:
        children = list(
            AssetOperatingProcedure.objects.filter(
                tenant=request.tenant, supersedes_id__in=frontier_ids
            )
            .only(*_SOP_LINEAGE_FIELDS)
            .order_by("pk")
        )
        next_frontier = []
        for child in children:
            if child.pk in seen:
                continue
            seen.add(child.pk)
            descendants.append(child)
            next_frontier.append(child.pk)
            if len(descendants) >= 25:
                break
        frontier_ids = next_frontier

    revision_history = list(reversed(ancestors)) + [proc] + descendants
    revision_history.reverse()

    certified_operators = (
        proc.operator_certifications.filter(tenant=request.tenant)
        .select_related("operator_party", "operator_user", "employee_profile__party")
        .order_by("expires_on", "number")
        if hasattr(proc, "operator_certifications")
        else AssetOperatingProcedure.objects.none()
    )
    linked_articles = (
        proc.knowledge_articles.filter(tenant=request.tenant).order_by("-updated_at")
        if hasattr(proc, "knowledge_articles")
        else AssetOperatingProcedure.objects.none()
    )

    is_admin = is_tenant_admin_user(request.user)
    return {
        "procedure": proc,
        "revision_history": revision_history,
        "certified_operators": certified_operators,
        "linked_articles": linked_articles,
        "can_view_primary_document": is_asset_document_readable(
            proc.primary_document, request.user
        ),
        "can_edit": proc.status in AssetOperatingProcedure.EDITABLE_STATUSES,
        "can_activate": (
            is_admin and proc.status in AssetOperatingProcedure.EDITABLE_STATUSES
        ),
    }


@login_required
def asset_operating_procedure_list(request):
    """SOP, PM protocol, and LOTO checklist list view."""
    today = timezone.localdate()
    base_qs = assets_scope(AssetOperatingProcedure.objects.all(), request)
    filtered_qs = _filter_procedure_queryset(request, base_qs)
    paginator = Paginator(filtered_qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "procedures": page_obj,
        "paginator": paginator,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": base_qs.count(),
        "active_count": base_qs.filter(status="active").count(),
        "loto_count": base_qs.filter(loto_required=True).count(),
        "overdue_review_count": base_qs.filter(
            status="active", next_review_date__lt=today
        ).count(),
        "type_choices": AssetOperatingProcedure.PROCEDURE_TYPE_CHOICES,
        "safety_choices": AssetOperatingProcedure.SAFETY_LEVEL_CHOICES,
        "status_choices": AssetOperatingProcedure.STATUS_CHOICES,
        "assets_list": Asset.objects.filter(tenant=request.tenant).order_by("name"),
        "categories": AssetCategory.objects.filter(tenant=request.tenant).order_by(
            "name"
        ),
        "search_query": request.GET.get("q", "").strip(),
    }
    return render(
        request,
        "assets/assetdocumentknowledge/asset_operating_procedure/list.html",
        context,
    )


@login_required
def asset_operating_procedure_export_csv(request):
    """Export filtered tenant SOPs & LOTO checklists as a hardened CSV download."""
    base_qs = assets_scope(AssetOperatingProcedure.objects.all(), request)
    filtered_qs = _filter_procedure_queryset(request, base_qs)
    headers = [
        "SOP #",
        "Title",
        "Type",
        "Safety Level",
        "Revision",
        "LOTO Required",
        "Duration (Min)",
        "Steps",
        "Status",
        "Asset",
        "Effective Date",
        "Next Review Date",
    ]
    rows = (
        [
            proc.number,
            proc.title,
            proc.get_procedure_type_display(),
            proc.get_safety_level_display(),
            proc.revision_label,
            "Yes" if proc.loto_required else "No",
            proc.estimated_duration_minutes,
            proc.step_count,
            proc.get_status_display(),
            str(proc.operational_asset) if proc.operational_asset else "",
            proc.effective_date.isoformat() if proc.effective_date else "",
            proc.next_review_date.isoformat() if proc.next_review_date else "",
        ]
        for proc in filtered_qs
    )
    return csv_export_response(
        filename="asset_operating_procedures_11_16.csv",
        headers=headers,
        rows=rows,
    )


@login_required
def asset_operating_procedure_detail(request, pk):
    """Controlled SOP detail view showing LOTO isolation matrix, steps, and qualified operators."""
    proc = assets_object(
        request,
        AssetOperatingProcedure,
        pk,
        select_related=(
            "operational_asset",
            "asset_category",
            "asset_model",
            "org_unit",
            "maintenance_schedule",
            "compliance_framework",
            "primary_document",
            "author",
            "safety_reviewer",
            "approved_by",
            "supersedes__supersedes__supersedes__supersedes",
        ),
    )
    context = _build_procedure_detail_context(request, proc)
    return render(
        request,
        "assets/assetdocumentknowledge/asset_operating_procedure/detail.html",
        context,
    )


@login_required
def asset_operating_procedure_print(request, pk):
    """Print-ready shop-floor SOP & LOTO bench sheet view."""
    proc = assets_object(
        request,
        AssetOperatingProcedure,
        pk,
        select_related=(
            "operational_asset",
            "asset_category",
            "asset_model",
            "org_unit",
            "primary_document",
            "author",
            "safety_reviewer",
            "maintenance_schedule",
            "approved_by",
            "supersedes",
        ),
    )
    return render(
        request,
        "assets/assetdocumentknowledge/asset_operating_procedure/print.html",
        {"procedure": proc},
    )


@login_required
def asset_operating_procedure_create(request):
    """Create a new Draft Operating Procedure / LOTO protocol."""
    if request.method == "POST":
        form = AssetOperatingProcedureForm(
            request.POST, request.FILES, tenant=request.tenant, user=request.user
        )
        if form.is_valid():
            proc = form.save(commit=False)
            proc.tenant = request.tenant
            proc.author = request.user
            proc.status = "draft"
            proc.save()
            write_audit_log(request.user, proc, "create", tenant=request.tenant)
            messages.success(request, f"Created SOP {proc.number}.")
            return redirect("assets:asset_operating_procedure_detail", pk=proc.pk)
    else:
        form = AssetOperatingProcedureForm(tenant=request.tenant, user=request.user)

    return render(
        request,
        "assets/assetdocumentknowledge/asset_operating_procedure/form.html",
        {
            "form": form,
            "procedure": None,
            "is_edit": False,
            "title": "New Operating Procedure (SOP)",
        },
    )


@login_required
def asset_operating_procedure_edit(request, pk):
    """Edit an unlocked Draft or Under Safety Review SOP."""
    proc = assets_object(request, AssetOperatingProcedure, pk)
    if proc.is_locked:
        messages.warning(
            request,
            f"SOP {proc.number} is {proc.get_status_display()} and locked. Clone a revision to update it.",
        )
        return redirect("assets:asset_operating_procedure_detail", pk=proc.pk)

    if request.method == "POST":
        form = AssetOperatingProcedureForm(
            request.POST,
            request.FILES,
            instance=proc,
            tenant=request.tenant,
            user=request.user,
        )
        if form.is_valid():
            updated = form.save()
            write_audit_log(request.user, updated, "update", tenant=request.tenant)
            messages.success(request, f"Updated SOP {updated.number}.")
            return redirect("assets:asset_operating_procedure_detail", pk=updated.pk)
    else:
        form = AssetOperatingProcedureForm(
            instance=proc, tenant=request.tenant, user=request.user
        )

    return render(
        request,
        "assets/assetdocumentknowledge/asset_operating_procedure/form.html",
        {
            "form": form,
            "procedure": proc,
            "is_edit": True,
            "title": f"Edit {proc.number}",
        },
    )


@login_required
@require_POST
@tenant_admin_required
def asset_operating_procedure_delete(request, pk):
    """Delete an unlocked Draft / Under Safety Review SOP."""
    proc = assets_object(request, AssetOperatingProcedure, pk)
    if proc.is_locked:
        messages.error(
            request,
            f"Cannot delete {proc.number} in status {proc.get_status_display()}. Retire it instead.",
        )
        return redirect("assets:asset_operating_procedure_detail", pk=proc.pk)
    proc_number = proc.number
    write_audit_log(request.user, proc, "delete", tenant=request.tenant)
    proc.delete()
    messages.success(request, f"Deleted SOP {proc_number}.")
    return redirect("assets:asset_operating_procedure_list")


@login_required
def asset_operating_procedure_download(request, pk):
    """Download the SOP supplementary attachment safely with nosniff."""
    proc = assets_object(request, AssetOperatingProcedure, pk)
    return serve_protected_attachment(
        proc, file_attr="attachment", original_filename_attr="original_filename"
    )


@login_required
@require_POST
def asset_operating_procedure_submit_review(request, pk):
    """Submit a Draft SOP for safety / EHS review."""
    with transaction.atomic():
        proc = assets_object(
            request,
            AssetOperatingProcedure,
            pk,
            queryset=AssetOperatingProcedure.objects.filter(
                tenant=request.tenant
            ).select_for_update(),
        )
        if proc.status != "draft":
            messages.warning(
                request,
                f"SOP {proc.number} must be Draft to submit for safety review.",
            )
            return redirect("assets:asset_operating_procedure_detail", pk=proc.pk)
        proc.status = "under_review"
        proc.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, proc, "review", tenant=request.tenant)
    messages.success(request, f"Submitted {proc.number} for safety review.")
    return redirect("assets:asset_operating_procedure_detail", pk=proc.pk)


@login_required
@require_POST
@tenant_admin_required
def asset_operating_procedure_activate(request, pk):
    """Activate a reviewed SOP and supersede any predecessor version."""
    with transaction.atomic():
        proc = assets_object(
            request,
            AssetOperatingProcedure,
            pk,
            queryset=AssetOperatingProcedure.objects.filter(
                tenant=request.tenant
            ).select_for_update(),
        )
        if proc.status not in AssetOperatingProcedure.EDITABLE_STATUSES:
            messages.warning(
                request,
                f"SOP {proc.number} cannot be activated from {proc.get_status_display()}.",
            )
            return redirect("assets:asset_operating_procedure_detail", pk=proc.pk)

        if proc.supersedes_id:
            prev = (
                AssetOperatingProcedure.objects.select_for_update()
                .filter(tenant=request.tenant, pk=proc.supersedes_id)
                .first()
            )
            if prev is not None and prev.status != "retired":
                prev.status = "superseded"
                prev.save(update_fields=["status", "updated_at"])

        if proc.effective_date is None:
            proc.effective_date = timezone.localdate()
        if proc.next_review_date is None:
            proc.next_review_date = _add_months(
                proc.effective_date, proc.review_cycle_months or 12
            )
        proc.status = "active"
        proc.approved_by = request.user
        proc.approved_at = timezone.now()
        proc.save(
            update_fields=[
                "status",
                "approved_by",
                "approved_at",
                "effective_date",
                "next_review_date",
                "updated_at",
            ]
        )
        write_audit_log(request.user, proc, "activate", tenant=request.tenant)
    messages.success(request, f"Activated SOP {proc.number} ({proc.revision_label}).")
    return redirect("assets:asset_operating_procedure_detail", pk=proc.pk)


@login_required
@require_POST
def asset_operating_procedure_clone_revision(request, pk):
    """Clone an SOP into a new Draft revision superseding the source SOP."""
    with transaction.atomic():
        source = assets_object(
            request,
            AssetOperatingProcedure,
            pk,
            queryset=AssetOperatingProcedure.objects.filter(
                tenant=request.tenant
            ).select_for_update(),
        )
        if source.status == "retired":
            messages.warning(
                request,
                f"Retired SOP {source.number} cannot be cloned into a new revision.",
            )
            return redirect("assets:asset_operating_procedure_detail", pk=source.pk)
        new_proc = AssetOperatingProcedure(
            tenant=request.tenant,
            title=source.title,
            procedure_type=source.procedure_type,
            safety_level=source.safety_level,
            revision_label=_next_proc_revision_label(source.revision_label),
            supersedes=source,
            purpose_scope=source.purpose_scope,
            hazard_warnings=source.hazard_warnings,
            required_ppe=source.required_ppe,
            loto_required=source.loto_required,
            loto_isolation_points=list(source.loto_isolation_points or []),
            procedure_steps=list(source.procedure_steps or []),
            required_qualification_code=source.required_qualification_code,
            estimated_duration_minutes=source.estimated_duration_minutes,
            review_cycle_months=source.review_cycle_months,
            status="draft",
            author=request.user,
            safety_reviewer=source.safety_reviewer,
            org_unit=source.org_unit,
            operational_asset=source.operational_asset,
            asset_category=source.asset_category,
            asset_model=source.asset_model,
            maintenance_schedule=source.maintenance_schedule,
            compliance_framework=source.compliance_framework,
            primary_document=source.primary_document,
        )
        new_proc.save()
        write_audit_log(
            request.user,
            new_proc,
            "revise",
            changes={"supersedes": source.number},
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"Created draft SOP revision {new_proc.number} ({new_proc.revision_label}).",
    )
    return redirect("assets:asset_operating_procedure_detail", pk=new_proc.pk)


@login_required
@require_POST
@tenant_admin_required
def asset_operating_procedure_retire(request, pk):
    """Retire a controlled operating procedure."""
    with transaction.atomic():
        proc = assets_object(
            request,
            AssetOperatingProcedure,
            pk,
            queryset=AssetOperatingProcedure.objects.filter(
                tenant=request.tenant
            ).select_for_update(),
        )
        if proc.status == "retired":
            messages.info(request, f"SOP {proc.number} is already retired.")
            return redirect("assets:asset_operating_procedure_detail", pk=proc.pk)
        proc.status = "retired"
        proc.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, proc, "retire", tenant=request.tenant)
    messages.success(request, f"Retired SOP {proc.number}.")
    return redirect("assets:asset_operating_procedure_detail", pk=proc.pk)
