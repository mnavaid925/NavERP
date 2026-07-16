"""HRM 3.24 Training Administration — Trainingnomination models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.JobRequisition.PRIORITY_CHOICESs import PRIORITY_CHOICES
from apps.hrm.models.JobRequisition.PRIORITY_CHOICESs import PRIORITY_CHOICES


# ---------------------------------------------------------------------------
# 3.24 Training Administration — the operational/transactional layer over the
# 3.22 ILT catalog (``TrainingSession``) and 3.23 LMS (``LearningProgress``):
# who's nominated (``TrainingNomination``), who showed up (``TrainingAttendance``),
# what they thought (``TrainingFeedback``), and what they earned
# (``TrainingCertificate``). Ordinary tenant-scoped CRUD; nomination approve/reject
# mirror the LeaveRequest workflow shape, feedback anonymity clones 3.20 Feedback.
#
# Reuses: ``hrm.TrainingSession``/``TrainingCourse`` (3.22), ``hrm.LearningProgress``
# (3.23), ``hrm.EmployeeProfile`` (nominee/attendee/holder), the reporting line
# (``EmployeeProfile.employment.manager``) for approvals, ``hrm.CostCenterProfile``/
# ``core.OrgUnit`` (3.2) for the budget view. **Training Budget is a COMPUTED view**
# (aggregate over ``TrainingSession`` costs vs ``CostCenterProfile.budget_annual``) —
# NO model. This is the FINAL sub-module of the 3.22/3.23/3.24 training cluster.
#
# Deferred: N-step approval chains, rule-based auto-enrollment, QR self-check-in,
# multi-level Kirkpatrick (L2-L4), a branded certificate-PDF renderer, a public
# verify-by-code page, expiry-reminder emails, a ring-fenced TrainingBudget model.
# ---------------------------------------------------------------------------
class TrainingNomination(TenantNumbered):
    """An employee nominated for a ``TrainingSession`` (3.24 Nomination) with a single-approver
    workflow. Born ``pending`` (no draft); a tenant admin OR the nominee's manager decides. A
    ``waitlisted`` state queues a nominee when the session is full (fulfilling
    ``TrainingSession.waitlist_enabled``). Mirrors the ``LeaveRequest`` approve/reject shape."""

    NUMBER_PREFIX = "NOM"

    NOMINATION_TYPE_CHOICES = [
        ("self", "Self-Nominated"),
        ("manager", "Manager-Nominated"),
        ("hr", "HR-Assigned"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("waitlisted", "Waitlisted"),
        ("cancelled", "Cancelled"),
        ("withdrawn", "Withdrawn"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
    ]

    session = models.ForeignKey("hrm.TrainingSession", on_delete=models.PROTECT, related_name="nominations")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
                                 related_name="training_nominations", help_text="The nominee.")
    nominated_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="nominations_made", help_text="Who nominated (null = self).")
    nomination_type = models.CharField(max_length=10, choices=NOMINATION_TYPE_CHOICES, default="self")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending",
                              help_text="Workflow — set by the approve/reject/waitlist/cancel/withdraw actions.")
    approver = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="nominations_approved", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    rejected_reason = models.TextField(blank=True)
    cancelled_reason = models.TextField(blank=True)
    justification = models.TextField(blank=True, help_text="Why this nomination (free text).")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="normal")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "session", "employee")
        indexes = [
            models.Index(fields=["tenant", "session"], name="hrm_nom_tenant_session_idx"),
            models.Index(fields=["tenant", "employee"], name="hrm_nom_tenant_emp_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_nom_tenant_status_idx"),
        ]

    def clean(self):
        if self.session_id and self.session.status in ("completed", "cancelled"):
            raise ValidationError({"session": "Cannot nominate for a completed or cancelled session."})

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.session}" if self.number else str(self.employee)
