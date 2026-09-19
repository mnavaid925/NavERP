"""Projects 7.16 Reporting & Business Intelligence — ProjectDashboard [PDB-].

The container for real-time tiles: an audience, a default window, a column layout, and optional
project/portfolio scope. A row with ``owner=None`` is a tenant-provided audience *template* rather than
someone's home screen.

Stores no measurements — every figure on a tile is computed by ``apps/projects.analytics`` when the page
renders, so a dashboard can never drift from the ledger it reports on (L29).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.projects.models._base import TenantNumbered
from apps.projects.models.ReportingBusinessIntelligence._choices import (
    AUDIENCE_CHOICES,
    LAYOUT_CHOICES,
    RANGE_CHOICES,
)

#: layout key → 12-column grid span each tile gets
_COLUMN_SPAN = {"one": 12, "two": 6, "three": 4}


class ProjectDashboard(TenantNumbered):
    NUMBER_PREFIX = "PDB"

    AUDIENCE_CHOICES = AUDIENCE_CHOICES
    LAYOUT_CHOICES = LAYOUT_CHOICES
    RANGE_CHOICES = RANGE_CHOICES

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_dashboards",
    )
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default="pm")
    default_range = models.CharField(max_length=10, choices=RANGE_CHOICES, default="last_90")
    layout = models.CharField(max_length=5, choices=LAYOUT_CHOICES, default="two")
    is_default = models.BooleanField(default=False)
    is_shared = models.BooleanField(default=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_dashboards",
    )
    portfolio = models.ForeignKey(
        "projects.Portfolio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_dashboards",
    )

    class Meta:
        ordering = ["-is_default", "name"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "owner"], name="pdb_tnt_own_idx"),
            models.Index(fields=["tenant", "is_shared"], name="pdb_tnt_share_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"

    # -- computed, never stored -----------------------------------------------------------------
    @property
    def widget_count(self):
        return self.widgets.count()

    @property
    def is_template(self):
        return self.owner_id is None

    @property
    def column_span(self):
        return _COLUMN_SPAN.get(self.layout, 6)

    # -- validation ---------------------------------------------------------------------------------
    def clean(self):
        errors = {}

        # MySQL has no partial unique index, so "at most one default per owner" is a SELECT, not a constraint.
        if self.is_default:
            others = ProjectDashboard.objects.filter(
                tenant_id=self.tenant_id, is_default=True
            )
            # exclude(pk=None) would compile to NOT (id IS NULL) and empty the queryset, so the
            # conflict rule would silently never fire when CREATING a dashboard.
            if self.pk is not None:
                others = others.exclude(pk=self.pk)
            others = (
                others.filter(owner__isnull=True)
                if self.owner_id is None
                else others.filter(owner_id=self.owner_id)
            )
            if others.exists():
                errors["is_default"] = (
                    "This workspace already has a default dashboard for that owner — "
                    "unset the other one first."
                )

        if self.is_default and not self.is_shared and self.owner_id is None:
            errors["is_shared"] = (
                "An unowned tenant template must be shared, or nothing can ever resolve it."
            )

        # Tiles carry no date pair, so only the presets resolve here (unlike ProjectReport).
        if self.default_range == "custom":
            errors["default_range"] = (
                "A dashboard window must be one of the presets — tiles have no date pair to resolve."
            )

        if self.tenant_id:
            for field in ("project", "portfolio"):
                related = getattr(self, field, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    errors[field] = "That scope belongs to another workspace."

        if errors:
            raise ValidationError(errors)
