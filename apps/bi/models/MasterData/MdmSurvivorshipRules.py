from decimal import Decimal
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class MdmSurvivorshipRule(TenantNumbered):
    NUMBER_PREFIX = "BMSR"

    DOMAIN_CHOICES = [
        ("all", "All Domains"),
        ("customer", "Customer Master"),
        ("vendor", "Vendor Master"),
        ("product", "Product Master"),
        ("asset", "Asset Master"),
        ("employee", "Employee Master"),
    ]

    SURVIVORSHIP_STRATEGY_CHOICES = [
        ("source_priority", "Source System Trust Precedence"),
        ("most_recent", "Most Recently Updated Timestamp"),
        ("highest_completeness", "Highest Completeness / Quality Score"),
        ("most_frequent", "Most Frequent Value (Majority Vote)"),
        ("manual_pick", "Manual Data Steward Selection"),
        ("oldest_original", "Oldest Original Value (Earliest Created)"),
    ]
    STRATEGY_CHOICES = SURVIVORSHIP_STRATEGY_CHOICES

    MATCH_ALGORITHM_CHOICES = [
        ("exact", "Exact Deterministic Match"),
        ("fuzzy_levenshtein", "Fuzzy Levenshtein Distance"),
        ("fuzzy_jaro_winkler", "Fuzzy Jaro-Winkler Similarity"),
        ("phonetic_soundex", "Phonetic Soundex / Metaphone"),
        ("token_set_ratio", "Token Set Ratio (Order Independent)"),
        ("rule_expression", "Custom Rule Expression"),
    ]
    MATCH_ALGO_CHOICES = MATCH_ALGORITHM_CHOICES

    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=60)
    domain = models.CharField(max_length=30, choices=DOMAIN_CHOICES, default="all")
    target_field = models.CharField(max_length=100, default="*")
    survivorship_strategy = models.CharField(
        max_length=30,
        choices=SURVIVORSHIP_STRATEGY_CHOICES,
        default="source_priority",
    )
    match_algorithm = models.CharField(
        max_length=30,
        choices=MATCH_ALGORITHM_CHOICES,
        default="exact",
    )
    match_threshold_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("80.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )
    auto_merge_threshold_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("95.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )
    source_priority_list_json = models.JSONField(default=list)
    priority_order = models.PositiveIntegerField(default=10)

    steward = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stewarded_mdm_rules",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_mdm_survivorship_rule"
        ordering = ["priority_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="bi_bmsr_tenant_code_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="bi_bmsr_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "domain"], name="idx_bmsr_ten_dom"),
            models.Index(fields=["tenant", "match_algorithm"], name="idx_bmsr_ten_alg"),
            models.Index(fields=["tenant", "target_field"], name="idx_bmsr_ten_tfield"),
            models.Index(fields=["tenant", "survivorship_strategy"], name="idx_bmsr_ten_strat"),
            models.Index(fields=["tenant", "priority_order"], name="idx_bmsr_ten_porder"),
            models.Index(fields=["tenant", "is_active"], name="idx_bmsr_ten_active"),
        ]

    def __init__(self, *args, **kwargs):
        if "source_precedence_list" in kwargs and "source_priority_list_json" not in kwargs:
            kwargs["source_priority_list_json"] = kwargs.pop("source_precedence_list")
        if kwargs.get("match_algorithm") == "fuzzy_token":
            kwargs["match_algorithm"] = "token_set_ratio"
        super().__init__(*args, **kwargs)

    @property
    def source_precedence_list(self):
        return self.source_priority_list_json

    @source_precedence_list.setter
    def source_precedence_list(self, value):
        self.source_priority_list_json = value

    def __str__(self):
        return f"{self.number} - {self.name} ({self.get_survivorship_strategy_display()})"

    def get_absolute_url(self):
        return reverse("bi:mdm_survivorship_rule_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        if not self.code and self.name:
            from django.utils.text import slugify
            self.code = slugify(self.name)[:60]
        return super().save(*args, **kwargs)
