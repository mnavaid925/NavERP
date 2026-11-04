from django.conf import settings
from django.db import models

from apps.bi.models._base import TenantNumbered


class DataMart(TenantNumbered):
    NUMBER_PREFIX = "BDMT"

    SUBJECT_AREA_CHOICES = [
        ("finance", "Finance & Accounting"),
        ("sales", "Sales & Customer Relationship"),
        ("hr", "Human Resources & Workforce"),
        ("supply_chain", "Supply Chain & Logistics"),
        ("procurement", "Procurement & Purchasing"),
        ("manufacturing", "Manufacturing & Production"),
        ("executive", "Executive & Cross-Functional"),
    ]

    ACCESS_TIER_CHOICES = [
        ("public", "Public (Tenant-Wide)"),
        ("department", "Departmental Only"),
        ("restricted", "Restricted / Confidential"),
    ]

    CERTIFICATION_STATUS_CHOICES = [
        ("draft", "Draft / In Development"),
        ("in_review", "Under Review & Validation"),
        ("certified", "Certified Single Source of Truth"),
        ("deprecated", "Deprecated / Sunset Pending"),
    ]

    REFRESH_CADENCE_CHOICES = [
        ("real_time", "Real-Time / Streaming"),
        ("hourly", "Hourly Micro-Batch"),
        ("daily", "Daily Overnight Batch"),
        ("weekly", "Weekly Snapshot"),
        ("on_demand", "On-Demand Only"),
    ]

    name = models.CharField(max_length=150, help_text="Subject data mart display name")
    code = models.SlugField(max_length=50, help_text="Unique slug code for mart identification")
    subject_area = models.CharField(max_length=30, choices=SUBJECT_AREA_CHOICES, default="finance")
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_data_marts",
        help_text="Owning organizational department or business unit",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_data_marts_owned",
        help_text="Primary business domain owner",
    )
    steward = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_data_marts_stewarded",
        help_text="Technical data steward responsible for data quality and SLAs",
    )
    access_tier = models.CharField(max_length=25, choices=ACCESS_TIER_CHOICES, default="department")
    certification_status = models.CharField(max_length=25, choices=CERTIFICATION_STATUS_CHOICES, default="draft")
    refresh_cadence = models.CharField(max_length=25, choices=REFRESH_CADENCE_CHOICES, default="daily")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_data_mart"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="bi_bdmt_tenant_code_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdmt_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "subject_area"], name="idx_bdmt_ten_subj"),
            models.Index(fields=["tenant", "certification_status"], name="idx_bdmt_ten_cert"),
            models.Index(fields=["tenant", "is_active"], name="idx_bdmt_ten_active"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"
