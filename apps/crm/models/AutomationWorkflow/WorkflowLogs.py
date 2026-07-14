"""CRM 1.10 Automation & Workflow Engine — WorkflowLogs models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class WorkflowLog(models.Model):
    """Immutable append-only fire-record for a WorkflowRule execution (1.10)."""

    STATUS_CHOICES = [("success", "Success"), ("failed", "Failed"), ("skipped", "Skipped")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    rule = models.ForeignKey("crm.WorkflowRule", on_delete=models.SET_NULL, null=True, related_name="logs")
    record_label = models.CharField(max_length=255)
    fired_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="success")
    error_msg = models.TextField(blank=True)

    class Meta:
        ordering = ["-fired_at"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_wfl_tnt_status_idx"),
            models.Index(fields=["tenant", "fired_at"], name="crm_wfl_tnt_fired_idx"),
            # rule detail shows this rule's recent logs; (tenant, rule, -fired_at) makes it a range scan (perf-review).
            models.Index(fields=["tenant", "rule", "-fired_at"], name="crm_wfl_tnt_rule_fired_idx"),
        ]

    def __str__(self):
        return f"{self.record_label} · {self.status}"
