from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetComplianceFramework(TenantNumbered):
    """
    Asset Compliance & Regulatory Framework [ACF-].
    Catalogs regulatory standards, compliance mandates, safety codes, and international
    frameworks governing enterprise assets (e.g. OSHA 1910, ISO 55001, EPA Title V, ASME).
    """

    NUMBER_PREFIX = "ACF"

    FRAMEWORK_TYPE_CHOICES = [
        ("regulatory", "Government Regulatory Mandate"),
        ("statutory", "Statutory / Legal Code"),
        ("voluntary_standard", "Voluntary Industry Standard (ISO/IEC)"),
        ("industry_code", "Industry Engineering Code (ASME/NFPA)"),
        ("corporate_policy", "Corporate Internal EHS Policy"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft (Proposed)"),
        ("active", "Active & Enforced"),
        ("under_review", "Under Revision / Review"),
        ("deprecated", "Deprecated / Superseded"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "active": "badge-green",
        "under_review": "badge-amber",
        "deprecated": "badge-muted",
    }

    FRAMEWORK_TYPE_CSS = {
        "regulatory": "badge-red",
        "statutory": "badge-amber",
        "voluntary_standard": "badge-info",
        "industry_code": "badge-slate",
        "corporate_policy": "badge-muted",
    }

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="compliance_frameworks",
    )
    name = models.CharField(
        max_length=255,
        help_text="Official standard or framework name",
    )
    code = models.CharField(
        max_length=50,
        help_text="Short standard code, e.g. OSHA-1910-PSM, ISO-55001, EPA-TITLE-V",
    )
    framework_type = models.CharField(
        max_length=24,
        choices=FRAMEWORK_TYPE_CHOICES,
        default="regulatory",
    )
    regulatory_agency = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compliance_frameworks",
        help_text="Enforcing agency or standard body",
    )
    applicable_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compliance_frameworks",
        help_text="Asset category governed by this framework",
    )
    effective_date = models.DateField(default=timezone.now)
    revision = models.CharField(
        max_length=50,
        default="Current",
        help_text="Standard edition or revision identifier",
    )
    mandatory_audit_cycle_months = models.PositiveIntegerField(
        default=12,
        help_text="Mandatory compliance review frequency in months",
    )
    readiness_score = models.PositiveIntegerField(
        default=100,
        help_text="Compliance readiness rating percentage (0-100)",
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed scope, mandate requirements, and compliance objectives",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_acf_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_acf_ten_stat"),
            models.Index(fields=["tenant", "framework_type"], name="idx_acf_ten_type"),
            models.Index(fields=["tenant", "code"], name="idx_acf_ten_code"),
            models.Index(fields=["tenant", "applicable_category"], name="idx_acf_ten_cat"),
        ]

    def __str__(self):
        return f"{self.code} — {self.name} ({self.number})"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def framework_type_badge_class(self):
        return self.FRAMEWORK_TYPE_CSS.get(self.framework_type, "badge-slate")

    @property
    def is_active(self):
        return self.status == "active"

    @property
    def is_audit_due(self):
        if not self.is_active:
            return False
        latest_audit = self.audits.filter(status="completed").order_by("-audit_date").first()
        ref_date = latest_audit.audit_date if latest_audit and latest_audit.audit_date else self.effective_date
        if not ref_date:
            return True
        if hasattr(ref_date, "date"):
            ref_date = ref_date.date()
        cycle_days = (self.mandatory_audit_cycle_months or 12) * 30
        return (timezone.now().date() - ref_date).days >= cycle_days
