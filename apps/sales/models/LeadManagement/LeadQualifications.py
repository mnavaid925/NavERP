from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import *


def _relation_belongs_to_tenant(instance, field_name):
    if not instance.tenant_id:
        return True
    field = instance._meta.get_field(field_name)
    related_id = getattr(instance, f"{field_name}_id", None)
    if not related_id:
        return True
    related_model = field.remote_field.model
    return related_model._default_manager.filter(pk=related_id, tenant_id=instance.tenant_id).exists()


class LeadQualification(TenantOwned):
    FRAMEWORK_CHOICES = [
        ("bant", "BANT"),
        ("meddic", "MEDDIC"),
        ("both", "BANT + MEDDIC"),
    ]
    STATUS_CHOICES = [
        ("unassessed", "Unassessed"),
        ("partially_qualified", "Partially Qualified"),
        ("qualified", "Qualified"),
        ("disqualified", "Disqualified"),
        ("archived", "Archived"),
    ]
    SENIORITY_CHOICES = [
        ("unknown", "Unknown"),
        ("individual_contributor", "Individual Contributor"),
        ("manager", "Manager"),
        ("director", "Director"),
        ("executive", "Executive"),
        ("owner", "Owner"),
    ]
    BUDGET_STATUS_CHOICES = [
        ("unknown", "Unknown"),
        ("not_confirmed", "Not Confirmed"),
        ("confirmed", "Confirmed"),
        ("adequate", "Adequate"),
        ("insufficient", "Insufficient"),
    ]
    AUTHORITY_LEVEL_CHOICES = [
        ("unknown", "Unknown"),
        ("influencer", "Influencer"),
        ("user", "User"),
        ("manager", "Manager"),
        ("director", "Director"),
        ("executive", "Executive"),
        ("owner", "Owner"),
    ]

    lead = models.OneToOneField("crm.Lead", on_delete=models.PROTECT, related_name="sales_qualification")
    framework = models.CharField(max_length=10, choices=FRAMEWORK_CHOICES, default="bant")
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="unassessed")
    country_code = models.CharField(max_length=2, blank=True)
    region = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    industry = models.CharField(max_length=120, blank=True)
    employee_count = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    seniority = models.CharField(max_length=24, choices=SENIORITY_CHOICES, default="unknown")
    budget_status = models.CharField(max_length=24, choices=BUDGET_STATUS_CHOICES, default="unknown")
    budget_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    budget_currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    authority_level = models.CharField(max_length=24, choices=AUTHORITY_LEVEL_CHOICES, default="unknown")
    need_summary = models.TextField(blank=True)
    expected_purchase_on = models.DateField(null=True, blank=True)
    economic_buyer = models.TextField(blank=True)
    decision_criteria = models.TextField(blank=True)
    decision_process = models.TextField(blank=True)
    technical_requirements = models.TextField(blank=True)
    pain_points = models.TextField(blank=True)
    success_metrics = models.TextField(blank=True)
    disqualification_reason = models.TextField(blank=True)
    assessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales_lead_assessments")
    assessed_at = models.DateTimeField(null=True, blank=True, editable=False)
    next_review_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_lq_tnt_status_idx"),
            models.Index(fields=["tenant", "framework"], name="sales_lq_tnt_framework_idx"),
            models.Index(fields=["tenant", "next_review_on"], name="sales_lq_tnt_review_idx"),
        ]

    @property
    def is_terminal(self):
        return self.status in {"qualified", "disqualified", "archived"}

    def clean(self):
        super().clean()
        if self.country_code:
            self.country_code = self.country_code.strip().upper()
            if len(self.country_code) != 2 or not self.country_code.isalpha():
                raise ValidationError({"country_code": "Enter a two-letter country code."})
        if not _relation_belongs_to_tenant(self, "lead"):
            raise ValidationError({"lead": "The lead must belong to this workspace."})
        if not _relation_belongs_to_tenant(self, "assessed_by"):
            raise ValidationError({"assessed_by": "The assessor must belong to this workspace."})
        if self.budget_amount is not None and not self.budget_currency_id:
            raise ValidationError({"budget_currency": "Choose a currency for the budget amount."})
        if self.status == "disqualified" and not (self.disqualification_reason or "").strip():
            raise ValidationError({"disqualification_reason": "A reason is required for a disqualified lead."})
        if self.status in {"qualified", "disqualified", "archived"} and not self.assessed_by_id:
            raise ValidationError({"assessed_by": "An assessor is required for a terminal decision."})
        if self.status == "qualified":
            required = ["need_summary", "expected_purchase_on"]
            if self.framework in {"meddic", "both"}:
                required.extend(["economic_buyer", "decision_criteria", "decision_process"])
            if self.framework in {"bant", "both"}:
                required.extend(["budget_status", "authority_level"])
            missing = [name for name in required if not getattr(self, name)]
            if self.framework in {"bant", "both"} and self.budget_status == "unknown":
                missing.append("budget_status")
            if self.framework in {"bant", "both"} and self.authority_level == "unknown":
                missing.append("authority_level")
            if missing:
                raise ValidationError({name: "This framework requires a value before qualification." for name in sorted(set(missing))})

    def save(self, *args, **kwargs):
        if self.pk:
            previous_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous_status == "archived" and self.status != "archived":
                raise ValidationError({"status": "Archived assessments cannot be reopened."})
        if self.status in {"qualified", "disqualified", "archived"} and self.assessed_at is None:
            self.assessed_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.lead.number} · {self.get_status_display()}"
