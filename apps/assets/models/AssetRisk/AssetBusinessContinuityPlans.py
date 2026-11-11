from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetBusinessContinuityPlan(TenantNumbered):
    """
    Asset Business Continuity Plan (BCP) [ABC-].
    Manages critical asset redundancy architecture, RTO/RPO targets,
    failover/failback procedures, disaster scenarios, and disaster recovery simulation drills.
    Aligned with ISO 22301 and NFPA 1600.
    """

    NUMBER_PREFIX = "ABC"

    REDUNDANCY_TYPE_CHOICES = [
        ("hot_standby", "Hot Standby (Instant Automatic Failover)"),
        ("warm_standby", "Warm Standby (Rapid Manual Spin-Up < 2 hrs)"),
        ("cold_standby", "Cold Standby (Offsite / Warehoused Spare)"),
        ("n_plus_one_cluster", "N+1 Resilient Active Cluster"),
        ("reciprocal_agreement", "Reciprocal Agreement / Partner Capacity"),
        ("mobile_replacement", "Mobile Replacement / Rental Unit"),
        ("none_single_point_of_failure", "Single Point of Failure (SPOF - No Redundancy)"),
    ]

    DISASTER_SCENARIO_CHOICES = [
        ("power_grid_outage", "Total Power Grid / Substation Outage"),
        ("fire_explosion", "Facility Fire / Industrial Explosion"),
        ("flood_natural_disaster", "Flood / Hurricane / Severe Weather"),
        ("cyber_attack_ransomware", "Cyber Attack / Ransomware Lockout"),
        ("critical_hardware_loss", "Catastrophic Mechanical / Hardware Loss"),
        ("hazmat_contamination", "Hazmat Release / Chemical Contamination"),
    ]

    DRILL_FREQUENCY_CHOICES = [
        ("quarterly", "Quarterly"),
        ("semi_annually", "Semi-Annually"),
        ("annually", "Annually"),
    ]

    DRILL_RESULT_CHOICES = [
        ("not_tested", "Not Tested / Planned"),
        ("passed", "Drill Passed (Met RTO/RPO)"),
        ("passed_with_deficiencies", "Passed with Deficiencies"),
        ("failed", "Drill Failed (Exceeded RTO/RPO)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft (Pending Validation)"),
        ("active", "Active & Approved BCP"),
        ("under_review", "Under Periodic Review"),
        ("deprecated", "Deprecated / Retired"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "active": "badge-green",
        "under_review": "badge-amber",
        "deprecated": "badge-muted",
    }

    REDUNDANCY_TYPE_CSS = {
        "hot_standby": "badge-green",
        "warm_standby": "badge-info",
        "cold_standby": "badge-slate",
        "n_plus_one_cluster": "badge-purple",
        "reciprocal_agreement": "badge-info",
        "mobile_replacement": "badge-slate",
        "none_single_point_of_failure": "badge-red",
    }

    DRILL_RESULT_CSS = {
        "not_tested": "badge-slate",
        "passed": "badge-green",
        "passed_with_deficiencies": "badge-amber",
        "failed": "badge-red",
    }

    DISASTER_SCENARIO_CSS = {
        "power_grid_outage": "badge-amber",
        "fire_explosion": "badge-red",
        "flood_natural_disaster": "badge-info",
        "cyber_attack_ransomware": "badge-red",
        "critical_hardware_loss": "badge-purple",
        "hazmat_contamination": "badge-amber",
    }

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="asset_continuity_plans",
    )
    title = models.CharField(
        max_length=255,
        help_text="BCP Title, e.g. Primary Turbine Redundancy & Recovery Plan",
    )
    primary_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="continuity_plans",
        help_text="Primary operational asset requiring continuity coverage",
    )
    backup_redundant_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="redundant_for_continuity_plans",
        help_text="Designated redundant or backup asset",
    )
    redundancy_type = models.CharField(
        max_length=32,
        choices=REDUNDANCY_TYPE_CHOICES,
        default="none_single_point_of_failure",
    )
    recovery_time_objective_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("4.00"),
        help_text="Recovery Time Objective (RTO in hours)",
    )
    recovery_point_objective_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("1.00"),
        help_text="Recovery Point Objective (RPO in hours)",
    )
    maximum_tolerable_downtime_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("24.00"),
        help_text="Maximum Tolerable Downtime (MTD in hours)",
    )
    disaster_scenario = models.CharField(
        max_length=30,
        choices=DISASTER_SCENARIO_CHOICES,
        default="critical_hardware_loss",
    )
    failover_procedure = models.TextField(
        blank=True,
        help_text="Step-by-step procedures to activate backup asset",
    )
    failback_procedure = models.TextField(
        blank=True,
        help_text="Step-by-step procedures to restore primary operations",
    )
    alternate_facility_site = models.CharField(
        max_length=255,
        blank=True,
        help_text="Secondary facility or backup plant site",
    )
    critical_spares_required = models.TextField(
        blank=True,
        help_text="Essential spare components and vendor SLA lead times",
    )
    emergency_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_asset_continuity_plans",
        help_text="Designated incident commander or plant resilience engineer",
    )
    drill_frequency = models.CharField(
        max_length=20,
        choices=DRILL_FREQUENCY_CHOICES,
        default="annually",
    )
    last_drill_date = models.DateField(
        null=True,
        blank=True,
    )
    next_drill_date = models.DateField(
        null=True,
        blank=True,
    )
    drill_result = models.CharField(
        max_length=30,
        choices=DRILL_RESULT_CHOICES,
        default="not_tested",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_abc_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_abc_ten_stat"),
            models.Index(fields=["tenant", "redundancy_type"], name="idx_abc_ten_red"),
            models.Index(fields=["tenant", "primary_asset"], name="idx_abc_ten_past"),
            models.Index(fields=["tenant", "drill_result"], name="idx_abc_ten_dres"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_redundancy_type_display()})"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def redundancy_type_badge_class(self):
        return self.REDUNDANCY_TYPE_CSS.get(self.redundancy_type, "badge-slate")

    @property
    def drill_result_badge_class(self):
        return self.DRILL_RESULT_CSS.get(self.drill_result, "badge-slate")

    @property
    def disaster_scenario_badge_class(self):
        return self.DISASTER_SCENARIO_CSS.get(self.disaster_scenario, "badge-slate")

    @property
    def is_spof(self):
        return self.redundancy_type == "none_single_point_of_failure"
