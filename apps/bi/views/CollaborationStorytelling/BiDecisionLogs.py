from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.CollaborationStorytelling.BiDecisionLogs import BiDecisionLogForm
from apps.bi.models.CollaborationStorytelling.BiDecisionLogs import BiDecisionLog
from apps.bi.models.CollaborationStorytelling.BiSharedWorkspaces import BiSharedWorkspace
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def bi_decision_log_list(request):
    qs = bi_scope(BiDecisionLog.objects.all(), request).select_related(
        "workspace", "dashboard", "widget", "kpi", "decision_maker", "created_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        approved=Count("id", filter=Q(status="approved")),
        strategic=Count("id", filter=Q(category="strategic")),
    )
    total_count = counts["total"] or 0
    approved_count = counts["approved"] or 0
    strategic_count = counts["strategic"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(slug__icontains=q)
            | Q(problem_statement__icontains=q)
            | Q(rationale__icontains=q)
        )

    # Filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(category=category)

    workspace_id = request.GET.get("workspace", "").strip()
    if workspace_id and workspace_id.isdigit():
        qs = qs.filter(workspace_id=int(workspace_id))

    dashboard_id = request.GET.get("dashboard", "").strip()
    if dashboard_id and dashboard_id.isdigit():
        qs = qs.filter(dashboard_id=int(dashboard_id))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    dashboards = BiDashboard.objects.filter(tenant=request.tenant).order_by("title")
    workspaces = BiSharedWorkspace.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "decisions": page_obj,
        "bi_decision_logs": page_obj,
        "total_count": total_count,
        "approved_count": approved_count,
        "strategic_count": strategic_count,
        "status_choices": BiDecisionLog.STATUS_CHOICES,
        "category_choices": BiDecisionLog.CATEGORY_CHOICES,
        "dashboards": dashboards,
        "workspaces": workspaces,
    }
    return render(
        request,
        "bi/collaboration_storytelling/bidecisionlog/list.html",
        context,
    )


@login_required
def bi_decision_log_create(request):
    initial = {}
    w_id = request.GET.get("workspace", "").strip()
    if w_id and w_id.isdigit():
        w = BiSharedWorkspace.objects.filter(tenant=request.tenant, pk=int(w_id)).first()
        if w:
            initial["workspace"] = w

    d_id = request.GET.get("dashboard", "").strip()
    if d_id and d_id.isdigit():
        d = BiDashboard.objects.filter(tenant=request.tenant, pk=int(d_id)).first()
        if d:
            initial["dashboard"] = d

    if request.method == "POST":
        form = BiDecisionLogForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                decision = form.save(commit=False)
                decision.tenant = request.tenant
                decision.created_by = request.user
                if not decision.decision_maker:
                    decision.decision_maker = request.user
                decision.save()
                write_audit_log(
                    request.user,
                    decision,
                    "create",
                    tenant=request.tenant,
                )
            messages.success(request, f"Decision '{decision.title}' logged successfully.")
            return redirect("bi:bi_decision_log_detail", pk=decision.pk)
    else:
        initial["decision_maker"] = request.user
        form = BiDecisionLogForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "bi/collaboration_storytelling/bidecisionlog/form.html",
        {"form": form, "title": "Log Business Decision & Annotation", "is_edit": False},
    )


@login_required
def bi_decision_log_detail(request, pk):
    decision = bi_object(
        request,
        BiDecisionLog,
        pk,
        select_related=("workspace", "dashboard", "widget", "kpi", "decision_maker", "created_by"),
    )

    context = {
        "decision": decision,
        "bi_decision_log": decision,
        "obj": decision,
    }
    return render(
        request,
        "bi/collaboration_storytelling/bidecisionlog/detail.html",
        context,
    )


@login_required
def bi_decision_log_edit(request, pk):
    decision = bi_object(request, BiDecisionLog, pk)

    if request.method == "POST":
        form = BiDecisionLogForm(request.POST, instance=decision, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                decision = form.save()
                write_audit_log(
                    request.user,
                    decision,
                    "update",
                    tenant=request.tenant,
                )
            messages.success(request, f"Decision '{decision.title}' updated successfully.")
            return redirect("bi:bi_decision_log_detail", pk=decision.pk)
    else:
        form = BiDecisionLogForm(instance=decision, tenant=request.tenant)

    return render(
        request,
        "bi/collaboration_storytelling/bidecisionlog/form.html",
        {
            "form": form,
            "title": f"Edit Decision: {decision.title}",
            "decision": decision,
            "bi_decision_log": decision,
            "obj": decision,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def bi_decision_log_delete(request, pk):
    decision = bi_object(request, BiDecisionLog, pk)
    title = decision.title
    with transaction.atomic():
        write_audit_log(
            request.user,
            decision,
            "delete",
            tenant=request.tenant,
        )
        decision.delete()
    messages.success(request, f"Decision '{title}' deleted successfully.")
    return redirect("bi:bi_decision_log_list")
