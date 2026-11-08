from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class BiDecisionLog(TenantNumbered):
    NUMBER_PREFIX = "DLOG"

    CATEGORY_CHOICES = [
        ("strategic", "Strategic Initiative"),
        ("operational", "Operational Adjustment"),
        ("pricing", "Pricing & Commercial"),
        ("budget", "Budget / Cost Control"),
        ("inventory", "Supply / Inventory Policy"),
    ]

    STATUS_CHOICES = [
        ("proposed", "Proposed / Under Review"),
        ("approved", "Approved & Enacted"),
        ("superseded", "Superseded"),
        ("revoked", "Revoked / Rolled Back"),
    ]

    MARKER_STYLE_CHOICES = [
        ("pin_flag", "Pin Flag Marker"),
        ("vertical_line_event", "Vertical Milestone Line"),
        ("highlight_band", "Highlight Region Band"),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)

    category = models.CharField(
        max_length=24,
        choices=CATEGORY_CHOICES,
        default="operational",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="approved",
    )
    decision_date = models.DateField(help_text="Effective date when this business decision was made")

    problem_statement = models.TextField(blank=True, help_text="Business condition or challenge requiring action")
    rationale = models.TextField(help_text="Key justification and business logic supporting this decision")
    alternatives_considered = models.TextField(blank=True, help_text="Evaluated options that were rejected")
    expected_impact = models.TextField(blank=True, help_text="Targeted ROI, metric improvement, or risk reduction")
    actual_outcome = models.TextField(blank=True, help_text="Post-mortem evaluation of actual results achieved")

    workspace = models.ForeignKey(
        "bi.BiSharedWorkspace",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decision_logs",
        help_text="Workspace context where this decision was discussed",
    )
    dashboard = models.ForeignKey(
        "bi.BiDashboard",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decision_logs",
        help_text="Dashboard where decision marker should be displayed",
    )
    widget = models.ForeignKey(
        "bi.BiDashboardWidget",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decision_logs",
        help_text="Specific chart card linked to this decision event",
    )
    kpi = models.ForeignKey(
        "bi.KpiDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decision_logs",
        help_text="Target KPI tracked against this decision",
    )

    decision_maker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_made_decisions",
        help_text="Principal decision authority or sponsor",
    )

    show_on_charts = models.BooleanField(
        default=True,
        help_text="Project milestone marker line or pin onto linked dashboard trend charts",
    )
    marker_style = models.CharField(
        max_length=24,
        choices=MARKER_STYLE_CHOICES,
        default="pin_flag",
    )
    marker_color = models.CharField(max_length=20, default="#10b981")

    supporting_documents = models.JSONField(
        default=list,
        blank=True,
        help_text="List of supporting analysis URLs or Document references",
    )
    review_date = models.DateField(
        null=True,
        blank=True,
        help_text="Scheduled post-decision audit or KPI impact review date",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_created_decisions",
    )

    class Meta:
        db_table = "bi_decision_log"
        ordering = ["-decision_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_dlog_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_dlog_ten_slug_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_dlog_ten_stat"),
            models.Index(fields=["tenant", "category"], name="idx_dlog_ten_cat"),
            models.Index(fields=["tenant", "decision_date"], name="idx_dlog_ten_date"),
            models.Index(fields=["tenant", "dashboard"], name="idx_dlog_ten_dash"),
            models.Index(fields=["tenant", "kpi"], name="idx_dlog_ten_kpi"),
            models.Index(fields=["tenant", "created_at"], name="idx_dlog_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.decision_date})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or "decision"
            slug = base_slug
            counter = 1
            qs = BiDecisionLog.objects.filter(tenant=self.tenant)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            while qs.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
