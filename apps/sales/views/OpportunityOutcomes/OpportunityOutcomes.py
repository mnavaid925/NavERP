from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.crud import paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity
from apps.sales.forms.OpportunityOutcomes.OpportunityOutcomes import (
    OpportunityTransitionForm,
    WinLossReasonForm,
)
from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import (
    OpportunityOutcome,
    WinLossReason,
)
from apps.sales.models.OpportunityPipeline.Pipelines import (
    OpportunityPipelinePlacement,
    PipelineStage,
)
from apps.sales.opportunity_services import sales_transition_opportunity


WIN_LOSS_ACTIVE_CHOICES = [("active", "Active"), ("inactive", "Inactive")]


def _win_loss_reason_validation_message(exc):
    return " ".join(getattr(exc, "messages", [str(exc)]))[:300]


def _win_loss_reason_form_context(form, is_edit, obj=None):
    context = {
        "form": form,
        "is_edit": is_edit,
        "result_choices": WinLossReason.RESULT_CHOICES,
        "category_choices": WinLossReason.CATEGORY_CHOICES,
    }
    if is_edit:
        context["obj"] = obj
    return context


@login_required
def opportunity_win_loss_reason_list(request):
    base_queryset = WinLossReason.objects.filter(tenant=request.tenant)
    q = request.GET.get("q", "").strip()[:200]
    result = request.GET.get("result", "").strip().lower()
    category = request.GET.get("category", "").strip().lower()
    active = request.GET.get("active", "").strip().lower()
    queryset = base_queryset
    if q:
        queryset = queryset.filter(
            Q(code__icontains=q)
            | Q(name__icontains=q)
            | Q(description__icontains=q)
        )
    if result in dict(WinLossReason.RESULT_CHOICES):
        queryset = queryset.filter(result=result)
    else:
        result = ""
    if category in dict(WinLossReason.CATEGORY_CHOICES):
        queryset = queryset.filter(category=category)
    else:
        category = ""
    if active == "active":
        queryset = queryset.filter(is_active=True)
    elif active == "inactive":
        queryset = queryset.filter(is_active=False)
    else:
        active = ""
    page_obj = paginate(request, queryset.order_by("sequence", "name", "id"), 20)
    stats = base_queryset.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
        won=Count("id", filter=Q(result="won")),
        lost=Count("id", filter=Q(result="lost")),
        both=Count("id", filter=Q(result="both")),
    )
    return render(
        request,
        "sales/opportunity/winlossreason/list.html",
        {
            "object_list": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "result": result,
            "category": category,
            "active": active,
            "active_choices": WIN_LOSS_ACTIVE_CHOICES,
            "result_choices": WinLossReason.RESULT_CHOICES,
            "category_choices": WinLossReason.CATEGORY_CHOICES,
            "stats": stats,
        },
    )


@tenant_admin_required
def opportunity_win_loss_reason_create(request):
    form = WinLossReasonForm(
        request.POST if request.method == "POST" else None,
        tenant=request.tenant,
    )
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        try:
            with transaction.atomic():
                obj.full_clean()
                obj.save()
                write_audit_log(
                    request.user,
                    obj,
                    "create",
                    {"operation": "create_win_loss_reason"},
                    tenant=request.tenant,
                )
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, _win_loss_reason_validation_message(exc))
        else:
            messages.success(request, "Win/loss reason created.")
            return redirect("sales:opportunity_win_loss_reason_detail", pk=obj.pk)
    return render(
        request,
        "sales/opportunity/winlossreason/form.html",
        _win_loss_reason_form_context(form, False),
    )


@login_required
def opportunity_win_loss_reason_detail(request, pk):
    obj = get_object_or_404(
        WinLossReason.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    outcomes = list(
        OpportunityOutcome.objects.filter(
            tenant=request.tenant,
            reason=obj,
        )
        .select_related(
            "opportunity",
            "competitor_link__competitor_profile__party",
            "recorded_by",
        )
        .order_by("-closed_at", "-id")
    )
    return render(
        request,
        "sales/opportunity/winlossreason/detail.html",
        {
            "obj": obj,
            "outcomes": outcomes,
            "can_edit": bool(
                getattr(request.user, "is_superuser", False)
                or getattr(request.user, "is_tenant_admin", False)
            ),
        },
    )


@tenant_admin_required
def opportunity_win_loss_reason_edit(request, pk):
    obj = get_object_or_404(WinLossReason, pk=pk, tenant=request.tenant)
    form = WinLossReasonForm(
        request.POST if request.method == "POST" else None,
        instance=obj,
        tenant=request.tenant,
    )
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        try:
            with transaction.atomic():
                obj.full_clean()
                obj.save()
                write_audit_log(
                    request.user,
                    obj,
                    "update",
                    {"operation": "update_win_loss_reason"},
                    tenant=request.tenant,
                )
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, _win_loss_reason_validation_message(exc))
        else:
            messages.success(request, "Win/loss reason updated.")
            return redirect("sales:opportunity_win_loss_reason_detail", pk=obj.pk)
    return render(
        request,
        "sales/opportunity/winlossreason/form.html",
        _win_loss_reason_form_context(form, True, obj),
    )


@require_POST
@tenant_admin_required
def opportunity_win_loss_reason_delete(request, pk):
    with transaction.atomic():
        obj = get_object_or_404(
            WinLossReason.objects.select_for_update(),
            pk=pk,
            tenant=request.tenant,
        )
        try:
            with transaction.atomic():
                if OpportunityOutcome.objects.filter(
                    tenant=request.tenant,
                    reason=obj,
                ).exists():
                    raise ValidationError("A referenced win/loss reason cannot be deleted.")
                write_audit_log(
                    request.user,
                    obj,
                    "delete",
                    {"operation": "delete_win_loss_reason"},
                    tenant=request.tenant,
                )
                obj.delete()
        except (ValidationError, ProtectedError) as exc:
            messages.error(request, _win_loss_reason_validation_message(exc))
        else:
            messages.success(request, "Win/loss reason deleted.")
    return redirect("sales:opportunity_win_loss_reason_list")


def _opportunity_transition_target_stages(placement):
    if placement is None:
        return []
    stages = list(
        PipelineStage.objects.filter(
            tenant_id=placement.tenant_id,
            pipeline_id=placement.pipeline_id,
            is_active=True,
        ).order_by("sequence", "pk")
    )
    current = next((stage for stage in stages if stage.pk == placement.current_stage_id), None)
    if current is None:
        return []
    if current.stage_kind == "open":
        next_open = next(
            (stage for stage in stages if stage.stage_kind == "open" and stage.sequence > current.sequence),
            None,
        )
        targets = [next_open] if next_open is not None else []
        targets.extend(stage for stage in stages if stage.stage_kind in {"won", "lost"})
        return targets
    if current.stage_kind in {"won", "lost"}:
        return [stage for stage in stages if stage.stage_kind == "open"]
    return []


def _opportunity_transition_form_error(form):
    errors = list(form.non_field_errors())
    if not errors:
        for field in form.fields.values():
            errors.extend(field.errors)
    if not errors:
        return "Choose a valid pipeline transition."
    return " ".join(str(error) for error in errors)[:300]


@login_required
@require_POST
def opportunity_transition(request, opportunity_pk):
    opportunity = get_object_or_404(
        Opportunity,
        pk=opportunity_pk,
        tenant=request.tenant,
    )
    placement = (
        OpportunityPipelinePlacement.objects.filter(
            tenant=request.tenant,
            opportunity=opportunity,
        )
        .select_related("current_stage", "pipeline")
        .first()
    )
    current_stage = placement.current_stage if placement is not None else None
    form = OpportunityTransitionForm(
        request.POST,
        tenant=request.tenant,
        opportunity=opportunity,
        placement=placement,
        current_stage=current_stage,
        allowed_target_stages=_opportunity_transition_target_stages(placement),
    )
    if form.is_valid():
        try:
            sales_transition_opportunity(
                opportunity=opportunity,
                target_stage=form.cleaned_data["target_stage"],
                tenant=request.tenant,
                user=request.user,
                reason=form.cleaned_data.get("reason"),
                competitor_link=form.cleaned_data.get("competitor_link"),
                notes=form.cleaned_data.get("notes", ""),
            )
        except (ValidationError, IntegrityError) as exc:
            messages.error(request, _win_loss_reason_validation_message(exc))
        else:
            messages.success(request, "Opportunity transitioned.")
            return redirect(
                "sales:opportunity_workspace_detail",
                opportunity_pk=opportunity.pk,
            )
    else:
        messages.error(request, _opportunity_transition_form_error(form))
    return redirect(
        "sales:opportunity_workspace_detail",
        opportunity_pk=opportunity.pk,
    )
