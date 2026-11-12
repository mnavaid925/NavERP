"""Function-based CRUD and CMDB Dependency Edge governance views (11.18)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.ItAssetManagement.CmdbRelationships import CmdbRelationshipForm
from apps.assets.models.ItAssetManagement.CmdbRelationships import CmdbRelationship
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.ItAssetManagement._helpers import (
    CMDB_REL_SELECT_RELATED,
    PAGE_SIZE,
    apply_choice_filter,
    csv_export_response,
)
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


def _filter_cmdb_queryset(request, base_qs):
    """Apply search and dropdown GET filters to a CmdbRelationship queryset."""
    qs = base_qs.select_related(*CMDB_REL_SELECT_RELATED)
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(blast_radius_notes__icontains=search_query)
            | Q(source_hardware__hostname__icontains=search_query)
            | Q(source_software__software_name__icontains=search_query)
            | Q(source_cloud__name__icontains=search_query)
            | Q(source_service__name__icontains=search_query)
            | Q(source_asset__name__icontains=search_query)
            | Q(target_hardware__hostname__icontains=search_query)
            | Q(target_software__software_name__icontains=search_query)
            | Q(target_cloud__name__icontains=search_query)
            | Q(target_service__name__icontains=search_query)
            | Q(target_asset__name__icontains=search_query)
        )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values={val for val, _ in CmdbRelationship.STATUS_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "relationship_type",
        allowed_values={val for val, _ in CmdbRelationship.RELATIONSHIP_TYPE_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "source_ci_type",
        allowed_values={val for val, _ in CmdbRelationship.CI_TYPE_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "target_ci_type",
        allowed_values={val for val, _ in CmdbRelationship.CI_TYPE_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "environment",
        allowed_values={val for val, _ in CmdbRelationship.ENVIRONMENT_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "criticality",
        allowed_values={val for val, _ in CmdbRelationship.CRITICALITY_CHOICES},
    )
    spof_param = request.GET.get("spof", "").strip().lower()
    if spof_param in ("1", "true", "yes"):
        qs = qs.filter(is_single_point_of_failure=True)
    elif spof_param in ("0", "false", "no"):
        qs = qs.filter(is_single_point_of_failure=False)
    return qs


def _matching_ci_filter(prefix, ci_key):
    """Build Q filter targeting the same CI node on outbound or inbound side."""
    if not ci_key:
        return Q(pk__isnull=True) & Q(pk__isnull=False)
    ci_type, pk = ci_key
    suffix = CmdbRelationship.CI_FIELD_BY_TYPE.get(ci_type)
    if not suffix:
        return Q(pk__isnull=True) & Q(pk__isnull=False)
    return Q(**{f"{prefix}_{suffix}_id": pk})


@login_required
def cmdb_relationship_list(request):
    """List CMDB dependency edges with blast-radius KPIs, filters, and pagination."""
    base_qs = assets_scope(CmdbRelationship.objects.all(), request)
    kpis = base_qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status="active")),
        spof_count=Count("id", filter=Q(status="active", is_single_point_of_failure=True)),
        tier1_count=Count("id", filter=Q(status="active", criticality="tier_1_mission_critical")),
    )
    filtered_qs = _filter_cmdb_queryset(request, base_qs)
    paginator = Paginator(filtered_qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "relationships": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "total_count": kpis["total_count"] or 0,
        "active_count": kpis["active_count"] or 0,
        "spof_count": kpis["spof_count"] or 0,
        "tier1_count": kpis["tier1_count"] or 0,
        "status_choices": CmdbRelationship.STATUS_CHOICES,
        "relationship_type_choices": CmdbRelationship.RELATIONSHIP_TYPE_CHOICES,
        "ci_type_choices": CmdbRelationship.CI_TYPE_CHOICES,
        "environment_choices": CmdbRelationship.ENVIRONMENT_CHOICES,
        "criticality_choices": CmdbRelationship.CRITICALITY_CHOICES,
        "search_query": request.GET.get("q", "").strip(),
    }
    return render(
        request,
        "assets/itassetmanagement/cmdb_relationship/list.html",
        context,
    )


@login_required
def cmdb_relationship_export_csv(request):
    """Export filtered CMDB dependency edges as a formula-safe CSV."""
    base_qs = assets_scope(CmdbRelationship.objects.all(), request)
    qs = _filter_cmdb_queryset(request, base_qs)
    headers = [
        "Edge #",
        "Source Type",
        "Source CI",
        "Relationship",
        "Target Type",
        "Target CI",
        "Environment",
        "Criticality",
        "Impact Severity",
        "SPOF",
        "Verified On",
        "Status",
    ]
    rows = (
        [
            rel.number,
            rel.get_source_ci_type_display(),
            rel.source_label,
            rel.get_relationship_type_display(),
            rel.get_target_ci_type_display(),
            rel.target_label,
            rel.get_environment_display(),
            rel.get_criticality_display(),
            rel.get_impact_severity_display(),
            "Yes" if rel.is_single_point_of_failure else "No",
            rel.verified_on.isoformat() if rel.verified_on else "",
            rel.get_status_display(),
        ]
        for rel in qs
    )
    return csv_export_response(
        filename="cmdb_relationships.csv",
        headers=headers,
        rows=rows,
    )


@login_required
def cmdb_relationship_create(request):
    """Create a new tenant-scoped CMDB dependency edge."""
    if request.method == "POST":
        form = CmdbRelationshipForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                relationship = form.save(commit=False)
                relationship.tenant = request.tenant
                if relationship.owner_id is None:
                    relationship.owner = request.user
                relationship.verified_on = timezone.now().date()
                relationship.verified_by = request.user
                relationship.save()
                write_audit_log(request.user, relationship, "create", tenant=request.tenant)
            messages.success(request, f"CMDB Relationship {relationship.number} created.")
            return redirect("assets:cmdb_relationship_detail", pk=relationship.pk)
    else:
        form = CmdbRelationshipForm(tenant=request.tenant)

    return render(
        request,
        "assets/itassetmanagement/cmdb_relationship/form.html",
        {
            "form": form,
            "relationship": None,
            "is_edit": False,
            "title": "New CMDB Dependency Edge",
        },
    )


@login_required
def cmdb_relationship_detail(request, pk):
    """Display a CMDB relationship edge along with adjacent neighbor edges."""
    relationship = assets_object(
        request,
        CmdbRelationship,
        pk,
        select_related=CMDB_REL_SELECT_RELATED,
    )
    related_source_edges = (
        CmdbRelationship.objects.filter(tenant=request.tenant)
        .filter(_matching_ci_filter("source", relationship.source_ci_key))
        .exclude(pk=relationship.pk)
        .select_related(*CMDB_REL_SELECT_RELATED)
        .order_by("-updated_at")
    )
    related_target_edges = (
        CmdbRelationship.objects.filter(tenant=request.tenant)
        .filter(_matching_ci_filter("target", relationship.target_ci_key))
        .exclude(pk=relationship.pk)
        .select_related(*CMDB_REL_SELECT_RELATED)
        .order_by("-updated_at")
    )
    return render(
        request,
        "assets/itassetmanagement/cmdb_relationship/detail.html",
        {
            "relationship": relationship,
            "related_source_edges": related_source_edges,
            "related_target_edges": related_target_edges,
        },
    )


@login_required
def cmdb_relationship_edit(request, pk):
    """Edit an unlocked CMDB relationship edge."""
    relationship = assets_object(request, CmdbRelationship, pk)
    if relationship.is_locked:
        messages.warning(
            request,
            f"CMDB Relationship {relationship.number} is severed and cannot be edited.",
        )
        return redirect("assets:cmdb_relationship_detail", pk=relationship.pk)

    if request.method == "POST":
        form = CmdbRelationshipForm(request.POST, instance=relationship, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                relationship = form.save()
                write_audit_log(request.user, relationship, "update", tenant=request.tenant)
            messages.success(request, f"CMDB Relationship {relationship.number} updated.")
            return redirect("assets:cmdb_relationship_detail", pk=relationship.pk)
    else:
        form = CmdbRelationshipForm(instance=relationship, tenant=request.tenant)

    return render(
        request,
        "assets/itassetmanagement/cmdb_relationship/form.html",
        {
            "form": form,
            "relationship": relationship,
            "is_edit": True,
            "title": f"Edit {relationship.number}",
        },
    )


@tenant_admin_required
@require_POST
def cmdb_relationship_delete(request, pk):
    """Delete an unlocked CMDB relationship edge (tenant admin only)."""
    relationship = assets_object(request, CmdbRelationship, pk)
    if relationship.is_locked:
        messages.warning(
            request,
            f"CMDB Relationship {relationship.number} is severed and cannot be deleted.",
        )
        return redirect("assets:cmdb_relationship_detail", pk=relationship.pk)
    number = relationship.number
    with transaction.atomic():
        write_audit_log(request.user, relationship, "delete", tenant=request.tenant)
        relationship.delete()
    messages.success(request, f"CMDB Relationship {number} deleted.")
    return redirect("assets:cmdb_relationship_list")


@login_required
@require_POST
def cmdb_relationship_verify(request, pk):
    """Verify CMDB dependency edge accuracy and stamp verification metadata."""
    relationship = assets_object(request, CmdbRelationship, pk)
    if relationship.is_locked:
        messages.warning(request, f"CMDB Relationship {relationship.number} is severed.")
        return redirect("assets:cmdb_relationship_detail", pk=relationship.pk)
    try:
        with transaction.atomic():
            relationship.verified_on = timezone.now().date()
            relationship.verified_by = request.user
            if relationship.status != "active":
                relationship.status = "active"
            relationship.full_clean()
            relationship.save(
                update_fields=["verified_on", "verified_by", "status", "updated_at"]
            )
            write_audit_log(request.user, relationship, "verify", tenant=request.tenant)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("assets:cmdb_relationship_detail", pk=relationship.pk)
    messages.success(request, f"CMDB Relationship {relationship.number} verified as active.")
    return redirect("assets:cmdb_relationship_detail", pk=relationship.pk)


@login_required
@require_POST
def cmdb_relationship_deprecate(request, pk):
    """Mark a CMDB relationship edge as deprecated pending cutover."""
    relationship = assets_object(request, CmdbRelationship, pk)
    if relationship.is_locked:
        messages.warning(request, f"CMDB Relationship {relationship.number} is severed.")
        return redirect("assets:cmdb_relationship_detail", pk=relationship.pk)
    with transaction.atomic():
        relationship.status = "deprecated"
        relationship.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, relationship, "deprec", tenant=request.tenant)
    messages.warning(request, f"CMDB Relationship {relationship.number} marked deprecated.")
    return redirect("assets:cmdb_relationship_detail", pk=relationship.pk)


@tenant_admin_required
@require_POST
def cmdb_relationship_sever(request, pk):
    """Permanently sever & lock a decommissioned CMDB relationship edge."""
    relationship = assets_object(request, CmdbRelationship, pk)
    if relationship.is_locked:
        messages.warning(request, f"CMDB Relationship {relationship.number} is already severed.")
        return redirect("assets:cmdb_relationship_detail", pk=relationship.pk)
    with transaction.atomic():
        relationship.status = "severed"
        relationship.severed_at = timezone.now()
        relationship.save(update_fields=["status", "severed_at", "updated_at"])
        write_audit_log(request.user, relationship, "sever", tenant=request.tenant)
    messages.success(request, f"CMDB Relationship {relationship.number} severed.")
    return redirect("assets:cmdb_relationship_detail", pk=relationship.pk)
