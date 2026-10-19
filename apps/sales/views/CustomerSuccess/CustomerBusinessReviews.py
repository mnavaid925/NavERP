"""Sales 8.11 — Views for `CustomerBusinessReview` (QBR/EBR & Advocacy)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.sales.forms.CustomerSuccess.CustomerBusinessReviews import CustomerBusinessReviewForm
from apps.sales.models.CustomerSuccess.CustomerBusinessReviews import (
    CASE_STUDY_CHOICES,
    REVIEW_PERIOD_CHOICES,
    STATUS_CHOICES,
    TEMPLATE_CHOICES,
    CustomerBusinessReview,
)


@login_required
def customer_business_review_list(request):
    qs = (
        CustomerBusinessReview.objects.filter(tenant=request.tenant)
        .select_related("account", "lead_csm", "account_plan")
        .order_by("-scheduled_date", "-review_year")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(account__name__icontains=q)
            | Q(client_attendees__icontains=q)
            | Q(key_achievements__icontains=q)
            | Q(testimonial_quote__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    review_period = request.GET.get("review_period", "").strip()
    if review_period:
        qs = qs.filter(review_period=review_period)

    template_type = request.GET.get("template_type", "").strip()
    if template_type:
        qs = qs.filter(template_type=template_type)

    account_id = request.GET.get("account", "").strip()
    if account_id and account_id.isdigit():
        qs = qs.filter(account_id=int(account_id))

    csm_id = request.GET.get("lead_csm", "").strip()
    if csm_id and csm_id.isdigit():
        qs = qs.filter(lead_csm_id=int(csm_id))

    is_ref = request.GET.get("is_referenceable", "").strip()
    if is_ref in ("1", "true", "True"):
        qs = qs.filter(is_referenceable=True)

    stats = qs.aggregate(
        total_count=Count("id"),
        scheduled_count=Count("id", filter=Q(status__in=["scheduled", "materials_prepared"])),
        conducted_count=Count("id", filter=Q(status__in=["conducted", "follow_up_sent"])),
        referenceable_count=Count("id", filter=Q(is_referenceable=True)),
        case_study_count=Count("id", filter=~Q(case_study_status="none")),
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
        "reviews": page_obj.object_list,
        "period_choices": REVIEW_PERIOD_CHOICES,
        "status_choices": STATUS_CHOICES,
        "template_choices": TEMPLATE_CHOICES,
        "case_study_choices": CASE_STUDY_CHOICES,
        "accounts": accounts,
        "csm_users": csm_users,
        "active_filters": {
            "q": q,
            "status": status,
            "review_period": review_period,
            "template_type": template_type,
            "account": account_id,
            "lead_csm": csm_id,
            "is_referenceable": is_ref,
        },
        "stats": stats,
    }
    return render(request, "sales/customersuccess/customerbusinessreview/list.html", context)


@login_required
def customer_business_review_detail(request, pk):
    obj = get_object_or_404(
        CustomerBusinessReview.objects.filter(tenant=request.tenant).select_related(
            "account", "lead_csm", "account_plan"
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/customersuccess/customerbusinessreview/detail.html",
        {"obj": obj, "review": obj},
    )


@login_required
def customer_business_review_create(request):
    if request.method == "POST":
        form = CustomerBusinessReviewForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                f"Scheduled QBR {obj.number} for {obj.account.name} on {obj.scheduled_date}",
                tenant=request.tenant,
            )
            messages.success(request, f"Customer business review {obj.number} created successfully.")
            return redirect("sales:customer_business_review_detail", pk=obj.pk)
    else:
        form = CustomerBusinessReviewForm(tenant=request.tenant)

    return render(
        request,
        "sales/customersuccess/customerbusinessreview/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@login_required
def customer_business_review_edit(request, pk):
    obj = get_object_or_404(
        CustomerBusinessReview.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = CustomerBusinessReviewForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                f"Updated business review {obj.number} for {obj.account.name}",
                tenant=request.tenant,
            )
            messages.success(request, f"Customer business review {obj.number} updated successfully.")
            return redirect("sales:customer_business_review_detail", pk=obj.pk)
    else:
        form = CustomerBusinessReviewForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/customersuccess/customerbusinessreview/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def customer_business_review_delete(request, pk):
    obj = get_object_or_404(
        CustomerBusinessReview.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    title = obj.title
    number = obj.number
    write_audit_log(
        request.user,
        obj,
        "delete",
        f"Deleted business review {number} ({title})",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Business review {number} deleted.")
    return redirect("sales:customer_business_review_list")


@login_required
def customer_qbr_studio(request):
    """Derived Console 5 — Executive & Quarterly Business Review Studio."""
    all_reviews = (
        CustomerBusinessReview.objects.filter(tenant=request.tenant)
        .select_related("account", "lead_csm", "account_plan")
        .order_by("scheduled_date")
    )

    today = timezone.localdate()
    upcoming_qbrs = all_reviews.filter(scheduled_date__gte=today, status__in=["scheduled", "materials_prepared"])[:10]
    recent_completed = all_reviews.filter(status__in=["conducted", "follow_up_sent"]).order_by("-completed_date")[:10]

    stats = all_reviews.aggregate(
        total_count=Count("id"),
        scheduled_count=Count("id", filter=Q(status="scheduled")),
        completed_count=Count("id", filter=Q(status__in=["conducted", "follow_up_sent"])),
        exec_sponsor_attended=Count("id", filter=Q(executive_sponsor_attended=True)),
    )

    context = {
        "upcoming_qbrs": upcoming_qbrs,
        "recent_completed": recent_completed,
        "template_choices": TEMPLATE_CHOICES,
        "stats": stats,
    }
    return render(request, "sales/customersuccess/qbr_studio.html", context)


@login_required
def customer_advocacy_hub(request):
    """Derived Console 4 — Advocacy & Reference Management Center."""
    all_reviews = (
        CustomerBusinessReview.objects.filter(tenant=request.tenant)
        .select_related("account", "lead_csm")
        .order_by("-scheduled_date")
    )

    referenceable_accounts = all_reviews.filter(is_referenceable=True)
    case_study_pipeline = all_reviews.exclude(case_study_status="none")
    testimonials = all_reviews.exclude(testimonial_quote="").exclude(testimonial_quote__isnull=True)

    stats = all_reviews.aggregate(
        referenceable_count=Count("id", filter=Q(is_referenceable=True)),
        case_study_count=Count("id", filter=~Q(case_study_status="none")),
        testimonial_count=Count(
            "id",
            filter=~Q(testimonial_quote="") & Q(testimonial_quote__isnull=False),
        ),
        published_case_studies=Count("id", filter=Q(case_study_status="published")),
    )

    context = {
        "referenceable_accounts": referenceable_accounts[:15],
        "case_study_pipeline": case_study_pipeline[:15],
        "testimonials": testimonials[:15],
        "stats": stats,
    }
    return render(request, "sales/customersuccess/advocacy_hub.html", context)
