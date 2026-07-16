"""HRM 3.8 Offer Management — Offer models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.JobRequisition.APPROVAL_STEP_STATUS_CHOICESs import APPROVAL_STEP_STATUS_CHOICES
from apps.hrm.models.JobRequisition.APPROVER_ROLE_CHOICESs import APPROVER_ROLE_CHOICES
from apps.hrm.models.OfferManagement.SIGNATURE_STATUS_CHOICESs import SIGNATURE_STATUS_CHOICES
from apps.hrm.models.JobRequisition.APPROVAL_STEP_STATUS_CHOICESs import APPROVAL_STEP_STATUS_CHOICES
from apps.hrm.models.JobRequisition.APPROVER_ROLE_CHOICESs import APPROVER_ROLE_CHOICES
from apps.hrm.models.OfferManagement.SIGNATURE_STATUS_CHOICESs import SIGNATURE_STATUS_CHOICES


# ---------------------------------------------------------------------------
# 3.8 Offer Management — offer-letter generation, multi-step approval, offer
# tracking, background verification, and pre-boarding document collection.
#
# Offers hang off the 3.6 ``JobApplication`` spine (candidate + requisition are
# reached through it — no duplicate FKs). The offer-approval chain REUSES the
# 3.5 ``RequisitionApproval`` shape verbatim (``APPROVER_ROLE_CHOICES`` /
# ``APPROVAL_STEP_STATUS_CHOICES`` — not redefined), and the offer/pre-boarding
# emails REUSE the 3.6 ``CandidateEmailTemplate`` + ``CandidateCommunication``
# log via ``_send_candidate_email`` (the ``"offer"`` template-type already
# exists). Offer acceptance drives ``JobApplication.stage`` → ``"hired"`` +
# ``hired_on`` (existing fields, no schema change). Live e-signature and live
# background-check vendor APIs are DEFERRED — ``signed_document`` /
# ``signature_status`` / ``BackgroundVerification.status``/``result`` are plain
# fields a manual action (or a future webhook) writes to; the printable offer
# letter is a server-rendered page, the invite/reminder a manual audited action.
# ---------------------------------------------------------------------------
OFFER_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("pending_approval", "Pending Approval"),
    ("approved", "Approved"),
    ("extended", "Extended to Candidate"),
    ("accepted", "Accepted"),
    ("declined", "Declined"),
    ("rescinded", "Rescinded"),
    ("expired", "Expired"),
]


# Closed statuses an offer can't be transitioned out of (mirrors
# INTERVIEW_TERMINAL_STATUSES / APPLICATION_TERMINAL_STAGES). Also drives the
# ``is_overdue`` guard so a settled offer never shows as overdue.
OFFER_TERMINAL_STATUSES = ("accepted", "declined", "rescinded", "expired")


# Candidate-side decline reasons (mirrors JobApplication.REJECTION_REASON_CHOICES shape).
OFFER_DECLINE_REASON_CHOICES = [
    ("salary", "Salary / Compensation"),
    ("competing_offer", "Accepted a Competing Offer"),
    ("counteroffer", "Counteroffer from Current Employer"),
    ("role_fit", "Role / Responsibilities Fit"),
    ("culture_fit", "Culture / Team Fit"),
    ("timing", "Timing / Start Date"),
    ("other", "Other"),
]


class Offer(TenantNumbered):
    """The offer-management hub (3.8) — one row per offer extended for a ``JobApplication`` (FK, not a hard
    1:1, so a re-issued offer supersedes rather than multiplies — mirrors how ``Interview`` FKs the
    application). ``status`` is the workflow-owned state machine
    (draft→pending_approval→approved→extended→accepted/declined/rescinded/expired), ``editable=False`` and
    set only by the audited POST actions — never the form. The approval chain (``approvals``) gates
    extension: an offer can't be extended to the candidate until every step is approved. Acceptance drives
    ``application.stage`` → ``"hired"`` + ``hired_on`` (existing fields)."""

    NUMBER_PREFIX = "OFR"

    application = models.ForeignKey("hrm.JobApplication", on_delete=models.CASCADE, related_name="offers")
    offer_letter_template = models.ForeignKey("hrm.OfferLetterTemplate", on_delete=models.SET_NULL,
                                              null=True, blank=True, related_name="offers")

    # Compensation breakdown (Workday comp bands / SAP SuccessFactors Offer Detail conventions).
    base_salary = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD",
                                help_text="Defaults from the requisition's salary_currency at creation.")
    bonus_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    bonus_terms = models.TextField(blank=True)
    signing_bonus = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    equity_terms = models.TextField(blank=True,
        help_text="Grant description / vesting schedule — equity plans aren't a structured table yet.")
    relocation_assistance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    benefits_summary = models.TextField(blank=True)

    start_date = models.DateField(help_text="Proposed joining date.")
    expires_on = models.DateField(null=True, blank=True, help_text="Offer response deadline.")

    status = models.CharField(max_length=20, choices=OFFER_STATUS_CHOICES, default="draft", editable=False)

    # Candidate decline tracking (recruiter-editable annotations, mirrors JobApplication.rejection_*).
    decline_reason = models.CharField(max_length=30, choices=OFFER_DECLINE_REASON_CHOICES, blank=True)
    decline_notes = models.TextField(blank=True)

    # E-signature — fields now, live vendor wiring deferred.
    signed_document = models.FileField(upload_to="hrm/offers/signed/%Y/%m/", null=True, blank=True)
    signature_status = models.CharField(max_length=20, choices=SIGNATURE_STATUS_CHOICES, default="not_sent")

    # Workflow stamps — set only by the POST actions.
    extended_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="extended_offers", editable=False)
    extended_at = models.DateTimeField(null=True, blank=True, editable=False)
    accepted_at = models.DateTimeField(null=True, blank=True, editable=False)
    declined_at = models.DateTimeField(null=True, blank=True, editable=False)
    rescinded_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="created_offers", editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_ofr_tenant_status_idx"),
            models.Index(fields=["tenant", "application"], name="hrm_ofr_tenant_app_idx"),
            models.Index(fields=["tenant", "created_at"], name="hrm_ofr_tenant_created_idx"),
        ]

    def clean(self):
        super().clean()
        for field in ("base_salary", "bonus_amount", "signing_bonus", "relocation_assistance"):
            value = getattr(self, field)
            if value is not None and value < ZERO:
                raise ValidationError({field: "Amount cannot be negative."})

    @property
    def candidate(self):
        """The offeree, via the application. Views listing offers must
        ``select_related("application__candidate")`` to keep this O(1)."""
        return self.application.candidate

    @property
    def requisition(self):
        """The open position, via the application (select_related in list views)."""
        return self.application.requisition

    @property
    def is_closed(self):
        return self.status in OFFER_TERMINAL_STATUSES

    @property
    def is_overdue(self):
        """True when the response deadline has passed and the offer isn't settled — drives the red
        'Overdue' indicator (mirrors ``JobRequisition.is_overdue``)."""
        return (self.expires_on is not None
                and self.expires_on < date.today()
                and self.status not in OFFER_TERMINAL_STATUSES)

    @property
    def total_compensation(self):
        """Base + bonus + signing bonus (relocation is a one-off, excluded) — used by the conditional
        approval-chain threshold and shown on the offer summary."""
        return (self.base_salary or ZERO) + (self.bonus_amount or ZERO) + (self.signing_bonus or ZERO)

    @property
    def approval_progress(self):
        """``(approved_count, total_count)`` over the approval chain — feeds the detail-hub progress text.

        PERF: fires a SELECT unless ``approvals`` is prefetched (the detail view prefetches it)."""
        steps = self.approvals.all()
        total = len(steps)
        approved = sum(1 for s in steps if s.status == "approved")
        return approved, total

    @property
    def current_approval_step(self):
        """The lowest-ordered still-pending approval step, or ``None`` when the chain is fully decided.

        PERF: fires a SELECT per call — don't call in a list loop."""
        return self.approvals.filter(status="pending").order_by("step_order").first()

    def __str__(self):
        return f"{self.number} · {self.application.candidate.name}" if self.number else str(self.pk)


class OfferApproval(TenantOwned):
    """One sequential approval step on an ``Offer`` (3.8). Mirrors ``RequisitionApproval`` field-for-field
    — the collection is both the approval chain (current step = lowest ``step_order`` still ``pending``)
    and the immutable audit trail (rows are never edited via a form: the approve/reject POST actions stamp
    ``status``/``decided_at``/``decided_by``). Reuses ``APPROVER_ROLE_CHOICES`` /
    ``APPROVAL_STEP_STATUS_CHOICES`` verbatim."""

    offer = models.ForeignKey("hrm.Offer", on_delete=models.CASCADE, related_name="approvals")
    step_order = models.PositiveSmallIntegerField(default=1)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_offer_approvals")
    approver_role = models.CharField(max_length=20, choices=APPROVER_ROLE_CHOICES, default="hr")
    status = models.CharField(max_length=20, choices=APPROVAL_STEP_STATUS_CHOICES,
                              default="pending", editable=False)
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="hrm_offer_approval_decisions", editable=False)
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["step_order"]
        unique_together = ("offer", "step_order")
        indexes = [
            models.Index(fields=["offer", "status"], name="hrm_oa_offer_status_idx"),
            models.Index(fields=["approver", "status"], name="hrm_oa_approver_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.step_order is not None and self.step_order < 1:
            raise ValidationError({"step_order": "Step order must be at least 1."})

    def __str__(self):
        return (f"Step {self.step_order} — {self.get_approver_role_display()} "
                f"— {self.get_status_display()}")
