from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from apps.sales.models._base import TenantNumbered, settings


class AccountPlan(TenantNumbered):
    NUMBER_PREFIX = "ACPL"
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("review_due", "Review Due"),
        ("completed", "Completed"),
        ("archived", "Archived"),
    ]

    account = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="sales_account_plans")
    title = models.CharField(max_length=160)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales_owned_account_plans",
    )
    business_drivers = models.TextField(blank=True)
    objectives = models.TextField(blank=True)
    strategy = models.TextField(blank=True)
    strengths = models.TextField(blank=True)
    weaknesses = models.TextField(blank=True)
    opportunities = models.TextField(blank=True)
    threats = models.TextField(blank=True)
    white_space_assessment = models.TextField(blank=True)
    growth_initiatives = models.TextField(blank=True)
    risk_summary = models.TextField(blank=True)
    next_review_on = models.DateField(null=True, blank=True)
    related_opportunities = models.ManyToManyField(
        "crm.Opportunity",
        related_name="sales_account_plans",
        blank=True,
    )

    class Meta:
        ordering = ["-period_start", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_acpl_tenant_number_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "account", "status"], name="sales_acpl_acct_status_idx"),
            models.Index(fields=["tenant", "owner", "next_review_on"], name="sales_acpl_owner_rev_idx"),
            models.Index(fields=["tenant", "status", "next_review_on"], name="sales_acpl_stat_rev_idx"),
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
        if not self.owner_id:
            errors["owner"] = "Choose an active user from this workspace."
        else:
            owner = type(self)._meta.get_field("owner").remote_field.model._default_manager.filter(
                pk=self.owner_id, tenant_id=self.tenant_id, is_active=True
            ).first()
            if owner is None:
                errors["owner"] = "Choose an active user from this workspace."
        if not self.period_start or not self.period_end:
            errors["period_start"] = "Choose a complete plan period."
        elif not isinstance(self.period_start, date) or not isinstance(self.period_end, date):
            errors["period_start"] = "Enter a valid plan period."
        elif self.period_end < self.period_start:
            errors["period_end"] = "The plan period cannot end before it starts."
        if errors:
            raise ValidationError(errors)

    def clean(self):
        super().clean()
        self._validate_data()

    def save(self, *args, **kwargs):
        self._validate_data()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.account} · {self.title}"


def validate_account_plan_opportunities(tenant, account, opportunities):
    if hasattr(opportunities, "values_list"):
        opportunity_ids = set(opportunities.values_list("pk", flat=True))
    else:
        opportunity_ids = {opportunity.pk for opportunity in opportunities}
    if not opportunity_ids:
        return
    if any(
        not isinstance(opportunity_id, int)
        or opportunity_id <= 0
        or opportunity_id > 9223372036854775807
        for opportunity_id in opportunity_ids
    ):
        raise ValidationError("Related opportunities must be selected by valid database identifiers.")
    from apps.core.models import Party

    account_id = getattr(account, "pk", account)
    account = Party.objects.filter(
        pk=account_id,
        tenant=tenant,
        kind="organization",
    ).first()
    if account is None:
        raise ValidationError("Related opportunities require a same-tenant organization account.")
    opportunity_model = AccountPlan._meta.get_field("related_opportunities").remote_field.model
    valid_ids = set(
        opportunity_model._default_manager.filter(
            tenant=tenant,
            account=account,
            account__tenant=tenant,
            account__kind="organization",
            pk__in=opportunity_ids,
        ).values_list("pk", flat=True)
    )
    if valid_ids != opportunity_ids:
        raise ValidationError("Related opportunities must belong to the selected account and workspace.")


@receiver(m2m_changed, sender=AccountPlan.related_opportunities.through)
def validate_account_plan_opportunity_links(sender, instance, action, reverse, model, pk_set, **kwargs):
    if not instance.pk or action != "pre_add":
        return
    try:
        selected_ids = {int(value) for value in (pk_set or set())}
    except (TypeError, ValueError) as exc:
        raise ValidationError("Related opportunities must be selected by valid database identifiers.") from exc
    if any(value <= 0 or value > 9223372036854775807 for value in selected_ids):
        raise ValidationError("Related opportunities must be selected by valid database identifiers.")
    if not selected_ids:
        return

    if reverse:
        plans = AccountPlan.objects.filter(pk__in=selected_ids).only("pk", "tenant_id", "account_id")
        if any(plan.tenant_id != instance.tenant_id or plan.account_id != instance.account_id for plan in plans):
            raise ValidationError("Related opportunities must belong to the selected account and workspace.")
        if plans.count() != len(selected_ids):
            raise ValidationError("Related opportunities must belong to the selected account and workspace.")
        return
    opportunity_model = AccountPlan._meta.get_field("related_opportunities").remote_field.model
    opportunities = opportunity_model._default_manager.filter(pk__in=selected_ids)
    validate_account_plan_opportunities(instance.tenant_id, instance.account_id, opportunities)
