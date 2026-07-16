"""tenants — HealthMetric models (split from apps/tenants/models.py)."""
from apps.tenants.models._base import *  # noqa: F401,F403


class HealthMetric(models.Model):
    METRIC_CHOICES = [
        ("users", "Active Users"),
        ("storage_mb", "Storage (MB)"),
        ("api_calls", "API Calls"),
        ("db_rows", "DB Rows"),
        ("uptime_pct", "Uptime %"),
    ]
    STATUS_CHOICES = [("ok", "OK"), ("warning", "Warning"), ("critical", "Critical")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="health_metrics", db_index=True)
    metric = models.CharField(max_length=20, choices=METRIC_CHOICES)
    value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ok")
    recorded_at = models.DateTimeField(null=True, blank=True)  # system-set, out of forms (L22)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "metric", "-created_at"], name="health_tenant_metric_idx"),
        ]

    def __str__(self):
        return f"{self.get_metric_display()}: {self.value}"
