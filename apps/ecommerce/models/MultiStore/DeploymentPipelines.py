from django.conf import settings
from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class DeploymentPipeline(TenantNumbered):
    NUMBER_PREFIX = "EDPL"

    STRATEGY_CHOICES = [
        ("blue_green", "Blue-Green Zero Downtime"),
        ("canary_shift", "Canary Traffic Shift"),
        ("rolling_update", "Rolling Update"),
        ("direct_recreate", "Direct Recreate / In-Place"),
        ("dry_run", "Dry Run / Schema Validation Only"),
    ]

    TARGET_SLOT_CHOICES = [
        ("blue", "Blue Slot"),
        ("green", "Green Slot"),
        ("primary", "Primary Single Slot"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending Build"),
        ("building", "Building & Compiling"),
        ("staging_preview", "Staging Preview Ready"),
        ("awaiting_approval", "Awaiting Production Approval"),
        ("promoted_active", "Promoted / Active Live"),
        ("rolled_back", "Rolled Back"),
        ("failed", "Deployment Failed"),
    ]

    environment = models.ForeignKey(
        "ecommerce.PlatformEnvironment",
        on_delete=models.CASCADE,
        related_name="deployment_pipelines",
    )
    release_version = models.CharField(max_length=50, help_text="Release tag or semantic version e.g. v2.4.0")
    git_branch = models.CharField(max_length=100, default="main")
    git_commit_sha = models.CharField(max_length=40, help_text="40-character Git commit hash")
    deployment_strategy = models.CharField(max_length=30, choices=STRATEGY_CHOICES, default="blue_green")
    target_slot = models.CharField(max_length=20, choices=TARGET_SLOT_CHOICES, default="green")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")
    preview_endpoint_url = models.URLField(max_length=500, blank=True, help_text="Pre-promotion test endpoint URL")
    traffic_percentage = models.PositiveSmallIntegerField(default=0, help_text="Traffic percentage cutover 0-100%")
    migration_executed = models.BooleanField(default=False)
    build_duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    deployment_notes = models.TextField(blank=True)
    promoted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promoted_deployments",
    )
    promoted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_edpl_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "deployment_strategy"], name="idx_edpl_ten_stat_strat"),
            models.Index(fields=["tenant", "environment", "created_at"], name="idx_edpl_ten_env_date"),
        ]

    def __str__(self):
        return f"{self.release_version} [{self.status}] ({self.number})"
