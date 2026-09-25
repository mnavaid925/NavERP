from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.accounts.models import User
from apps.core.models import Party
from apps.crm.models import Opportunity
from apps.sales.forms._common import TenantModelForm, _reject_foreign
from apps.sales.models.ContactAccountManagement.AccountPlans import AccountPlan, validate_account_plan_opportunities


class AccountPlanForm(TenantModelForm):
    class Meta:
        model = AccountPlan
        fields = [
            "account", "title", "period_start", "period_end", "owner",
            "business_drivers", "objectives", "strategy", "strengths", "weaknesses",
            "opportunities", "threats", "white_space_assessment", "growth_initiatives",
            "risk_summary", "next_review_on", "related_opportunities",
        ]
        widgets = {
            "business_drivers": forms.Textarea(attrs={"rows": 3}),
            "objectives": forms.Textarea(attrs={"rows": 3}),
            "strategy": forms.Textarea(attrs={"rows": 5}),
            "strengths": forms.Textarea(attrs={"rows": 3}),
            "weaknesses": forms.Textarea(attrs={"rows": 3}),
            "opportunities": forms.Textarea(attrs={"rows": 3}),
            "threats": forms.Textarea(attrs={"rows": 3}),
            "white_space_assessment": forms.Textarea(attrs={"rows": 4}),
            "growth_initiatives": forms.Textarea(attrs={"rows": 4}),
            "risk_summary": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, tenant=None, user=None, **kwargs):
        self.user = user
        instance = kwargs.get("instance")
        if instance is None and len(args) > 5:
            instance = args[5]
        if instance is not None and instance.pk:
            if not hasattr(instance, "_prefetched_objects_cache"):
                instance._prefetched_objects_cache = {}
            instance._prefetched_objects_cache["related_opportunities"] = list(
                Opportunity.objects.filter(
                    sales_account_plans=instance,
                    tenant=instance.tenant_id,
                    account_id=instance.account_id,
                ).only(
                    "id", "number", "name", "tenant_id", "account_id", "created_at"
                )
            )
            if "instance" not in kwargs:
                args = list(args)
                args[5] = instance
        super().__init__(*args, tenant=tenant, **kwargs)
        if tenant is not None:
            account_ids = list(Party.objects.filter(
                tenant=tenant, kind="organization"
            ).order_by("name").values_list("pk", flat=True)[:500])
            owner_ids = list(User.objects.filter(
                tenant=tenant, is_active=True
            ).order_by("username").values_list("pk", flat=True)[:500])
            self.fields["account"].queryset = Party.objects.filter(pk__in=account_ids)
            self.fields["owner"].queryset = User.objects.filter(pk__in=owner_ids)
            opportunity_queryset = Opportunity.objects.filter(tenant=tenant)
            account_value = self.data.get("account") if self.is_bound else None
            if not account_value and self.instance.pk:
                account_value = self.instance.account_id
            selected_ids = []
            if self.instance.pk:
                cached = getattr(self.instance, "_prefetched_objects_cache", {}).get("related_opportunities")
                if cached is not None:
                    selected_ids = [opportunity.pk for opportunity in cached]
                else:
                    selected_ids = list(
                        self.instance.related_opportunities.filter(
                            tenant=self.instance.tenant_id,
                            account_id=self.instance.account_id,
                        ).values_list("pk", flat=True)
                    )
            if account_value and str(account_value).isdecimal():
                opportunity_queryset = opportunity_queryset.filter(
                    Q(account_id=account_value) | Q(pk__in=selected_ids)
                )
            elif selected_ids:
                opportunity_queryset = opportunity_queryset.filter(pk__in=selected_ids)
            bounded_opportunity_ids = list(opportunity_queryset.only(
                "id", "number", "name", "tenant_id", "account_id", "created_at"
            ).order_by("-created_at").values_list("pk", flat=True)[:500])
            self.fields["related_opportunities"].queryset = Opportunity.objects.filter(
                pk__in=bounded_opportunity_ids
            ).only("id", "number", "name", "tenant_id", "account_id", "created_at").order_by("-created_at")
        else:
            self.fields["account"].queryset = Party.objects.none()
            self.fields["owner"].queryset = User.objects.none()
            self.fields["related_opportunities"].queryset = Opportunity.objects.none()
        if self.instance.pk:
            self.fields["account"].disabled = True
        if user is not None and not (
            getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False)
        ):
            self.fields["owner"].queryset = User.objects.filter(pk=user.pk, tenant=tenant, is_active=True)
            self.fields["owner"].disabled = True
            if not self.instance.pk:
                self.initial["owner"] = user.pk

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["account", "owner", "related_opportunities"])
        period_start = cleaned.get("period_start")
        period_end = cleaned.get("period_end")
        if period_start and period_end and period_end < period_start:
            self.add_error("period_end", "The plan period cannot end before it starts.")
        account = cleaned.get("account")
        if account is not None and account.kind != "organization":
            self.add_error("account", "Choose a same-tenant organization account.")
        opportunities = cleaned.get("related_opportunities")
        if account and opportunities is not None:
            try:
                validate_account_plan_opportunities(self.tenant, account, opportunities)
            except ValidationError as exc:
                self.add_error("related_opportunities", exc)
        return cleaned
