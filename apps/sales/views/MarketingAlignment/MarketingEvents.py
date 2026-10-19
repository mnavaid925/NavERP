"""Sales 8.13 — Views for `MarketingEvent` and its `EventRegistration` child."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Campaign
from apps.sales.forms.MarketingAlignment.MarketingEvents import (
    EventRegistrationForm,
    MarketingEventForm,
)
from apps.sales.models.MarketingAlignment.MarketingEvents import (
    EVENT_STATUS_CHOICES,
    EVENT_TYPE_CHOICES,
    FOLLOWUP_STATUS_CHOICES,
    REGISTRATION_STATUS_CHOICES,
    EventRegistration,
    MarketingEvent,
)
from apps.sales.views.MarketingAlignment._common import pk_from_param


def _event_annotations(queryset):
    """Annotate registration and attendance totals without a JOIN.

    Two correlated subqueries are used instead of a ``Count("registrations")`` annotation: a
    multi-valued annotation adds a JOIN, and the outer ``Count("id")`` on such a queryset
    counts the joined rows, which would inflate every event-level total on the page.
    """
    registered = (
        EventRegistration.objects.filter(event=OuterRef("pk"))
        .values("event")
        .annotate(c=Count("id"))
        .values("c")
    )
    attended = (
        EventRegistration.objects.filter(
            event=OuterRef("pk"), registration_status="attended"
        )
        .values("event")
        .annotate(c=Count("id"))
        .values("c")
    )
    return queryset.annotate(
        registered_total=Coalesce(Subquery(registered), 0),
        attended_total=Coalesce(Subquery(attended), 0),
    )


@login_required
def marketing_event_list(request):
    qs = (
        MarketingEvent.objects.filter(tenant=request.tenant)
        .select_related("owner", "campaign", "currency")
        .order_by("-start_at", "-created_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(venue__icontains=q) | Q(number__icontains=q)
        )

    event_type = request.GET.get("event_type", "").strip()
    if event_type:
        qs = qs.filter(event_type=event_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    owner_id = request.GET.get("owner", "").strip()
    owner_pk = pk_from_param(owner_id)
    if owner_pk is not None:
        qs = qs.filter(owner_id=owner_pk)

    campaign_id = request.GET.get("campaign", "").strip()
    campaign_pk = pk_from_param(campaign_id)
    if campaign_pk is not None:
        qs = qs.filter(campaign_id=campaign_pk)

    now = timezone.now()
    stats = qs.aggregate(
        total_count=Count("id"),
        published_count=Count("id", filter=Q(status="published")),
        upcoming_count=Count("id", filter=Q(start_at__gte=now)),
    )
    qs = _event_annotations(qs)
    registration_stats = qs.aggregate(
        total_registrations=Sum("registered_total"),
        total_attendance=Sum("attended_total"),
    )
    stats["total_registrations"] = registration_stats["total_registrations"] or 0
    stats["total_attendance"] = registration_stats["total_attendance"] or 0
    if stats["total_registrations"]:
        stats["avg_show_up_pct"] = round(
            stats["total_attendance"] / stats["total_registrations"] * 100, 1
        )
    else:
        stats["avg_show_up_pct"] = None

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    owners = User.objects.filter(tenant=request.tenant).order_by("username")
    campaigns = Campaign.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "page_obj": page_obj,
        "events": page_obj.object_list,
        "event_type_choices": EVENT_TYPE_CHOICES,
        "status_choices": EVENT_STATUS_CHOICES,
        "owners": owners,
        "campaigns": campaigns,
        "active_filters": {
            "q": q,
            "event_type": event_type,
            "status": status,
            "owner": owner_id,
            "campaign": campaign_id,
        },
        "stats": stats,
    }
    return render(
        request,
        "sales/marketingalignment/marketingevent/list.html",
        context,
    )


@login_required
def marketing_event_detail(request, pk):
    obj = get_object_or_404(
        _event_annotations(
            MarketingEvent.objects.filter(tenant=request.tenant).select_related(
                "owner", "campaign", "currency"
            )
        ),
        pk=pk,
    )
    registrations = (
        EventRegistration.objects.filter(tenant=request.tenant, event=obj)
        .select_related("lead", "account", "campaign", "opportunity")
        .order_by("-registered_at")
    )
    context = {
        "obj": obj,
        "event": obj,
        "registrations": registrations,
        "registration_status_choices": REGISTRATION_STATUS_CHOICES,
        "followup_status_choices": FOLLOWUP_STATUS_CHOICES,
    }
    return render(
        request,
        "sales/marketingalignment/marketingevent/detail.html",
        context,
    )


@login_required
def marketing_event_create(request):
    if request.method == "POST":
        form = MarketingEventForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                f"Created marketing event {obj.number} ({obj.name})",
                tenant=request.tenant,
            )
            messages.success(request, f"Marketing event {obj.number} created successfully.")
            return redirect("sales:marketing_event_detail", pk=obj.pk)
    else:
        form = MarketingEventForm(tenant=request.tenant)

    return render(
        request,
        "sales/marketingalignment/marketingevent/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@login_required
def marketing_event_edit(request, pk):
    obj = get_object_or_404(
        MarketingEvent.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = MarketingEventForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                f"Updated marketing event {obj.number} ({obj.name})",
                tenant=request.tenant,
            )
            messages.success(request, f"Marketing event {obj.number} updated successfully.")
            return redirect("sales:marketing_event_detail", pk=obj.pk)
    else:
        form = MarketingEventForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/marketingalignment/marketingevent/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def marketing_event_delete(request, pk):
    obj = get_object_or_404(
        MarketingEvent.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    number = obj.number
    name = obj.name
    write_audit_log(
        request.user,
        obj,
        "delete",
        f"Deleted marketing event {number} ({name})",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Marketing event {number} deleted.")
    return redirect("sales:marketing_event_list")


@login_required
def marketing_event_registrations(request, pk):
    """The registration and attendance list for one event."""
    obj = get_object_or_404(
        MarketingEvent.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    qs = (
        EventRegistration.objects.filter(tenant=request.tenant, event=obj)
        .select_related("lead", "account", "campaign", "opportunity")
        .order_by("-registered_at")
    )

    registration_status = request.GET.get("registration_status", "").strip()
    if registration_status:
        qs = qs.filter(registration_status=registration_status)

    followup_status = request.GET.get("followup_status", "").strip()
    if followup_status:
        qs = qs.filter(followup_status=followup_status)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "event": obj,
        "obj": obj,
        "registrations": page_obj.object_list,
        "page_obj": page_obj,
        "registration_status_choices": REGISTRATION_STATUS_CHOICES,
        "followup_status_choices": FOLLOWUP_STATUS_CHOICES,
        "active_filters": {
            "registration_status": registration_status,
            "followup_status": followup_status,
        },
    }
    return render(
        request,
        "sales/marketingalignment/marketingevent/registrations.html",
        context,
    )


@login_required
def marketing_event_registration_create(request, pk):
    """Add a registration to one event."""
    obj = get_object_or_404(
        MarketingEvent.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = EventRegistrationForm(
            request.POST, tenant=request.tenant, instance=EventRegistration(
                tenant=request.tenant, event=obj
            )
        )
        # The event comes from the URL, never from the form post.
        form.fields["event"].disabled = True
        if form.is_valid():
            registration = form.save(commit=False)
            registration.tenant = request.tenant
            registration.event = obj
            registration.save()
            write_audit_log(
                request.user,
                registration,
                "create",
                f"Registered {registration.registrant_name} for event {obj.number}",
                tenant=request.tenant,
            )
            messages.success(
                request, f"Registration for {registration.registrant_name} added."
            )
            return redirect("sales:marketing_event_registrations", pk=obj.pk)
    else:
        form = EventRegistrationForm(
            tenant=request.tenant,
            instance=EventRegistration(tenant=request.tenant, event=obj),
        )
        form.fields["event"].disabled = True

    return render(
        request,
        "sales/marketingalignment/marketingevent/registration_form.html",
        {"form": form, "event": obj, "obj": None, "is_edit": False},
    )
