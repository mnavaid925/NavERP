"""Projects 7.1 Project Initiation & Charter — ProjectStakeholder [PST-].

Realizes NavERP 7.1 bullet **4 Stakeholder Identification & Analysis**.

The register **is** the RACI matrix and **is** the engagement plan — there is no second artefact
table. One row per (person-or-organisation, RACI assignment), which is what lets the same sponsor
appear once as `a` for "charter approval" and again as `c` for "vendor selection": a RACI is a
relationship to a piece of work, not an attribute of a person.

* `party` is a `core.Party` — a person *or* an organisation, internal *or* external. Employees are
  a `PartyRole` on `Party`, never a second person master.
* `user` is the optional platform account, for anything that needs a login (comms, notifications).
* At least one of the two must be set; `clean()` enforces it.
* `attending_kickoff` is the kickoff attendee list **without an M2M** — see `ProjectKickoff`.

`org_unit` is deliberately NOT modelled (the research's optional fifth FK). Four nullable FKs on
one row is enough, and "this whole department is a stakeholder" is expressed as a `party` of
`kind="organization"`.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class ProjectStakeholder(TenantNumbered):
    NUMBER_PREFIX = "PST"

    STAKEHOLDER_TYPE_CHOICES = [
        ("sponsor", "Sponsor"),
        ("approver", "Approver"),
        ("resource_provider", "Resource Provider"),
        ("subject_matter_expert", "Subject Matter Expert"),
        ("affected", "Affected Party"),
        ("team_member", "Team Member"),
        ("other", "Other"),
    ]
    RACI_ROLE_CHOICES = [
        ("r", "R (Responsible)"),
        ("a", "A (Accountable)"),
        ("c", "C (Consulted)"),
        ("i", "I (Informed)"),
    ]
    INFLUENCE_CHOICES = [("high", "High"), ("medium", "Medium"), ("low", "Low")]
    INTEREST_CHOICES = [("high", "High"), ("medium", "Medium"), ("low", "Low")]
    COMMS_PREFERENCE_CHOICES = [
        ("email", "Email"),
        ("meeting", "Meeting"),
        ("written_report", "Written Report"),
        ("portal", "Portal"),
        ("none", "None"),
    ]
    COMMS_FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("at_milestone", "At Milestone"),
        ("ad_hoc", "Ad-hoc"),
    ]
    #: A LABEL SET, not a column. It exists so the template has get_…-style labels to render the
    #: influence/interest grid without re-deriving the quadrant in Jinja.
    ENGAGEMENT_STRATEGY_CHOICES = [
        ("manage_closely", "Manage Closely"),
        ("keep_satisfied", "Keep Satisfied"),
        ("keep_informed", "Keep Informed"),
        ("monitor", "Monitor"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="stakeholders")
    party = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_stakeholders")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_stakeholders")

    stakeholder_type = models.CharField(
        max_length=24, choices=STAKEHOLDER_TYPE_CHOICES, default="other")
    raci_role = models.CharField(max_length=1, choices=RACI_ROLE_CHOICES, default="i")
    raci_scope = models.CharField(
        max_length=120, blank=True,
        help_text="What this RACI assignment covers, e.g. 'charter approval'.")

    influence = models.CharField(max_length=8, choices=INFLUENCE_CHOICES, default="medium")
    interest = models.CharField(max_length=8, choices=INTEREST_CHOICES, default="medium")
    comms_preference = models.CharField(
        max_length=16, choices=COMMS_PREFERENCE_CHOICES, default="email")
    comms_frequency = models.CharField(
        max_length=16, choices=COMMS_FREQUENCY_CHOICES, default="weekly")
    attending_kickoff = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        # NOT ["-influence", "party__name"]: `influence` is a CharField, so a descending sort is
        # ALPHABETICAL — medium, then low, then high — the exact inverse of the power ranking the
        # grid exists to show; and `party__name` sorts NULLs differently on SQLite (tests) than on
        # MariaDB (prod). Index-backed and deterministic instead; the power ranking is a list-view
        # annotation (`influence_rank`), which is where the intent actually belongs.
        ordering = ["-created_at", "-id"]
        unique_together = (
            ("tenant", "number"),
            # PARTIAL constraint: `party` is nullable and SQL treats every NULL as distinct, so
            # this binds only the party-set case. The form's clean() covers the rest.
            ("tenant", "project", "party", "raci_scope"),
        )
        indexes = [
            models.Index(fields=["tenant", "project"], name="pst_tnt_project_idx"),
            models.Index(fields=["tenant", "stakeholder_type"], name="pst_tnt_type_idx"),
        ]

    def __str__(self):
        who = self.party or self.user or "—"
        return f"{self.number} — {who} ({self.get_raci_role_display()})"

    @property
    def engagement_strategy(self):
        """The influence/interest quadrant.

        ``medium`` maps to the LOW side on both axes — deliberate and documented: a three-point
        scale has no neutral middle, and leaving it ambiguous is how two people read the same grid
        differently. High/high → manage closely, high/low → keep satisfied, low/high → keep
        informed, everything else → monitor.
        """
        high_influence = self.influence == "high"
        high_interest = self.interest == "high"
        if high_influence and high_interest:
            return "manage_closely"
        if high_influence:
            return "keep_satisfied"
        if high_interest:
            return "keep_informed"
        return "monitor"

    def get_engagement_strategy_display(self):
        """The label for ``engagement_strategy``.

        Django only generates ``get_FOO_display`` for real FIELDS with choices; this is a derived
        property, so without this method the template would render an empty cell — which is
        exactly the L7 blank-at-200 failure mode, on a column that looks like it worked.
        """
        return dict(self.ENGAGEMENT_STRATEGY_CHOICES).get(self.engagement_strategy, "—")

    def clean(self):
        super().clean()
        if not self.party_id and not self.user_id:
            raise ValidationError(
                "Name a party or a user — a stakeholder row with neither identifies nobody.")
        if self.project_id and self.party_id:
            dupes = ProjectStakeholder.objects.filter(
                tenant_id=self.tenant_id,
                project_id=self.project_id,
                party_id=self.party_id,
                raci_scope=self.raci_scope,
            )
            if self.pk:
                dupes = dupes.exclude(pk=self.pk)
            if dupes.exists():
                raise ValidationError(
                    "That party already holds this RACI role for this scope on this project. "
                    "A duplicate row would double-count them in the grid.")
