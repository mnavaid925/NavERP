"""HRM 3.39 Compliance & Legal — Hrpolicy models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class HRPolicy(TenantNumbered):
    """A versioned HR policy (``POL-#####``). ``previous_version`` chains supersessions; a policy targeted at
    one ``applicable_org_unit`` applies only there (blank = the whole tenant). When ``requires_acknowledgment``
    is set, publishing raises a ``PolicyAcknowledgment`` row per targeted employee. ``acknowledgment_rate`` is
    COMPUTED (annotation-aware for list rendering)."""

    NUMBER_PREFIX = "POL"

    CATEGORY_CHOICES = [
        ("code_of_conduct", "Code of Conduct"),
        ("leave", "Leave"),
        ("attendance", "Attendance"),
        ("it_security", "IT & Security"),
        ("harassment", "Anti-Harassment"),
        ("health_safety", "Health & Safety"),
        ("travel", "Travel & Expense"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    title = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    version_number = models.CharField(max_length=20, default="1.0")
    previous_version = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="superseded_by")
    applicable_org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name="hrm_policies",
                                            help_text="Blank = applies to the whole organization.")
    summary = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)
    document = models.FileField(upload_to="hrm/policies/%Y/%m/", null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    effective_from = models.DateField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    requires_acknowledgment = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("tenant", "number"), ("tenant", "title", "version_number"))
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_pol_tnt_status_idx"),
            models.Index(fields=["tenant", "category"], name="hrm_pol_tnt_cat_idx"),
            models.Index(fields=["tenant", "-created_at"], name="hrm_pol_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.title} v{self.version_number}"

    @property
    def acknowledged_count(self):
        annotated = getattr(self, "_acknowledged_count", None)
        if annotated is not None:
            return annotated
        return self.acknowledgments.filter(status="acknowledged").count()

    @property
    def target_count(self):
        annotated = getattr(self, "_target_count", None)
        if annotated is not None:
            return annotated
        return self.acknowledgments.count()

    @property
    def acknowledgment_rate(self):
        """Percent of targeted employees who have acknowledged (0 when nobody is targeted)."""
        total = self.target_count
        if not total:
            return Decimal("0")
        return (Decimal(self.acknowledged_count) / total * 100).quantize(Decimal("0.1"))
