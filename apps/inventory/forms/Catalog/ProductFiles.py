"""Inventory 5.1 Product & Catalog Management — ProductFile form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import MAX_UPLOAD_BYTES, TenantUniqueMixin, _reject_foreign
from apps.inventory.models import ProductFile


class ProductFileForm(TenantUniqueMixin, TenantModelForm):
    """One image or document.

    The TenantUniqueMixin is load-bearing even though this model has no unique constraint: its
    ``__init__`` stamps ``instance.tenant`` BEFORE validation, which is what lets the model's
    ``clean()`` foreign-item check pass on CREATE (``crud_create`` only assigns tenant after
    ``is_valid()`` — without the stamp every create would be falsely rejected as cross-tenant).

    Both pointers stay optional ON the form — the model's ``clean()`` insists on at least one, so
    its error lands on ``file`` (a field this form has) and renders. The crafted-POST re-check
    covers the one tenant-scoped FK; the upload cap mirrors the core document tooling.
    """

    class Meta:
        model = ProductFile
        fields = ["item", "kind", "title", "file", "url", "is_primary"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item"])
        uploaded = cleaned.get("file")
        if uploaded and uploaded.size > MAX_UPLOAD_BYTES:
            # Same ceiling and same wording shape as the core document tooling — a tenant user
            # must not be able to stream unbounded files into MEDIA_ROOT.
            self.add_error("file", "File too large. Maximum size is 20 MB.")
        return cleaned
