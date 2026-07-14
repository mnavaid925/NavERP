"""CRM 1.8 Project & Delivery Management — Projects models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# -------------------------------------------- 1.8 Project & Delivery Management (Post-Sale)
class CrmProject(TenantNumbered):
    """A post-sale delivery project (1.8), often auto-created from a won Opportunity."""

    NUMBER_PREFIX = "PRJ"

    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("active", "Active"),
        ("on_hold", "On Hold"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    name = models.CharField(max_length=255)
    account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_projects")
    source_opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_projects")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planning")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_projects")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_prj_tnt_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_prj_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"

    @property
    def progress_pct(self):
        """Completed milestones ÷ total, as a 0–100 int. Uses the list view's ``ms_total``/
        ``ms_done`` annotations when present (no N+1); falls back to a count on the detail page."""
        total = getattr(self, "ms_total", None)
        done = getattr(self, "ms_done", None)
        if total is None:
            total = self.milestones.count()
            done = self.milestones.filter(status="completed").count()
        return round(done * 100 / total) if total else 0

    @property
    def is_overdue(self):
        return bool(self.end_date and self.status not in ("completed", "cancelled")
                    and self.end_date < timezone.localdate())
