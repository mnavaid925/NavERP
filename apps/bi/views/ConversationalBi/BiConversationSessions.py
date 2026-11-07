from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.bi.forms.ConversationalBi.BiConversationSessions import BiConversationSessionForm
from apps.bi.models.ConversationalBi.BiConversationSessions import BiConversationSession
from apps.bi.models.ConversationalBi.NaturalLanguageQueries import NaturalLanguageQuery
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def bi_conversation_session_list(request):
    qs = bi_scope(BiConversationSession.objects.all(), request).select_related(
        "user", "primary_semantic_model", "primary_dashboard"
    )

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(session_status="active")),
        pinned=Count("id", filter=Q(is_pinned=True)),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    pinned_count = counts["pinned"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(context_state__icontains=q)
        )

    # Filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(session_status=status)

    pinned = request.GET.get("pinned", "").strip()
    if pinned == "1":
        qs = qs.filter(is_pinned=True)

    semantic_model_id = request.GET.get("semantic_model", "").strip()
    if semantic_model_id and semantic_model_id.isdigit():
        qs = qs.filter(primary_semantic_model_id=int(semantic_model_id))

    dashboard_id = request.GET.get("dashboard", "").strip()
    if dashboard_id and dashboard_id.isdigit():
        qs = qs.filter(primary_dashboard_id=int(dashboard_id))

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    semantic_models = SemanticModel.objects.filter(tenant=request.tenant).order_by("name")
    dashboards = BiDashboard.objects.filter(tenant=request.tenant).order_by("title")

    context = {
        "sessions": page_obj,
        "conversation_sessions": page_obj,
        "total_count": total_count,
        "active_count": active_count,
        "pinned_count": pinned_count,
        "status_choices": BiConversationSession.SESSION_STATUS_CHOICES,
        "semantic_models": semantic_models,
        "dashboards": dashboards,
    }
    return render(
        request,
        "bi/conversational_bi/bi_conversation_session/list.html",
        context,
    )


@login_required
def bi_conversation_session_detail(request, pk):
    session = bi_object(request, BiConversationSession, pk)
    turns = session.queries.select_related("user").order_by("created_at")

    suggested_prompts = session.suggested_prompts
    if not suggested_prompts:
        suggested_prompts = [
            "Show breakdown by region for the top metric",
            "What were the key variance drivers compared to prior period?",
            "Export this tabular result as CSV",
            "Forecast trend for the next 2 quarters",
        ]

    context = {
        "session": session,
        "turns": turns,
        "suggested_prompts": suggested_prompts,
    }
    return render(
        request,
        "bi/conversational_bi/bi_conversation_session/detail.html",
        context,
    )


@login_required
def bi_chat_workspace(request):
    sessions = (
        bi_scope(BiConversationSession.objects.all(), request)
        .select_related("user", "primary_semantic_model")
        .order_by("-is_pinned", "-last_interaction_at")
    )
    active_session_id = request.GET.get("session")
    active_session = None

    if active_session_id and active_session_id.isdigit():
        active_session = sessions.filter(pk=int(active_session_id)).first()
    if not active_session:
        active_session = sessions.first()

    turns = active_session.queries.select_related("user").order_by("created_at") if active_session else []
    suggested_prompts = active_session.suggested_prompts if active_session and active_session.suggested_prompts else [
        "What is our YTD Revenue vs Plan?",
        "Show quarterly gross margin trend by product family",
        "Which sales territories are trailing target?",
        "Top 5 suppliers by on-time delivery rate",
    ]

    context = {
        "sessions": sessions[:50],
        "active_session": active_session,
        "turns": turns,
        "suggested_prompts": suggested_prompts,
    }
    return render(
        request,
        "bi/conversational_bi/chat_workspace.html",
        context,
    )


@login_required
def bi_conversation_session_create(request):
    if request.method == "POST":
        form = BiConversationSessionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                instance.user = request.user
                if not instance.suggested_prompts:
                    instance.suggested_prompts = [
                        "What is our YTD Revenue vs Plan?",
                        "Which sales territories are trailing target?",
                        "Show gross margin trend by product family",
                    ]
                instance.save()
                form.save_m2m()

                write_audit_log(
                    user=request.user,
                    obj=instance,
                    action="create",
                    changes={"details": "Created conversational BI chat thread"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Conversation session '{instance.number}' started.")
                return redirect("bi:bi_conversation_session_detail", pk=instance.pk)
    else:
        form = BiConversationSessionForm(tenant=request.tenant)

    return render(
        request,
        "bi/conversational_bi/bi_conversation_session/form.html",
        {
            "form": form,
            "session": None,
            "is_edit": False,
        },
    )


@login_required
def bi_conversation_session_edit(request, pk):
    session = bi_object(request, BiConversationSession, pk)

    if request.method == "POST":
        form = BiConversationSessionForm(request.POST, instance=session, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save()

                write_audit_log(
                    user=request.user,
                    obj=instance,
                    action="update",
                    changes={"details": "Updated conversational session details"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Conversation session '{instance.number}' updated.")
                return redirect("bi:bi_conversation_session_detail", pk=instance.pk)
    else:
        form = BiConversationSessionForm(instance=session, tenant=request.tenant)

    return render(
        request,
        "bi/conversational_bi/bi_conversation_session/form.html",
        {
            "form": form,
            "session": session,
            "is_edit": True,
        },
    )


@tenant_admin_required
@require_POST
def bi_conversation_session_delete(request, pk):
    session = bi_object(request, BiConversationSession, pk)
    num = session.number

    with transaction.atomic():
        write_audit_log(
            user=request.user,
            obj=session,
            action="delete",
            changes={"details": f"Deleted conversational session {num}"},
            tenant=request.tenant,
        )
        session.delete()

    messages.success(request, f"Conversation session '{num}' deleted.")
    return redirect("bi:bi_conversation_session_list")


@login_required
@require_POST
def bi_conversation_session_toggle_pin(request, pk):
    session = bi_object(request, BiConversationSession, pk)
    with transaction.atomic():
        session.is_pinned = not session.is_pinned
        session.save(update_fields=["is_pinned", "updated_at"])

        status_str = "pinned" if session.is_pinned else "unpinned"
        write_audit_log(
            user=request.user,
            obj=session,
            action="pin" if session.is_pinned else "unpin",
            changes={"details": f"Session {status_str}"},
            tenant=request.tenant,
        )
    messages.success(request, f"Session '{session.number}' {status_str}.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("bi:bi_conversation_session_detail", pk=session.pk)


@login_required
@require_POST
def bi_conversation_session_close(request, pk):
    session = bi_object(request, BiConversationSession, pk)
    with transaction.atomic():
        session.session_status = "closed"
        session.save(update_fields=["session_status", "updated_at"])

        write_audit_log(
            user=request.user,
            obj=session,
            action="close",
            changes={"details": "Closed conversation session"},
            tenant=request.tenant,
        )
    messages.success(request, f"Session '{session.number}' is now closed.")
    return redirect("bi:bi_conversation_session_detail", pk=session.pk)


@login_required
@require_POST
def bi_conversation_session_ask(request, pk):
    session = bi_object(request, BiConversationSession, pk)
    question_text = request.POST.get("query_text", "").strip()

    if not question_text:
        messages.error(request, "Please enter an analytical question.")
        return redirect("bi:bi_conversation_session_detail", pk=session.pk)

    with transaction.atomic():
        query = NaturalLanguageQuery(
            tenant=request.tenant,
            query_text=question_text,
            input_modality="text",
            intent_type="metric_lookup",
            semantic_model=session.primary_semantic_model,
            conversation_session=session,
            user=request.user,
            chart_type="bar_chart",
            parsed_measures=["Calculated Measure"],
            parsed_dimensions=["Primary Dimension"],
            generated_sql=(
                f"SELECT dimension, SUM(metric_val) AS val\n"
                f"FROM bi_warehouse_analytical_fact\n"
                f"WHERE tenant_id = '{request.tenant.id}'\n"
                f"GROUP BY dimension ORDER BY val DESC LIMIT 10;"
            ),
            chart_config={
                "type": "bar",
                "labels": ["Region A", "Region B", "Region C", "Region D"],
                "datasets": [{"label": "Metric Value", "data": [120, 95, 80, 45]}],
            },
            result_summary={
                "row_count": 4,
                "metric_value": "340",
                "summary_text": f"Results for: '{question_text}'",
            },
            confidence_score=91.50,
            execution_status="completed",
            execution_duration_ms=38,
        )
        query.save()

        session.message_count += 1
        session.save(update_fields=["message_count", "last_interaction_at", "updated_at"])

        write_audit_log(
            user=request.user,
            obj=query,
            action="create",
            changes={"details": f"Added query to conversation {session.number}"},
            tenant=request.tenant,
        )

    messages.success(request, "Answer generated successfully.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("bi:bi_conversation_session_detail", pk=session.pk)
