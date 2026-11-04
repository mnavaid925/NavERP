from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class MdmReferenceCode(TenantNumbered):
    NUMBER_PREFIX = "BMRD"

    STATUS_CHOICES = [
        ("draft", "Draft / Under Review"),
        ("active", "Active & Canonical"),
        ("deprecated", "Deprecated (Do Not Use for New Records)"),
        ("superseded", "Superseded by Newer Standard"),
        ("inactive", "Inactive"),
    ]

    code_set = models.CharField(
        max_length=80,
        db_index=True,
        help_text="Grouping code set, e.g. country_codes, currency_codes, uom_codes, payment_terms",
    )
    canonical_code = models.CharField(
        max_length=60,
        db_index=True,
        help_text="Canonical standardized enterprise code, e.g. USA, EUR, KGM, NET30",
    )
    canonical_name = models.CharField(max_length=200)

    source_system = models.CharField(
        max_length=80,
        blank=True,
        help_text="External or feeder system source, e.g. crm_sales, sap_erp, iso_standard",
    )
    source_code = models.CharField(
        max_length=80,
        blank=True,
        help_text="Original code in the source system",
    )
    category = models.CharField(max_length=80, blank=True)

    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="active")
    superseded_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="superseded_codes",
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    attributes_json = models.JSONField(default=dict)

    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_mdm_reference_code"
        ordering = ["code_set", "canonical_code", "source_system"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code_set", "canonical_code", "source_system", "source_code"],
                name="bi_bmrd_ten_cset_ccode_src_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bmrd_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "code_set"], name="idx_bmrd_ten_cset"),
            models.Index(fields=["tenant", "canonical_code"], name="idx_bmrd_ten_ccode"),
            models.Index(fields=["tenant", "status"], name="idx_bmrd_ten_status"),
            models.Index(fields=["tenant", "source_system", "source_code"], name="idx_bmrd_ten_src"),
            models.Index(fields=["tenant", "is_active"], name="idx_bmrd_ten_active"),
        ]

    def __str__(self):
        source_info = f" [{self.source_system}:{self.source_code}]" if self.source_system else ""
        return f"{self.code_set} / {self.canonical_code} - {self.canonical_name}{source_info}"

    def get_absolute_url(self):
        return reverse("bi:mdm_reference_code_detail", kwargs={"pk": self.pk})
