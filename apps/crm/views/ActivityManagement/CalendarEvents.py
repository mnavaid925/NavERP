"""CRM 1.5 Activity & Communication Management — CalendarEvents views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    CalendarEvent,
    EventAttendee,
)
from apps.crm.forms import (
    CalendarEventForm,
    EventAttendeeForm,
    PublicRsvpForm,
)


# ===================== Calendar Events (1.5 Calendar Integration) ===========================
@login_required
def calendarevent_list(request):
    return crud_list(
        request,
        CalendarEvent.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/activities/calendarevent/list.html",
        search_fields=["title", "number", "location"],
        filters=[("status", "status", False), ("event_type", "event_type", False)],
        extra_context={"status_choices": CalendarEvent.STATUS_CHOICES,
                       "type_choices": CalendarEvent.TYPE_CHOICES},
    )


@login_required
def calendarevent_create(request):
    return crud_create(request, form_class=CalendarEventForm,
                       template="crm/activities/calendarevent/form.html",
                       success_url="crm:calendarevent_list")


@login_required
def calendarevent_detail(request, pk):
    event = get_object_or_404(
        CalendarEvent.objects.select_related("owner", "party", "related_opportunity", "related_case"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/activities/calendarevent/detail.html", {
        "obj": event,
        "attendees": event.attendees.select_related("party").all(),
        "attendee_form": EventAttendeeForm(tenant=request.tenant),  # L7: always pass the add form
    })


@login_required
def calendarevent_edit(request, pk):
    return crud_edit(request, model=CalendarEvent, pk=pk, form_class=CalendarEventForm,
                     template="crm/activities/calendarevent/form.html",
                     success_url="crm:calendarevent_list")


@login_required
@require_POST
def calendarevent_delete(request, pk):
    return crud_delete(request, model=CalendarEvent, pk=pk, success_url="crm:calendarevent_list")


# ----- EventAttendee inline actions (managed on the event detail page) ----------------------
@login_required
@require_POST
def event_attendee_add(request, event_pk):
    event = get_object_or_404(CalendarEvent, pk=event_pk, tenant=request.tenant)
    form = EventAttendeeForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        cd = form.cleaned_data
        email = cd.get("email") or None
        if email:
            # Upsert by (event, email) — avoids the unique_together IntegrityError on re-add.
            EventAttendee.objects.update_or_create(
                event=event, email=email,
                defaults={"tenant": event.tenant, "party": cd.get("party"), "name": cd["name"],
                          "rsvp_status": cd["rsvp_status"], "is_organizer": cd["is_organizer"]})
        else:
            attendee = form.save(commit=False)
            attendee.tenant = event.tenant
            attendee.event = event
            attendee.save()
        messages.success(request, "Attendee added.")
    else:
        messages.error(request, "Could not add attendee — check the name/email and try again.")
    return redirect("crm:calendarevent_detail", pk=event_pk)


@login_required
@require_POST
def event_attendee_delete(request, pk):
    attendee = get_object_or_404(EventAttendee, pk=pk, tenant=request.tenant)
    event_pk = attendee.event_id
    attendee.delete()
    messages.success(request, "Attendee removed.")
    return redirect("crm:calendarevent_detail", pk=event_pk)


# ----- Public meeting-invite pages (no login — the token is the bearer credential) ----------
def event_invite(request, token):
    """Public meeting invite + RSVP (1.5). No login; the unguessable ``public_token`` gates one
    event. The RSVP upserts an ``EventAttendee`` by email. CSRF enforced by the template tag;
    tenant taken from the event itself.
    # WARNING: unauthenticated POST — add per-IP rate-limiting (django-ratelimit) or a WAF throttle
    # in production to stop public RSVP floods."""
    event = get_object_or_404(
        CalendarEvent.objects.select_related("owner", "party"), public_token=token)
    form = PublicRsvpForm()
    if request.method == "POST":
        form = PublicRsvpForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # First response wins: the invite token is shared with every invitee, so an anonymous
            # visitor who knows another invitee's email must not overwrite a response already on file.
            existing = EventAttendee.objects.filter(event=event, email=cd["email"]).first()
            if existing and existing.rsvp_status != "no_response":
                messages.info(request, "A response for that email is already recorded.")
            else:
                EventAttendee.objects.update_or_create(
                    event=event, email=cd["email"],
                    defaults={"tenant": event.tenant, "name": cd["name"],
                              "rsvp_status": cd["rsvp_status"], "responded_at": timezone.now()})
                messages.success(request, "Thanks — your response has been recorded.")
            return redirect("crm:event_invite", token=token)
    return render(request, "crm/activities/event_invite.html", {
        "event": event, "attendees": event.attendees.all(), "form": form,
    })


def event_ics(request, token):
    """Public iCalendar (.ics) export for one event (1.5) — the realistic, offline-true version of
    "add to Google/Outlook/iCal". No login; the ``public_token`` is the bearer credential. Times
    are emitted in UTC (``...Z``) so any calendar app imports them unambiguously."""
    event = get_object_or_404(CalendarEvent, public_token=token)

    def _ics_dt(dt):
        return dt.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ") if dt else ""

    def _esc(text):  # RFC 5545 TEXT escaping (strip bare CR first — no meaning in a TEXT value)
        return (str(text or "").replace("\r", "").replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))

    def _fold(line):  # RFC 5545 §3.1: fold content lines >75 octets (continuation = leading space)
        if len(line) <= 74:
            return line
        out = [line[:74]]
        for i in range(74, len(line), 73):
            out.append(line[i:i + 73])
        return "\r\n ".join(out)

    end = event.end or event.start
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NavERP//CRM 1.5//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT",
        f"UID:{event.number}-{event.public_token}@naverp",
        f"DTSTAMP:{_ics_dt(timezone.now())}",
        f"DTSTART:{_ics_dt(event.start)}",
        f"DTEND:{_ics_dt(end)}",
        f"SUMMARY:{_esc(event.title)}",
        f"LOCATION:{_esc(event.location)}",
        f"DESCRIPTION:{_esc(event.description)}",
        f"STATUS:{'CANCELLED' if event.status == 'cancelled' else 'CONFIRMED'}",
        "END:VEVENT", "END:VCALENDAR",
    ]
    resp = HttpResponse("\r\n".join(_fold(ln) for ln in lines) + "\r\n",
                        content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{event.number}.ics"'
    return resp
