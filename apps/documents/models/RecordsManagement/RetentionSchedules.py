from django.db import models

from apps.documents.models._base import TenantNumbered


class RetentionSchedule(TenantNumbered):
    """File plan retention blueprint and regulatory compliance disposition rules."""

    NUMBER_PREFIX = "DRTN"

    TRIGGER_TYPE_CHOICES = (
        ("creation_date", "Creation Date"),
        ("last_modified", "Last Modified Date"),
        ("declaration_date", "Record Declaration Date"),
        ("event_based", "Event Completion (Superseded/Closed)"),
    )

    CUTOFF_RULE_CHOICES = (
        ("immediate", "Immediate Cutoff"),
        ("calendar_year_end", "End of Calendar Year (Dec 31)"),
        ("fiscal_year_end", "End of Fiscal Year"),
        ("event_completion", "Upon Specified Trigger Event"),
    )

    DISPOSITION_ACTION_CHOICES = (
        ("destroy", "Secure Destruction"),
        ("archive", "Permanent Archival / Long-Term Preservation"),
        ("review", "Disposition Review & Re-evaluation"),
        ("transfer", "Transfer to National / External Archives"),
    )

    FRAMEWORK_CHOICES = (
        ("iso_15489", "ISO 15489 (Information & Documentation)"),
        ("dod_5015_2", "DoD 5015.2 (Records Management Standard)"),
        ("sec_17a_4", "SEC Rule 17a-4 (Electronic Records WORM)"),
        ("gdpr", "GDPR (Article 5(1)(e) Storage Limitation)"),
        ("hipaa", "HIPAA (45 CFR § 164.316(b)(2)(i))"),
        ("irs_tax", "IRS Tax & Financial Records (7 Years)"),
        ("general", "General Corporate Governance"),
    )

    RETENTION_MODE_CHOICES = (
        ("modifiable", "Modifiable (Standard Corporate)"),
        ("regulatory_worm", "Regulatory WORM (Strict Non-Erasable)"),
    )

    FRAMEWORK_CSS = {
        "iso_15489": "badge-info",
        "dod_5015_2": "badge-slate",
        "sec_17a_4": "badge-red",
        "gdpr": "badge-amber",
        "hipaa": "badge-green",
        "irs_tax": "badge-slate",
        "general": "badge-muted",
    }

    RETENTION_MODE_CSS = {
        "modifiable": "badge-info",
        "regulatory_worm": "badge-red",
    }

    DISPOSITION_ACTION_CSS = {
        "destroy": "badge-red",
        "archive": "badge-green",
        "review": "badge-amber",
        "transfer": "badge-info",
    }

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, db_index=True)
    description = models.TextField(blank=True)
    retention_period_years = models.PositiveIntegerField(default=7)
    retention_period_months = models.PositiveIntegerField(default=0)
    is_permanent = models.BooleanField(default=False)
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_TYPE_CHOICES, default="creation_date")
    cutoff_rule = models.CharField(max_length=30, choices=CUTOFF_RULE_CHOICES, default="calendar_year_end")
    disposition_action = models.CharField(max_length=30, choices=DISPOSITION_ACTION_CHOICES, default="destroy")
    compliance_framework = models.CharField(max_length=30, choices=FRAMEWORK_CHOICES, default="iso_15489", db_index=True)
    retention_mode = models.CharField(max_length=30, choices=RETENTION_MODE_CHOICES, default="modifiable")
    legal_citation = models.CharField(max_length=255, blank=True)
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retention_schedules",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code", "name"]
        verbose_name = "Retention Schedule"
        verbose_name_plural = "Retention Schedules"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="doc_drtn_tnt_code_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "compliance_framework"], name="doc_drtn_tnt_fmwk_idx"),
            models.Index(fields=["tenant", "is_active"], name="doc_drtn_tnt_act_idx"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def framework_badge_class(self):
        return self.FRAMEWORK_CSS.get(self.compliance_framework, "badge-slate")

    @property
    def retention_mode_badge_class(self):
        return self.RETENTION_MODE_CSS.get(self.retention_mode, "badge-info")

    @property
    def disposition_badge_class(self):
        return self.DISPOSITION_ACTION_CSS.get(self.disposition_action, "badge-slate")

    @property
    def status_badge_class(self):
        return "badge-green" if self.is_active else "badge-muted"

    @property
    def retention_summary(self):
        if self.is_permanent:
            return "Permanent (Do Not Destroy)"
        parts = []
        if self.retention_period_years:
            parts.append(f"{self.retention_period_years}y")
        if self.retention_period_months:
            parts.append(f"{self.retention_period_months}m")
        return " ".join(parts) if parts else "0m"
