from datetime import date

from django.core.exceptions import ValidationError
from django.db import models

from apps.sales.models._base import TenantOwned, settings


class AccountStakeholder(TenantOwned):
    ROLE_CHOICES = [
        ("decision_maker", "Decision Maker"),
        ("economic_buyer", "Economic Buyer"),
        ("champion", "Champion"),
        ("influencer", "Influencer"),
        ("blocker", "Blocker"),
        ("technical_evaluator", "Technical Evaluator"),
        ("procurement", "Procurement"),
        ("end_user", "End User"),
        ("advisor", "Advisor"),
        ("other", "Other"),
    ]
    INFLUENCE_CHOICES = [
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
        ("unknown", "Unknown"),
    ]
    ATTITUDE_CHOICES = [
        ("positive", "Positive"),
        ("neutral", "Neutral"),
        ("negative", "Negative"),
        ("unknown", "Unknown"),
    ]
    RELATIONSHIP_STRENGTH_CHOICES = [
        ("strong", "Strong"),
        ("moderate", "Moderate"),
        ("weak", "Weak"),
        ("unknown", "Unknown"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("former", "Former"),
    ]

    account = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="sales_account_stakeholders")
    contact = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="sales_stakeholder_contacts")
    role = models.CharField(max_length=24, choices=ROLE_CHOICES)
    influence = models.CharField(max_length=12, choices=INFLUENCE_CHOICES, default="unknown")
    attitude = models.CharField(max_length=12, choices=ATTITUDE_CHOICES, default="unknown")
    relationship_strength = models.CharField(max_length=12, choices=RELATIONSHIP_STRENGTH_CHOICES, default="unknown")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["account__name", "contact__name", "role"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "account", "contact", "role"],
                name="sales_ast_tenant_account_contact_role_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "account", "status"], name="sales_ast_acct_status_idx"),
            models.Index(fields=["tenant", "contact", "status"], name="sales_ast_contact_status_idx"),
            models.Index(fields=["tenant", "role", "attitude"], name="sales_ast_role_attitude_idx"),
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
        if not self.contact_id:
            errors["contact"] = "Choose a same-tenant person contact."
        else:
            contact = type(self)._meta.get_field("contact").remote_field.model._default_manager.filter(
                pk=self.contact_id, tenant_id=self.tenant_id, kind="person"
            ).first()
            if contact is None:
                errors["contact"] = "Choose a same-tenant person contact."
        if self.account_id and self.account_id == self.contact_id:
            errors["contact"] = "An account and contact must be different Parties."
        if self.valid_from is not None and not isinstance(self.valid_from, date):
            errors["valid_from"] = "Enter a valid start date."
        if self.valid_to is not None and not isinstance(self.valid_to, date):
            errors["valid_to"] = "Enter a valid end date."
        if isinstance(self.valid_from, date) and isinstance(self.valid_to, date) and self.valid_to < self.valid_from:
            errors["valid_to"] = "The end date cannot precede the start date."
        if errors:
            raise ValidationError(errors)

    def clean(self):
        super().clean()
        self._validate_data()

    def save(self, *args, **kwargs):
        self._validate_data()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account} · {self.contact} · {self.get_role_display()}"
