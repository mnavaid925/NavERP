import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.Personalization.AudienceSegments import AudienceSegmentForm
from apps.ecommerce.models.CustomerAccount.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.Personalization.AudienceSegments import AudienceSegment
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def audiencesegment_list(request):
    qs = ecommerce_scope(AudienceSegment.objects.all(), request)

    search_query = request.GET.get("q", "").strip()
    lifecycle_stage = request.GET.get("lifecycle_stage", "").strip()
    is_active = request.GET.get("is_active", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(code__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    if lifecycle_stage:
        qs = qs.filter(lifecycle_stage=lifecycle_stage)

    if is_active in ("1", "true", "True"):
        qs = qs.filter(is_active=True)
    elif is_active in ("0", "false", "False"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "segments": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": search_query,
        "search_query": search_query,
        "selected_lifecycle": lifecycle_stage,
        "selected_active": is_active,
        "lifecycle_choices": AudienceSegment.LIFECYCLE_STAGE_CHOICES,
    }
    return render(request, "ecommerce/personalization/audiencesegment/list.html", context)


@login_required
def audiencesegment_detail(request, pk):
    segment = ecommerce_object(request, AudienceSegment, pk)
    experiences = segment.experiences.filter(is_active=True).order_by("-priority")
    strategies = segment.recommendation_strategies.filter(is_active=True)

    context = {
        "segment": segment,
        "experiences": experiences,
        "recommendation_strategies": strategies,
    }
    return render(request, "ecommerce/personalization/audiencesegment/detail.html", context)


@login_required
@tenant_admin_required
def audiencesegment_create(request):
    if request.method == "POST":
        form = AudienceSegmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            segment = form.save(commit=False)
            segment.tenant = request.tenant
            segment.save()
            write_audit_log(
                request.tenant,
                request.user,
                "create",
                "AudienceSegment",
                segment.pk,
                f"Created audience segment {segment.name} ({segment.number})",
            )
            messages.success(request, f"Audience segment '{segment.name}' created.")
            return redirect("ecommerce:audiencesegment_detail", pk=segment.pk)
    else:
        form = AudienceSegmentForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/personalization/audiencesegment/form.html", context)


@login_required
@tenant_admin_required
def audiencesegment_edit(request, pk):
    segment = ecommerce_object(request, AudienceSegment, pk)
    if request.method == "POST":
        form = AudienceSegmentForm(request.POST, instance=segment, tenant=request.tenant)
        if form.is_valid():
            segment = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "update",
                "AudienceSegment",
                segment.pk,
                f"Updated audience segment {segment.name} ({segment.number})",
            )
            messages.success(request, f"Audience segment '{segment.name}' updated.")
            return redirect("ecommerce:audiencesegment_detail", pk=segment.pk)
    else:
        form = AudienceSegmentForm(instance=segment, tenant=request.tenant)

    context = {
        "form": form,
        "segment": segment,
        "is_edit": True,
    }
    return render(request, "ecommerce/personalization/audiencesegment/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def audiencesegment_delete(request, pk):
    segment = ecommerce_object(request, AudienceSegment, pk)
    name = segment.name
    number = segment.number
    segment.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "delete",
        "AudienceSegment",
        pk,
        f"Deleted audience segment {name} ({number})",
    )
    messages.success(request, f"Audience segment '{name}' deleted.")
    return redirect("ecommerce:audiencesegment_list")


@login_required
@tenant_admin_required
@require_POST
def audiencesegment_toggle(request, pk):
    segment = ecommerce_object(request, AudienceSegment, pk)
    segment.is_active = not segment.is_active
    segment.save(update_fields=["is_active", "updated_at"])
    state = "activated" if segment.is_active else "deactivated"
    write_audit_log(
        request.tenant,
        request.user,
        "toggle",
        "AudienceSegment",
        segment.pk,
        f"{state.capitalize()} audience segment {segment.name} ({segment.number})",
    )
    messages.success(request, f"Audience segment '{segment.name}' {state}.")
    return redirect("ecommerce:audiencesegment_detail", pk=segment.pk)


@login_required
@tenant_admin_required
@require_POST
def audiencesegment_recalculate(request, pk):
    segment = ecommerce_object(request, AudienceSegment, pk)
    qs = CustomerAccountProfile.objects.filter(tenant=request.tenant)

    if segment.min_order_count > 0:
        qs = qs.filter(order_count__gte=segment.min_order_count)

    if segment.min_lifetime_spend > Decimal("0.00"):
        qs = qs.filter(total_spent__gte=segment.min_lifetime_spend)

    if segment.recency_days_max:
        cutoff = timezone.now() - datetime.timedelta(days=segment.recency_days_max)
        qs = qs.filter(last_order_at__gte=cutoff)

    count = qs.count()
    segment.cached_member_count = count
    segment.last_evaluated_at = timezone.now()
    segment.save(update_fields=["cached_member_count", "last_evaluated_at", "updated_at"])

    write_audit_log(
        request.tenant,
        request.user,
        "recalculate",
        "AudienceSegment",
        segment.pk,
        f"Recalculated audience segment {segment.name} ({segment.number}) member count: {count}",
    )
    messages.success(request, f"Audience segment '{segment.name}' recalculated: {count} matching profiles.")
    return redirect("ecommerce:audiencesegment_detail", pk=segment.pk)
