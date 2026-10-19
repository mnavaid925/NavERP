"""Sales 8.11 — Views for `CustomerOnboarding`."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.sales.forms.CustomerSuccess.CustomerOnboardings import CustomerOnboardingForm
from apps.sales.models.CustomerSuccess.CustomerOnboardings import (
    PLAYBOOK_CHOICES,
    STAGE_CHOICES,
    STATUS_CHOICES,
    CustomerOnboarding,
)


@login_required
def customer_onboarding_list(request):
    qs = (
        CustomerOnboarding.objects.filter(tenant=request.tenant)
        .select_related("account", "lead_csm", "sales_order")
        .order_by("target_go_live_date", "-kickoff_date")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(account__name__icontains=q)
            | Q(executive_sponsor_name__icontains=q)
            | Q(blockers__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    stage = request.GET.get("stage", "").strip()
    if stage:
        qs = qs.filter(stage=stage)

    playbook = request.GET.get("playbook_template", "").strip()
    if playbook:
        qs = qs.filter(playbook_template=playbook)

    account_id = request.GET.get("account", "").strip()
    if account_id and account_id.isdigit():
        qs = qs.filter(account_id=int(account_id))

    csm_id = request.GET.get("lead_csm", "").strip()
    if csm_id and csm_id.isdigit():
        qs = qs.filter(lead_csm_id=int(csm_id))

    stats = qs.aggregate(
        total_count=Count("id"),
        in_progress_count=Count("id", filter=Q(status__in=["in_progress", "on_track"])),
        at_risk_count=Count("id", filter=Q(status__in=["at_risk", "blocked"])),
        completed_count=Count("id", filter=Q(status="completed")),
        avg_progress=Avg("progress_pct"),
        avg_ttv=Avg("time_to_value_days", filter=Q(status="completed")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    accounts = (
        Party.objects.filter(tenant=request.tenant, roles__role="customer")
        .distinct()
        .order_by("name")
    )
    csm_users = User.objects.filter(tenant=request.tenant).order_by("username")

    context = {
        "page_obj": page_obj,
        "onboardings": page_obj.object_list,
        "playbook_choices": PLAYBOOK_CHOICES,
        "stage_choices": STAGE_CHOICES,
        "status_choices": STATUS_CHOICES,
        "accounts": accounts,
        "csm_users": csm_users,
        "active_filters": {
            "q": q,
            "status": status,
            "stage": stage,
            "playbook_template": playbook,
            "account": account_id,
            "lead_csm": csm_id,
        },
        "stats": stats,
    }
    return render(request, "sales/customersuccess/customeronboarding/list.html", context)


@login_required
def customer_onboarding_detail(request, pk):
    obj = get_object_or_404(
        CustomerOnboarding.objects.filter(tenant=request.tenant).select_related(
            "account", "lead_csm", "sales_order"
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/customersuccess/customeronboarding/detail.html",
        {"obj": obj, "onboarding": obj},
    )


@login_required
def customer_onboarding_create(request):
    if request.method == "POST":
        form = CustomerOnboardingForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                f"Launched customer onboarding {obj.number} for {obj.account.name} (Playbook: {obj.get_playbook_template_display()})",
                tenant=request.tenant,
            )
            messages.success(request, f"Customer onboarding project {obj.number} created successfully.")
            return redirect("sales:customer_onboarding_detail", pk=obj.pk)
    else:
        form = CustomerOnboardingForm(tenant=request.tenant)

    return render(
        request,
        "sales/customersuccess/customeronboarding/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@login_required
def customer_onboarding_edit(request, pk):
    obj = get_object_or_404(
        CustomerOnboarding.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = CustomerOnboardingForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                f"Updated onboarding {obj.number} for {obj.account.name}",
                tenant=request.tenant,
            )
            messages.success(request, f"Customer onboarding {obj.number} updated successfully.")
            return redirect("sales:customer_onboarding_detail", pk=obj.pk)
    else:
        form = CustomerOnboardingForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/customersuccess/customeronboarding/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def customer_onboarding_delete(request, pk):
    obj = get_object_or_404(
        CustomerOnboarding.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    title = obj.title
    number = obj.number
    write_audit_log(
        request.user,
        obj,
        "delete",
        f"Deleted customer onboarding {number} ({title})",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Customer onboarding {number} deleted.")
    return redirect("sales:customer_onboarding_list")


@login_required
def customer_onboarding_hub(request):
    """Derived Console 3 — Onboarding & Implementation Playbook Hub."""
    all_onboardings = (
        CustomerOnboarding.objects.filter(tenant=request.tenant)
        .select_related("account", "lead_csm", "sales_order")
        .order_by("target_go_live_date")
    )

    active_onboardings = all_onboardings.filter(status__in=["in_progress", "on_track"])[:10]
    blocked_onboardings = all_onboardings.filter(status__in=["at_risk", "blocked"])[:10]
    completed_recent = all_onboardings.filter(status="completed")[:10]

    stats = all_onboardings.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status__in=["in_progress", "on_track"])),
        blocked_count=Count("id", filter=Q(status__in=["at_risk", "blocked"])),
        completed_count=Count("id", filter=Q(status="completed")),
        avg_progress=Avg("progress_pct"),
        avg_ttv=Avg("time_to_value_days", filter=Q(status="completed")),
    )

    context = {
        "active_onboardings": active_onboardings,
        "blocked_onboardings": blocked_onboardings,
        "completed_recent": completed_recent,
        "stats": stats,
    }
    return render(request, "sales/customersuccess/onboarding_hub.html", context)
