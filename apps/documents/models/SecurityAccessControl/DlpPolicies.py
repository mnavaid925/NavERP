import re

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.documents.models._base import TenantNumbered


class DlpPolicy(TenantNumbered):
    """
    Data Loss Prevention (DLP) rule defining sensitive content patterns
    (PCI cards, SSN, IBAN, API keys, confidential keywords), severity levels,
    and automated enforcement actions.
    """

    NUMBER_PREFIX = "DDLP"

    RULE_TYPE_CHOICES = (
        ("built_in_pattern", "Built-in SIT Pattern"),
        ("sensitive_keywords", "Sensitive Keyword List"),
        ("custom_regex", "Custom Regular Expression"),
        ("classification_anomaly", "Classification Level Anomaly"),
    )

    BUILT_IN_PATTERN_CHOICES = (
        ("none", "None / Custom Only"),
        ("credit_card_pci", "Payment Card Industry (PCI-DSS Credit Cards)"),
        ("us_ssn", "US Social Security Number (SSN)"),
        ("iban_banking", "International Bank Account Number (IBAN)"),
        ("national_id_pii", "National ID & Government Identifiers"),
        ("email_list", "Bulk Email Addresses Extraction"),
        ("api_keys_secrets", "API Keys, Tokens & Private Keys"),
    )

    ACTION_CHOICES = (
        ("log_only", "Audit Log Only (Silent Monitor)"),
        ("warn_author", "Warn Author on Save"),
        ("block_save", "Block Document Save / Upload"),
        ("quarantine", "Quarantine Document for Review"),
        ("force_watermark", "Force Strict Watermarking"),
    )

    SEVERITY_CHOICES = (
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    )

    SEVERITY_CSS = {
        "low": "badge-slate",
        "medium": "badge-info",
        "high": "badge-amber",
        "critical": "badge-red",
    }

    ACTION_CSS = {
        "log_only": "badge-slate",
        "warn_author": "badge-info",
        "block_save": "badge-red",
        "quarantine": "badge-amber",
        "force_watermark": "badge-slate",
    }

    # Precompiled Built-In Pattern Regexes
    PATTERNS = {
        "credit_card_pci": r"\b(?:\d{4}[- ]?){3}\d{4}\b",
        "us_ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "iban_banking": r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b",
        "national_id_pii": r"\b[A-Z]{1,2}\d{6,8}[A-Z0-9]?\b",
        "email_list": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b",
        "api_keys_secrets": r"(?:api[_-]?key|secret|token|bearer|password)[\s:=]+['\"]?([a-zA-Z0-9_\-]{16,64})['\"]?",
    }

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, blank=True)
    description = models.TextField(blank=True)

    rule_type = models.CharField(
        max_length=30,
        choices=RULE_TYPE_CHOICES,
        default="built_in_pattern",
    )
    built_in_pattern = models.CharField(
        max_length=30,
        choices=BUILT_IN_PATTERN_CHOICES,
        default="none",
    )
    custom_regex = models.TextField(blank=True)
    sensitive_keywords = models.JSONField(default=list, blank=True)
    match_threshold = models.PositiveIntegerField(default=1)

    # Enforcement Actions
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        default="warn_author",
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="high",
    )
    notify_security_officer = models.BooleanField(default=True)
    notification_email = models.CharField(max_length=255, blank=True)

    # Scope
    apply_to_all_types = models.BooleanField(default=True)
    target_document_types = models.JSONField(default=list, blank=True)
    target_classifications = models.JSONField(default=list, blank=True)

    # Telemetry
    incident_count = models.PositiveIntegerField(default=0)
    last_triggered_at = models.DateTimeField(null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_dlp_policies",
    )

    class Meta:
        ordering = ["severity", "name"]
        verbose_name = "DLP Policy"
        verbose_name_plural = "DLP Policies"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_ddlp_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "slug"], name="doc_ddlp_tnt_slug_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "severity"], name="doc_ddlp_tnt_act_sev_idx"),
            models.Index(fields=["tenant", "rule_type", "is_active"], name="doc_ddlp_tnt_rule_act_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} ({self.get_severity_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:140] or "dlp-policy"
            slug = base_slug
            counter = 1
            while DlpPolicy.objects.filter(tenant=self.tenant, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def severity_badge(self):
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def action_badge(self):
        return self.ACTION_CSS.get(self.action, "badge-slate")

    def inspect_text(self, text):
        """
        Inspects given text against this policy rule.
        Returns a tuple: (violated: bool, match_count: int, redacted_snippet: str)
        """
        if not text or not self.is_active:
            return False, 0, ""

        matches = []
        if self.rule_type == "built_in_pattern" and self.built_in_pattern in self.PATTERNS:
            pattern = self.PATTERNS[self.built_in_pattern]
            matches = re.findall(pattern, text, re.IGNORECASE)
        elif self.rule_type == "custom_regex" and self.custom_regex:
            try:
                matches = re.findall(self.custom_regex, text, re.IGNORECASE)
            except re.error:
                matches = []
        elif self.rule_type == "sensitive_keywords" and self.sensitive_keywords:
            for kw in self.sensitive_keywords:
                if kw and str(kw).lower() in text.lower():
                    matches.append(str(kw))

        count = len(matches)
        if count >= self.match_threshold:
            first_match = str(matches[0]) if matches else ""
            if len(first_match) > 4:
                redacted = first_match[:2] + "*" * (len(first_match) - 4) + first_match[-2:]
            else:
                redacted = "****"
            return True, count, f"Detected {count} occurrence(s) matching '{self.name}'. Snippet: {redacted}"
        return False, 0, ""
