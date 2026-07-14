"""Accounting 2.4 Accounts Receivable — PaymentAllocations models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


class PaymentAllocation(models.Model):
    """Cash-application join: applies part of a :class:`Payment` to an Invoice (AR) or Bill (AP).
    Tenant is inherited from ``payment`` (child table)."""

    payment = models.ForeignKey("accounting.Payment", on_delete=models.CASCADE, related_name="allocations")
    invoice = models.ForeignKey("accounting.Invoice", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="allocations")
    bill = models.ForeignKey("accounting.Bill", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="allocations")
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=2)
    discount_taken = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def clean(self):
        # Apply to exactly one document.
        if bool(self.invoice_id) == bool(self.bill_id):
            raise ValidationError("Allocate to exactly one of an invoice or a bill.")

    def __str__(self):
        target = self.invoice_id and self.invoice or self.bill_id and self.bill
        return f"{self.allocated_amount} → {target}"
