"""CRM 1.11 Customer Success & Retention — Surveys models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class Survey(TenantNumbered):
    """An NPS/CSAT/CES survey + response (1.11). ``classification`` is auto-set for NPS."""

    NUMBER_PREFIX = "NPS"

    TYPE_CHOICES = [("nps", "NPS"), ("csat", "CSAT"), ("ces", "CES")]
    TRIGGER_CHOICES = [
        ("manual", "Manual"),
        ("post_close", "Post Close Won"),
        ("post_ticket", "Post Ticket Close"),
        ("scheduled", "Scheduled"),
    ]
    CLASSIFICATION_CHOICES = [
        # NPS
        ("promoter", "Promoter"),
        ("passive", "Passive"),
        ("detractor", "Detractor"),
        # CSAT
        ("satisfied", "Satisfied"),
        ("neutral", "Neutral"),
        ("dissatisfied", "Dissatisfied"),
        # CES (effort) — "neutral" is shared with CSAT
        ("easy", "Low Effort"),
        ("hard", "High Effort"),
    ]

    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_surveys")
    contact = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_survey_contacts")
    survey_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="nps")
    trigger = models.CharField(max_length=12, choices=TRIGGER_CHOICES, default="manual")
    related_case = models.ForeignKey("crm.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_surveys")
    score = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(10)])
    feedback_text = models.TextField(blank=True)
    classification = models.CharField(max_length=12, choices=CLASSIFICATION_CHOICES, blank=True)  # auto-set
    token = models.CharField(max_length=64, unique=True, null=True, blank=True)  # public respond link
    sent_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "survey_type"], name="crm_nps_tnt_type_idx"),
            models.Index(fields=["tenant", "account"], name="crm_nps_tnt_account_idx"),
            models.Index(fields=["tenant", "sent_at"], name="crm_nps_tnt_sent_idx"),
        ]

    def save(self, *args, **kwargs):
        # Public respond-link token (random, URL-safe) generated once.
        if not self.token:
            self.token = secrets.token_urlsafe(32)  # 256-bit — match the project public-token standard
        # Auto-classify by type against each type's own scale (1.11 recreate):
        #   NPS 0–10:  9–10 promoter / 7–8 passive / ≤6 detractor
        #   CSAT 1–5:  ≥4 satisfied / 3 neutral / ≤2 dissatisfied
        #   CES 1–7 (effort): ≤2 easy / 3–5 neutral / ≥6 hard
        if self.score is None:
            self.classification = ""
        elif self.survey_type == "nps":
            self.classification = ("promoter" if self.score >= 9
                                   else "passive" if self.score >= 7 else "detractor")
        elif self.survey_type == "csat":
            self.classification = ("satisfied" if self.score >= 4
                                   else "neutral" if self.score == 3 else "dissatisfied")
        elif self.survey_type == "ces":
            self.classification = ("easy" if self.score <= 2
                                   else "neutral" if self.score <= 5 else "hard")
        else:
            self.classification = ""
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.get_survey_type_display()}"
