from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from apps.core.crud import as_db_int, apply_search, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.crm.models import HealthScore, HealthScoreHistory
from apps.sales.forms.ContactAccountManagement.AccountClassifications import AccountClassificationForm
from apps.sales.models.ContactAccountManagement.AccountClassifications import AccountClassification
from apps.sales.services import account_hierarchy_rows, account_rollups
from apps.sales.views._common import *


def _classification_queryset(request):
    return AccountClassification.objects.filter(tenant=request.tenant).select_related("account", "classified_by")


def _filter_classification_queryset(request, queryset):
    filters = {
        "q": request.GET.get("q", "").strip(),
        "account": as_db_int(request.GET.get("account")),
        "tier": request.GET.get("tier", ""),
        "lifecycle_stage": request.GET.get("lifecycle_stage", ""),
        "strategic_priority": request.GET.get("strategic_priority", ""),
        "revenue_potential": request.GET.get("revenue_potential", ""),
        "wallet_category": request.GET.get("wallet_category", ""),
        "review_due": request.GET.get("review_due", ""),
    }
    queryset = apply_search(queryset, filters["q"], ["account__name", "rationale"])
    if filters["account"]:
        queryset = queryset.filter(account_id=filters["account"])
    for key, field, choices in (
        ("tier", "tier", dict(AccountClassification.TIER_CHOICES)),
        ("lifecycle_stage", "lifecycle_stage", dict(AccountClassification.LIFECYCLE_STAGE_CHOICES)),
        ("strategic_priority", "strategic_priority", dict(AccountClassification.STRATEGIC_PRIORITY_CHOICES)),
        ("revenue_potential", "revenue_potential", dict(AccountClassification.REVENUE_POTENTIAL_CHOICES)),
        ("wallet_category", "wallet_category", dict(AccountClassification.WALLET_CATEGORY_CHOICES)),
    ):
        if filters[key] in choices:
            queryset = queryset.filter(**{field: filters[key]})
    today = timezone.localdate()
    if filters["review_due"] == "overdue":
        queryset = queryset.filter(review_due_on__lt=today)
    elif filters["review_due"] == "due_soon":
        queryset = queryset.filter(review_due_on__gte=today, review_due_on__lte=today + timedelta(days=30))
    elif filters["review_due"] == "scheduled":
        queryset = queryset.filter(review_due_on__isnull=False)
    return queryset, filters


@login_required
def account_classification_list(request):
    queryset = _classification_queryset(request)
    queryset, filters = _filter_classification_queryset(request, queryset)
    q = filters["q"]
    account_id = filters["account"]
    tier = filters["tier"]
    lifecycle_stage = filters["lifecycle_stage"]
    strategic_priority = filters["strategic_priority"]
    revenue_potential = filters["revenue_potential"]
    wallet_category = filters["wallet_category"]
    review_due = filters["review_due"]
    page_obj = paginate(request, queryset, 20)
    base = _classification_queryset(request)
    today = timezone.localdate()
    stats = base.aggregate(
        total=Count("pk"),
        strategic=Count("pk", filter=Q(tier="strategic")),
        key=Count("pk", filter=Q(tier="key")),
        review_overdue=Count("pk", filter=Q(review_due_on__lt=today)),
    )
    export_url = reverse("sales:account_classification_export")
    if request.GET:
        export_url = f"{export_url}?{request.GET.urlencode()}"
    return render(request, "sales/contactaccountmanagement/accountclassification/list.html", {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "accounts": list(Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")[:500]),
        "tier_choices": AccountClassification.TIER_CHOICES,
        "lifecycle_stage_choices": AccountClassification.LIFECYCLE_STAGE_CHOICES,
        "strategic_priority_choices": AccountClassification.STRATEGIC_PRIORITY_CHOICES,
        "revenue_potential_choices": AccountClassification.REVENUE_POTENTIAL_CHOICES,
        "wallet_category_choices": AccountClassification.WALLET_CATEGORY_CHOICES,
        "account_id": account_id or "",
        "tier": tier,
        "lifecycle_stage": lifecycle_stage,
        "strategic_priority": strategic_priority,
        "revenue_potential": revenue_potential,
        "wallet_category": wallet_category,
        "review_due": review_due,
        "stats": stats,
        "export_url": export_url,
        "can_edit": request.user.is_superuser or getattr(request.user, "is_tenant_admin", False),
    })


@tenant_admin_required
def account_classification_create(request):
    if request.method == "POST":
        form = AccountClassificationForm(request.POST, tenant=request.tenant)
        account_id = as_db_int(request.POST.get("account"))
        if account_id:
            existing = AccountClassification.objects.filter(
                tenant=request.tenant,
                account_id=account_id,
            ).first()
            if existing is not None:
                messages.info(request, "This account already has a current classification.")
                return redirect("sales:account_classification_edit", pk=existing.pk)
        if form.is_valid():
            redirect_pk = None
            try:
                with transaction.atomic():
                    account = Party.objects.select_for_update().get(
                        pk=form.cleaned_data["account"].pk,
                        tenant=request.tenant,
                        kind="organization",
                    )
                    existing = AccountClassification.objects.select_for_update().filter(
                        tenant=request.tenant,
                        account=account,
                    ).first()
                    if existing is not None:
                        redirect_pk = existing.pk
                    else:
                        obj = form.save(commit=False)
                        obj.tenant = request.tenant
                        obj.account = account
                        obj.classified_by = request.user
                        obj.save()
                        write_audit_log(request.user, obj, "create", {"action": "account_classification", "tier": obj.tier}, tenant=request.tenant)
            except IntegrityError:
                existing = AccountClassification.objects.filter(
                    tenant=request.tenant,
                    account=form.cleaned_data["account"],
                ).first()
                if existing is None:
                    raise
                redirect_pk = existing.pk
            if redirect_pk is not None:
                messages.info(request, "This account already has a current classification.")
                return redirect("sales:account_classification_edit", pk=redirect_pk)
            messages.success(request, "Account classification saved.")
            return redirect("sales:account_classification_detail", pk=obj.pk)
    else:
        form = AccountClassificationForm(tenant=request.tenant)
    return render(request, "sales/contactaccountmanagement/accountclassification/form.html", {
        "form": form,
        "is_edit": False,
        "accounts": list(Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")[:500]),
    })


@tenant_admin_required
def account_classification_edit(request, pk):
    obj = get_object_or_404(_classification_queryset(request), pk=pk)
    if request.method == "POST":
        form = AccountClassificationForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                locked = AccountClassification.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
                form.instance = locked
                for field_name in form._meta.fields:
                    model_field = form.instance._meta.get_field(field_name)
                    if model_field.concrete and not model_field.many_to_many and field_name in form.cleaned_data:
                        setattr(form.instance, field_name, form.cleaned_data[field_name])
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.classified_by = request.user
                obj.save()
                write_audit_log(request.user, obj, "update", {"action": "account_classification", "tier": obj.tier, "status": obj.lifecycle_stage}, tenant=request.tenant)
            messages.success(request, "Account classification updated.")
            return redirect("sales:account_classification_detail", pk=obj.pk)
    else:
        form = AccountClassificationForm(instance=obj, tenant=request.tenant)
    return render(request, "sales/contactaccountmanagement/accountclassification/form.html", {
        "form": form,
        "obj": obj,
        "is_edit": True,
        "accounts": list(Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")[:500]),
    })


@login_required
def account_classification_detail(request, pk):
    obj = get_object_or_404(_classification_queryset(request), pk=pk)
    health = HealthScore.objects.filter(tenant=request.tenant, account=obj.account).order_by("-computed_at", "-id").first()
    history = HealthScoreHistory.objects.filter(tenant=request.tenant, account=obj.account).order_by("-computed_at")[:20]
    hierarchy = next((row for row in account_hierarchy_rows(request.tenant) if row["party"].pk == obj.account_id), None)
    rollups = account_rollups(request.tenant, [obj.account_id]).get(obj.account_id, {})
    return render(request, "sales/contactaccountmanagement/accountclassification/detail.html", {
        "obj": obj,
        "account": obj.account,
        "health": health,
        "health_history": history,
        "hierarchy_position": hierarchy,
        "opportunity_rollups": rollups,
        "invoice_rollups": rollups,
        "order_rollups": rollups,
        "currency_rollups": rollups.get("currencies", {}),
        "can_edit": request.user.is_superuser or getattr(request.user, "is_tenant_admin", False),
    })


@require_POST
@tenant_admin_required
def account_classification_delete(request, pk):
    obj = get_object_or_404(_classification_queryset(request), pk=pk)
    with transaction.atomic():
        locked = AccountClassification.objects.select_for_update().get(pk=obj.pk, tenant=request.tenant)
        write_audit_log(request.user, locked, "delete", {"action": "account_classification", "account_id": locked.account_id, "tier": locked.tier}, tenant=request.tenant)
        locked.delete()
    messages.success(request, "Account classification deleted.")
    return redirect("sales:account_classification_list")


@login_required
def account_classification_export(request):
    queryset, filters = _filter_classification_queryset(request, _classification_queryset(request))
    rows = (
        (
            obj.account.name,
            obj.get_tier_display(),
            obj.get_lifecycle_stage_display(),
            obj.get_strategic_priority_display(),
            obj.get_revenue_potential_display(),
            obj.get_wallet_category_display(),
            obj.effective_on,
            obj.review_due_on or "",
            obj.rationale,
        )
        for obj in queryset.order_by("account__name")[:5000]
    )
    return csv_export_response(
        request,
        filename="sales-account-classifications.csv",
        dataset="account_classifications",
        headers=["Account", "Tier", "Lifecycle", "Priority", "Potential", "Wallet", "Effective", "Review due", "Rationale"],
        rows=rows,
        filters={key: value for key, value in filters.items() if key != "q"},
    )
