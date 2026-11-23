import json
from django.conf import settings
from django.db import models

from apps.documents.models._base import TenantNumbered


class TaxonomyTerm(TenantNumbered):
    """
    Sub-module 13.5 Metadata & Indexing: Controlled Vocabulary & Thesauri
    Standardized enterprise taxonomy terms with hierarchical parent-child relationships,
    synonym lists for search expansion, and cross-reference code mappings.
    """
    NUMBER_PREFIX = "DTAX"

    CATEGORY_CHOICES = [
        ("general", "General Enterprise Taxonomy"),
        ("legal", "Legal & Contracts Thesaurus"),
        ("finance", "Financial & Accounting Terms"),
        ("compliance", "Regulatory Compliance & Risk"),
        ("technical", "Engineering & Specifications"),
        ("hr", "Human Resources & Workforce"),
        ("procurement", "Procurement & SCM Thesaurus"),
        ("industry", "Industry Standard Classifications"),
    ]

    CATEGORY_CSS = {
        "general": "badge-info",
        "legal": "badge-amber",
        "finance": "badge-green",
        "compliance": "badge-red",
        "technical": "badge-info",
        "hr": "badge-amber",
        "procurement": "badge-slate",
        "industry": "badge-slate",
    }

    name = models.CharField(max_length=150)
    term_code = models.CharField(max_length=60, help_text="Canonical term code e.g. TAX_CONFIDENTIALITY")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="general", db_index=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        db_index=True,
    )
    description = models.TextField(blank=True)
    synonyms_json = models.TextField(
        default="[]",
        help_text="JSON list of alternate labels and synonyms e.g. ['NDA', 'Proprietary Information']",
    )
    external_code = models.CharField(
        max_length=100,
        blank=True,
        help_text="Cross-reference standard code e.g. ISO 27001 / NAICS / UNSPSC",
    )
    is_governed = models.BooleanField(
        default=True,
        help_text="Governed term requiring admin approval to alter",
    )
    usage_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_taxonomy_terms",
    )

    class Meta:
        ordering = ["category", "name"]
        verbose_name = "Taxonomy Term"
        verbose_name_plural = "Taxonomy Terms"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dtax_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "category", "term_code"], name="doc_dtax_tnt_cat_code_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "category", "is_active"], name="doc_dtax_tnt_cat_act_idx"),
        ]

    def __str__(self):
        return f"{self.name} [{self.term_code}]"

    @property
    def category_badge(self):
        return self.CATEGORY_CSS.get(self.category, "badge-info")

    @property
    def status_badge(self):
        return "badge-green" if self.is_active else "badge-slate"

    @property
    def active_children(self):
        return [c for c in self.children.all() if c.is_active]

    @property
    def parsed_synonyms(self):
        try:
            val = json.loads(self.synonyms_json)
            return val if isinstance(val, list) else []
        except (ValueError, TypeError):
            return []
