from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class BusinessGlossaryTerm(TenantNumbered):
    NUMBER_PREFIX = "BGLO"

    DOMAIN_CATEGORY_CHOICES = [
        ("finance", "Finance & Accounting"),
        ("sales", "Sales & Commercial"),
        ("marketing", "Marketing & Demand Gen"),
        ("hr", "Human Resources & People"),
        ("supply_chain", "Supply Chain & Inventory"),
        ("operations", "Operations & Manufacturing"),
        ("general", "General Enterprise"),
    ]

    CERTIFICATION_STATUS_CHOICES = [
        ("draft", "Draft / In Development"),
        ("in_review", "Under Review & Validation"),
        ("certified", "Certified Corporate Standard"),
        ("deprecated", "Deprecated / Superseded"),
    ]

    name = models.CharField(max_length=150, help_text="Canonical business term title")
    code = models.SlugField(max_length=50, help_text="Unique term identifier slug")
    domain_category = models.CharField(
        max_length=30,
        choices=DOMAIN_CATEGORY_CHOICES,
        default="finance",
        help_text="Functional enterprise business domain",
    )

    short_definition = models.CharField(
        max_length=300,
        help_text="Executive one-line definition",
    )
    full_definition = models.TextField(
        blank=True,
        help_text="Comprehensive corporate standard definition",
    )
    calculation_rule = models.TextField(
        blank=True,
        help_text="Prose business rule or formula narrative",
    )
    synonyms = models.CharField(
        max_length=255,
        blank=True,
        help_text="Alternative names or acronyms (comma-separated)",
    )

    steward = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_glossary_terms_stewarded",
        help_text="Data steward responsible for business term accuracy",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_glossary_terms",
        help_text="Owning organizational business unit",
    )

    certification_status = models.CharField(
        max_length=25,
        choices=CERTIFICATION_STATUS_CHOICES,
        default="draft",
    )
    certified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    certified_at = models.DateTimeField(null=True, blank=True)
    certification_notes = models.TextField(blank=True)

    related_terms = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=True,
        help_text="Related or complementary business glossary terms",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_business_glossary_term"
        ordering = ["domain_category", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="bi_bglo_tenant_code_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bglo_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "domain_category"], name="idx_bglo_ten_domain"),
            models.Index(fields=["tenant", "certification_status"], name="idx_bglo_ten_cert"),
            models.Index(fields=["tenant", "is_active"], name="idx_bglo_ten_active"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:business_glossary_term_detail", kwargs={"pk": self.pk})
