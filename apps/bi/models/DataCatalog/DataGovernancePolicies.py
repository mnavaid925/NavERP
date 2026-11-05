from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class DataGovernancePolicy(TenantNumbered):
    NUMBER_PREFIX = "BGOV"

    POLICY_TYPE_CHOICES = [
        ("regulatory_compliance", "Regulatory Compliance Mandate"),
        ("retention_archival", "Data Retention & Archival Schedule"),
        ("sensitivity_classification", "Data Sensitivity & Tagging Policy"),
        ("data_masking", "Column Masking & Redaction Rule"),
        ("acceptable_use", "Data Sharing & Acceptable Use Policy"),
        ("sox_financial_control", "SOX Financial Internal Control"),
    ]

    REGULATORY_FRAMEWORK_CHOICES = [
        ("gdpr_eu", "GDPR - European Privacy Regulation"),
        ("hipaa_healthcare", "HIPAA - Health Information Privacy"),
        ("sox_financial", "SOX - Sarbanes-Oxley Financial Reporting"),
        ("pci_dss", "PCI-DSS - Payment Card Security"),
        ("ccpa_cpra", "CCPA/CPRA - California Consumer Privacy"),
        ("iso_27001", "ISO 27001 - Security Standards"),
        ("internal_standard", "Internal Enterprise Standard"),
    ]

    ENFORCEMENT_LEVEL_CHOICES = [
        ("advisory_informational", "Advisory / Informational Guidelines"),
        ("audit_warning", "Audit Warning / Compliance Alert"),
        ("strict_blocking", "Strict Blocking / Enforcement Gate"),
        ("automated_masking", "Automated Dynamic Column Masking"),
    ]

    MASKING_ALGORITHM_CHOICES = [
        ("none", "No Masking (Plaintext)"),
        ("full_redaction", "Full Redaction (***)"),
        ("partial_mask_email_phone", "Partial Masking (Email / Phone)"),
        ("hash_sha256", "Cryptographic SHA-256 Hash"),
        ("tokenization", "Irreversible Tokenization"),
        ("nullify", "Nullify / Blank Value"),
    ]

    name = models.CharField(max_length=180)
    code = models.SlugField(max_length=80)
    policy_type = models.CharField(
        max_length=30,
        choices=POLICY_TYPE_CHOICES,
        default="regulatory_compliance",
    )
    regulatory_framework = models.CharField(
        max_length=30,
        choices=REGULATORY_FRAMEWORK_CHOICES,
        default="gdpr_eu",
    )
    enforcement_level = models.CharField(
        max_length=30,
        choices=ENFORCEMENT_LEVEL_CHOICES,
        default="audit_warning",
    )
    retention_period_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Statutory retention duration in days (e.g. 2555 days for 7 years SOX)",
    )
    masking_algorithm = models.CharField(
        max_length=30,
        choices=MASKING_ALGORITHM_CHOICES,
        default="none",
    )

    policy_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_governance_policies",
        help_text="Compliance officer or data protection officer (DPO) accountable for policy",
    )

    effective_date = models.DateField(help_text="Date from which this policy takes effect")
    expiration_date = models.DateField(null=True, blank=True, help_text="Optional sunset / expiration date")
    review_frequency_days = models.PositiveIntegerField(
        default=365,
        help_text="Mandatory policy review cadence in days (default: annual / 365 days)",
    )
    last_reviewed_at = models.DateTimeField(null=True, blank=True)

    compliance_notes = models.TextField(
        blank=True,
        help_text="Legal citations, audit guidance, and statutory references",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_data_governance_policy"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="bi_bgov_tenant_code_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bgov_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "policy_type"], name="idx_bgov_ten_ptype"),
            models.Index(fields=["tenant", "regulatory_framework"], name="idx_bgov_ten_rframe"),
            models.Index(fields=["tenant", "enforcement_level"], name="idx_bgov_ten_enforce"),
            models.Index(fields=["tenant", "is_active"], name="idx_bgov_ten_active"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name}"

    def get_absolute_url(self):
        return reverse("bi:data_governance_policy_detail", kwargs={"pk": self.pk})
