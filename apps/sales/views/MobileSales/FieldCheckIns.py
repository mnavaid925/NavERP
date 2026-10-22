"""Sales 8.16 — FieldCheckIn views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.sales.forms.MobileSales.FieldCheckIns import (
    FieldCheckInFilterForm,
    FieldCheckInForm,
    FieldCheckOutForm,
)
from apps.sales.models.MobileSales.FieldCheckIns import (
    VERIFICATION_STATUS_CHOICES,
    VISIT_OUTCOME_CHOICES,
    VISIT_PURPOSE_CHOICES,
    FieldCheckIn,
)
from apps.sales.models.MobileSales.FieldSalesRoutes import FieldSalesRoute


@login_required
def field_check_in_list(request):
    tenant = request.tenant
    qs = (
        FieldCheckIn.objects.filter(tenant=tenant)
        .select_related("party", "sales_rep", "route", "resulting_quote", "opportunity")
        .order_by("-check_in_at")
    )

    filter_form = FieldCheckInFilterForm(request.GET, tenant=tenant)
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get("q")
        if q:
            qs = qs.filter(
                Q(party__name__icontains=q)
                | Q(number__icontains=q)
                | Q(notes__icontains=q)
                | Q(route__name__icontains=q)
            )

        verification_status = filter_form.cleaned_data.get("verification_status")
        if verification_status:
            qs = qs.filter(verification_status=verification_status)

        visit_purpose = filter_form.cleaned_data.get("visit_purpose")
        if visit_purpose:
            qs = qs.filter(visit_purpose=visit_purpose)

        outcome = filter_form.cleaned_data.get("outcome")
        if outcome:
            qs = qs.filter(outcome=outcome)

        sales_rep = filter_form.cleaned_data.get("sales_rep")
        if sales_rep:
            qs = qs.filter(sales_rep=sales_rep)

    all_checkins = FieldCheckIn.objects.filter(tenant=tenant)
    total_checkins_count = all_checkins.count()
    verified_checkins_count = all_checkins.filter(is_geofence_verified=True).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "check_ins": page_obj.object_list,
        "filter_form": filter_form,
        "verification_choices": VERIFICATION_STATUS_CHOICES,
        "purpose_choices": VISIT_PURPOSE_CHOICES,
        "outcome_choices": VISIT_OUTCOME_CHOICES,
        "total_checkins_count": total_checkins_count,
        "verified_checkins_count": verified_checkins_count,
    }
    return render(request, "sales/mobilesales/fieldcheckin/list.html", context)


@login_required
def field_check_in_detail(request, pk):
    tenant = request.tenant
    check_in = get_object_or_404(
        FieldCheckIn.objects.filter(tenant=tenant).select_related(
            "party", "contact", "opportunity", "sales_rep", "route", "photo_document", "resulting_quote", "communication_log"
        ),
        pk=pk,
    )

    duration_display = f"{check_in.duration_minutes} minutes" if check_in.duration_minutes else "In Progress"

    context = {
        "check_in": check_in,
        "duration_display": duration_display,
    }
    return render(request, "sales/mobilesales/fieldcheckin/detail.html", context)


@login_required
@transaction.atomic
def field_check_in_create(request):
    tenant = request.tenant
    route_id = request.GET.get("route")
    initial = {"sales_rep": request.user}
    if route_id and route_id.isdigit():
        route = FieldSalesRoute.objects.filter(tenant=tenant, pk=int(route_id)).first()
        if route:
            initial["route"] = route
            initial["stop_number"] = route.check_ins.count() + 1

    if request.method == "POST":
        form = FieldCheckInForm(request.POST, tenant=tenant)
        if form.is_valid():
            check_in = form.save(commit=False)
            check_in.tenant = tenant
            check_in.save()
            write_audit_log(
                request.user,
                check_in,
                "create",
                tenant=tenant,
            )
            messages.success(request, f"Check-In '{check_in.number}' at {check_in.party.name} recorded successfully.")
            return redirect("sales:field_check_in_detail", pk=check_in.pk)
    else:
        form = FieldCheckInForm(tenant=tenant, initial=initial)

    context = {
        "form": form,
        "check_in": None,
        "is_edit": False,
    }
    return render(request, "sales/mobilesales/fieldcheckin/form.html", context)


@login_required
@transaction.atomic
def field_check_in_edit(request, pk):
    tenant = request.tenant
    check_in = get_object_or_404(FieldCheckIn.objects.filter(tenant=tenant), pk=pk)

    if request.method == "POST":
        form = FieldCheckInForm(request.POST, instance=check_in, tenant=tenant)
        if form.is_valid():
            check_in = form.save()
            write_audit_log(
                request.user,
                check_in,
                "update",
                tenant=tenant,
            )
            messages.success(request, f"Check-In '{check_in.number}' updated successfully.")
            return redirect("sales:field_check_in_detail", pk=check_in.pk)
    else:
        form = FieldCheckInForm(instance=check_in, tenant=tenant)

    context = {
        "form": form,
        "check_in": check_in,
        "is_edit": True,
    }
    return render(request, "sales/mobilesales/fieldcheckin/form.html", context)


@login_required
@require_POST
@transaction.atomic
def field_check_in_delete(request, pk):
    tenant = request.tenant
    check_in = get_object_or_404(FieldCheckIn.objects.filter(tenant=tenant), pk=pk)
    num = check_in.number
    party_name = check_in.party.name
    check_in_pk = check_in.pk
    route = check_in.route

    write_audit_log(
        request.user,
        check_in,
        "delete",
        tenant=tenant,
    )
    check_in.delete()
    if route:
        route.completed_stops = route.check_ins.filter(check_out_at__isnull=False).count()
        route.save(update_fields=["completed_stops"])
    messages.success(request, f"Check-In '{num}' deleted successfully.")
    return redirect("sales:field_check_in_list")


@login_required
@transaction.atomic
def field_check_in_checkout(request, pk):
    tenant = request.tenant
    check_in = get_object_or_404(FieldCheckIn.objects.filter(tenant=tenant), pk=pk)

    if request.method == "POST":
        form = FieldCheckOutForm(request.POST, instance=check_in)
        if form.is_valid():
            check_in = form.save(commit=False)
            if not check_in.check_out_at:
                check_in.check_out_at = timezone.now()
            check_in.duration_minutes = check_in.calculate_duration()
            check_in.save()

            if check_in.route:
                completed = check_in.route.check_ins.filter(check_out_at__isnull=False).count()
                check_in.route.completed_stops = completed
                check_in.route.save(update_fields=["completed_stops"])

            write_audit_log(
                request.user,
                check_in,
                "update",
                changes={"action": "checkout"},
                tenant=tenant,
            )
            messages.success(request, f"Departure check-out recorded for {check_in.party.name} ({check_in.duration_minutes} min).")
            return redirect("sales:field_check_in_detail", pk=check_in.pk)
    else:
        form = FieldCheckOutForm(instance=check_in, initial={"check_out_lat": check_in.check_in_lat, "check_out_lng": check_in.check_in_lng})

    context = {
        "form": form,
        "check_in": check_in,
    }
    return render(request, "sales/mobilesales/fieldcheckin/checkout.html", context)
