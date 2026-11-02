from django.conf import settings
from django.db import models
from apps.ecommerce.models._base import TenantNumbered


class AccountSecurityAlert(TenantNumbered):
    NUMBER_PREFIX = "EASA"

    ALERT_TYPE_CHOICES = [
        ("credential_stuffing", "Credential Stuffing Attack Spike"),
        ("brute_force", "Brute-Force Password Attempts"),
        ("suspicious_login", "Suspicious / New Device Login"),
        ("impossible_travel", "Impossible Travel (Geo Velocity)"),
        ("session_hijack", "Session / User-Agent Anomaly"),
        ("sanctions_screening_hit", "Sanctions List Potential Match"),
        ("pep_screening_hit", "Politically Exposed Person (PEP) Match"),
        ("aml_velocity_alert", "Anti-Money Laundering (AML) Velocity Spike"),
        ("excessive_refunds", "Refund / Voucher Abuse Pattern"),
    ]

    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    STATUS_CHOICES = [
        ("new", "New / Unassigned"),
        ("investigating", "Under Investigation"),
        ("resolved_legitimate", "Resolved: Legitimate Activity"),
        ("confirmed_threat", "Confirmed Security Threat"),
        ("dismissed", "False Positive / Dismissed"),
    ]

    AUTOMATED_ACTION_CHOICES = [
        ("none", "None / Log Only"),
        ("force_password_reset", "Forced Password Reset"),
        ("lock_account", "Account Locked"),
        ("terminate_sessions", "Active Sessions Terminated"),
        ("challenge_mfa", "Step-Up MFA Challenge Triggered"),
        ("notify_user", "Security Email Alert Sent"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="account_security_alerts",
        help_text="Target user account under potential threat or compromise",
    )
    party = models.ForeignKey(
        "core.Party",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="security_alerts",
        help_text="Underlying customer or employee party in core spine",
    )
    alert_type = models.CharField(
        max_length=35,
        choices=ALERT_TYPE_CHOICES,
        default="suspicious_login",
        help_text="Classification of security event or policy violation",
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="medium",
        help_text="Threat severity level driving operational urgency",
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="new",
        help_text="Triage and investigation status of the security alert",
    )
    automated_action_taken = models.CharField(
        max_length=35,
        choices=AUTOMATED_ACTION_CHOICES,
        default="none",
        help_text="Immediate automated policy action executed upon event detection",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Threat actor originating IP address",
    )
    location_info = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text="City, Region, and Country resolved from threat IP",
    )
    user_agent = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Client browser/device User-Agent string",
    )
    incident_details = models.TextField(
        blank=True,
        default="",
        help_text="Technical diagnostic telemetry, failed attempt count, or match strings",
    )
    assigned_investigator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_security_alerts",
        help_text="Security officer or fraud analyst assigned to triage",
    )
    investigation_notes = models.TextField(
        blank=True,
        default="",
        help_text="Case investigation notes, forensic commentary, and resolution rationale",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_security_alerts",
        help_text="User who marked the security incident as resolved or dismissed",
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when alert was resolved",
    )

    class Meta:
        db_table = "ecommerce_account_security_alert"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_easa_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "alert_type"], name="idx_easa_ten_type"),
            models.Index(fields=["tenant", "severity"], name="idx_easa_ten_sev"),
            models.Index(fields=["tenant", "status"], name="idx_easa_ten_stat"),
            models.Index(fields=["tenant", "-created_at"], name="idx_easa_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.get_alert_type_display()} [{self.get_severity_display()}]"
