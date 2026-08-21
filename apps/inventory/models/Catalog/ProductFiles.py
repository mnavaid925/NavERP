"""Inventory 5.1 Product & Catalog Management — ProductFile.

**Product Imagery & Documents** bullet: photos, safety sheets and manuals attached to a product.
One table with a ``kind`` covers both halves of the bullet deliberately — an image, a safety data
sheet and a manual are the same object (a titled artifact pointing at a product) differing only by
label and audience, and splitting them would fork the upload path, the primary-image rule and the
CRUD surface to express one choice field's worth of difference.

The pointer is **file OR url**: an uploaded artifact for what the workspace owns, a link for what
it merely references. ``clean()`` insists on at least one so a detail page never renders a card
that goes nowhere. Uploads follow the crm pattern (``Expenses.receipt``,
``DocumentVersion.file``): a dated ``upload_to`` under MEDIA_ROOT, with this module's OWN
allowlist enforced in ``clean()`` — deliberately a CURATED SUBSET of the core document tooling's
``ALLOWED_DOC_EXTENSIONS``: product artifacts are images and documents opened directly in a
browser or PDF reader, so archives (``.zip``) are excluded; the size cap stays with the core
constant, enforced at the form boundary.

``is_primary`` picks the thumbnail; ``save()`` demotes the item's other primary rows so there is
exactly one per product — the same auto-demote discipline as HRM 3.25's EmergencyContact.
"""
import os

from django.core.exceptions import ValidationError

from apps.inventory.models._base import *  # noqa: F401,F403


class ProductFile(TenantOwned):
    """One image or document attached to a product."""

    KIND_CHOICES = [
        ("photo", "Photo"),
        ("safety_sheet", "Safety Sheet"),
        ("manual", "Manual"),
        ("datasheet", "Datasheet"),
        ("certificate", "Certificate"),
        ("other", "Other"),
    ]
    #: Extensions accepted for UPLOADS. A link is not constrained by this — it points wherever it
    #: points — but a stored file should stay inside formats a browser or PDF reader opens.
    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp",
                          ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"}

    item = models.ForeignKey(
        "scm.Item", on_delete=models.CASCADE, related_name="catalog_files",
        help_text="The product this file or link documents")
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="photo")
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="inventory/products/%Y/%m/", blank=True, null=True)
    url = models.URLField(blank=True, help_text="External link — used when no file is uploaded")
    is_primary = models.BooleanField(default=False,
                                     help_text="The product's cover image; saving a new primary "
                                               "demotes the previous one")

    class Meta:
        ordering = ["item_id", "-is_primary", "kind", "title"]
        indexes = [
            models.Index(fields=["tenant", "item"], name="inv_pfl_tnt_item_idx"),
            # The kind dropdown filter and the overview's recent-files sort are both per-tenant
            # hot paths; without these they full-scan the tenant's range.
            models.Index(fields=["tenant", "kind"], name="inv_pfl_tnt_kind_idx"),
            models.Index(fields=["tenant", "created_at"], name="inv_pfl_tnt_created_idx"),
        ]

    def clean(self):
        errors = {}
        if self.item_id and self.item.tenant_id != self.tenant_id:
            errors["item"] = "That item belongs to another workspace."
        if not self.file and not self.url:
            # Keyed on a field the form actually has, so it renders instead of 500ing.
            errors["file"] = "Attach a file or paste a link — at least one is required."
        if self.file:
            ext = os.path.splitext(self.file.name)[1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                errors["file"] = f"Files of type '{ext or '(none)'}' are not allowed."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.is_primary and self.item_id:
            type(self).objects.filter(
                tenant_id=self.tenant_id, item_id=self.item_id, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    @property
    def href(self):
        """Where this artifact lives — the uploaded file when there is one, else the link."""
        return self.file.url if self.file else (self.url or "")

    def __str__(self):
        sku = self.item.sku if self.item_id else "?"
        return f"{sku} · {self.title}"
