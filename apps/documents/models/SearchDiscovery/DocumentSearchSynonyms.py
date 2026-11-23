from django.conf import settings
from django.db import models

from apps.documents.models._base import TenantNumbered


class DocumentSearchSynonym(TenantNumbered):
    NUMBER_PREFIX = "DSYN"

    CATEGORY_CHOICES = (
        ("general", "General Synonym"),
        ("acronym", "Acronym / Abbreviation"),
        ("domain", "Domain & Industry Jargon"),
        ("spelling", "Spelling & Variant"),
    )

    CATEGORY_CSS = {
        "general": "badge-info",
        "acronym": "badge-green",
        "domain": "badge-amber",
        "spelling": "badge-slate",
    }

    STATUS_CSS = {
        True: "badge-green",
        False: "badge-slate",
    }

    term = models.CharField(max_length=100, db_index=True)
    synonyms = models.TextField(help_text="Comma-separated synonyms or expansion words")
    category = models.CharField(
        max_length=25,
        choices=CATEGORY_CHOICES,
        default="general",
        db_index=True,
    )
    is_bidirectional = models.BooleanField(
        default=True,
        help_text="True for two-way equivalence; False for one-way term expansion",
    )
    language = models.CharField(max_length=10, default="en")
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_search_synonyms",
    )
    hit_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["term"]
        verbose_name = "Search Synonym"
        verbose_name_plural = "Search Synonyms"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="doc_dsyn_ten_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "term", "language"],
                name="doc_dsyn_tnt_trm_lng_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "category", "is_active"],
                name="doc_dsyn_tnt_cat_act_idx",
            ),
            models.Index(
                fields=["tenant", "is_active", "term"],
                name="doc_dsyn_tnt_act_trm_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} - {self.term} ↔ {self.synonyms[:30]}"

    @property
    def category_badge_class(self):
        return self.CATEGORY_CSS.get(self.category, "badge-slate")

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.is_active, "badge-slate")

    def get_synonym_list(self):
        if not self.synonyms:
            return []
        items = [s.strip() for s in self.synonyms.split(",") if s.strip()]
        return items

    def get_all_terms(self):
        base = [self.term.strip()]
        base.extend(self.get_synonym_list())
        # Dedupe while preserving order
        seen = set()
        out = []
        for t in base:
            tl = t.lower()
            if tl not in seen:
                seen.add(tl)
                out.append(t)
        return out
