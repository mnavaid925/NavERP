"""CRM 1.7 Finance & Billing Management — Expenses models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# -------------------------------------------------- 1.7 Finance & Billing Management
class Expense(TenantNumbered):
    """A deal/project-related cost (1.7) used to derive true opportunity profit margin."""

    NUMBER_PREFIX = "EXP"

    CATEGORY_CHOICES = [
        ("travel", "Travel"),
        ("meals", "Meals"),
        ("software", "Software"),
        ("accommodation", "Accommodation"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses")
    project = models.ForeignKey("crm.CrmProject", on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="travel")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency_code = models.CharField(max_length=3, default="USD")  # core.Currency master not built yet
    expense_date = models.DateField()
    description = models.TextField(blank=True)
    receipt = models.FileField(upload_to="crm/receipts/%Y/%m/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_submitted_expenses")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_approved_expenses")
    is_billable = models.BooleanField(
        default=False,
        help_text="Billable costs are re-billed to the client, so they are excluded from the deal's true margin.")

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_exp_tnt_status_idx"),
            models.Index(fields=["tenant", "expense_date"], name="crm_exp_tnt_date_idx"),
            models.Index(fields=["tenant", "opportunity"], name="crm_exp_tnt_opp_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.get_category_display()} {self.amount}"
