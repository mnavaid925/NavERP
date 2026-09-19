"""core — 0.10 bullet 3: Numbering & Sequence Management.

**Allocation is NOT here, and must not be.** `apps.core.utils.next_number()` already mints every
per-tenant document number in the repo, and `TenantNumbered` calls it for every PO/PR/RFQ/GRN/SO/… A
second allocator would be a second source of truth for the same counter — the L36 mistake.

So this is the CONFIG and RECONCILIATION register: the intended prefix, padding and reset rule for a
document kind, plus a computed check of whether that prefix is actually in use by any model's
`NUMBER_PREFIX`. That check is the useful part — it catches a scheme configured with a prefix no
model mints, or a model minting a prefix with no scheme behind it.
"""
from apps.core.models._base import *  # noqa: F401,F403


class NumberingScheme(models.Model):
    """The intended format for one document kind. Allocation stays in `next_number()`."""

    RESET_CHOICES = [
        ("never", "Never resets"),
        ("yearly", "Resets each year"),
        ("monthly", "Resets each month"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="numbering_schemes", db_index=True)
    document_kind = models.CharField(max_length=150, help_text="e.g. 'Purchase Order'.")
    prefix = models.CharField(max_length=20, help_text="e.g. 'PO' — matches TenantNumbered.NUMBER_PREFIX.")
    padding_width = models.PositiveIntegerField(default=5)
    reset_rule = models.CharField(max_length=10, choices=RESET_CHOICES, default="never")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["document_kind"]
        unique_together = ("tenant", "prefix")
        indexes = [models.Index(fields=["tenant", "prefix"], name="numscheme_tenant_prefix_idx")]

    def __str__(self):
        return f"{self.document_kind} ({self.prefix}-{'0' * self.padding_width}1)"
