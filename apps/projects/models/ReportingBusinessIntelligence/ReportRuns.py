"""Projects 7.16 Reporting & Business Intelligence — ProjectReportRun (the frozen answer).

An immutable snapshot of one report at one instant: the resolved window, the computed ``summary``/``data``
payload, and a human narrative that moves ``draft → issued → archived``. Rows are minted ONLY by
``rep_freeze``; there is no create view and no builder form, exactly like ``procurement.SpendReportSnapshot``.

This table is the whole point of being a table rather than a query: "this project has been amber for six
weeks" and period-over-period EVM are derivable from nothing else. ``analytics.rag_streak()`` walks this
series read-only.

Read-only rule (L29): stores a *record* of what was computed once — never refreshed, never used to answer a
different question, never read back into ``analytics`` as an input.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.projects.models.ReportingBusinessIntelligence._choices import RUN_STATUS_CHOICES

_MAX_WINDOW_DAYS = 730

#: RAG letter → colour-named badge class. theme.css has no badge-success/-danger (L33).
_RAG_CSS = {
    "green": "badge-green",
    "amber": "badge-amber",
    "red": "badge-red",
}


class ProjectReportRun(models.Model):
    STATUS_CHOICES = RUN_STATUS_CHOICES

    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True
    )
    report = models.ForeignKey(
        "projects.ProjectReport", on_delete=models.CASCADE, related_name="runs"
    )
    title = models.CharField(max_length=200)
    period_from = models.DateField(null=True, blank=True)
    period_to = models.DateField(null=True, blank=True)
    as_of = models.DateField()
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    generated_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    summary = models.JSONField(default=dict, blank=True)
    data = models.JSONField(default=dict, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    narrative = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=RUN_STATUS_CHOICES, default="draft"
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    issued_at = models.DateTimeField(null=True, blank=True, editable=False)
    document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_report_runs",
    )

    class Meta:
        ordering = ["-generated_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "generated_at"], name="run_tnt_gen_idx"),
            models.Index(fields=["tenant", "report"], name="run_tnt_rep_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.generated_at:%Y-%m-%d %H:%M})"

    # -- status ------------------------------------------------------------------------------------
    @property
    def is_draft(self):
        return self.status == "draft"

    @property
    def is_issued(self):
        return self.status == "issued"

    @property
    def is_archived(self):
        return self.status == "archived"

    @property
    def is_editable(self):
        """The only gate on ``run_narrative`` — an issued pack is a published document."""
        return self.status == "draft"

    # -- thin readers over the frozen payload -------------------------------------------------------
    # Templates must never index a JSONField: a missing key there is a blank region at HTTP 200 (L8).
    @property
    def rating(self):
        return (self.data or {}).get("rating") or ""

    @property
    def rag_css(self):
        return _RAG_CSS.get(self.rating, "badge-muted")

    @property
    def columns(self):
        return (self.data or {}).get("columns") or []

    @property
    def rows(self):
        return (self.data or {}).get("rows") or []

    @property
    def chart_type(self):
        return (self.data or {}).get("chart_type") or "table"

    @property
    def chart_labels(self):
        return (self.data or {}).get("chart_labels") or []

    @property
    def chart_data(self):
        return (self.data or {}).get("chart_data") or []

    @property
    def caveats(self):
        return (self.data or {}).get("caveats") or []

    @property
    def truncated(self):
        return bool((self.data or {}).get("truncated"))

    @property
    def summary_cards(self):
        """``summary`` is stored as {label: value}; the KPI strip wants [{label, value}]."""
        return [
            {"label": label, "value": value}
            for label, value in (self.summary or {}).items()
        ]

    # -- validation ---------------------------------------------------------------------------------
    def clean(self):
        errors = {}

        if self.period_from and self.period_to:
            if self.period_from > self.period_to:
                errors["period_from"] = "The start date cannot be after the end date."
            elif (self.period_to - self.period_from).days > _MAX_WINDOW_DAYS:
                errors["period_to"] = "A frozen window cannot span more than 730 days."
            elif self.as_of and not (self.period_from <= self.as_of <= self.period_to):
                errors["as_of"] = "The as-of date must fall inside the frozen window."

        if self.document_id and self.tenant_id and self.document.tenant_id != self.tenant_id:
            errors["document"] = "That document belongs to another workspace."

        # Status transitions are verb-gated in the views (run_issue / run_archive), not here: a
        # model-level guard would fight the .update() calls that deliberately skip updated_at.
        if errors:
            raise ValidationError(errors)
