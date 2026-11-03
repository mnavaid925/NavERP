from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class PlatformEnvironment(TenantNumbered):
    NUMBER_PREFIX = "EENV"

    ENV_TYPE_CHOICES = [
        ("production", "Production Live"),
        ("staging", "Staging / Pre-Production"),
        ("sandbox", "Developer / QA Sandbox"),
        ("preview", "Feature Branch Preview"),
        ("disaster_recovery", "Disaster Recovery"),
    ]

    REGION_CHOICES = [
        ("us-east-1", "US East (N. Virginia)"),
        ("us-west-2", "US West (Oregon)"),
        ("eu-central-1", "Europe (Frankfurt)"),
        ("eu-west-1", "Europe (Ireland)"),
        ("ap-southeast-1", "Asia Pacific (Singapore)"),
        ("local_cluster", "Local / On-Premise Cluster"),
    ]

    SLOT_CHOICES = [
        ("blue", "Blue Slot (Active Live)"),
        ("green", "Green Slot (Active Live)"),
        ("single_slot", "Standard Single Slot"),
    ]

    STATUS_CHOICES = [
        ("healthy", "Healthy / Online"),
        ("deploying", "Deployment In Progress"),
        ("maintenance", "Maintenance Window"),
        ("degraded", "Degraded Performance"),
        ("decommissioned", "Decommissioned"),
    ]

    RESOURCE_TIER_CHOICES = [
        ("starter", "Starter (Shared Container)"),
        ("standard", "Standard Production"),
        ("high_performance", "High Performance (Multi-Node)"),
        ("enterprise_dedicated", "Enterprise Dedicated HA"),
    ]

    name = models.CharField(max_length=255, help_text="Environment name e.g. Production Cluster")
    env_type = models.CharField(max_length=30, choices=ENV_TYPE_CHOICES, default="sandbox")
    storefront = models.ForeignKey(
        "ecommerce.StorefrontInstance",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="environments",
    )
    cluster_region = models.CharField(max_length=50, choices=REGION_CHOICES, default="us-east-1")
    base_url = models.URLField(max_length=500, help_text="Canonical URL or preview URL")
    current_active_slot = models.CharField(max_length=20, choices=SLOT_CHOICES, default="single_slot")
    is_sandbox_locked = models.BooleanField(default=False, help_text="Prevents live payment capture and emails")
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="healthy")
    resource_tier = models.CharField(max_length=30, choices=RESOURCE_TIER_CHOICES, default="standard")
    last_health_check_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecommerce_eenv_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "env_type", "status"], name="idx_eenv_ten_type_stat"),
            models.Index(fields=["tenant", "current_active_slot"], name="idx_eenv_ten_slot"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_env_type_display()}) [{self.number}]"
