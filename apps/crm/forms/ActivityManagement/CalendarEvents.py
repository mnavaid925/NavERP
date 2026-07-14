"""CRM 1.5 Activity & Communication Management — CalendarEvents forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    CalendarEvent,
    EventAttendee,
)


# ===== 1.5 Activity & Communication Management (recreated) ====================
class CalendarEventForm(TenantModelForm):
    class Meta:
        model = CalendarEvent
        # public_token + number are system-set (L20/L22) → excluded.
        fields = ["title", "event_type", "start", "end", "all_day", "location", "video_url",
                  "status", "sync_source", "reminder_minutes", "owner", "party",
                  "related_opportunity", "related_case", "description"]


class EventAttendeeForm(TenantModelForm):
    class Meta:
        model = EventAttendee
        # tenant + event are set by the view; responded_at is system-set on RSVP.
        fields = ["party", "name", "email", "rsvp_status", "is_organizer"]


class PublicRsvpForm(forms.Form):
    """Public meeting-invite RSVP (no tenant binding — written directly in the view). Choices
    omit ``no_response`` (the default) since the form is an affirmative RSVP action."""

    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-input"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-input"}))
    rsvp_status = forms.ChoiceField(
        label="Your response",
        choices=[("accepted", "Accept"), ("declined", "Decline"), ("tentative", "Maybe")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
