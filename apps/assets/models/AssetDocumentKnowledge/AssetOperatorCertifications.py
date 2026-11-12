"""Asset Operator Qualification, Training & Certification Record model (11.16)."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.assets.models._base import TenantNumbered
from apps.assets.models.AssetDocumentKnowledge._validators import (
    add_field_error,
    compute_uploaded_file_metadata,
    validate_tenant_fks,
)


class AssetOperatorCertification(TenantNumbered):
    """Operator equipment competency, LOTO authorization, and SOP acknowledgment [AOCT]."""

    NUMBER_PREFIX = "AOCT"

    QUALIFICATION_TYPE_CHOICES = [
        ("equipment_operator", "Equipment Operator"),
        ("maintenance_technician", "Maintenance Technician"),
        ("loto_authorized", "LOTO Authorized Person"),
        ("electrical_hv", "High-Voltage Electrical"),
        ("confined_space", "Confined Space Entry"),
        ("crane_rigging", "Crane & Rigging Operations"),
        ("pressure_welding", "Pressure Vessel / Welding"),
        ("calibration_specialist", "Calibration Specialist"),
        ("oem_certified", "OEM Certified Specialist"),
    ]

    PROFICIENCY_LEVEL_CHOICES = [
        ("trainee_supervised", "Trainee (Supervised)"),
        ("qualified_operator", "Qualified Operator"),
        ("senior_technician", "Senior Technician"),
        ("lead_inspector", "Lead Inspector / SME"),
        ("trainer_assessor", "Certified Trainer / Assessor"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending Verification"),
        ("active", "Active / Certified"),
        ("expiring_soon", "Expiring Soon"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
    ]

    STATUS_CSS = {
        "pending": "badge-slate",
        "active": "badge-green",
        "expiring_soon": "badge-amber",
        "expired": "badge-red",
        "revoked": "badge-muted",
    }

    PROFICIENCY_CSS = {
        "trainee_supervised": "badge-slate",
        "qualified_operator": "badge-info",
        "senior_technician": "badge-green",
        "lead_inspector": "badge-amber",
        "trainer_assessor": "badge-green",
    }

    EDITABLE_STATUSES = {"pending", "active", "expiring_soon"}

    _TENANT_FK_FIELDS = (
        "org_unit",
        "operator_party",
        "operator_user",
        "employee_profile",
        "hrm_certificate",
        "issuing_party",
        "assessor",
        "operational_asset",
        "asset_category",
        "asset_model",
        "operating_procedure",
        "compliance_framework",
    )

    title = models.CharField(max_length=200)
    qualification_code = models.CharField(max_length=64, blank=True)
    qualification_type = models.CharField(
        max_length=28,
        choices=QUALIFICATION_TYPE_CHOICES,
        default="equipment_operator",
    )
    proficiency_level = models.CharField(
        max_length=24,
        choices=PROFICIENCY_LEVEL_CHOICES,
        default="qualified_operator",
    )
    issuing_authority = models.CharField(max_length=150, blank=True)
    certificate_reference = models.CharField(max_length=80, blank=True)
    certificate_file = models.FileField(
        upload_to="assets/certifications/%Y/%m/", blank=True, null=True
    )
    original_filename = models.CharField(max_length=255, blank=True, editable=False)
    file_checksum = models.CharField(max_length=64, blank=True, editable=False)

    issued_date = models.DateField(default=timezone.localdate)
    expires_on = models.DateField(null=True, blank=True)
    renewal_lead_days = models.PositiveSmallIntegerField(default=30)
    last_assessed_date = models.DateField(null=True, blank=True)
    training_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00")
    )
    assessment_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    sop_acknowledged = models.BooleanField(default=False, editable=False)
    sop_acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", editable=False
    )

    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operator_certifications",
    )
    operator_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operator_asset_certifications",
    )
    operator_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operator_certifications",
    )
    employee_profile = models.ForeignKey(
        "hrm.EmployeeProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operator_certifications",
    )
    hrm_certificate = models.ForeignKey(
        "hrm.TrainingCertificate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operator_certifications",
    )
    issuing_party = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_asset_certifications",
    )
    assessor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessed_asset_certifications",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operator_certifications",
    )
    asset_category = models.ForeignKey(
        "assets.AssetCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operator_certifications",
    )
    asset_model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operator_certifications",
    )
    operating_procedure = models.ForeignKey(
        "assets.AssetOperatingProcedure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operator_certifications",
    )
    compliance_framework = models.ForeignKey(
        "assets.AssetComplianceFramework",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_operator_certifications",
    )

    class Meta:
        ordering = ["expires_on", "-issued_date", "-number"]
        verbose_name = "Asset Operator Certification"
        verbose_name_plural = "Asset Operator Certifications"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_aoct_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_aoct_ten_stat"),
            models.Index(fields=["tenant", "qualification_type"], name="idx_aoct_ten_type"),
            models.Index(fields=["tenant", "expires_on"], name="idx_aoct_ten_exp"),
            models.Index(fields=["tenant", "operator_user"], name="idx_aoct_ten_usr"),
            models.Index(fields=["tenant", "operator_party"], name="idx_aoct_ten_pty"),
        ]

    def __str__(self):
        if self.number:
            return f"{self.number} \u00b7 {self.operator_display_name} ({self.title})"
        return self.title

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def proficiency_badge_class(self):
        return self.PROFICIENCY_CSS.get(self.proficiency_level, "badge-slate")

    @property
    def days_until_expiry(self):
        if not self.expires_on:
            return None
        return (self.expires_on - timezone.localdate()).days

    @property
    def is_expired(self):
        if not self.expires_on:
            return False
        return self.expires_on < timezone.localdate()

    @property
    def is_renewal_due(self):
        if not self.expires_on or self.is_expired:
            return False
        days = self.days_until_expiry
        return days is not None and days <= (self.renewal_lead_days or 30)

    @property
    def operator_display_name(self):
        if self.operator_party_id:
            return str(self.operator_party)
        if self.employee_profile_id:
            return str(self.employee_profile)
        if self.operator_user_id:
            full_name = self.operator_user.get_full_name().strip()
            return full_name or self.operator_user.username
        return "\u2014"

    def compute_expiry_status(self, as_of=None):
        """Determine target active/expiring_soon/expired status from expires_on and lead window."""
        if not self.expires_on:
            return "active"
        ref_date = as_of or timezone.localdate()
        if self.expires_on < ref_date:
            return "expired"
        days_left = (self.expires_on - ref_date).days
        if days_left <= (self.renewal_lead_days or 30):
            return "expiring_soon"
        return "active"

    def sync_expiry_status(self, save=True, as_of=None):
        """Synchronize active/expiring_soon/expired status against current date; return True if changed."""
        if self.status not in ("active", "expiring_soon", "expired"):
            return False
        target = self.compute_expiry_status(as_of=as_of)
        if self.status == target:
            return False
        self.status = target
        if save and self.pk:
            self.save(update_fields=["status", "updated_at"])
        return True

    def sync_certificate_metadata(self):
        """Capture uploaded certificate filename and SHA-256 digest."""
        if not self.certificate_file or not getattr(self.certificate_file, "name", ""):
            self.original_filename = ""
            self.file_checksum = ""
            return
        if not getattr(self.certificate_file, "_committed", True) or not self.file_checksum:
            orig_name, _, checksum = compute_uploaded_file_metadata(self.certificate_file)
            if orig_name:
                self.original_filename = orig_name
            if checksum:
                self.file_checksum = checksum

    def clean(self):
        super().clean()
        errors = {}
        if not (
            self.operator_party_id
            or self.operator_user_id
            or self.employee_profile_id
        ):
            add_field_error(
                errors,
                "__all__",
                "Assign an Operator Party, Operator User, or Employee Profile.",
            )
        if self.issued_date and self.expires_on and self.expires_on < self.issued_date:
            add_field_error(
                errors,
                "expires_on",
                "Expiry date cannot be earlier than the issued date.",
            )
        if self.training_hours is not None and self.training_hours < Decimal("0.00"):
            add_field_error(
                errors,
                "training_hours",
                "Training hours cannot be negative.",
            )
        if self.assessment_score is not None and (
            self.assessment_score < Decimal("0.00")
            or self.assessment_score > Decimal("100.00")
        ):
            add_field_error(
                errors,
                "assessment_score",
                "Assessment score must be between 0 and 100.",
            )
        if self.renewal_lead_days is not None and self.renewal_lead_days < 1:
            add_field_error(
                errors,
                "renewal_lead_days",
                "Renewal alert lead days must be at least 1.",
            )
        validate_tenant_fks(self, errors, self._TENANT_FK_FIELDS)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.sync_certificate_metadata()
        super().save(*args, **kwargs)


def is_operator_certified(
    tenant,
    *,
    user=None,
    party=None,
    operational_asset=None,
    asset_category=None,
    qualification_code=None,
    as_of=None,
):
    """Cross-module helper: return True if an operator holds a non-expired active certification."""
    if tenant is None or (user is None and party is None):
        return False

    ref_date = as_of or timezone.localdate()
    qs = AssetOperatorCertification.objects.filter(
        tenant=tenant,
        status__in=("active", "expiring_soon"),
    ).filter(Q(expires_on__isnull=True) | Q(expires_on__gte=ref_date))

    if user is not None and party is not None:
        qs = qs.filter(Q(operator_user=user) | Q(operator_party=party))
    elif user is not None:
        qs = qs.filter(operator_user=user)
    else:
        qs = qs.filter(operator_party=party)

    if operational_asset is not None:
        asset_cat = asset_category or getattr(operational_asset, "asset_category", None)
        scope_q = Q(operational_asset=operational_asset) | Q(
            operational_asset__isnull=True, asset_category__isnull=True
        )
        if asset_cat is not None:
            scope_q = scope_q | Q(
                operational_asset__isnull=True, asset_category=asset_cat
            )
        else:
            cat_name = (getattr(operational_asset, "category", "") or "").strip()
            if cat_name:
                scope_q = (
                    scope_q
                    | Q(
                        operational_asset__isnull=True,
                        asset_category__name__iexact=cat_name,
                    )
                    | Q(
                        operational_asset__isnull=True,
                        asset_category__code__iexact=cat_name,
                    )
                )
        qs = qs.filter(scope_q)
    elif asset_category is not None:
        qs = qs.filter(
            Q(asset_category=asset_category)
            | Q(asset_category__isnull=True, operational_asset__isnull=True)
        )

    if qualification_code:
        qs = qs.filter(qualification_code=qualification_code)

    return qs.exists()
