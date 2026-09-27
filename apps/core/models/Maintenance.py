"""core — 0.20 bullet 3a: maintenance windows.

A `MaintenanceWindow` is a declared period during which something is expected to be off limits or
noisy: a deploy, a migration, a certificate rotation. It is the PagerDuty window, the Datadog
downtime and the Grafana mute timing in one tenant-scoped row, and it carries the three things
those products agree on — a **start AND an end** (a one-ended window is not a window, which is the
same rule `core.Incident` already enforces on its own notice), a **recurrence**, and an **outward
notice that is linked rather than copied**.

**Why this FKs `core.Incident` instead of copying it (L29/L36).** 0.17's `Incident` already owns
the `scheduled_maintenance` notice, and its own `clean()` error message says so in as many words:
"A maintenance notice must say when the window opens. This is the notice, not the change record
(**0.20 owns that**)." So `incident` is a SET_NULL FK with `related_name="+"` — no reverse
accessor, because the notice owns its own page and 0.20 does not rewrite it. The change record
itself lives in `apps/core/models/Change.py`.

**What a window does NOT do.** `suppresses_jobs` and `blocks_admin_writes` are the two
consequences an operator must be able to *state*, and **nothing in this repository enforces
either**. No alert rule consults `suppressed_alert_rules`, no notification rule consults
`suppressed_notification_rules`, and no permission check consults `blocks_admin_writes`. 0.17
stays the alert surface and 0.12 stays the delivery owner. Every page that shows this model says
so in words rather than implying the silence is in force.

**Past windows are history and are kept.** Only a window that has not started yet may be deleted —
the guard lives in the view (so a hand-made POST cannot reach it) *and* in each template's Actions
column, because a window somebody ran and might need for an incident review is evidence.
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.core.models._base import *  # noqa: F401,F403
from apps.core.utils import next_number


#: How often the window repeats. `once` is the only shape a single row can express on its own —
#: a recurring window is a policy somebody reads, not a series this repository generates.
RECURRENCE_CHOICES = [
    ("once", "Once"),
    ("daily", "Daily"),
    ("weekly", "Weekly"),
    ("monthly", "Monthly"),
]

#: The window lifecycle. `draft` and `scheduled` have not started; `active` is the window as it
#: runs; `ended_early` is PagerDuty's "End Now"; `completed` ran its course; `cancelled` never
#: will. Nothing here transitions on its own — `ended_early` is written by the POST-only
#: `maintenance_window_end_now` verb and nothing else.
WINDOW_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("scheduled", "Scheduled"),
    ("active", "Active"),
    ("ended_early", "Ended early"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]

#: The statuses that mean the window has not started yet. Only one of these may be deleted.
FUTURE_STATUSES = ("draft", "scheduled")

class MaintenanceWindow(models.Model):
    """A declared quiet period with an explicit start, an explicit end, and a stated scope."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="maintenance_windows", db_index=True)
    #: MNTW-##### — literal mint; see `core.settings_engine.LITERAL_PREFIX_MODELS`.
    number = models.CharField(max_length=20, editable=False)
    title = models.CharField(max_length=200)
    #: PagerDuty windows carry a purpose because a window nobody can name the reason for is one
    #: nobody can audit afterwards.
    purpose = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    recurrence = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, default="once")
    #: The zone the times above are expressed in. Recorded for the reader; TIME_ZONE is still
    #: whatever Django is configured with, so this is documentation, not conversion.
    timezone_label = models.CharField(max_length=60, blank=True)
    status = models.CharField(max_length=20, choices=WINDOW_STATUS_CHOICES, default="draft")
    #: PagerDuty "End Now". Written only by the POST-only end_now verb.
    ended_at = models.DateTimeField(null=True, blank=True)
    affected_services = models.ManyToManyField("core.ServiceComponent", blank=True,
                                                related_name="maintenance_windows")
    #: RECORDED SCOPE, NOT ENFORCED SCOPE. No alert engine reads this set — see the module
    #: docstring. 0.17's AlertEvent remains the thing an operator actually sees.
    suppressed_alert_rules = models.ManyToManyField("core.AlertRule", blank=True,
                                                    related_name="maintenance_windows")
    suppressed_notification_rules = models.ManyToManyField("core.NotificationRule", blank=True,
                                                           related_name="maintenance_windows")
    #: 0.17's outward notice, LINKED not copied. `related_name="+"` because the notice owns its own
    #: page and 0.20 does not add a reverse accessor to another sub-module's model.
    incident = models.ForeignKey("core.Incident", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="+")
    environment = models.ForeignKey("core.EnvironmentInstance", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="maintenance_windows")
    change_request = models.ForeignKey("core.ChangeRequest", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="maintenance_windows")
    #: The two consequences an operator must be able to state. RECORDED, NOT ENFORCED — nothing
    #: consults either flag.
    suppresses_jobs = models.BooleanField(
        default=False, help_text="Recorded intent. No scheduler exists to suppress anything.")
    blocks_admin_writes = models.BooleanField(
        default=False, help_text="Recorded intent. No permission check consults this flag.")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    STATUS_CHOICES = WINDOW_STATUS_CHOICES
    RECURRENCE_CHOICES = RECURRENCE_CHOICES

    class Meta:
        ordering = ["-starts_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="mntwin_tenant_status_idx"),
            models.Index(fields=["tenant", "starts_at"], name="mntwin_tenant_starts_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        for _ in range(5):
            self.number = next_number(MaintenanceWindow, self.tenant, "MNTW")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        # Both ends, always. A window with an open end is a notice, and 0.17's Incident already
        # owns notices — this is the same rule, enforced on the other object.
        if not self.starts_at:
            raise ValidationError({"starts_at": "A maintenance window must say when it opens."})
        if not self.ends_at:
            raise ValidationError({"ends_at": "A maintenance window must say when it closes."})
        if self.starts_at and self.ends_at and self.ends_at < self.starts_at:
            raise ValidationError({"ends_at": "A window cannot close before it opens."})
        # Ended-early is an evidence stamp (L22): its only writer is the end_now verb, and a row
        # claiming it without the stamp is a claim with nothing behind it.
        if self.status == "ended_early" and not self.ended_at:
            raise ValidationError({"ended_at": "An ended-early window must record when it was ended."})
        if self.ended_at and self.ends_at and self.ended_at > self.ends_at:
            raise ValidationError({"ended_at": "A window cannot be ended after it was due to close."})

    @property
    def is_future(self):
        """True while the window has not started.

        This is the deletability rule: a window that has already run is history somebody may need
        for an incident review, so it is kept. A window that never ran is a draft.
        """
        return bool(self.starts_at) and self.starts_at > timezone.now()

    @property
    def is_current(self):
        """True exactly while now falls inside the declared window."""
        now = timezone.now()
        return bool(self.starts_at) and bool(self.ends_at) and self.starts_at <= now < self.ends_at

    @property
    def duration_human(self):
        """The window's length, or an em dash when either end is missing — never `0`."""
        if not self.starts_at or not self.ends_at:
            return "—"
        seconds = int((self.ends_at - self.starts_at).total_seconds())
        if seconds <= 0:
            return "0m"
        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60
        if hours and minutes:
            return "%dh %dm" % (hours, minutes)
        if hours:
            return "%dh" % hours
        return "%dm" % minutes

    def __str__(self):
        return "%s %s" % (self.number, self.title)


