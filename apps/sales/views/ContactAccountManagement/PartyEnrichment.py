from datetime import date, datetime, time, timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.core.crud import as_db_int, apply_search, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.models import AuditLog, Party
from apps.sales.forms.ContactAccountManagement.PartyEnrichment import (
    PartyEnrichmentApplyForm,
    PartyEnrichmentProposalForm,
    PartyEnrichmentRejectForm,
)
from apps.sales.models.ContactAccountManagement.PartyEnrichment import PartyEnrichmentEvent
from apps.sales.services import (
    _enrichment_canonical_values,
    apply_enrichment_event,
    create_enrichment_event,
    reject_enrichment_event,
)
from apps.sales.views._common import *


def _enrichment_queryset(request):
    return PartyEnrichmentEvent.objects.filter(tenant=request.tenant).select_related(
        "party", "legal_basis_purpose", "requested_by", "reviewed_by"
    )


def _filter_enrichment_queryset(request, queryset):
    filters = {
        "q": request.GET.get("q", "").strip(),
        "party": as_db_int(request.GET.get("party")),
        "kind": request.GET.get("kind", ""),
        "source_kind": request.GET.get("source_kind", ""),
        "status": request.GET.get("status", ""),
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
    }
    queryset = apply_search(
        queryset,
        filters["q"],
        ["party__name", "source_name", "source_reference", "error_code", "error_summary"],
    )
    if filters["party"]:
        queryset = queryset.filter(party_id=filters["party"])
    if filters["kind"] in dict(PartyEnrichmentEvent.KIND_CHOICES):
        queryset = queryset.filter(kind=filters["kind"])
    if filters["source_kind"] in dict(PartyEnrichmentEvent.SOURCE_KIND_CHOICES):
        queryset = queryset.filter(source_kind=filters["source_kind"])
    if filters["status"] in dict(PartyEnrichmentEvent.STATUS_CHOICES):
        queryset = queryset.filter(status=filters["status"])
    from_date = safe_parse_date(filters["date_from"]) if filters["date_from"] else None
    to_date = safe_parse_date(filters["date_to"]) if filters["date_to"] else None
    current_timezone = timezone.get_current_timezone()
    if from_date:
        queryset = queryset.filter(occurred_at__gte=timezone.make_aware(datetime.combine(from_date, time.min), current_timezone))
    if to_date:
        if to_date == date.max:
            queryset = queryset.filter(
                occurred_at__lte=timezone.make_aware(datetime.combine(to_date, time.max), current_timezone)
            )
        else:
            queryset = queryset.filter(
                occurred_at__lt=timezone.make_aware(datetime.combine(to_date + timedelta(days=1), time.min), current_timezone)
            )
    return queryset, filters


@login_required
def party_enrichment_list(request):
    queryset = _enrichment_queryset(request)
    queryset, filters = _filter_enrichment_queryset(request, queryset)
    q = filters["q"]
    party_id = filters["party"]
    kind = filters["kind"]
    source_kind = filters["source_kind"]
    status = filters["status"]
    date_from = filters["date_from"]
    date_to = filters["date_to"]
    page_obj = paginate(request, queryset, 20)
    stats_base = _enrichment_queryset(request)
    stats_rows = stats_base.aggregate(
        total=Count("pk"),
        proposed=Count("pk", filter=Q(status="proposed")),
        applied=Count("pk", filter=Q(status="applied")),
        rejected=Count("pk", filter=Q(status="rejected")),
        no_match=Count("pk", filter=Q(status="no_match")),
        failed=Count("pk", filter=Q(status="failed")),
    )
    export_url = reverse("sales:party_enrichment_export")
    if request.GET:
        export_url = f"{export_url}?{request.GET.urlencode()}"
    return render(request, "sales/contactaccountmanagement/partyenrichmentevent/list.html", {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "parties": list(Party.objects.filter(tenant=request.tenant).order_by("name")[:500]),
        "kind_choices": PartyEnrichmentEvent.KIND_CHOICES,
        "source_kind_choices": PartyEnrichmentEvent.SOURCE_KIND_CHOICES,
        "status_choices": PartyEnrichmentEvent.STATUS_CHOICES,
        "party_id": party_id or "",
        "kind": kind,
        "source_kind": source_kind,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
        "stats": stats_rows,
        "proposal_form": PartyEnrichmentProposalForm(tenant=request.tenant),
        "export_url": export_url,
    })


@login_required
def party_enrichment_detail(request, pk):
    obj = get_object_or_404(_enrichment_queryset(request), pk=pk)
    audit_events = AuditLog.objects.filter(
        tenant=request.tenant,
        content_type=ContentType.objects.get_for_model(PartyEnrichmentEvent),
        object_id=obj.pk,
    ).select_related("user").order_by("-at")[:20]
    canonical_values = _enrichment_canonical_values(obj.party)
    proposal_rows = [
        {
            "field": field_name,
            "value": proposal.get("value"),
            "current": canonical_values.get(field_name),
            "confidence": proposal.get("confidence"),
        }
        for field_name, proposal in (obj.changes or {}).items()
    ]
    export_url = reverse("sales:party_enrichment_export")
    if request.GET:
        export_url = f"{export_url}?{request.GET.urlencode()}"
    return render(request, "sales/contactaccountmanagement/partyenrichmentevent/detail.html", {
        "obj": obj,
        "party": obj.party,
        "proposal_rows": proposal_rows,
        "canonical_values": canonical_values,
        "can_apply": obj.status == "proposed" and (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        "can_reject": obj.status == "proposed",
        "apply_form": PartyEnrichmentApplyForm(tenant=request.tenant, event=obj),
        "reject_form": PartyEnrichmentRejectForm(tenant=request.tenant),
        "audit_events": audit_events,
        "export_url": export_url,
    })


@require_POST
@login_required
def party_enrichment_request(request):
    form = PartyEnrichmentProposalForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "The enrichment proposal could not be saved.")
        return redirect("sales:party_enrichment_list")
    try:
        event = create_enrichment_event(
            request.tenant,
            request.user,
            party=form.cleaned_data["party"],
            kind=form.cleaned_data["kind"],
            source_kind=form.cleaned_data["source_kind"],
            source_name=form.cleaned_data.get("source_name", ""),
            source_reference=form.cleaned_data.get("source_reference", ""),
            changes=form.cleaned_data.get("changes") or {},
            legal_basis_purpose=form.cleaned_data.get("legal_basis_purpose"),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:party_enrichment_list")
    messages.success(request, "Enrichment proposal submitted for review.")
    return redirect("sales:party_enrichment_detail", pk=event.pk)


@require_POST
@tenant_admin_required
def party_enrichment_apply(request, pk):
    obj = get_object_or_404(_enrichment_queryset(request), pk=pk)
    form = PartyEnrichmentApplyForm(request.POST, tenant=request.tenant, event=obj)
    if not form.is_valid():
        messages.error(request, "Choose at least one valid field to apply.")
        return redirect("sales:party_enrichment_detail", pk=obj.pk)
    try:
        apply_enrichment_event(
            obj,
            request.tenant,
            request.user,
            form.cleaned_data["selected_fields"],
            form.cleaned_data.get("review_note", ""),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:party_enrichment_detail", pk=obj.pk)
    messages.success(request, "Selected enrichment fields were applied.")
    return redirect("sales:party_enrichment_detail", pk=obj.pk)


@require_POST
@login_required
def party_enrichment_reject(request, pk):
    obj = get_object_or_404(_enrichment_queryset(request), pk=pk)
    form = PartyEnrichmentRejectForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "A rejection reason is required.")
        return redirect("sales:party_enrichment_detail", pk=obj.pk)
    try:
        reject_enrichment_event(obj, request.tenant, request.user, form.cleaned_data["review_note"])
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:party_enrichment_detail", pk=obj.pk)
    messages.success(request, "Enrichment proposal rejected.")
    return redirect("sales:party_enrichment_detail", pk=obj.pk)


@login_required
def party_enrichment_export(request):
    queryset, filters = _filter_enrichment_queryset(request, _enrichment_queryset(request))
    rows = (
        (
            obj.party.name,
            obj.get_kind_display(),
            obj.source_name or obj.get_source_kind_display(),
            obj.get_status_display(),
            obj.occurred_at.isoformat(),
            obj.applied_at.isoformat() if obj.applied_at else "",
            obj.error_code,
            obj.error_summary,
        )
        for obj in queryset.order_by("-occurred_at", "-id")[:5000]
    )
    return csv_export_response(
        request,
        filename="sales-enrichment-events.csv",
        dataset="party_enrichment_events",
        headers=["Party", "Kind", "Source", "Status", "Occurred", "Applied", "Error code", "Error summary"],
        rows=rows,
        filters={key: value for key, value in filters.items() if key != "q"},
    )
