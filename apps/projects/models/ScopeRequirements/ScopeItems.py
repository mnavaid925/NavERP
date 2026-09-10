"""Projects 7.7 — ScopeItem [SCI-]: the scope boundary / assumption / constraint registry row.

Bullet 3 ("Scope Definition & Boundaries — In-scope/out-scope statements, assumptions, and
constraints registry") in one table, discriminated by ``item_type``. The in-scope and out-of-scope
*statements* stay on the 7.1 charter (``Project.in_scope`` / ``Project.out_of_scope`` — the scope
narrative belongs with the charter it was signed against); this register is the itemised
**boundary registry** the charter only summarises, plus the assumptions and constraints that can be
individually validated, realized or retired as the project runs.

**Why one table and not four.** An assumption, a constraint, a dependency and a boundary statement
are the same shape — a declared statement, an impact area, an owner, a review date and an outcome —
and the 7.7 pages slice them by ``item_type``. Four tables would be four registers that all render
identically and all need the same lifecycle verbs (the 7.5 ``ProjectIssue`` ``issue_type`` ruling).

**Lifecycle is verb-driven** (validate / realize / retire), so ``status`` and ``outcome`` are off
the form: the outcome text and the status transition are written by the verb that stamps
``closed_at`` in the same request.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class ScopeItem(TenantNumbered):
    NUMBER_PREFIX = "SCI"

    ITEM_TYPE_CHOICES = [
        ("in_scope", "In Scope"),
        ("out_of_scope", "Out of Scope"),
        ("assumption", "Assumption"),
        ("constraint", "Constraint"),
        ("dependency", "Dependency"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("validated", "Validated"),
        ("realized", "Realized"),
        ("retired", "Retired"),
    ]
    IMPACT_AREA_CHOICES = [
        ("schedule", "Schedule"),
        ("cost", "Cost"),
        ("quality", "Quality"),
        ("scope", "Scope"),
        ("resource", "Resource"),
        ("compliance", "Compliance"),
    ]

    #: The two types that are *boundaries* rather than risks-in-waiting — the ``?boundaries=1``
    #: lens and the matrix page's boundary panel read this, so the definition lives in one place.
    BOUNDARY_TYPES = {"in_scope", "out_of_scope"}

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="scope_items")
    requirement = models.ForeignKey(
        "projects.Requirement", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="scope_items",
        help_text="The requirement this item qualifies, when it attaches to one.")
    item_type = models.CharField(max_length=12, choices=ITEM_TYPE_CHOICES, default="assumption")
    #: The registry statement itself — one sentence, the thing that is in or out of scope, assumed
    #: or constrained.
    statement = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    impact_area = models.CharField(max_length=12, choices=IMPACT_AREA_CHOICES, default="scope")
    #: Verb-driven (validate/realize/retire) — OFF the form.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="open")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_scope_items")
    identified_date = models.DateField(default=timezone.localdate)
    review_date = models.DateField(
        null=True, blank=True, help_text="The next scheduled review of this item.")
    #: Verb-written: what actually happened to the assumption/constraint.
    outcome = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="sci_created")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="sci_tnt_project_idx"),
            models.Index(fields=["tenant", "item_type"], name="sci_tnt_type_idx"),
            models.Index(fields=["tenant", "status"], name="sci_tnt_status_idx"),
            models.Index(fields=["tenant", "impact_area"], name="sci_tnt_impact_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.statement}"

    # -- derived predicates (never stored) -------------------------------------------------------

    @property
    def is_boundary(self):
        return self.item_type in self.BOUNDARY_TYPES

    @property
    def is_open(self):
        """Live rows: an open item can still be validated; a validated one can still be realized."""
        return self.status in ("open", "validated")

    @property
    def is_locked(self):
        """Realized / retired rows are closed evidence — edit/delete refuse them."""
        return self.status in ("realized", "retired")

    @property
    def is_review_overdue(self):
        """Review date passed and the item is still live. Uses ``timezone.localdate()`` (L16)."""
        if not self.review_date:
            return False
        return self.review_date < timezone.localdate() and self.is_open

    def clean(self):
        super().clean()
        if self.requirement_id and self.project_id \
                and self.requirement.project_id != self.project_id:
            raise ValidationError(
                {"requirement": "The requirement must belong to the same project as the scope "
                                "item."})
