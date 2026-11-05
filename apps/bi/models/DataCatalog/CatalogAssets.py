from decimal import Decimal
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class CatalogAsset(TenantNumbered):
    NUMBER_PREFIX = "BCAT"

    DOMAIN_CHOICES = [
        ("finance", "Finance & Accounting"),
        ("sales", "Sales & CRM"),
        ("supply_chain", "Supply Chain & Inventory"),
        ("procurement", "Procurement & Sourcing"),
        ("human_resources", "Human Resources"),
        ("customer", "Customer & Marketing"),
        ("operations", "Operations & Manufacturing"),
        ("cross_domain", "Cross-Domain Enterprise"),
    ]

    ASSET_TYPE_CHOICES = [
        ("warehouse_table", "Warehouse Table / View"),
        ("semantic_model", "Semantic Layer Model"),
        ("golden_record", "MDM Golden Record"),
        ("metric", "Calculated Measure / KPI"),
        ("report", "Operational / Regulatory Report"),
        ("pipeline", "Ingestion / ETL Pipeline"),
        ("source_dataset", "Raw Source Connector Dataset"),
    ]

    SENSITIVITY_CHOICES = [
        ("public", "Public - Unrestricted Access"),
        ("internal", "Internal - Standard Organization Access"),
        ("confidential", "Confidential - Restricted Business Need"),
        ("restricted_pii", "Restricted PII - Personal Data (GDPR/CCPA)"),
        ("highly_sensitive_pci_phi", "Highly Sensitive - Financial / Health (PCI/PHI)"),
    ]

    TIER_CHOICES = [
        ("tier_1_mission_critical", "Tier 1 - Mission-Critical Enterprise Data"),
        ("tier_2_production_core", "Tier 2 - Production Core Analytics"),
        ("tier_3_departmental", "Tier 3 - Departmental / Team Ad-Hoc"),
        ("tier_4_sandbox", "Tier 4 - Exploratory / Sandbox"),
    ]

    CERTIFICATION_STATUS_CHOICES = [
        ("draft", "Draft / Unreviewed"),
        ("under_review", "Under Stewardship Review"),
        ("certified", "Certified Production-Ready"),
        ("endorsed", "Peer Endorsed"),
        ("deprecated", "Deprecated / Retiring"),
        ("quarantined", "Quarantined / Quality Breach"),
    ]

    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=80)
    domain = models.CharField(max_length=30, choices=DOMAIN_CHOICES, default="cross_domain")
    asset_type = models.CharField(max_length=30, choices=ASSET_TYPE_CHOICES, default="warehouse_table")

    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="catalog_assets",
        help_text="Underlying warehouse storage table or analytical mart view",
    )
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="catalog_assets",
        help_text="Governed semantic model representation",
    )
    golden_record = models.ForeignKey(
        "bi.MdmGoldenRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="catalog_assets",
        help_text="Underlying authoritative MDM golden master record",
    )
    business_glossary_term = models.ForeignKey(
        "bi.BusinessGlossaryTerm",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="catalog_assets",
        help_text="Governed business glossary definition",
    )

    data_steward = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stewarded_catalog_assets",
        help_text="Designated data steward accountable for dataset accuracy and compliance",
    )
    owning_org_unit = models.ForeignKey(
        "core.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="catalog_assets",
        help_text="Owning business unit or operational department",
    )

    data_sensitivity = models.CharField(max_length=30, choices=SENSITIVITY_CHOICES, default="internal")
    enterprise_tier = models.CharField(max_length=30, choices=TIER_CHOICES, default="tier_2_production_core")
    certification_status = models.CharField(max_length=30, choices=CERTIFICATION_STATUS_CHOICES, default="draft")

    deprecation_replacement = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deprecated_assets_replaced",
        help_text="Recommended replacement asset if this dataset is deprecated",
    )

    schema_columns_json = models.JSONField(default=list, blank=True, help_text="List of schema columns: [{name, data_type, is_nullable, description, is_pii}]")
    search_tags_json = models.JSONField(default=list, blank=True, help_text="Search keywords, labels, and analytical domain tags")
    view_count = models.PositiveIntegerField(default=0, help_text="Number of catalog inspection views and query executions")
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("5.00"))],
        help_text="Average community rating from 1.00 to 5.00 stars",
    )

    quality_scorecard = models.ForeignKey(
        "bi.DataQualityScorecard",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="catalog_assets",
        help_text="Latest data quality scorecard health assessment",
    )

    description = models.TextField(blank=True, help_text="Comprehensive overview of dataset contents, grain, and business context")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_catalog_asset"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="bi_bcat_tenant_code_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bcat_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "domain"], name="idx_bcat_ten_dom"),
            models.Index(fields=["tenant", "asset_type"], name="idx_bcat_ten_atype"),
            models.Index(fields=["tenant", "data_sensitivity"], name="idx_bcat_ten_sens"),
            models.Index(fields=["tenant", "enterprise_tier"], name="idx_bcat_ten_tier"),
            models.Index(fields=["tenant", "certification_status"], name="idx_bcat_ten_cert"),
            models.Index(fields=["tenant", "is_active"], name="idx_bcat_ten_active"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name}"

    def get_absolute_url(self):
        return reverse("bi:catalog_asset_detail", kwargs={"pk": self.pk})
