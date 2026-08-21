"""Inventory 5.1 Product & Catalog Management — ProductFile form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import _reject_foreign
from apps.inventory.models import ProductFile


class ProductFileForm(TenantModelForm):
    """One image or document. Both pointers stay optional ON the form — the model's ``clean()``
    insists on at least one, so its error lands on ``file`` (a field this form has) and renders.
    The crafted-POST re-check covers the one tenant-scoped FK."""

    class Meta:
        model = ProductFile
        fields = ["item", "kind", "title", "file", "url", "is_primary"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item"])
        return cleaned
