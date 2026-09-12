"""Projects 7.6 — QualityDefect [QDF-]: one punch-list item on one deliverable.

Bullet **3's defect tracking** and bullet **5's punch list** share this table: a punch list IS
the conditional-acceptance view of the defect log — the open items that stand between a recorded
``conditional`` result and a clean sign-off.

**It is NOT a second issue log and NOT a second NCR.** A defect carries the quality-native fields
the issue register does not (the violated criterion via ``quality_plan``, the ``defect_category``,
the ``disposition``); a 7.5 ``ProjectIssue`` carries the RAID treatment (severity bands, escalation,
resolution). The two are linked, never duplicated: ``project_issue`` is a nullable FK written only
by the POST-only ``qdf_raise_issue`` verb — the exact bridge idiom 7.5's ``rsk_realize`` shipped
for risk→issue (Ruling 2). And the enterprise nonconformance register is scm 4.9's
(``NonConformance[NCR-]``, goods/production-scoped with a stock effect): a genuine enterprise NCR
is not this row (Ruling 1).

**Everything derived is a Python property, never a column.** ``is_overdue``, ``age_days``,
``is_open`` and ``is_locked`` are pure functions of the status and the dates (the 7.1 ROI / 7.4
EVM ruling). ``age_days`` reads ``timezone.localdate()`` — the same clock the rest of 7.6 uses
(L16).

**Verb-driven lifecycle.** ``status``, ``root_cause``, ``resolution_note``, ``resolved_by``,
``resolved_at`` and ``created_by`` are all OFF the model form: ``qdf_resolve`` and ``qdf_close``
are the only writers of those stamps, so the evidence trail keeps its timestamps. ``is_locked``
(``resolved``/``closed``/``cancelled``) is what makes edit/delete refuse a finished row.

**No money column (Ruling 7).** The cost of a rework is a 7.4 ``ProjectExpense`` — a soft
cross-reference in the notes, never a column here, so this module declares no ``DecimalField``.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class QualityDefect(TenantNumbered):
    NUMBER_PREFIX = "QDF"

    #: Deliverable-quality categories — deliberately distinct from scm 4.9's goods categories
    #: (Ruling 1): a punch list triages what is wrong with an OUTPUT, not with a batch.
    DEFECT_CATEGORY_CHOICES = [
        ("functional", "Functional"),
        ("performance", "Performance"),
        ("documentation", "Documentation"),
        ("compliance", "Compliance"),
        ("dimensional", "Dimensional"),
        ("workmanship", "Workmanship"),
        ("usability", "Usability"),
        ("other", "Other"),
    ]
    #: The scm 4.9 ``NonConformance.SEVERITY_CHOICES`` vocabulary, reused verbatim — one severity
    #: language across the two quality registers a workspace actually reads side by side.
    #: ``max_length=12`` fits ``observation`` — the same width scm 4.9's ``NonConformance
    #: .severity`` uses for the same vocabulary.
    SEVERITY_CHOICES = [
        ("critical", "Critical"),
        ("major", "Major"),
        ("minor", "Minor"),
        ("observation", "Observation"),
    ]
    #: The punch-list disposition — what happens to the deliverable because of this defect.
    DISPOSITION_CHOICES = [
        ("open", "Open"),
        ("rework", "Rework"),
        ("repair", "Repair"),
        ("resubmit", "Resubmit"),
        ("accept_as_is", "Accept As Is"),
        ("reject", "Reject"),
        ("deferred", "Deferred"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="quality_defects")
    #: The deliverable the defect is on. Same-project ``clean()`` guard — the
    #: ``ProjectMilestone.anchor_task`` pattern.
    wbs_node = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="quality_defects")
    #: The entity-1 plan whose acceptance criterion this defect violates. Optional, but
    #: same-project guarded — this FK is what makes the criterion → inspection → defect chain
    #: traceable without a matrix table.
    quality_plan = models.ForeignKey(
        "projects.QualityPlan", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="defects")
    #: The entity-3 inspection that found it — SET_NULL so deleting an inspection never deletes
    #: the punch-list evidence.
    inspection = models.ForeignKey(
        "projects.DeliverableInspection", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="defects")
    #: The 7.5 issue this defect became, when it needs RAID treatment. Written only by
    #: ``qdf_raise_issue`` — the bridge, never a second issue log (Ruling 2).
    project_issue = models.ForeignKey(
        "projects.ProjectIssue", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="quality_defects")
    title = models.CharField(max_length=255)
    description = models.TextField()
    defect_category = models.CharField(
        max_length=16, choices=DEFECT_CATEGORY_CHOICES, default="other")
    severity = models.CharField(max_length=12, choices=SEVERITY_CHOICES, default="minor")
    disposition = models.CharField(max_length=16, choices=DISPOSITION_CHOICES, default="open")
    #: Verb-driven (resolve / close) — OFF the form, so the evidence trail keeps its stamps.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="open")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_quality_defects")
    identified_date = models.DateField(default=timezone.localdate)
    #: When this defect must be dispositioned by — drives ``is_overdue`` while it is open.
    due_date = models.DateField(null=True, blank=True)
    #: The resolution capture — written by ``qdf_resolve``, never by a generic edit.
    root_cause = models.TextField(blank=True)
    resolution_note = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="resolved_quality_defects")
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: The closed-row takeaway. A field, NOT a store — the lessons repository is 7.10's (Ruling 6);
    #: the improvement page reads it back as a lens, the same idiom 7.5's monitoring page uses.
    lessons_learned = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="qdf_created")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="qdf_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="qdf_tnt_status_idx"),
            models.Index(fields=["tenant", "severity"], name="qdf_tnt_severity_idx"),
            models.Index(fields=["tenant", "disposition"], name="qdf_tnt_disp_idx"),
            models.Index(fields=["tenant", "-created_at"], name="qdf_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    # -- derived figures (never stored) ---------------------------------------------------------

    @property
    def is_overdue(self):
        """Due date passed while the defect is still open. Uses ``timezone.localdate()`` (L16)."""
        if not self.due_date:
            return False
        return self.due_date < timezone.localdate() and self.is_open

    @property
    def age_days(self):
        """Days since the defect was identified (0 when ``identified_date`` is unset)."""
        if not self.identified_date:
            return 0
        return (timezone.localdate() - self.identified_date).days

    @property
    def is_open(self):
        """The two live statuses — everything but the resolved/closed terminals + cancelled."""
        return self.status in ("open", "in_progress")

    @property
    def is_locked(self):
        """Resolved, closed and cancelled rows are frozen evidence — edit/delete refuse them
        (the QRV/QCI siblings lock ``cancelled`` too, so a cancelled defect is equally
        un-writable: no edit, no hard delete, no resolve stamps, no issue bridge)."""
        return self.status in ("resolved", "closed", "cancelled")

    def clean(self):
        super().clean()
        if self.wbs_node_id and self.project_id \
                and self.wbs_node.project_id != self.project_id:
            raise ValidationError(
                {"wbs_node": "The WBS node must belong to the same project as the defect."})
        if self.quality_plan_id and self.project_id \
                and self.quality_plan.project_id != self.project_id:
            raise ValidationError(
                {"quality_plan": "The quality plan must belong to the same project as the "
                                 "defect."})
        if self.inspection_id and self.project_id \
                and self.inspection.project_id != self.project_id:
            raise ValidationError(
                {"inspection": "The inspection must belong to the same project as the defect."})
