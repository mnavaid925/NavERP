"""Projects 7.16 Reporting & Business Intelligence — ProjectReport [REP-].

The *saved question*: a frozen-axis report definition (subject, 1–3 measures, up to 2 dimensions, a
window, four tenant-revalidated scope FKs, a chart kind). It stores NO results — the numbers are
computed live by ``apps/projects.analytics.compute_report`` and only persisted when a run is frozen
(``ProjectReportRun``).

Read-only rule (L29): this model never writes money, never calls ``accounting.*``, and never mutates a
7.4 or 7.15 row. ``accounting`` owns the ledger; 7.4 owns EVM as ``@property`` reads; 7.15 owns billing.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.projects.models._base import TenantNumbered
from apps.projects.models.ReportingBusinessIntelligence._choices import (
    CHART_CHOICES,
    DIMENSION_CHOICES,
    MEASURE_CHOICES,
    RANGE_CHOICES,
    REPORT_TYPE_CHOICES,
    SUBJECT_CHOICES,
)

_MEASURE_KEYS = {key for key, _label in MEASURE_CHOICES}
_MAX_WINDOW_DAYS = 730

#: scope FKs that must belong to the same tenant as the report itself
_SCOPE_FIELDS = (
    ("project", "project"),
    ("portfolio", "portfolio"),
    ("client", "client"),
    ("org_unit", "department"),
)


class ProjectReport(TenantNumbered):
    NUMBER_PREFIX = "REP"

    REPORT_TYPE_CHOICES = REPORT_TYPE_CHOICES
    SUBJECT_CHOICES = SUBJECT_CHOICES
    MEASURE_CHOICES = MEASURE_CHOICES
    DIMENSION_CHOICES = DIMENSION_CHOICES
    RANGE_CHOICES = RANGE_CHOICES
    CHART_CHOICES = CHART_CHOICES

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    report_type = models.CharField(
        max_length=24, choices=REPORT_TYPE_CHOICES, default="status_report"
    )
    subject = models.CharField(max_length=24, choices=SUBJECT_CHOICES, default="project")
    measures = models.JSONField(default=list, blank=True)
    dimension_1 = models.CharField(
        max_length=20, choices=DIMENSION_CHOICES, default="project"
    )
    dimension_2 = models.CharField(
        max_length=20, choices=DIMENSION_CHOICES, default="none"
    )
    date_range = models.CharField(max_length=10, choices=RANGE_CHOICES, default="last_90")
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    as_of = models.DateField(null=True, blank=True)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_reports",
    )
    portfolio = models.ForeignKey(
        "projects.Portfolio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_reports",
    )
    client = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_reports",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_reports",
    )
    chart_type = models.CharField(max_length=10, choices=CHART_CHOICES, default="table")
    top_n = models.PositiveSmallIntegerField(
        default=20, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    sort_by = models.CharField(max_length=24, blank=True)
    notes = models.TextField(blank=True)
    is_favorite = models.BooleanField(default=False)
    is_shared = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_reports",
    )
    last_run_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-is_favorite", "name"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "report_type"], name="rep_tnt_type_idx"),
            models.Index(fields=["tenant", "is_shared"], name="rep_tnt_share_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"

    # -- computed, never stored -----------------------------------------------------------------
    @property
    def is_custom(self):
        return self.report_type == "custom"

    @property
    def is_canned(self):
        return not self.is_custom

    @property
    def metric_labels(self):
        labels = dict(MEASURE_CHOICES)
        return [labels[key] for key in (self.measures or []) if key in labels]

    @property
    def dimension_labels(self):
        labels = dict(DIMENSION_CHOICES)
        return [
            labels[key]
            for key in (self.dimension_1, self.dimension_2)
            if key and key != "none" and key in labels
        ]

    @property
    def window_label(self):
        if self.date_from and self.date_to:
            return f"{self.date_from:%Y-%m-%d} → {self.date_to:%Y-%m-%d}"
        return dict(RANGE_CHOICES).get(self.date_range, self.get_date_range_display())

    @property
    def scope_label(self):
        for attr in ("project", "portfolio", "client", "org_unit"):
            related = getattr(self, attr, None)
            if related is not None:
                return str(related)
        return "All projects"

    # -- validation ------------------------------------------------------------------------------
    def clean(self):
        errors = {}
        measures = self.measures or []

        if not isinstance(measures, list) or not measures:
            errors["measures"] = "Pick between 1 and 3 measures."
        elif len(measures) > 3:
            errors["measures"] = "Pick between 1 and 3 measures."
        else:
            unknown = [key for key in measures if key not in _MEASURE_KEYS]
            if unknown:
                errors["measures"] = f"Unknown measure: {', '.join(unknown)}."

        if self.date_range == "custom":
            if not self.date_from:
                errors["date_from"] = "A custom range needs a start date."
            if not self.date_to:
                errors["date_to"] = "A custom range needs an end date."
        elif self.date_range == "all":
            if self.date_from or self.date_to:
                errors["date_range"] = "An all-time report cannot carry a window."
        elif bool(self.date_from) != bool(self.date_to):
            missing = "date_from" if not self.date_from else "date_to"
            errors[missing] = "Set both dates or neither."

        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                errors["date_from"] = "The start date cannot be after the end date."
            elif (self.date_to - self.date_from).days > _MAX_WINDOW_DAYS:
                errors["date_to"] = "A report window cannot span more than 730 days."
            if self.as_of and not (self.date_from <= self.as_of <= self.date_to):
                errors["as_of"] = "The as-of date must fall inside the window."

        if (
            self.dimension_1
            and self.dimension_1 == self.dimension_2
            and self.dimension_1 != "none"
        ):
            errors["dimension_2"] = "Pick a different second dimension, or set it to none."

        if self.sort_by and self.sort_by not in _MEASURE_KEYS:
            errors["sort_by"] = "Unknown sort measure."

        if self.report_type == "custom" and not self.subject:
            errors["subject"] = "A custom report must name what its rows are."

        tenant_id = self.tenant_id
        if tenant_id:
            for field, label in _SCOPE_FIELDS:
                related = getattr(self, field, None)
                if related is not None and related.tenant_id != tenant_id:
                    errors[field] = f"That {label} belongs to another workspace."

        if errors:
            raise ValidationError(errors)
