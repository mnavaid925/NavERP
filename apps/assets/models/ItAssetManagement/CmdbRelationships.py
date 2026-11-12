"""Configuration Management Database (CMDB) Dependency Edge model (11.18)."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.assets.models._base import TenantNumbered
from apps.assets.models.ItAssetManagement._validators import (
    add_field_error,
    validate_tenant_fks,
)


class CmdbRelationship(TenantNumbered):
    """Typed CI-to-CI dependency edge with criticality & SPOF tracking [CMDB]."""

    NUMBER_PREFIX = "CMDB"

    CI_TYPE_CHOICES = [
        ("it_hardware", "IT Hardware Asset"),
        ("software_license", "Software License"),
        ("cloud_asset", "Cloud Asset / SaaS"),
        ("service_component", "Core Service Component"),
        ("operational_asset", "Operational Asset (SCM)"),
    ]

    RELATIONSHIP_TYPE_CHOICES = [
        ("runs_on", "Runs On"),
        ("depends_on", "Depends On"),
        ("hosted_in", "Hosted In"),
        ("connects_to", "Connects To"),
        ("backed_up_by", "Backed Up By"),
        ("licensed_by", "Licensed By"),
        ("integrates_with", "Integrates With"),
        ("replicates_to", "Replicates To"),
    ]

    ENVIRONMENT_CHOICES = [
        ("production", "Production"),
        ("staging", "Staging"),
        ("development", "Development"),
        ("dr_failover", "DR / Failover"),
        ("shared_infra", "Shared Infrastructure"),
    ]

    CRITICALITY_CHOICES = [
        ("tier_1_mission_critical", "Tier 1 — Mission Critical"),
        ("tier_2_business_important", "Tier 2 — Business Important"),
        ("tier_3_operational", "Tier 3 — Operational"),
        ("tier_4_low", "Tier 4 — Low"),
    ]

    IMPACT_SEVERITY_CHOICES = [
        ("hard_outage", "Hard Outage"),
        ("degraded_performance", "Degraded Performance"),
        ("failover_available", "Failover Available"),
        ("informational", "Informational"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("planned", "Planned"),
        ("deprecated", "Deprecated"),
        ("severed", "Severed"),
    ]

    STATUS_CSS = {
        "active": "badge-green",
        "planned": "badge-info",
        "deprecated": "badge-amber",
        "severed": "badge-muted",
    }

    CRITICALITY_CSS = {
        "tier_1_mission_critical": "badge-red",
        "tier_2_business_important": "badge-amber",
        "tier_3_operational": "badge-info",
        "tier_4_low": "badge-slate",
    }

    LOCKED_STATUSES = {"severed"}

    CI_FIELD_BY_TYPE = {
        "it_hardware": "hardware",
        "software_license": "software",
        "cloud_asset": "cloud",
        "service_component": "service",
        "operational_asset": "asset",
    }

    _TENANT_FK_FIELDS = (
        "source_hardware",
        "source_software",
        "source_cloud",
        "source_service",
        "source_asset",
        "target_hardware",
        "target_software",
        "target_cloud",
        "target_service",
        "target_asset",
        "owner",
        "verified_by",
    )

    source_ci_type = models.CharField(
        max_length=24,
        choices=CI_TYPE_CHOICES,
        default="service_component",
    )
    source_hardware = models.ForeignKey(
        "assets.ItHardwareAsset",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="outbound_cmdb_edges",
    )
    source_software = models.ForeignKey(
        "assets.SoftwareLicense",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="outbound_cmdb_edges",
    )
    source_cloud = models.ForeignKey(
        "assets.CloudAssetSubscription",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="outbound_cmdb_edges",
    )
    source_service = models.ForeignKey(
        "core.ServiceComponent",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="outbound_cmdb_edges",
    )
    source_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="outbound_cmdb_edges",
    )

    relationship_type = models.CharField(
        max_length=24,
        choices=RELATIONSHIP_TYPE_CHOICES,
        default="depends_on",
    )

    target_ci_type = models.CharField(
        max_length=24,
        choices=CI_TYPE_CHOICES,
        default="it_hardware",
    )
    target_hardware = models.ForeignKey(
        "assets.ItHardwareAsset",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inbound_cmdb_edges",
    )
    target_software = models.ForeignKey(
        "assets.SoftwareLicense",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inbound_cmdb_edges",
    )
    target_cloud = models.ForeignKey(
        "assets.CloudAssetSubscription",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inbound_cmdb_edges",
    )
    target_service = models.ForeignKey(
        "core.ServiceComponent",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inbound_cmdb_edges",
    )
    target_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inbound_cmdb_edges",
    )

    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        default="production",
    )
    criticality = models.CharField(
        max_length=32,
        choices=CRITICALITY_CHOICES,
        default="tier_2_business_important",
    )
    impact_severity = models.CharField(
        max_length=28,
        choices=IMPACT_SEVERITY_CHOICES,
        default="degraded_performance",
    )
    is_single_point_of_failure = models.BooleanField(default=False)

    verified_on = models.DateField(null=True, blank=True, editable=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="verified_cmdb_edges",
    )
    severed_at = models.DateTimeField(null=True, blank=True, editable=False)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="active",
        editable=False,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_cmdb_relationships",
    )
    blast_radius_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-updated_at", "-number"]
        verbose_name = "CMDB Relationship"
        verbose_name_plural = "CMDB Relationships"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_cmdb_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_cmdb_ten_stat"),
            models.Index(fields=["tenant", "relationship_type"], name="idx_cmdb_ten_rel"),
            models.Index(fields=["tenant", "source_ci_type"], name="idx_cmdb_ten_src"),
            models.Index(fields=["tenant", "target_ci_type"], name="idx_cmdb_ten_tgt"),
        ]

    def __str__(self):
        return f"{self.number}: {self.source_label} -> {self.relationship_type} -> {self.target_label}"

    def _validate_endpoint(self, errors, prefix, ci_type):
        expected_suffix = self.CI_FIELD_BY_TYPE.get(ci_type)
        if not expected_suffix:
            add_field_error(errors, f"{prefix}_ci_type", f"Unsupported CI type '{ci_type}'.")
            return None
        expected_field = f"{prefix}_{expected_suffix}"
        if getattr(self, f"{expected_field}_id", None) is None:
            add_field_error(
                errors,
                expected_field,
                f"Select a {prefix} CI matching the chosen CI type.",
            )
        for ci_key, suffix in self.CI_FIELD_BY_TYPE.items():
            field_name = f"{prefix}_{suffix}"
            if ci_key != ci_type and getattr(self, f"{field_name}_id", None) is not None:
                add_field_error(
                    errors,
                    field_name,
                    f"Only the {prefix} FK matching '{ci_type}' may be populated.",
                )
        return expected_suffix

    def clean(self):
        super().clean()
        errors = validate_tenant_fks(self, self._TENANT_FK_FIELDS)
        src_suffix = self._validate_endpoint(errors, "source", self.source_ci_type)
        tgt_suffix = self._validate_endpoint(errors, "target", self.target_ci_type)

        src_key = self.source_ci_key
        tgt_key = self.target_ci_key
        if src_key and tgt_key and src_key == tgt_key:
            add_field_error(
                errors,
                f"target_{tgt_suffix or 'ci_type'}",
                "Source CI and target CI cannot be the same configuration item (self-loop forbidden).",
            )

        if (
            self.status == "active"
            and self.tenant_id
            and src_suffix
            and tgt_suffix
            and src_key
            and tgt_key
        ):
            src_field = f"source_{src_suffix}_id"
            tgt_field = f"target_{tgt_suffix}_id"
            duplicate_exists = (
                CmdbRelationship.objects.filter(
                    tenant_id=self.tenant_id,
                    status="active",
                    relationship_type=self.relationship_type,
                    **{src_field: src_key[1], tgt_field: tgt_key[1]},
                )
                .exclude(pk=self.pk)
                .exists()
            )
            if duplicate_exists:
                add_field_error(
                    errors,
                    "relationship_type",
                    "An active CMDB relationship with this exact source, relation type, and target already exists.",
                )

        if errors:
            raise ValidationError(errors)

    def _resolve_ci(self, prefix, ci_type):
        suffix = self.CI_FIELD_BY_TYPE.get(ci_type)
        if not suffix:
            return None
        return getattr(self, f"{prefix}_{suffix}", None)

    @property
    def source_ci(self):
        return self._resolve_ci("source", self.source_ci_type)

    @property
    def target_ci(self):
        return self._resolve_ci("target", self.target_ci_type)

    @property
    def source_ci_key(self):
        suffix = self.CI_FIELD_BY_TYPE.get(self.source_ci_type)
        pk = getattr(self, f"source_{suffix}_id", None) if suffix else None
        return (self.source_ci_type, pk) if pk else None

    @property
    def target_ci_key(self):
        suffix = self.CI_FIELD_BY_TYPE.get(self.target_ci_type)
        pk = getattr(self, f"target_{suffix}_id", None) if suffix else None
        return (self.target_ci_type, pk) if pk else None

    @property
    def source_label(self):
        ci = self.source_ci
        return str(ci) if ci is not None else "Unlinked Source CI"

    @property
    def target_label(self):
        ci = self.target_ci
        return str(ci) if ci is not None else "Unlinked Target CI"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def criticality_badge_class(self):
        return self.CRITICALITY_CSS.get(self.criticality, "badge-slate")

    @property
    def is_locked(self):
        return self.status in self.LOCKED_STATUSES
