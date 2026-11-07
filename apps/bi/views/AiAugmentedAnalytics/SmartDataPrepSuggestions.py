import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.bi.forms.AiAugmentedAnalytics.SmartDataPrepSuggestions import SmartDataPrepSuggestionForm
from apps.bi.models.AiAugmentedAnalytics.SmartDataPrepSuggestions import SmartDataPrepSuggestion
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def smart_data_prep_suggestion_list(request):
    qs = bi_scope(SmartDataPrepSuggestion.objects.all(), request).select_related(
        "target_table", "related_table", "reviewed_by"
    )

    counts = qs.aggregate(
        pending=Count("id", filter=Q(status="pending")),
    )
    pending_count = counts["pending"] or 0

    tables = WarehouseTable.objects.filter(tenant=request.tenant).order_by("name")

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(target_column__icontains=q)
            | Q(number__icontains=q)
            | Q(rationale__icontains=q)
            | Q(target_table__name__icontains=q)
            | Q(related_table__name__icontains=q)
        )

    # Filters
    suggestion_type = request.GET.get("suggestion_type", "").strip()
    if suggestion_type:
        qs = qs.filter(suggestion_type=suggestion_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    target_table_id = request.GET.get("target_table", "").strip()
    if target_table_id.isdigit():
        qs = qs.filter(target_table_id=int(target_table_id))

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "bi/ai_augmented_analytics/smart_data_prep_suggestion/list.html",
        {
            "suggestions": page_obj,
            "suggestion_type_choices": SmartDataPrepSuggestion.SUGGESTION_TYPE_CHOICES,
            "status_choices": SmartDataPrepSuggestion.STATUS_CHOICES,
            "tables": tables,
            "pending_count": pending_count,
        },
    )


@login_required
def smart_data_prep_suggestion_detail(request, pk):
    suggestion = bi_object(
        request,
        SmartDataPrepSuggestion,
        pk,
        select_related=("target_table", "related_table", "reviewed_by"),
    )

    config_items = []
    if isinstance(suggestion.suggested_config, dict):
        config_items = list(suggestion.suggested_config.items())
    elif isinstance(suggestion.suggested_config, str) and suggestion.suggested_config.strip():
        try:
            parsed = json.loads(suggestion.suggested_config)
            if isinstance(parsed, dict):
                config_items = list(parsed.items())
        except json.JSONDecodeError:
            config_items = []

    return render(
        request,
        "bi/ai_augmented_analytics/smart_data_prep_suggestion/detail.html",
        {
            "suggestion": suggestion,
            "config_items": config_items,
        },
    )


@login_required
@transaction.atomic
def smart_data_prep_suggestion_create(request):
    if request.method == "POST":
        form = SmartDataPrepSuggestionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            suggestion = form.save(commit=False)
            suggestion.tenant = request.tenant
            suggestion.save()
            write_audit_log(
                request.user,
                suggestion,
                "create",
                changes={"details": f"Created prep suggestion {suggestion.number} for {suggestion.target_table.name}.{suggestion.target_column}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Data prep suggestion {suggestion.number} created successfully.")
            return redirect("bi:smart_data_prep_suggestion_detail", pk=suggestion.pk)
    else:
        form = SmartDataPrepSuggestionForm(tenant=request.tenant)

    return render(
        request,
        "bi/ai_augmented_analytics/smart_data_prep_suggestion/form.html",
        {
            "form": form,
            "suggestion": None,
            "is_edit": False,
        },
    )


@login_required
@transaction.atomic
def smart_data_prep_suggestion_edit(request, pk):
    suggestion = bi_object(request, SmartDataPrepSuggestion, pk)
    if request.method == "POST":
        form = SmartDataPrepSuggestionForm(request.POST, instance=suggestion, tenant=request.tenant)
        if form.is_valid():
            suggestion = form.save()
            write_audit_log(
                request.user,
                suggestion,
                "update",
                changes={"details": f"Updated prep suggestion {suggestion.number}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Data prep suggestion {suggestion.number} updated successfully.")
            return redirect("bi:smart_data_prep_suggestion_detail", pk=suggestion.pk)
    else:
        form = SmartDataPrepSuggestionForm(instance=suggestion, tenant=request.tenant)

    return render(
        request,
        "bi/ai_augmented_analytics/smart_data_prep_suggestion/form.html",
        {
            "form": form,
            "suggestion": suggestion,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def smart_data_prep_suggestion_delete(request, pk):
    suggestion = bi_object(request, SmartDataPrepSuggestion, pk)
    number = suggestion.number
    write_audit_log(
        request.user,
        suggestion,
        "delete",
        changes={"number": number, "details": f"Deleted data prep suggestion {number}"},
        tenant=request.tenant,
    )
    suggestion.delete()
    messages.success(request, f"Data prep suggestion {number} was deleted.")
    return redirect("bi:smart_data_prep_suggestion_list")


@login_required
@require_POST
@transaction.atomic
def smart_data_prep_suggestion_action(request, pk):
    suggestion = bi_object(request, SmartDataPrepSuggestion, pk)
    if suggestion.status == "applied":
        messages.warning(request, f"Data prep suggestion {suggestion.number} has already been applied and cannot be modified.")
        return redirect("bi:smart_data_prep_suggestion_detail", pk=suggestion.pk)

    action_type = request.POST.get("action_type", "").strip()
    review_notes = request.POST.get("review_notes", "").strip()

    if action_type in ["accept", "reject", "apply"]:
        status_map = {
            "accept": "accepted",
            "reject": "rejected",
            "apply": "applied",
        }
        suggestion.status = status_map[action_type]
        suggestion.reviewed_by = request.user
        suggestion.reviewed_at = timezone.now()
        if review_notes:
            suggestion.review_notes = review_notes
        suggestion.save()

        write_audit_log(
            request.user,
            suggestion,
            action_type,
            changes={"action": action_type, "status": suggestion.status, "details": f"Data prep suggestion {suggestion.number} was marked as {suggestion.get_status_display()}"},
            tenant=request.tenant,
        )
        messages.success(request, f"Data prep suggestion {suggestion.number} is now {suggestion.get_status_display()}.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("bi:smart_data_prep_suggestion_detail", pk=suggestion.pk)
