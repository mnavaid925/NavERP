import json
from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.documents.models._base import TenantNumbered


class DocumentFolder(TenantNumbered):
    """Hierarchical folder repository taxonomy and smart virtual folder views."""

    NUMBER_PREFIX = "DFLD"

    CLASSIFICATION_CHOICES = (
        ("public", "Public"),
        ("internal", "Internal Use Only"),
        ("confidential", "Confidential"),
        ("restricted", "Strictly Restricted"),
    )

    DOCUMENT_TYPE_CHOICES = (
        ("general", "General Document"),
        ("contract", "Legal Contract & Agreement"),
        ("policy", "Corporate Policy & Governance"),
        ("sop", "Standard Operating Procedure (SOP)"),
        ("report", "Business & Operational Report"),
        ("specification", "Technical Specification"),
        ("proposal", "Commercial Proposal / Pitch"),
        ("technical", "Technical & Engineering Doc"),
    )

    CLASSIFICATION_CSS = {
        "public": "badge-green",
        "internal": "badge-info",
        "confidential": "badge-amber",
        "restricted": "badge-red",
    }

    STATUS_CSS = {
        True: "badge-green",
        False: "badge-slate",
    }

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        db_index=True,
    )
    path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Materialized path e.g. /Corporate/Legal/Contracts/",
    )
    description = models.TextField(blank=True)
    color_code = models.CharField(max_length=20, default="#3B82F6")
    icon_name = models.CharField(max_length=50, default="folder")
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_folders",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_document_folders",
    )
    default_classification = models.CharField(
        max_length=25,
        choices=CLASSIFICATION_CHOICES,
        default="internal",
        db_index=True,
    )
    default_document_type = models.CharField(
        max_length=40,
        choices=DOCUMENT_TYPE_CHOICES,
        default="general",
        blank=True,
    )
    is_virtual = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Dynamic Smart Folder driven by query criteria",
    )
    virtual_criteria_json = models.TextField(blank=True, default="{}")
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["path", "name"]
        verbose_name = "Document Folder"
        verbose_name_plural = "Document Folders"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dfld_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "parent", "slug"], name="doc_dfld_tnt_par_slug_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "parent", "is_active"], name="doc_dfld_tnt_par_act_idx"),
            models.Index(fields=["tenant", "path"], name="doc_dfld_tnt_path_idx"),
        ]

    def __str__(self):
        return f"{self.path or self.name} ({self.number})"

    def save(self, *args, **kwargs):
        old_path = None
        if self.pk:
            old_path = (
                DocumentFolder.objects.filter(pk=self.pk).values_list("path", flat=True).first()
            )

        if not self.slug and self.name:
            self.slug = slugify(self.name)[:160]
        if self.parent:
            parent_path = self.parent.path.rstrip("/") if self.parent.path else f"/{self.parent.slug}"
            self.path = f"{parent_path}/{self.slug}/"
        else:
            self.path = f"/{self.slug}/"
        super().save(*args, **kwargs)

        if old_path and old_path != self.path:
            self._update_children_paths()

    def _update_children_paths(self):
        parent_path = self.path.rstrip("/")
        for child in self.children.all():
            child.path = f"{parent_path}/{child.slug}/"
            DocumentFolder.objects.filter(pk=child.pk).update(path=child.path)
            child._update_children_paths()

    @property
    def classification_badge_class(self):
        return self.CLASSIFICATION_CSS.get(self.default_classification, "badge-info")

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.is_active, "badge-slate")

    @property
    def is_root(self):
        return self.parent_id is None

    @property
    def subfolder_count(self):
        return self.children.filter(is_active=True).count()

    @property
    def criteria_dict(self):
        if not self.virtual_criteria_json:
            return {}
        try:
            return json.loads(self.virtual_criteria_json)
        except (ValueError, TypeError):
            return {}
