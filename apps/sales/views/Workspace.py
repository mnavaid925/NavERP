from copy import copy
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist, FieldError, ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.models import AuditLog, Document
from apps.crm.models import (
    CalendarEvent,
    CommunicationLog,
    ContractDocument,
    CrmTask,
    Opportunity,
    Territory,
)
from apps.sales.forms.CompetitiveIntelligence.CompetitiveIntelligence import OpportunityCompetitorForm
from apps.sales.forms.OpportunityOutcomes.OpportunityOutcomes import OpportunityTransitionForm
from apps.sales.forms.OpportunityPipeline.Pipelines import OpportunityPipelinePlacementForm
from apps.sales.forms.OpportunityTeams.OpportunityTeams import OpportunityTeamMemberForm
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import (
    CompetitorProfile,
    OpportunityCompetitor,
)
from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import (
    OpportunityOutcome,
    WinLossReason,
)
from apps.sales.models.OpportunityPipeline.Pipelines import (
    OpportunityPipelinePlacement,
    Pipeline,
    PipelineStage,
)
from apps.sales.models.OpportunityTeams.OpportunityTeams import OpportunityTeamMember

from apps.sales.opportunity_analytics import (
    SALES_HEALTH_CHOICES,
    opportunity_pipeline_health_projection,
)
from apps.sales.opportunity_services import (
    sales_allowed_transition_stages,
    sales_place_opportunity,
    sales_unplace_opportunity,
)


_WORKSPACE_PAGE_SIZE = 20
_WORKSPACE_ACTIVITY_LIMIT = 50
_WORKSPACE_RELATION_LIMIT = 100
_WORKSPACE_TIMELINE_LIMIT = 100


def _workspace_positive_id(value):
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if 0 < parsed <= 9223372036854775807 else None


def _workspace_opportunity_related_fields():
    fields = ["account", "primary_contact", "owner", "territory"]
    try:
        Opportunity._meta.get_field("currency")
    except FieldDoesNotExist:
        return tuple(fields)
    return tuple(fields + ["currency"])


def _workspace_opportunity_queryset(tenant):
    queryset = Opportunity.objects.filter(tenant=tenant)
    related_fields = _workspace_opportunity_related_fields()
    try:
        return queryset.select_related(
            *related_fields,
            "sales_pipeline_placement__pipeline",
            "sales_pipeline_placement__current_stage",
        )
    except FieldError:
        return queryset.select_related(*related_fields)


def _workspace_cached_placement(opportunity):
    try:
        return getattr(opportunity, "sales_pipeline_placement", None)
    except (AttributeError, ObjectDoesNotExist):
        return None


def _workspace_placement_queryset(tenant, opportunity):
    return (
        OpportunityPipelinePlacement.objects.filter(
            tenant=tenant,
            opportunity=opportunity,
        )
        .select_related("pipeline", "current_stage")
    )


def _workspace_pipeline_queryset(tenant):
    if tenant is None:
        return Pipeline.objects.none()
    return Pipeline.objects.filter(tenant=tenant, is_active=True).order_by(
        "-is_default",
        "name",
        "-created_at",
    )


def _workspace_default_pipeline(pipelines):
    for pipeline in pipelines:
        if pipeline.is_default:
            return pipeline
    return pipelines[0] if pipelines else None


def _workspace_selected_pipeline(request, pipelines):
    requested_id = _workspace_positive_id(request.GET.get("pipeline"))
    selected = next((pipeline for pipeline in pipelines if pipeline.pk == requested_id), None)
    return selected or _workspace_default_pipeline(pipelines)


def _workspace_stage_queryset(tenant, pipeline):
    if tenant is None or pipeline is None:
        return PipelineStage.objects.none()
    return PipelineStage.objects.filter(
        tenant=tenant,
        pipeline=pipeline,
        is_active=True,
    ).order_by("sequence", "pk")


def _workspace_currency_label(opportunity):
    currency = getattr(opportunity, "currency", None)
    code = getattr(currency, "code", None)
    return str(code).strip().upper() if code else "Unspecified"


def _workspace_effective_probability(opportunity, placement):
    if placement is not None:
        try:
            return placement.effective_probability
        except (AttributeError, ObjectDoesNotExist):
            pass
    try:
        return int(opportunity.probability or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def _workspace_weighted_amount(opportunity, placement):
    amount = Decimal(opportunity.amount or 0)
    probability = Decimal(_workspace_effective_probability(opportunity, placement))
    return amount * probability / Decimal(100)


def _workspace_attach_row_data(opportunity, placement, health):
    opportunity.workspace_placement = placement
    opportunity.workspace_pipeline = placement.pipeline if placement is not None else None
    opportunity.workspace_stage = placement.current_stage if placement is not None else None
    opportunity.workspace_health = health
    opportunity.workspace_currency_label = _workspace_currency_label(opportunity)
    opportunity.workspace_effective_probability = _workspace_effective_probability(
        opportunity,
        placement,
    )
    opportunity.workspace_weighted_amount = _workspace_weighted_amount(opportunity, placement)


def _workspace_health_fallback():
    return {
        "opportunity_id": None,
        "status": "watch",
        "health_status": "watch",
        "factors": [
            {
                "key": "health_unavailable",
                "label": "Health unavailable",
                "severity": "watch",
                "detail": "Deal health could not be computed; review the opportunity data.",
                "date": None,
            }
        ],
        "stage_age_days": 0,
        "target_days": None,
        "last_activity_at": None,
        "as_of": timezone.now().isoformat(),
    }


def _workspace_health_row(projection, opportunity_id):
    row = projection.get(opportunity_id)
    if not isinstance(row, dict) or not row.get("status"):
        return _workspace_health_fallback()
    return row


def _workspace_currency_stats(opportunities):
    rows = {}
    for opportunity in opportunities:
        label = getattr(opportunity, "workspace_currency_label", None) or "Unspecified"
        code = None if label == "Unspecified" else label
        row = rows.setdefault(
            label,
            {
                "currency_code": code,
                "currency_label": label,
                "count": 0,
                "amount": Decimal("0"),
                "weighted_amount": Decimal("0"),
            },
        )
        row["count"] += 1
        row["amount"] += Decimal(opportunity.amount or 0)
        row["weighted_amount"] += getattr(
            opportunity,
            "workspace_weighted_amount",
            Decimal("0"),
        )
    result = [rows[label] for label in sorted(rows)]
    return result


def _workspace_stats(opportunities):
    placed = sum(1 for opportunity in opportunities if opportunity.workspace_placement is not None)
    open_count = sum(1 for opportunity in opportunities if opportunity.stage in Opportunity.OPEN_STAGES)
    won_count = sum(1 for opportunity in opportunities if opportunity.stage == "closed_won")
    lost_count = sum(1 for opportunity in opportunities if opportunity.stage == "closed_lost")
    currency_totals = _workspace_currency_stats(opportunities)
    stats = {
        "total": len(opportunities),
        "placed": placed,
        "unplaced": len(opportunities) - placed,
        "open": open_count,
        "closed": won_count + lost_count,
        "won": won_count,
        "lost": lost_count,
        "currency_totals": currency_totals,
        "currency_count": len(currency_totals),
        "mixed_currencies": len(currency_totals) > 1,
    }
    if len(currency_totals) <= 1:
        stats["amount"] = currency_totals[0]["amount"] if currency_totals else Decimal("0")
        stats["weighted_amount"] = (
            currency_totals[0]["weighted_amount"] if currency_totals else Decimal("0")
        )
    else:
        stats["amount"] = None
        stats["weighted_amount"] = None
    return stats


def _workspace_excerpt(value, length=180):
    if not value:
        return ""
    text = str(value).strip()
    return text if len(text) <= length else text[: length - 1] + "…"


def _workspace_activity_row(kind, at, title, detail, url=""):
    return {
        "kind": kind,
        "at": at,
        "title": title or "Activity",
        "detail": detail or "",
        "url": url or "",
    }


def _workspace_activity_timeline(tasks, communications, events, outcomes, audit_entries, user=None):
    can_view_audit = bool(user and (user.is_superuser or getattr(user, "is_tenant_admin", False)))
    rows = []
    for task in tasks:
        rows.append(
            _workspace_activity_row(
                "task",
                task.updated_at,
                task.subject,
                f"{task.get_type_display()} · {task.get_status_display()}",
                reverse("crm:task_detail", kwargs={"pk": task.pk}),
            )
        )
    for communication in communications:
        detail = communication.subject or communication.get_channel_display()
        if communication.body:
            detail = f"{detail} · {_workspace_excerpt(communication.body)}"
        rows.append(
            _workspace_activity_row(
                "communication",
                communication.occurred_at,
                communication.subject or communication.get_channel_display(),
                detail,
                reverse("crm:communicationlog_detail", kwargs={"pk": communication.pk}),
            )
        )
    for event in events:
        rows.append(
            _workspace_activity_row(
                "event",
                event.start,
                event.title,
                event.location or event.get_event_type_display(),
                reverse("crm:calendarevent_detail", kwargs={"pk": event.pk}),
            )
        )
    for outcome in outcomes:
        reason_name = outcome.reason.name if outcome.reason_id and outcome.reason else ""
        detail = reason_name or outcome.get_result_display()
        if outcome.notes:
            detail = f"{detail} · {_workspace_excerpt(outcome.notes)}"
        rows.append(
            _workspace_activity_row(
                "outcome",
                outcome.closed_at,
                outcome.get_result_display(),
                detail,
            )
        )
    for audit_entry in audit_entries:
        changes = audit_entry.changes if isinstance(audit_entry.changes, dict) else {}
        operation = changes.get("operation") or changes.get("action") or audit_entry.get_action_display()
        audit_url = (
            reverse("core:auditlog_detail", kwargs={"pk": audit_entry.pk})
            if can_view_audit
            else ""
        )
        rows.append(
            _workspace_activity_row(
                "audit",
                audit_entry.at,
                audit_entry.target or audit_entry.get_action_display(),
                str(operation),
                audit_url,
            )
        )
    rows = [row for row in rows if row["at"] is not None]
    rows.sort(key=lambda row: row["at"], reverse=True)
    return rows[:_WORKSPACE_TIMELINE_LIMIT]


def _workspace_audit_entries(
    tenant,
    opportunity,
    placement,
    team_members,
    competitor_links,
    outcomes,
):
    content_type = ContentType.objects.get_for_model(Opportunity)
    query = Q(content_type=content_type, object_id=opportunity.pk)
    related = (
        (OpportunityPipelinePlacement, [placement.pk] if placement is not None else []),
        (OpportunityTeamMember, [member.pk for member in team_members]),
        (OpportunityCompetitor, [link.pk for link in competitor_links]),
        (OpportunityOutcome, [outcome.pk for outcome in outcomes]),
    )
    for model, object_ids in related:
        if not object_ids:
            continue
        query |= Q(
            content_type=ContentType.objects.get_for_model(model),
            object_id__in=object_ids,
        )
    return list(
        AuditLog.objects.filter(tenant=tenant)
        .filter(query)
        .select_related("user")
        .order_by("-at", "-id")[:_WORKSPACE_ACTIVITY_LIMIT]
    )


def _workspace_placement_form(
    opportunity,
    tenant,
    *,
    data=None,
    instance=None,
    selected_pipeline=None,
):
    form_instance = copy(instance) if instance is not None else OpportunityPipelinePlacement(
        tenant=tenant,
        opportunity=opportunity,
    )
    form = OpportunityPipelinePlacementForm(
        data,
        instance=form_instance,
        tenant=tenant,
        selected_pipeline=selected_pipeline,
    )
    form.fields["opportunity"].queryset = Opportunity.objects.filter(
        tenant=tenant,
        pk=opportunity.pk,
    )
    form.fields["opportunity"].widget = forms.HiddenInput()
    form.fields["opportunity"].disabled = True
    form.fields["opportunity"].initial = opportunity.pk
    if selected_pipeline is not None:
        form.initial["pipeline"] = selected_pipeline.pk
        form.fields["pipeline"].initial = selected_pipeline.pk
        form.fields["pipeline"].disabled = True
    return form


def _workspace_error_message(exc):
    return " ".join(getattr(exc, "messages", [str(exc)]))[:500]


@login_required
def opportunity_workspace_list(request):
    tenant = request.tenant
    q = request.GET.get("q", "").strip()[:200]
    health = request.GET.get("health", "").strip().lower()
    owner_id = _workspace_positive_id(request.GET.get("owner"))
    territory_id = _workspace_positive_id(request.GET.get("territory"))
    pipeline_id = _workspace_positive_id(request.GET.get("pipeline"))
    if health not in dict(SALES_HEALTH_CHOICES):
        health = ""

    pipelines = list(_workspace_pipeline_queryset(tenant))
    owners = (
        []
        if tenant is None
        else list(User.objects.filter(tenant=tenant, is_active=True).order_by("email"))
    )
    territories = (
        []
        if tenant is None
        else list(Territory.objects.filter(tenant=tenant, is_active=True).order_by("name"))
    )

    queryset = _workspace_opportunity_queryset(tenant)
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(name__icontains=q)
            | Q(account__name__icontains=q)
            | Q(primary_contact__name__icontains=q)
            | Q(owner__email__icontains=q)
            | Q(owner__username__icontains=q)
        )
    if owner_id is not None:
        queryset = queryset.filter(owner_id=owner_id)
    if territory_id is not None:
        queryset = queryset.filter(territory_id=territory_id)
    if pipeline_id is not None:
        queryset = queryset.filter(sales_pipeline_placement__pipeline_id=pipeline_id)

    if not health:
        page_obj = Paginator(queryset.order_by("-updated_at", "-id"), _WORKSPACE_PAGE_SIZE).get_page(
            request.GET.get("page")
        )
        page_opportunities = list(page_obj.object_list)
        placements = []
        for opportunity in page_opportunities:
            placement = _workspace_cached_placement(opportunity)
            if placement is not None:
                placements.append(placement)
        as_of = timezone.now()
        health_projection = opportunity_pipeline_health_projection(
            tenant,
            page_opportunities,
            placements,
            as_of=as_of,
        )
        for opportunity in page_opportunities:
            health_row = _workspace_health_row(health_projection, opportunity.pk)
            _workspace_attach_row_data(
                opportunity,
                _workspace_cached_placement(opportunity),
                health_row,
            )

        health_counts = {"on_track": 0, "watch": 0, "at_risk": 0}
        for opportunity in page_opportunities:
            status = opportunity.workspace_health.get("status")
            if status in health_counts:
                health_counts[status] += 1
        stats = _workspace_stats(page_opportunities)
        stats["total"] = page_obj.paginator.count
        stats["placed"] = queryset.filter(sales_pipeline_placement__isnull=False).count()
        stats["unplaced"] = stats["total"] - stats["placed"]
        stats["scope_total"] = page_obj.paginator.count
        return render(
            request,
            "sales/opportunity/workspace.html",
            {
                "opportunities": page_opportunities,
                "page_obj": page_obj,
                "q": q,
                "health": health,
                "owner_id": owner_id,
                "territory_id": territory_id,
                "pipeline_id": pipeline_id,
                "pipelines": pipelines,
                "owners": owners,
                "territories": territories,
                "health_choices": SALES_HEALTH_CHOICES,
                "health_counts": health_counts,
                "stats": stats,
            },
        )

    scope_opportunities = list(queryset.order_by("-updated_at", "-id"))
    placements = []
    for opportunity in scope_opportunities:
        placement = _workspace_cached_placement(opportunity)
        if placement is not None:
            placements.append(placement)
    as_of = timezone.now()
    health_projection = opportunity_pipeline_health_projection(
        tenant,
        scope_opportunities,
        placements,
        as_of=as_of,
    )
    for opportunity in scope_opportunities:
        health_row = _workspace_health_row(health_projection, opportunity.pk)
        _workspace_attach_row_data(opportunity, _workspace_cached_placement(opportunity), health_row)

    visible_opportunities = []
    for opportunity in scope_opportunities:
        if health and opportunity.workspace_health.get("status") != health:
            continue
        visible_opportunities.append(opportunity)
    health_counts = {"on_track": 0, "watch": 0, "at_risk": 0}
    for opportunity in visible_opportunities:
        status = opportunity.workspace_health.get("status")
        if status in health_counts:
            health_counts[status] += 1
    page_obj = Paginator(visible_opportunities, _WORKSPACE_PAGE_SIZE).get_page(request.GET.get("page"))
    stats = _workspace_stats(visible_opportunities)
    stats["scope_total"] = len(scope_opportunities)
    return render(
        request,
        "sales/opportunity/workspace.html",
        {
            "opportunities": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "health": health,
            "owner_id": owner_id,
            "territory_id": territory_id,
            "pipeline_id": pipeline_id,
            "pipelines": pipelines,
            "owners": owners,
            "territories": territories,
            "health_choices": SALES_HEALTH_CHOICES,
            "health_counts": health_counts,
            "stats": stats,
        },
    )


@login_required
def opportunity_workspace_detail(request, opportunity_pk):
    tenant = request.tenant
    opportunity = get_object_or_404(
        _workspace_opportunity_queryset(tenant),
        pk=opportunity_pk,
        tenant=tenant,
    )
    placement = _workspace_cached_placement(opportunity)
    if placement is None:
        placement = _workspace_placement_queryset(tenant, opportunity).first()
    pipelines = list(_workspace_pipeline_queryset(tenant))
    pipeline = placement.pipeline if placement is not None else _workspace_default_pipeline(pipelines)
    current_stage = placement.current_stage if placement is not None else None
    stages = list(_workspace_stage_queryset(tenant, pipeline))

    placement_form = _workspace_placement_form(
        opportunity,
        tenant,
        instance=placement,
        selected_pipeline=pipeline,
    )
    team_member_form = OpportunityTeamMemberForm(
        opportunity=opportunity,
        tenant=tenant,
    )
    competitor_form = OpportunityCompetitorForm(
        opportunity=opportunity,
        tenant=tenant,
    )
    closure_form = OpportunityTransitionForm(
        tenant=tenant,
        opportunity=opportunity,
        placement=placement,
        current_stage=current_stage,
        allowed_target_stages=sales_allowed_transition_stages(placement),
    )

    team_members = list(
        OpportunityTeamMember.objects.filter(
            tenant=tenant,
            opportunity=opportunity,
        )
        .select_related("user", "org_unit")
        .order_by("is_active", "role", "id")[:_WORKSPACE_RELATION_LIMIT]
    )
    competitor_links = list(
        OpportunityCompetitor.objects.filter(
            tenant=tenant,
            opportunity=opportunity,
        )
        .select_related("competitor_profile__party")
        .order_by("-is_primary", "relationship", "id")[:_WORKSPACE_RELATION_LIMIT]
    )
    competitor_profiles = list(
        CompetitorProfile.objects.filter(tenant=tenant, is_active=True)
        .select_related("party")
        .order_by("party__name")[:_WORKSPACE_RELATION_LIMIT]
    )
    outcomes = list(
        OpportunityOutcome.objects.filter(
            tenant=tenant,
            opportunity=opportunity,
        )
        .select_related("reason", "competitor_link__competitor_profile__party", "recorded_by")
        .order_by("-closed_at", "-id")[:_WORKSPACE_RELATION_LIMIT]
    )
    win_loss_reasons = list(
        WinLossReason.objects.filter(tenant=tenant, is_active=True).order_by(
            "result",
            "sequence",
            "name",
            "pk",
        )[:_WORKSPACE_RELATION_LIMIT]
    )
    tasks = list(
        CrmTask.objects.filter(tenant=tenant, related_opportunity=opportunity)
        .select_related("owner")
        .order_by("-updated_at", "-id")[:_WORKSPACE_ACTIVITY_LIMIT]
    )
    communications = list(
        CommunicationLog.objects.filter(tenant=tenant, related_opportunity=opportunity)
        .select_related("owner")
        .order_by("-occurred_at", "-id")[:_WORKSPACE_ACTIVITY_LIMIT]
    )
    events = list(
        CalendarEvent.objects.filter(tenant=tenant, related_opportunity=opportunity)
        .select_related("owner", "party")
        .order_by("-start", "-id")[:_WORKSPACE_ACTIVITY_LIMIT]
    )
    contracts = list(
        ContractDocument.objects.filter(tenant=tenant, opportunity=opportunity)
        .select_related("template", "account", "owner")
        .defer("body_snapshot")
        .order_by("-created_at", "-id")[:_WORKSPACE_ACTIVITY_LIMIT]
    )
    opportunity_content_type = ContentType.objects.get_for_model(Opportunity)
    documents = list(
        Document.objects.filter(
            tenant=tenant,
            content_type=opportunity_content_type,
            object_id=opportunity.pk,
        ).order_by("-uploaded_at", "-id")[:_WORKSPACE_ACTIVITY_LIMIT]
    )
    for document in documents:
        try:
            document.workspace_file_url = document.file.url if document.file and document.file.name else ""
        except (AttributeError, ValueError):
            document.workspace_file_url = ""
    audit_entries = _workspace_audit_entries(
        tenant,
        opportunity,
        placement,
        team_members,
        competitor_links,
        outcomes,
    )
    as_of = timezone.now()
    health_projection = opportunity_pipeline_health_projection(
        tenant,
        [opportunity],
        [placement] if placement is not None else [],
        as_of=as_of,
    )
    health = _workspace_health_row(health_projection, opportunity.pk)
    activity_timeline = _workspace_activity_timeline(
        tasks,
        communications,
        events,
        outcomes,
        audit_entries,
        user=request.user,
    )
    currency_label = _workspace_currency_label(opportunity)
    weighted_amount = _workspace_weighted_amount(opportunity, placement)
    return render(
        request,
        "sales/opportunity/workspace.html",
        {
            "opportunity": opportunity,
            "placement": placement,
            "placement_form": placement_form,
            "pipelines": pipelines,
            "stages": stages,
            "health": health,
            "health_status": health.get("status", "watch"),
            "health_factors": health.get("factors", []),
            "health_stage_age_days": health.get("stage_age_days", 0),
            "health_target_days": health.get("target_days"),
            "last_activity_at": health.get("last_activity_at"),
            "team_members": team_members,
            "team_member_form": team_member_form,
            "competitor_links": competitor_links,
            "competitor_form": competitor_form,
            "competitor_profiles": competitor_profiles,
            "closure_form": closure_form,
            "outcomes": outcomes,
            "win_loss_reasons": win_loss_reasons,
            "tasks": tasks,
            "communications": communications,
            "events": events,
            "contracts": contracts,
            "documents": documents,
            "audit_entries": audit_entries,
            "activity_timeline": activity_timeline,
            "crm_edit_url": reverse("crm:opportunity_edit", kwargs={"pk": opportunity.pk}),
            "can_edit_crm": bool(getattr(request.user, "is_authenticated", False)),
            "current_stage": current_stage,
            "pipeline": pipeline,
            "currency_label": currency_label,
            "weighted_amount": weighted_amount,
        },
    )


@login_required
def opportunity_place(request, opportunity_pk):
    tenant = request.tenant
    opportunity = get_object_or_404(
        _workspace_opportunity_queryset(tenant),
        pk=opportunity_pk,
        tenant=tenant,
    )
    placement = _workspace_cached_placement(opportunity)
    if placement is None:
        placement = _workspace_placement_queryset(tenant, opportunity).first()
    pipelines = list(_workspace_pipeline_queryset(tenant))
    selected_pipeline = _workspace_selected_pipeline(request, pipelines)
    form = _workspace_placement_form(
        opportunity,
        tenant,
        data=request.POST if request.method == "POST" else None,
        instance=placement,
        selected_pipeline=selected_pipeline,
    )
    if request.method == "POST" and form.is_valid():
        selected_opportunity = form.cleaned_data.get("opportunity") or opportunity
        selected_pipeline = form.cleaned_data.get("pipeline")
        selected_stage = form.cleaned_data.get("current_stage")
        active_team_member = OpportunityTeamMember.objects.filter(
            tenant=tenant,
            opportunity=selected_opportunity,
            is_active=True,
        ).exists()
        try:
            sales_place_opportunity(
                opportunity=selected_opportunity,
                pipeline=selected_pipeline,
                stage=selected_stage,
                tenant=tenant,
                user=request.user,
                probability_override=form.cleaned_data.get("probability_override"),
                active_team_member=active_team_member,
            )
        except ValidationError as exc:
            form.add_error(None, _workspace_error_message(exc))
        except IntegrityError:
            form.add_error(None, "The placement could not be saved. Try again.")
        else:
            messages.success(request, "Opportunity placement saved.")
            return redirect(
                "sales:opportunity_workspace_detail",
                opportunity_pk=opportunity.pk,
            )
    stages = list(_workspace_stage_queryset(tenant, selected_pipeline))
    return render(
        request,
        "sales/opportunity/placement.html",
        {
            "opportunity": opportunity,
            "placement": placement,
            "form": form,
            "pipelines": pipelines,
            "selected_pipeline": selected_pipeline,
            "selected_pipeline_id": selected_pipeline.pk if selected_pipeline else None,
            "stages": stages,
            "is_edit": placement is not None,
        },
    )


@require_POST
@login_required
def opportunity_unplace(request, opportunity_pk):
    tenant = request.tenant
    opportunity = get_object_or_404(
        _workspace_opportunity_queryset(tenant),
        pk=opportunity_pk,
        tenant=tenant,
    )
    try:
        removed = sales_unplace_opportunity(opportunity, tenant, request.user)
    except ValidationError as exc:
        messages.error(request, _workspace_error_message(exc))
    else:
        if removed:
            messages.success(request, "Opportunity removed from its pipeline.")
        else:
            messages.info(request, "This opportunity is not placed in a pipeline.")
    return redirect(
        "sales:opportunity_workspace_detail",
        opportunity_pk=opportunity.pk,
    )
