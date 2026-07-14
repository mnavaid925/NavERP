"""Accounting 2.9 Project/Job Costing — Projects models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ============================================================ 2.9 Project / Job Costing
class Project(TenantNumbered):
    """A costing/billing project (job). Actuals are DERIVED from posted ``JobCostEntry`` rows."""

    NUMBER_PREFIX = "PRJ"
    BILLING_CHOICES = [("fixed", "Fixed Price"), ("time_materials", "Time & Materials"), ("milestone", "Milestone")]
    STATUS_CHOICES = [("planning", "Planning"), ("active", "Active"), ("on_hold", "On Hold"), ("closed", "Closed")]

    name = models.CharField(max_length=255)
    client = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="costing_projects")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="costing_projects")
    billing_method = models.CharField(max_length=16, choices=BILLING_CHOICES, default="time_materials")
    budget_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="planning")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_prj_tenant_status_idx")]

    def _posted_sum(self, kind):
        from django.db.models import Sum
        return self.cost_entries.filter(status="posted", kind=kind).aggregate(s=Sum("amount"))["s"] or ZERO

    def actual_cost(self):
        return self._posted_sum("cost")

    def actual_revenue(self):
        return self._posted_sum("revenue")

    def budget_variance(self):
        return (self.budget_amount or ZERO) - self.actual_cost()

    def margin(self):
        return self.actual_revenue() - self.actual_cost()

    def __str__(self):
        return f"{self.number} · {self.name}"
