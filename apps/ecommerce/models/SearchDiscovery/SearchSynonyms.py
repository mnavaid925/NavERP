from django.core.exceptions import ValidationError
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class SearchSynonym(TenantNumbered):
    NUMBER_PREFIX = "ESYM"

    SYNONYM_TYPE_CHOICES = [
        ("two_way", "Two-Way Equivalent"),
        ("one_way", "One-Way Directional"),
        ("replacement", "Explicit Replacement"),
    ]

    name = models.CharField(
        max_length=120,
        help_text="Administrative label for this synonym rule",
    )
    synonym_type = models.CharField(
        max_length=20,
        choices=SYNONYM_TYPE_CHOICES,
        default="two_way",
    )
    root_term = models.CharField(
        max_length=120,
        db_index=True,
        help_text="Root trigger keyword for one-way and replacement rules; primary anchor for two-way",
    )
    synonyms = models.TextField(
        help_text="Comma-separated list of synonym terms, e.g. 'couch, sofa, settee'",
    )
    is_active = models.BooleanField(default=True)
    hit_count = models.PositiveIntegerField(
        default=0,
        help_text="Times this synonym rule has expanded a search query",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["root_term", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_esym_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_active", "synonym_type"],
                name="idx_esym_ten_act_type",
            ),
            models.Index(
                fields=["tenant", "root_term"],
                name="idx_esym_ten_root",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.get_synonym_type_display()})"

    def get_synonym_list(self):
        """Return list of stripped lowercase synonym words."""
        if not self.synonyms:
            return []
        return [term.strip().lower() for term in self.synonyms.split(",") if term.strip()]

    def clean(self):
        super().clean()
        if self.root_term:
            self.root_term = self.root_term.strip().lower()
        terms = self.get_synonym_list()
        if not terms:
            raise ValidationError({"synonyms": "At least one synonym term must be provided."})
        if self.synonym_type == "replacement" and len(terms) > 1:
            raise ValidationError(
                {"synonyms": "Explicit replacement rules must contain exactly one replacement term."}
            )
        self.synonyms = ", ".join(terms)
