"""Projects 7.7 — Requirement [REQ-]: one elicited, documented and traceable requirement.

This row is where three of the five 7.7 bullets meet: **1 Requirements Elicitation** (the
``elicitation_method`` and the party/user it came from), **2 Documentation & Traceability** (the
``acceptance_criteria``, the ``version`` stamp, the ``parent`` hierarchy and the ``wbs_node`` link
into 7.2's WBS) and the front half of **5 Scope Verification** (the verification method and the
``verified_by``/``verified_at`` evidence pair).

**The lifecycle is verb-driven, never form-driven.** ``status``, ``rejection_reason``,
``approved_by``/``approved_at`` and ``verified_by``/``verified_at`` are all OFF the model form: a
requirement moves draft → submitted → approved → implemented → verified through the five audited
POST-only verbs, so the approval evidence cannot be minted by a plain edit. That is the module's
evidence model (7.1's charter gate, 7.5's realize/close/reopen) applied to requirements.

**Traceability is a link, not a table.** ``wbs_node`` points at the 7.2 ``ProjectTask`` that
delivers the requirement and ``parent`` points at the requirement it derives from — both FK'd **by
string** (L36), so 7.7 declares no task table and no second requirement table. The traceability
*matrix* is computed from these two columns (the ``scope_matrix`` page), never stored: a matrix
that can go stale is a matrix nobody trusts.

**Boundaries:** the scope statements/assumptions/constraints registry is 7.7's ``ScopeItem``; the
change proposals are 7.7's ``ScopeChangeRequest``; the inspection/acceptance record is 7.7's
``ScopeVerification``. This row owns the requirement text and its approval evidence, nothing else.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class Requirement(TenantNumbered):
    NUMBER_PREFIX = "REQ"

    REQUIREMENT_TYPE_CHOICES = [
        ("functional", "Functional"),
        ("non_functional", "Non-Functional"),
        ("business", "Business"),
        ("technical", "Technical"),
        ("regulatory", "Regulatory"),
        ("interface", "Interface"),
    ]
    #: Bullet 1's elicitation techniques — how the requirement was actually captured. A documented
    #: closed list rather than free text so the register can be sliced by technique.
    ELICITATION_METHOD_CHOICES = [
        ("interview", "Interview"),
        ("workshop", "Workshop"),
        ("survey", "Survey"),
        ("user_story", "User Story Mapping"),
        ("observation", "Observation"),
        ("document_analysis", "Document Analysis"),
        ("prototype", "Prototype"),
        ("brainstorm", "Brainstorming"),
    ]
    #: MoSCoW. The prioritisation framework bullet 2's documentation step records.
    PRIORITY_CHOICES = [
        ("must", "Must Have"),
        ("should", "Should Have"),
        ("could", "Could Have"),
        ("wont", "Won't Have"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("implemented", "Implemented"),
        ("verified", "Verified"),
        ("deferred", "Deferred"),
    ]
    #: The four classic verification techniques (IEEE 1012's inspection/analysis/demonstration/test).
    VERIFICATION_METHOD_CHOICES = [
        ("inspection", "Inspection"),
        ("analysis", "Analysis"),
        ("demonstration", "Demonstration"),
        ("test", "Test"),
    ]

    #: status -> the theme.css badge class the templates render. A documented constant map (the
    #: 7.5 ``PROBABILITY_PCT`` idiom) so the badge colour is decided in one place.
    STATUS_BANDS = {
        "draft": "muted",
        "submitted": "amber",
        "approved": "info",
        "rejected": "red",
        "implemented": "green",
        "verified": "green",
        "deferred": "slate",
    }

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="requirements")
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children",
        help_text="The requirement this one derives from (an epic, a story's parent).")
    #: The traceability link: the 7.2 work package that delivers this requirement.
    wbs_node = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="requirements",
        help_text="The WBS work package that delivers this requirement — the traceability link.")
    title = models.CharField(max_length=255)
    description = models.TextField()
    requirement_type = models.CharField(
        max_length=16, choices=REQUIREMENT_TYPE_CHOICES, default="functional")
    elicitation_method = models.CharField(
        max_length=20, choices=ELICITATION_METHOD_CHOICES, default="interview")
    #: How the session actually went — who said what, what was out of reach.
    elicitation_note = models.TextField(blank=True)
    #: The stakeholder organisation the requirement came from. A ``core.Party`` — never a second
    #: stakeholder table (7.1's ProjectStakeholder already owns the RACI register).
    source_party = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="requirements")
    priority = models.CharField(max_length=12, choices=PRIORITY_CHOICES, default="must")
    #: Bullet 2's documentation core: the testable "done" statement the verification checks against.
    acceptance_criteria = models.TextField(blank=True)
    #: Bullet 2's version control: the documented revision of THIS requirement statement. A change
    #: to the statement is a new version, and the change proposal that caused it is 7.7's
    #: ``ScopeChangeRequest`` — this column is the marker, not the audit trail.
    version = models.CharField(max_length=16, default="1.0")
    verification_method = models.CharField(
        max_length=16, choices=VERIFICATION_METHOD_CHOICES, default="test")
    #: Verb-driven (submit/approve/reject/implement/verify) — OFF the form.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_requirements")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="requested_requirements")
    rejection_reason = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="approved_requirements")
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="verified_requirements")
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    verification_note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="req_created")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="req_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="req_tnt_status_idx"),
            models.Index(fields=["tenant", "requirement_type"], name="req_tnt_type_idx"),
            models.Index(fields=["tenant", "priority"], name="req_tnt_priority_idx"),
            models.Index(fields=["tenant", "-created_at"], name="req_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    # -- derived predicates (never stored) -------------------------------------------------------

    @property
    def is_approved(self):
        """Approved OR further along the lifecycle — a verified requirement is still approved."""
        return self.status in ("approved", "implemented", "verified")

    @property
    def is_verified(self):
        return self.status == "verified"

    @property
    def is_traced(self):
        """A requirement is traceable the moment it names the work package that delivers it."""
        return self.wbs_node_id is not None

    @property
    def is_open(self):
        return self.status in ("draft", "submitted", "approved", "implemented")

    @property
    def is_locked(self):
        """A verified requirement is frozen evidence — edit/delete refuse it."""
        return self.status == "verified"

    @property
    def badge_class(self):
        return self.STATUS_BANDS.get(self.status, "slate")

    def clean(self):
        super().clean()
        if self.wbs_node_id and self.project_id \
                and self.wbs_node.project_id != self.project_id:
            raise ValidationError(
                {"wbs_node": "The WBS node must belong to the same project as the requirement."})
        if self.parent_id and self.project_id and self.parent.project_id != self.project_id:
            raise ValidationError(
                {"parent": "The parent requirement must belong to the same project as the "
                           "requirement."})
