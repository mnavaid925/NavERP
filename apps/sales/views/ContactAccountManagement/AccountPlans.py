from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.accounts.models import User
from apps.core.crud import as_db_int, apply_search, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.models import Activity, Document, Party
from apps.core.utils import write_audit_log
from apps.crm.models import AccountProfile, CrmTask, HealthScore, HealthScoreHistory, Opportunity
from apps.sales.forms.ContactAccountManagement.AccountPlans import AccountPlanForm
from apps.sales.models.ContactAccountManagement.AccountStakeholders import AccountStakeholder
from apps.sales.models.ContactAccountManagement.AccountPlans import AccountPlan
from apps.sales.services import (
    account_plan_allowed_actions,
    account_rollups,
    can_manage_account_plan,
    save_account_plan,
    transition_account_plan,
)
from apps.sales.views._common import *


def _plan_queryset(request):
    return AccountPlan.objects.filter(tenant=request.tenant).select_related("account", "owner")


def _filter_plan_queryset(request, queryset):
    filters = {
        "q": request.GET.get("q", "").strip(),
        "account": as_db_int(request.GET.get("account")),
        "owner": as_db_int(request.GET.get("owner")),
        "status": request.GET.get("status", ""),
        "next_review": request.GET.get("next_review", ""),
        "period_from": request.GET.get("period_from", ""),
        "period_to": request.GET.get("period_to", ""),
    }
    queryset = apply_search(
        queryset,
        filters["q"],
        ["number", "title", "business_drivers", "objectives", "strategy", "white_space_assessment", "growth_initiatives"],
    )
    if filters["account"]:
        queryset = queryset.filter(account_id=filters["account"])
    if filters["owner"]:
        queryset = queryset.filter(owner_id=filters["owner"])
    if filters["status"] in dict(AccountPlan.STATUS_CHOICES):
        queryset = queryset.filter(status=filters["status"])
    today = timezone.localdate()
    if filters["next_review"] == "overdue":
        queryset = queryset.filter(next_review_on__lt=today)
    elif filters["next_review"] == "due_soon":
        queryset = queryset.filter(next_review_on__gte=today, next_review_on__lte=today + timedelta(days=30))
    elif filters["next_review"] == "scheduled":
        queryset = queryset.filter(next_review_on__isnull=False)
    from_date = safe_parse_date(filters["period_from"]) if filters["period_from"] else None
    to_date = safe_parse_date(filters["period_to"]) if filters["period_to"] else None
    if from_date:
        queryset = queryset.filter(period_end__gte=from_date)
    if to_date:
        queryset = queryset.filter(period_start__lte=to_date)
    return queryset, filters


@login_required
def account_plan_list(request):
    queryset = _plan_queryset(request)
    queryset, filters = _filter_plan_queryset(request, queryset)
    q = filters["q"]
    account_id = filters["account"]
    owner_id = filters["owner"]
    status = filters["status"]
    next_review = filters["next_review"]
    period_from = filters["period_from"]
    period_to = filters["period_to"]
    page_obj = paginate(request, queryset, 20)
    for obj in page_obj.object_list:
        obj.can_edit = can_manage_account_plan(obj, request.user) and obj.status != "archived"
    base = _plan_queryset(request)
    today = timezone.localdate()
    stats = base.aggregate(
        total=Count("pk"),
        draft=Count("pk", filter=Q(status="draft")),
        active=Count("pk", filter=Q(status="active")),
        review_due=Count("pk", filter=Q(status="review_due")),
        review_overdue=Count("pk", filter=Q(next_review_on__lt=today)),
    )
    export_url = reverse("sales:account_plan_export")
    if request.GET:
        export_url = f"{export_url}?{request.GET.urlencode()}"
    return render(request, "sales/contactaccountmanagement/accountplan/list.html", {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "accounts": list(Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")[:500]),
        "owners": list(User.objects.filter(tenant=request.tenant, is_active=True).order_by("username")[:500]) if request.tenant is not None else [],
        "status_choices": AccountPlan.STATUS_CHOICES,
        "account_id": account_id or "",
        "owner_id": owner_id or "",
        "status": status,
        "next_review": next_review,
        "period_from": period_from,
        "period_to": period_to,
        "stats": stats,
        "export_url": export_url,
        "can_edit_all": request.user.is_superuser or getattr(request.user, "is_tenant_admin", False),
    })


@login_required
def account_plan_create(request):
    if request.method == "POST":
        form = AccountPlanForm(request.POST, tenant=request.tenant, user=request.user)
        if form.is_valid():
            try:
                obj = save_account_plan(form, request.tenant, request.user)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "Account plan created.")
                return redirect("sales:account_plan_detail", pk=obj.pk)
    else:
        form = AccountPlanForm(tenant=request.tenant, user=request.user)
    return render(request, "sales/contactaccountmanagement/accountplan/form.html", {
        "form": form,
        "is_edit": False,
        "accounts": list(Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")[:500]),
        "owners": list(User.objects.filter(tenant=request.tenant, is_active=True).order_by("username")[:500]) if request.tenant is not None else [],
        "opportunities": list(Opportunity.objects.filter(tenant=request.tenant).only("id", "number", "name", "tenant_id", "account_id", "created_at").order_by("-created_at")[:500]),
    })


@login_required
def account_plan_edit(request, pk):
    obj = get_object_or_404(_plan_queryset(request), pk=pk)
    if not can_manage_account_plan(obj, request.user):
        raise PermissionDenied
    if obj.status == "archived":
        messages.info(request, "Archived account plans are read-only.")
        return redirect("sales:account_plan_detail", pk=obj.pk)
    if request.method == "POST":
        form = AccountPlanForm(request.POST, instance=obj, tenant=request.tenant, user=request.user)
        if form.is_valid():
            try:
                obj = save_account_plan(form, request.tenant, request.user, instance=obj)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "Account plan updated.")
                return redirect("sales:account_plan_detail", pk=obj.pk)
    else:
        form = AccountPlanForm(instance=obj, tenant=request.tenant, user=request.user)
    return render(request, "sales/contactaccountmanagement/accountplan/form.html", {
        "form": form,
        "obj": obj,
        "is_edit": True,
        "accounts": list(Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")[:500]),
        "owners": list(User.objects.filter(tenant=request.tenant, is_active=True).order_by("username")[:500]) if request.tenant is not None else [],
        "opportunities": list(Opportunity.objects.filter(tenant=request.tenant, account=obj.account).only("id", "number", "name", "tenant_id", "account_id", "created_at").order_by("-created_at")[:500]),
    })


@login_required
def account_plan_detail(request, pk):
    obj = get_object_or_404(_plan_queryset(request), pk=pk)
    related = list(
        obj.related_opportunities.filter(
            tenant=request.tenant,
            account=obj.account,
            account__tenant=request.tenant,
            account__kind="organization",
        )
        .only("id", "number", "name", "stage", "amount", "close_date", "account_id", "created_at")
        .order_by("-created_at")
    )
    rollups = account_rollups(request.tenant, [obj.account_id]).get(obj.account_id, {})
    health = HealthScore.objects.filter(tenant=request.tenant, account=obj.account).order_by("-computed_at", "-id").first()
    health_history = HealthScoreHistory.objects.filter(tenant=request.tenant, account=obj.account).order_by("-computed_at")[:20]
    tasks = list(
        CrmTask.objects.filter(
            tenant=request.tenant,
            party=obj.account,
            status__in=CrmTask.OPEN_STATUSES,
        ).select_related("owner").order_by("due_date", "-created_at")[:20]
    )
    activities = list(Activity.objects.filter(tenant=request.tenant, party=obj.account).order_by("-created_at")[:20])
    document_filter = Q(content_type=ContentType.objects.get_for_model(Party), object_id=obj.account_id)
    profile = AccountProfile.objects.filter(
        tenant=request.tenant,
        party=obj.account,
        party__tenant=request.tenant,
        party__kind="organization",
    ).only("pk").first()
    if profile is not None:
        document_filter |= Q(content_type=ContentType.objects.get_for_model(AccountProfile), object_id=profile.pk)
    documents = list(Document.objects.filter(tenant=request.tenant).filter(document_filter).order_by("-uploaded_at")[:20])
    coverage_roles = list(
        AccountStakeholder.objects.filter(
            tenant=request.tenant,
            account=obj.account,
            account__tenant=request.tenant,
            account__kind="organization",
            contact__tenant=request.tenant,
            contact__kind="person",
            status="active",
        ).values_list("role", flat=True).distinct()[:100]
    )
    return render(request, "sales/contactaccountmanagement/accountplan/detail.html", {
        "obj": obj,
        "account": obj.account,
        "owner": obj.owner,
        "related_opportunities": related,
        "opportunity_rollups": rollups,
        "health": health,
        "health_history": health_history,
        "tasks": tasks,
        "recent_activity": activities,
        "documents": documents,
        "currency_rollups": rollups.get("currencies", {}),
        "coverage": coverage_roles,
        "white_space_note": "Exact product white-space is incomplete until CRM Product and SCM Item have a governed mapping.",
        "allowed_actions": account_plan_allowed_actions(obj, request.user),
        "can_edit": obj.status != "archived" and can_manage_account_plan(obj, request.user),
    })


@require_POST
@tenant_admin_required
def account_plan_delete(request, pk):
    obj = get_object_or_404(_plan_queryset(request), pk=pk)
    if obj.status != "draft":
        messages.error(request, "Only draft plans can be deleted; archive non-draft plans instead.")
        return redirect("sales:account_plan_detail", pk=obj.pk)
    with transaction.atomic():
        locked = AccountPlan.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        if locked.status != "draft":
            messages.error(request, "Only draft plans can be deleted; archive non-draft plans instead.")
            return redirect("sales:account_plan_detail", pk=locked.pk)
        write_audit_log(request.user, locked, "delete", {"action": "account_plan"}, tenant=request.tenant)
        locked.delete()
    messages.success(request, "Account plan deleted.")
    return redirect("sales:account_plan_list")


def _transition_plan(request, pk, target_status):
    obj = get_object_or_404(_plan_queryset(request), pk=pk)
    try:
        transition_account_plan(obj, request.tenant, request.user, target_status)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:account_plan_detail", pk=obj.pk)
    messages.success(request, f"Account plan marked {target_status.replace('_', ' ')}.")
    return redirect("sales:account_plan_detail", pk=obj.pk)


@require_POST
@login_required
def account_plan_activate(request, pk):
    return _transition_plan(request, pk, "active")


@require_POST
@login_required
def account_plan_review_due(request, pk):
    return _transition_plan(request, pk, "review_due")


@require_POST
@login_required
def account_plan_complete(request, pk):
    return _transition_plan(request, pk, "completed")


@require_POST
@login_required
def account_plan_archive(request, pk):
    return _transition_plan(request, pk, "archived")


@login_required
def account_plan_export(request):
    from django.db.models import Prefetch

    queryset, filters = _filter_plan_queryset(request, _plan_queryset(request))
    plans = list(
        queryset.defer(
            "business_drivers", "objectives", "strategy", "strengths", "weaknesses",
            "opportunities", "threats", "white_space_assessment", "growth_initiatives", "risk_summary",
        )
        .prefetch_related(
            Prefetch(
                "related_opportunities",
                queryset=Opportunity.objects.filter(tenant=request.tenant).only("number", "tenant_id", "account_id"),
                to_attr="safe_related_opportunities",
            )
        )
        .order_by("-created_at")[:5000]
    )
    rows = (
        (
            plan.number,
            plan.account.name,
            plan.title,
            plan.get_status_display(),
            plan.period_start,
            plan.period_end,
            plan.owner.username,
            plan.next_review_on or "",
            ", ".join(
                opportunity.number
                for opportunity in plan.safe_related_opportunities
                if opportunity.tenant_id == request.tenant.pk and opportunity.account_id == plan.account_id
            ),
        )
        for plan in plans
    )
    return csv_export_response(
        request,
        filename="sales-account-plans.csv",
        dataset="account_plans",
        headers=["Number", "Account", "Title", "Status", "Period start", "Period end", "Owner", "Next review", "Linked opportunities"],
        rows=rows,
        filters={key: value for key, value in filters.items() if key != "q"},
    )
