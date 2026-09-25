from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantOwned, settings


class AccountClassification(TenantOwned):
    TIER_CHOICES = [
        ("strategic", "Strategic"),
        ("key", "Key"),
        ("growth", "Growth"),
        ("nurture", "Nurture"),
    ]
    LIFECYCLE_STAGE_CHOICES = [
        ("prospect", "Prospect"),
        ("active_customer", "Active Customer"),
        ("expansion_candidate", "Expansion Candidate"),
        ("dormant", "Dormant"),
        ("former_customer", "Former Customer"),
    ]
    STRATEGIC_PRIORITY_CHOICES = [
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]
    REVENUE_POTENTIAL_CHOICES = [
        ("very_high", "Very High"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
        ("unknown", "Unknown"),
    ]
    WALLET_CATEGORY_CHOICES = [
        ("none", "None"),
        ("small", "Small"),
        ("medium", "Medium"),
        ("large", "Large"),
        ("full_wallet", "Full Wallet"),
    ]

    account = models.OneToOneField("core.Party", on_delete=models.PROTECT, related_name="sales_account_classification")
    tier = models.CharField(max_length=16, choices=TIER_CHOICES, default="growth")
    lifecycle_stage = models.CharField(max_length=24, choices=LIFECYCLE_STAGE_CHOICES, default="prospect")
    strategic_priority = models.CharField(max_length=12, choices=STRATEGIC_PRIORITY_CHOICES, default="medium")
    revenue_potential = models.CharField(max_length=16, choices=REVENUE_POTENTIAL_CHOICES, default="unknown")
    wallet_category = models.CharField(max_length=16, choices=WALLET_CATEGORY_CHOICES, default="none")
    rationale = models.TextField()
    effective_on = models.DateField(default=timezone.localdate)
    review_due_on = models.DateField(null=True, blank=True)
    classified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="sales_account_classifications",
    )

    class Meta:
        ordering = ["-effective_on", "account__name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "account"], name="sales_aclass_tenant_account_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "tier", "lifecycle_stage"], name="sales_aclass_tnt_tier_life_idx"),
            models.Index(fields=["tenant", "strategic_priority", "review_due_on"], name="sales_aclass_prio_idx"),
        ]

    def _validate_data(self):
        if not self.tenant_id:
            return
        errors = {}
        if not self.account_id:
            errors["account"] = "Choose a same-tenant organization account."
        else:
            account = type(self)._meta.get_field("account").remote_field.model._default_manager.filter(
                pk=self.account_id, tenant_id=self.tenant_id, kind="organization"
            ).first()
            if account is None:
                errors["account"] = "Choose a same-tenant organization account."
        if not (self.rationale or "").strip():
            errors["rationale"] = "A rationale is required for every classification."
        if self.tier in {"strategic", "key"} and not self.review_due_on:
            errors["review_due_on"] = "Strategic and key accounts require a review date."
        if self.effective_on is not None and not isinstance(self.effective_on, date):
            errors["effective_on"] = "Enter a valid effective date."
        if self.review_due_on is not None and not isinstance(self.review_due_on, date):
            errors["review_due_on"] = "Enter a valid review date."
        if isinstance(self.review_due_on, date) and isinstance(self.effective_on, date) and self.review_due_on < self.effective_on:
            errors["review_due_on"] = "The review date cannot precede the effective date."
        if self.classified_by_id:
            user_model = type(self)._meta.get_field("classified_by").remote_field.model
            if not user_model._default_manager.filter(pk=self.classified_by_id, tenant_id=self.tenant_id).exists():
                errors["classified_by"] = "The classifier must belong to this workspace."
        if errors:
            raise ValidationError(errors)

    def clean(self):
        super().clean()
        self._validate_data()

    def save(self, *args, **kwargs):
        self._validate_data()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account} · {self.get_tier_display()} · {self.get_lifecycle_stage_display()}"
