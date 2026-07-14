"""CRM 1.5 Activity & Communication Management — CommunicationLogs models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class CommunicationLog(TenantNumbered):
    """A logged interaction — call/email/sms/note/meeting (1.5 Email & Call Integration). The
    unified activity-history record: call logging (duration/outcome) + email sync (BCC dropbox).
    Live send/receive engines are deferred; ``logged_via`` records provenance."""

    NUMBER_PREFIX = "COM"

    CHANNEL_CHOICES = [
        ("call", "Call"),
        ("email", "Email"),
        ("sms", "SMS"),
        ("note", "Note"),
        ("meeting", "Meeting"),
    ]
    DIRECTION_CHOICES = [("inbound", "Inbound"), ("outbound", "Outbound")]
    OUTCOME_CHOICES = [
        ("connected", "Connected"),
        ("voicemail", "Voicemail"),
        ("no_answer", "No Answer"),
        ("busy", "Busy"),
        ("wrong_number", "Wrong Number"),
    ]
    LOGGED_VIA_CHOICES = [
        ("manual", "Manual"),
        ("bcc_dropbox", "BCC Dropbox"),
        ("voip", "VoIP Auto-log"),
        ("sync", "Calendar Sync"),
    ]

    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default="call")
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_logs")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_logs")
    related_opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_logs")
    related_case = models.ForeignKey("crm.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_logs")
    occurred_at = models.DateTimeField(default=timezone.now)  # the actual interaction time
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)  # calls only
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, blank=True)  # calls only
    logged_via = models.CharField(max_length=20, choices=LOGGED_VIA_CHOICES, default="manual")
    email_message_id = models.CharField(max_length=255, blank=True, db_index=True)  # dedup synced email

    class Meta:
        ordering = ["-occurred_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "channel"], name="crm_commlog_tnt_channel_idx"),
            models.Index(fields=["tenant", "occurred_at"], name="crm_commlog_tnt_occurred_idx"),
        ]

    @property
    def duration_display(self):
        """``mm:ss`` for a call duration, else ``""``."""
        if self.duration_seconds is not None:
            return "%d:%02d" % divmod(self.duration_seconds, 60)
        return ""

    @property
    def is_call(self):
        return self.channel == "call"

    def __str__(self):
        return f"{self.number} · {self.get_channel_display()} ({self.occurred_at:%Y-%m-%d})"
