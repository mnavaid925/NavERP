"""Projects 7.1 Project Initiation & Charter — ProjectKickoff [PKO-].

Realizes NavERP 7.1 bullet **5 Project Kickoff & Launch**: meeting templates, the team
onboarding checklist, and the baseline-setting ceremony.

Scope notes, so nobody reads this row as more than it is:

* **The baseline RECORD is 7.2's.** This row attests that the ceremony happened
  (`baseline_acknowledged_at/by`); the frozen schedule it acknowledged lives with the schedule
  baseline in Project Planning & Scheduling.
* **The reusable agenda-template library is 7.19's.** `agenda_template` is which canned shape was
  used, not the library itself.
* **Individual onboarding items are `core.Activity(kind="task")` rows GFK'd to the project.**
  `onboarding_notes` is the free-text summary; capturing each item as its own trackable row is
  7.9 Collaboration & Communication's.
* **No `ProjectKickoffItem` table** — the checklist is those `core.Activity` rows, deliberately.
* **Plain FK + `unique_together`, not a OneToOneField.** A OneToOne fights a partially-created row
  (the reverse side raises `RelatedObjectDoesNotExist` on a project that has no kickoff yet), and
  a project that re-kicks-off after a false start is a real case.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class ProjectKickoff(TenantNumbered):
    NUMBER_PREFIX = "PKO"

    AGENDA_TEMPLATE_CHOICES = [
        ("standard", "Standard"),
        ("agile", "Agile"),
        ("client_facing", "Client-Facing"),
        ("custom", "Custom"),
    ]
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("scheduled", "Scheduled"),
        ("held", "Held"),
        ("completed", "Completed"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="kickoffs")
    meeting_date = models.DateTimeField(null=True, blank=True)
    location_or_link = models.CharField(max_length=255, blank=True)
    agenda_template = models.CharField(
        max_length=16, choices=AGENDA_TEMPLATE_CHOICES, default="standard")
    agenda = models.TextField(blank=True)
    attendee_summary = models.TextField(
        blank=True, help_text="External attendees not on the stakeholder register.")
    onboarding_notes = models.TextField(
        blank=True,
        help_text="Individual items are core.Activity(kind='task') rows on the project.")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="planned")

    baseline_acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    baseline_acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = (("tenant", "number"), ("tenant", "project"))
        indexes = [
            models.Index(fields=["tenant", "project"], name="pko_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="pko_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.project} ({self.get_status_display()})"

    @property
    def attendee_count(self):
        """Stakeholders flagged as attending — the register is the attendee list."""
        if not self.project_id:
            return 0
        return self.project.stakeholders.filter(attending_kickoff=True).count()
