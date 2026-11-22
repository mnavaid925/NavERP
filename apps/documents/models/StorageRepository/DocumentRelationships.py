from django.conf import settings
from django.db import models

from apps.documents.models._base import TenantNumbered


class DocumentRelationship(TenantNumbered):
    """Semantic cross-document relationships and bidirectional linkage graph."""

    NUMBER_PREFIX = "DREL"

    RELATIONSHIP_TYPE_CHOICES = (
        ("parent_child", "Parent / Child Document Family"),
        ("supersedes", "Supersedes / Superseded By"),
        ("references", "References / Cited By"),
        ("derived_from", "Derived From (Variant/Draft)"),
        ("contract_exhibit", "Contract Master / Exhibit / SOW"),
        ("supporting_evidence", "Supporting Evidence / Attachment"),
        ("amendment", "Legal Amendment / Addendum"),
    )

    DEPENDENCY_CHOICES = (
        ("informational", "Informational Link"),
        ("contractual", "Contractual Dependency"),
        ("strict_blocking", "Strict Blocking Prerequisite"),
    )

    RELATIONSHIP_TYPE_CSS = {
        "parent_child": "badge-info",
        "supersedes": "badge-amber",
        "references": "badge-slate",
        "derived_from": "badge-info",
        "contract_exhibit": "badge-green",
        "supporting_evidence": "badge-slate",
        "amendment": "badge-amber",
    }

    DEPENDENCY_CSS = {
        "informational": "badge-slate",
        "contractual": "badge-info",
        "strict_blocking": "badge-red",
    }

    source_document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="outgoing_relationships",
        db_index=True,
    )
    target_document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="incoming_relationships",
        db_index=True,
    )
    relationship_type = models.CharField(
        max_length=30,
        choices=RELATIONSHIP_TYPE_CHOICES,
        default="references",
        db_index=True,
    )
    is_bidirectional = models.BooleanField(
        default=True,
        help_text="Displays symmetrically in both documents",
    )
    dependency_level = models.CharField(
        max_length=25,
        choices=DEPENDENCY_CHOICES,
        default="informational",
    )
    description = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_document_relationships",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Document Relationship"
        verbose_name_plural = "Document Relationships"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_drel_ten_num_uniq"),
            models.UniqueConstraint(
                fields=["tenant", "source_document", "target_document", "relationship_type"],
                name="doc_drel_tnt_rel_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "source_document", "relationship_type"], name="doc_drel_tnt_src_rel_idx"),
            models.Index(fields=["tenant", "target_document", "relationship_type"], name="doc_drel_tnt_tgt_rel_idx"),
        ]

    def __str__(self):
        return f"{self.source_document.number} —[{self.get_relationship_type_display()}]→ {self.target_document.number}"

    @property
    def type_badge_class(self):
        return self.RELATIONSHIP_TYPE_CSS.get(self.relationship_type, "badge-slate")

    @property
    def dependency_badge_class(self):
        return self.DEPENDENCY_CSS.get(self.dependency_level, "badge-slate")
