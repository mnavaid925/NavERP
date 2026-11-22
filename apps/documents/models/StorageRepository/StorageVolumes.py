from decimal import Decimal
from django.db import models

from apps.documents.models._base import TenantNumbered


class StorageVolume(TenantNumbered):
    """Physical and cloud storage repository targets, tiering policies, and quota monitoring."""

    NUMBER_PREFIX = "DSTG"

    BACKEND_TYPE_CHOICES = (
        ("local_filesystem", "Local Server Filesystem"),
        ("network_nas", "Network Attached Storage (NAS / NFS)"),
        ("s3_compatible", "AWS S3 / Compatible Object Storage"),
        ("azure_blob", "Microsoft Azure Blob Storage"),
        ("google_cloud_storage", "Google Cloud Storage (GCS)"),
        ("air_gapped", "Air-Gapped Secure On-Premises SAN"),
    )

    TIER_CHOICES = (
        ("hot", "Hot Tier (High-Speed NVMe/SSD)"),
        ("warm", "Warm Tier (Standard Disk/Object)"),
        ("cold", "Cold Tier (Infrequent Access)"),
        ("glacier_archive", "Archive Tier (Deep Archive/Tape)"),
    )

    COMPRESSION_CHOICES = (
        ("none", "None (Uncompressed)"),
        ("gzip", "Gzip"),
        ("zstandard", "Zstandard (Zstd)"),
    )

    ENCRYPTION_CHOICES = (
        ("none", "None (Plaintext)"),
        ("aes_256", "AES-256 Server-Side"),
        ("kms_managed", "Enterprise KMS Managed Key"),
    )

    TIER_CSS = {
        "hot": "badge-red",
        "warm": "badge-amber",
        "cold": "badge-info",
        "glacier_archive": "badge-slate",
    }

    BACKEND_CSS = {
        "local_filesystem": "badge-slate",
        "network_nas": "badge-info",
        "s3_compatible": "badge-amber",
        "azure_blob": "badge-info",
        "google_cloud_storage": "badge-green",
        "air_gapped": "badge-slate",
    }

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, db_index=True)
    backend_type = models.CharField(
        max_length=30,
        choices=BACKEND_TYPE_CHOICES,
        default="local_filesystem",
        db_index=True,
    )
    tier = models.CharField(
        max_length=25,
        choices=TIER_CHOICES,
        default="hot",
        db_index=True,
    )
    base_path = models.CharField(
        max_length=255,
        help_text="Mount path or bucket/container name",
    )
    region = models.CharField(max_length=50, blank=True)
    endpoint_url = models.CharField(max_length=255, blank=True)
    max_capacity_bytes = models.BigIntegerField(
        default=107374182400,
        help_text="Total storage capacity in bytes (default 100 GB)",
    )
    utilized_bytes = models.BigIntegerField(default=0)
    utilized_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.0"),
    )
    warning_threshold_pct = models.PositiveIntegerField(
        default=85,
        help_text="Warning threshold % for rollover/alerts",
    )
    is_default = models.BooleanField(default=False, db_index=True)
    is_full = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    compression_type = models.CharField(
        max_length=20,
        choices=COMPRESSION_CHOICES,
        default="none",
    )
    deduplication_enabled = models.BooleanField(default=True)
    encryption_type = models.CharField(
        max_length=20,
        choices=ENCRYPTION_CHOICES,
        default="aes_256",
    )
    rollover_volume = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overflow_sources",
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Storage Volume"
        verbose_name_plural = "Storage Volumes"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dstg_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "code"], name="doc_dstg_tnt_code_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "backend_type", "tier"], name="doc_dstg_tnt_bknd_tier_idx"),
            models.Index(fields=["tenant", "is_default", "is_active"], name="doc_dstg_tnt_def_act_idx"),
        ]

    def __str__(self):
        return f"{self.name} [{self.code}] — {self.get_tier_display()}"

    def save(self, *args, **kwargs):
        if self.max_capacity_bytes > 0:
            pct = (Decimal(self.utilized_bytes) / Decimal(self.max_capacity_bytes)) * Decimal("100.0")
            self.utilized_percentage = min(Decimal("100.0"), round(pct, 2))
            self.is_full = self.utilized_bytes >= self.max_capacity_bytes
        else:
            self.utilized_percentage = Decimal("0.0")
            self.is_full = False

        if self.is_default and self.tenant_id:
            StorageVolume.objects.filter(
                tenant=self.tenant,
                is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)

    @property
    def tier_badge_class(self):
        return self.TIER_CSS.get(self.tier, "badge-slate")

    @property
    def backend_badge_class(self):
        return self.BACKEND_CSS.get(self.backend_type, "badge-slate")

    @property
    def max_capacity_gb(self):
        return round(self.max_capacity_bytes / (1024**3), 2)

    @property
    def utilized_gb(self):
        return round(self.utilized_bytes / (1024**3), 2)

    @property
    def free_bytes(self):
        return max(0, self.max_capacity_bytes - self.utilized_bytes)

    @property
    def free_gb(self):
        return round(self.free_bytes / (1024**3), 2)

    @property
    def is_over_warning(self):
        return self.utilized_percentage >= self.warning_threshold_pct
