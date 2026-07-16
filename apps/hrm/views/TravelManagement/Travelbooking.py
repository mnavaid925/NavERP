"""HRM 3.35 Travel Management — Travelbooking views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    TravelBooking,
    TravelRequest,
)
from apps.hrm.forms import (
    TravelBookingForm,
)
from apps.hrm.views.PersonalInformation._helpers import _can_manage_own_child


@login_required
@require_POST
def travelbooking_add(request, travel_request_pk):
    trip = get_object_or_404(TravelRequest, pk=travel_request_pk, tenant=request.tenant)
    if not _can_manage_own_child(request, trip):
        raise PermissionDenied("This trip belongs to another employee.")
    if trip.status not in TravelRequest.OPEN_STATUSES:
        messages.error(request, "Bookings can only be added while the trip is draft or pending.")
        return redirect("hrm:travelrequest_detail", pk=trip.pk)
    form = TravelBookingForm(request.POST, request.FILES,
                             instance=TravelBooking(tenant=request.tenant, travel_request=trip),
                             tenant=request.tenant)
    if form.is_valid():
        form.save()
        write_audit_log(request.user, trip, "update", {"action": "booking_add"})
        messages.success(request, "Booking added.")
    else:
        messages.error(request, "; ".join(f"{fld}: {errs[0]}" for fld, errs in form.errors.items()))
    return redirect("hrm:travelrequest_detail", pk=trip.pk)


@login_required
def travelbooking_edit(request, pk):
    booking = get_object_or_404(TravelBooking.objects.select_related("travel_request"), pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, booking.travel_request):
        raise PermissionDenied("This trip belongs to another employee.")
    if booking.travel_request.status not in TravelRequest.OPEN_STATUSES:
        messages.error(request, "Bookings can only be edited while the trip is draft or pending.")
        return redirect("hrm:travelrequest_detail", pk=booking.travel_request_id)
    if request.method == "POST":
        form = TravelBookingForm(request.POST, request.FILES, instance=booking, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, booking.travel_request, "update", {"action": "booking_edit"})
            messages.success(request, "Booking updated.")
            return redirect("hrm:travelrequest_detail", pk=booking.travel_request_id)
    else:
        form = TravelBookingForm(instance=booking, tenant=request.tenant)
    return render(request, "hrm/travel/travelbooking/form.html",
                  {"form": form, "obj": booking, "travel_request": booking.travel_request, "is_edit": True})


@login_required
@require_POST
def travelbooking_delete(request, pk):
    booking = get_object_or_404(TravelBooking.objects.select_related("travel_request"), pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, booking.travel_request):
        raise PermissionDenied("This trip belongs to another employee.")
    if booking.travel_request.status not in TravelRequest.OPEN_STATUSES:
        messages.error(request, "Bookings can only be removed while the trip is draft or pending.")
        return redirect("hrm:travelrequest_detail", pk=booking.travel_request_id)
    trip_pk = booking.travel_request_id
    booking.delete()
    write_audit_log(request.user, booking.travel_request, "update", {"action": "booking_delete"})
    messages.success(request, "Booking removed.")
    return redirect("hrm:travelrequest_detail", pk=trip_pk)
