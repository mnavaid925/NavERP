"""SalesRegionalSetting model for 8.19 Master Data & Configuration — Localization & Multi-Language."""
from django.core.exceptions import ValidationError
from django.db import models

from apps.sales.models._base import TenantNumbered


class SalesRegionalSetting(TenantNumbered):
    """Regional commercial configurations, localized tax display, and statutory compliance rules."""

    NUMBER_PREFIX = "SRG"

    REGION_CODE_CHOICES = [
        ("NA", "North America (US / CA)"),
        ("EMEA", "Europe, Middle East & Africa"),
        ("APAC", "Asia-Pacific"),
        ("DACH", "DACH (Germany, Austria, Switzerland)"),
        ("UK", "United Kingdom"),
        ("LATAM", "Latin America"),
        ("GLOBAL", "Global Default"),
    ]

    DATE_FORMAT_CHOICES = [
        ("YYYY-MM-DD", "ISO 8601 (YYYY-MM-DD)"),
        ("MM/DD/YYYY", "US Standard (MM/DD/YYYY)"),
        ("DD/MM/YYYY", "EU / British (DD/MM/YYYY)"),
        ("DD.MM.YYYY", "German / Swiss (DD.MM.YYYY)"),
    ]

    NUMBER_FORMAT_CHOICES = [
        ("1,234.56", "Comma thousand, period decimal (1,234.56)"),
        ("1.234,56", "Period thousand, comma decimal (1.234,56)"),
        ("1 234,56", "Space thousand, comma decimal (1 234,56)"),
    ]

    TAX_DISPLAY_CHOICES = [
        ("tax_exclusive", "Tax Exclusive (Subtotal + Tax = Total)"),
        ("tax_inclusive", "Tax Inclusive (Prices include VAT/GST)"),
    ]

    COMPLIANCE_CHOICES = [
        ("standard", "Standard Commercial Terms"),
        ("gdpr_commercial", "GDPR Commercial & Data Privacy Compliant"),
        ("sox_revenue", "SOX 404 & ASC 606 Revenue Recognition Compliant"),
        ("consumer_protection", "Consumer Rights & Statutory Cooling-Off Compliant"),
        ("export_control", "EAR / ITAR Commercial Trade & Export Compliant"),
    ]

    name = models.CharField(
        max_length=150,
        help_text="Regional profile label, e.g. 'EMEA Commercial Profile' or 'DACH Enterprise'",
    )
    region_code = models.CharField(
        max_length=20,
        choices=REGION_CODE_CHOICES,
        default="GLOBAL",
        help_text="Standard commercial sales territory or economic zone",
    )
    primary_currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="Base currency for regional quotes, orders, and targets",
    )
    supported_currencies = models.JSONField(
        default=list,
        blank=True,
        help_text="Allowed billing currencies in this territory, e.g. ['USD', 'EUR', 'GBP']",
    )
    date_format = models.CharField(
        max_length=20,
        choices=DATE_FORMAT_CHOICES,
        default="YYYY-MM-DD",
        help_text="Display date format for proposals, quotes, and schedules",
    )
    number_format = models.CharField(
        max_length=20,
        choices=NUMBER_FORMAT_CHOICES,
        default="1,234.56",
        help_text="Localized decimal and thousand separators",
    )
    tax_display_mode = models.CharField(
        max_length=20,
        choices=TAX_DISPLAY_CHOICES,
        default="tax_exclusive",
        help_text="Whether proposal subtotals are tax exclusive or inclusive of VAT/GST",
    )
    default_quote_terms = models.TextField(
        blank=True,
        default="",
        help_text="Standard payment terms, warranty, and commercial terms appended to proposals",
    )
    statutory_disclaimer = models.TextField(
        blank=True,
        default="",
        help_text="Mandatory legal disclaimer, cooling-off notices, and statutory disclosures",
    )
    compliance_framework = models.CharField(
        max_length=30,
        choices=COMPLIANCE_CHOICES,
        default="standard",
        help_text="Commercial regulatory and compliance standard applied in this region",
    )
    cooling_off_days = models.PositiveIntegerField(
        default=14,
        help_text="Statutory cancellation or cooling-off period in days",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the fallback regional profile for quotes without a specified region",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this regional configuration is active",
    )

    class Meta:
        ordering = ["-is_default", "region_code", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_srg_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "region_code"],
                name="sales_srg_tnt_reg_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_default", "is_active"], name="sales_srg_tnt_def_idx"),
            models.Index(fields=["tenant", "region_code"], name="sales_srg_code_idx"),
            models.Index(fields=["tenant", "compliance_framework"], name="sales_srg_cmpl_idx"),
        ]

    def clean(self):
        super().clean()
        self.primary_currency = self.primary_currency.upper().strip()
        if not isinstance(self.supported_currencies, list):
            raise ValidationError({"supported_currencies": "Supported currencies must be a JSON array of currency codes."})
        if self.is_default and not self.is_active:
            raise ValidationError({"is_default": "The default regional configuration must be active."})

    def save(self, *args, **kwargs):
        if self.is_default and self.tenant_id:
            SalesRegionalSetting.objects.filter(
                tenant_id=self.tenant_id, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.name} ({self.region_code} - {self.primary_currency})"
