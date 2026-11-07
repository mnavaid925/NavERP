from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.bi.forms.ConversationalBi.NaturalLanguageQueries import NaturalLanguageQueryForm
from apps.bi.models.ConversationalBi.NaturalLanguageQueries import NaturalLanguageQuery
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def natural_language_query_list(request):
    qs = bi_scope(NaturalLanguageQuery.objects.all(), request).select_related(
        "semantic_model", "warehouse_table", "kpi_definition", "conversation_session", "user"
    )

    counts = qs.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(execution_status="completed")),
        voice=Count("id", filter=Q(input_modality="voice")),
        helpful=Count("id", filter=Q(user_rating="helpful")),
    )
    total_count = counts["total"] or 0
    completed_count = counts["completed"] or 0
    voice_count = counts["voice"] or 0
    helpful_count = counts["helpful"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(query_text__icontains=q)
            | Q(number__icontains=q)
            | Q(generated_sql__icontains=q)
            | Q(user_feedback_notes__icontains=q)
        )

    # Filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(execution_status=status)

    modality = request.GET.get("modality", "").strip()
    if modality:
        qs = qs.filter(input_modality=modality)

    intent = request.GET.get("intent", "").strip()
    if intent:
        qs = qs.filter(intent_type=intent)

    semantic_model_id = request.GET.get("semantic_model", "").strip()
    if semantic_model_id and semantic_model_id.isdigit():
        qs = qs.filter(semantic_model_id=int(semantic_model_id))

    rating = request.GET.get("rating", "").strip()
    if rating:
        qs = qs.filter(user_rating=rating)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    semantic_models = SemanticModel.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "queries": page_obj,
        "natural_language_queries": page_obj,
        "total_count": total_count,
        "completed_count": completed_count,
        "voice_count": voice_count,
        "helpful_count": helpful_count,
        "status_choices": NaturalLanguageQuery.EXECUTION_STATUS_CHOICES,
        "modality_choices": NaturalLanguageQuery.INPUT_MODALITY_CHOICES,
        "intent_choices": NaturalLanguageQuery.INTENT_TYPE_CHOICES,
        "semantic_models": semantic_models,
    }
    return render(
        request,
        "bi/conversational_bi/natural_language_query/list.html",
        context,
    )


@login_required
def natural_language_query_detail(request, pk):
    query = bi_object(NaturalLanguageQuery, request, pk)

    parsed_measures = query.parsed_measures if isinstance(query.parsed_measures, list) else []
    parsed_dimensions = query.parsed_dimensions if isinstance(query.parsed_dimensions, list) else []
    parsed_filters = query.parsed_filters if isinstance(query.parsed_filters, dict) else {}

    context = {
        "query": query,
        "parsed_measures": parsed_measures,
        "parsed_dimensions": parsed_dimensions,
        "parsed_filters": parsed_filters,
        "rating_choices": NaturalLanguageQuery.USER_RATING_CHOICES,
    }
    return render(
        request,
        "bi/conversational_bi/natural_language_query/detail.html",
        context,
    )


@login_required
def natural_language_query_create(request):
    if request.method == "POST":
        form = NaturalLanguageQueryForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                if not instance.user_id:
                    instance.user = request.user

                # Simulate intent extraction & SQL generation if empty
                if not instance.parsed_measures:
                    instance.parsed_measures = ["Revenue", "Margin"]
                if not instance.parsed_dimensions:
                    instance.parsed_dimensions = ["Fiscal Quarter", "Region"]
                if not instance.generated_sql:
                    instance.generated_sql = (
                        f"SELECT region, fiscal_quarter, SUM(revenue) AS total_revenue\n"
                        f"FROM bi_warehouse_sales_fact\n"
                        f"WHERE tenant_id = '{request.tenant.id}'\n"
                        f"GROUP BY region, fiscal_quarter ORDER BY total_revenue DESC;"
                    )
                if not instance.chart_config:
                    instance.chart_config = {
                        "type": instance.chart_type if instance.chart_type in ["bar", "line", "donut"] else "bar",
                        "labels": ["Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026"],
                        "datasets": [{"label": "Revenue ($K)", "data": [450, 520, 610, 780]}],
                    }
                if not instance.result_summary:
                    instance.result_summary = {
                        "row_count": 4,
                        "metric_value": "$2,360,000",
                        "summary_text": f"Found 4 periods matching '{instance.query_text}'.",
                    }
                if instance.execution_status == "completed" and instance.execution_duration_ms == 0:
                    instance.execution_duration_ms = 48

                instance.save()
                form.save_m2m()

                write_audit_log(
                    user=request.user,
                    obj=instance,
                    action="create",
                    changes={"details": "Created natural language analytical query"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Natural language query '{instance.number}' submitted successfully.")
                return redirect("bi:natural_language_query_detail", pk=instance.pk)
    else:
        initial = {}
        session_id = request.GET.get("session")
        if session_id and session_id.isdigit():
            initial["conversation_session"] = int(session_id)
        form = NaturalLanguageQueryForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "bi/conversational_bi/natural_language_query/form.html",
        {
            "form": form,
            "query": None,
            "is_edit": False,
        },
    )


@login_required
def natural_language_query_edit(request, pk):
    query = bi_object(NaturalLanguageQuery, request, pk)

    if request.method == "POST":
        form = NaturalLanguageQueryForm(request.POST, instance=query, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save()

                write_audit_log(
                    user=request.user,
                    obj=instance,
                    action="update",
                    changes={"details": "Updated natural language query parameters"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Natural language query '{instance.number}' updated.")
                return redirect("bi:natural_language_query_detail", pk=instance.pk)
    else:
        form = NaturalLanguageQueryForm(instance=query, tenant=request.tenant)

    return render(
        request,
        "bi/conversational_bi/natural_language_query/form.html",
        {
            "form": form,
            "query": query,
            "is_edit": True,
        },
    )


@tenant_admin_required
@require_POST
def natural_language_query_delete(request, pk):
    query = bi_object(NaturalLanguageQuery, request, pk)
    num = query.number

    with transaction.atomic():
        write_audit_log(
            user=request.user,
            obj=query,
            action="delete",
            changes={"details": f"Deleted natural language query {num}"},
            tenant=request.tenant,
        )
        query.delete()

    messages.success(request, f"Query '{num}' has been deleted.")
    return redirect("bi:natural_language_query_list")


@login_required
@require_POST
def natural_language_query_rate(request, pk):
    query = bi_object(NaturalLanguageQuery, request, pk)
    rating = request.POST.get("rating", "").strip()
    notes = request.POST.get("notes", "").strip()

    valid_ratings = [c[0] for c in NaturalLanguageQuery.USER_RATING_CHOICES]
    if rating in valid_ratings:
        with transaction.atomic():
            query.user_rating = rating
            if notes:
                query.user_feedback_notes = notes
            query.save(update_fields=["user_rating", "user_feedback_notes", "updated_at"])

            write_audit_log(
                user=request.user,
                obj=query,
                action="rate",
                changes={"details": f"Logged user accuracy rating: {rating}"},
                tenant=request.tenant,
            )
        messages.success(request, f"Thank you for rating query '{query.number}'.")
    else:
        messages.error(request, "Invalid rating value provided.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("bi:natural_language_query_detail", pk=query.pk)
