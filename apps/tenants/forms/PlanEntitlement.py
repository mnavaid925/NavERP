"""tenants — PlanEntitlement form (0.19, plan grants + subscription-level overrides)."""
from django.core.exceptions import ValidationError

from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    PlanEntitlement,
)


class PlanEntitlementForm(TenantModelForm):
    """`TenantModelForm`, never a plain `ModelForm` ([RULING] 9) — see the 0.19 contract.

    Excluded from `Meta.fields`:
      * `number` — `editable=False`, minted in `save()`; the exclusion is belt-and-braces.
      * `tenant` — set by the view.

    `subscription` STAYS on the form, and that is the point of the model: an operator has to be able
    to record an override, and a form that could not set it would leave `is_override` permanently
    `False`. It is nullable, so the empty choice IS the "plan-level grant" case.

    `is_override` is NOT a field — it is a `@property` derived from `subscription_id` ([RULING] 3).
    """

    class Meta:
        model = PlanEntitlement
        fields = ["plan", "feature", "privilege_value", "is_add_on", "subscription",
                  "effective_from", "effective_to", "is_enabled", "notes"]

    def clean(self):
        """The [RULING] 2 duplicate-plan-grant guard, keyed on `subscription`.

        `unique_together = (tenant, plan, feature, subscription)` does NOT stop two plan-level
        grants for the same triple: MySQL and SQLite BOTH treat NULLs as distinct inside a unique
        index, so both rows are accepted, every time — on the production database and on the
        in-memory test database alike, which is why no test written against this project would
        surface it. The tuple is still load-bearing for the OVERRIDE case (two identical overrides
        should collide), so it stays; the plan-level invariant is enforced here instead, at the only
        place a user can create one.

        Keyed on a field this form actually HAS, so it renders as a form error rather than a 500.

        The model's privilege-value TYPE check and the date-ordering check are enforced automatically
        by `full_clean()` and are deliberately not duplicated here.
        """
        super().clean()
        subscription = self.cleaned_data.get("subscription")
        plan = self.cleaned_data.get("plan")
        feature = self.cleaned_data.get("feature")
        tenant = getattr(self, "tenant", None)
        if subscription is not None or not plan or feature is None or tenant is None:
            # An override's duplicate is caught by the real unique_together (all four members
            # non-null), so only the plan-level case needs a guard here.
            return self.cleaned_data
        clash = PlanEntitlement.objects.filter(
            tenant=tenant, plan=plan, feature=feature, subscription__isnull=True,
        )
        if self.instance and self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise ValidationError({
                "subscription": "This plan already has a grant for that feature. Edit it, or set a "
                                 "subscription to record an override instead.",
            })
        return self.cleaned_data
