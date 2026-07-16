"""HRM 3.20 Continuous Feedback — Feedback models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class Feedback(TenantNumbered):
    """A real-time feedback row (3.20) — any employee to any employee, any time. One table serves
    kudos/appreciation/constructive feedback AND the "request feedback" pull workflow (via
    ``status`` + the ``requested_from`` self-FK, so no second table). ``is_anonymous`` masks the
    giver on read for non-admins — a direct clone of the 3.19 ``PerformanceReview.reviewer`` +
    ``is_anonymous`` precedent (the FK is kept; only the RENDER is masked)."""

    NUMBER_PREFIX = "FBK"

    FEEDBACK_TYPE_CHOICES = [
        ("kudos", "Kudos"),
        ("appreciation", "Appreciation"),
        ("constructive", "Constructive"),
        ("request", "Feedback Request"),
    ]
    VISIBILITY_CHOICES = [
        ("private", "Private"),
        ("team", "Team"),
        ("public", "Public"),
    ]
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("given", "Given"),
        ("acknowledged", "Acknowledged"),
        ("responded", "Responded"),
    ]

    giver = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, null=True, blank=True,
                              related_name="feedback_given",
                              help_text="Who gave the feedback (masked on read when is_anonymous).")
    receiver = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
                                 related_name="feedback_received")
    feedback_type = models.CharField(max_length=15, choices=FEEDBACK_TYPE_CHOICES, default="kudos")
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="private",
                                  help_text="private = giver/receiver/admin; team = receiver's org unit; public = the feed.")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="given",
                              help_text="A plain kudos is born 'given'; a pull request is born 'requested' and "
                                        "becomes 'responded' once answered.")
    message = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False,
                                       help_text="Masks the giver on the receiver-facing view (admins still see it).")
    badge = models.ForeignKey("hrm.KudosBadge", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="feedback_items")
    related_objective = models.ForeignKey("hrm.Objective", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="feedback_items",
                                          help_text="Optional 3.18 goal this feedback is about.")
    related_review = models.ForeignKey("hrm.PerformanceReview", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="feedback_items",
                                       help_text="Optional 3.19 review this feedback is about.")
    requested_from = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="requested_responses",
                                       help_text="On a response row, points back at the 'requested' ask it answers.")
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "receiver"], name="hrm_fbk_tenant_recv_idx"),
            models.Index(fields=["tenant", "giver"], name="hrm_fbk_tenant_giver_idx"),
            models.Index(fields=["tenant", "feedback_type"], name="hrm_fbk_tenant_type_idx"),
            models.Index(fields=["tenant", "visibility"], name="hrm_fbk_tenant_vis_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_fbk_tenant_status_idx"),
        ]

    def clean(self):
        if self.giver_id and self.receiver_id and self.giver_id == self.receiver_id:
            raise ValidationError({"receiver": "You cannot give feedback to yourself."})

    @property
    def giver_anonymized(self):
        """True when the giver's name should be hidden from non-admin viewers. Kept as a property so
        any future per-type masking rule has one place to change (mirrors
        ``PerformanceReview.reviewer_anonymized``)."""
        return self.is_anonymous

    def __str__(self):
        who = self.receiver.party.name if self.receiver_id else "?"
        return f"{self.number} · {self.get_feedback_type_display()} → {who}"
