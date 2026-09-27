"""tenants — PlanEntitlement (0.19 "License & Subscription Administration", bullet 2, grant half).

A PRIVILEGE GRANTED AT A PLAN, OR OVERRIDDEN AT ONE SUBSCRIPTION.

A row here is a commercial term somebody wrote down, not a control that ran. `NULL` subscription =
the plan-level grant every customer on that plan receives. A set subscription = the ONE subscription
that differs. Nothing reads this at request time — enforcement is decline #1 of the ten — so the
precedence rule is honoured only by the READ ORDER on the detail page, and the page says so.

`is_override` is a `@property`, NOT a column ([RULING] 3): `subscription` is `SET_NULL`, so a stored
boolean plus a nullable FK is a permanently-lying pair — delete the Subscription, `subscription_id`
becomes None while a stored `is_override` stays True, and the register then reports an override that
no longer exists. Derived from the FK it cannot lie.

**The `unique_together` is INERT for plan-level grants** ([RULING] 2): MySQL and SQLite BOTH treat
NULLs as distinct inside a unique index, so `(tenant, plan, feature, subscription)` does not stop two
plan-level grants for the same triple — both are accepted, every time. The tuple is kept because it
IS correct and load-bearing for the override case (two identical overrides should collide), and the
invariant that actually matters is enforced in `clean()` below, at the only place a user can create
one. The database is not asked to do what it cannot do.

**Ownership:** 0.19 owns the COMMERCIAL limit only. The abuse bound is `core.IpAccessRule` (0.18)
and operational thresholds are `core.AlertRule` (0.17); neither is re-declared here. `EntitlementFeature`
is deliberately not FK'd to `core.FeatureFlag` (0.6) — a runtime switch and a price-list term are
two different facts.

**The same TEN declines as the rest of 0.19, restated so this file stands alone:** entitlement
enforcement · quota enforcement/throttling · seat auto-deprovisioning · metered event ingestion ·
proration · prepaid credit grants · rate cards / tiered / multi-currency pricing · plan versioning &
grandfathering · automatic renewal execution · expiry email delivery.
"""
from django.core.exceptions import ValidationError

from apps.tenants.models._base import *  # noqa: F401,F403


#: `Tenant.PLAN_CHOICES` BY REFERENCE (L36: assign the object, never rebuild the tuple) — the
#: four-value vocabulary already exists and a second one would drift. There is deliberately NO
#: `PlanTier` table: Zuora-scale plan modelling is out of scope.
PLAN_CHOICES = Tenant.PLAN_CHOICES


class PlanEntitlement(models.Model):
    #: Re-exposed on the class exactly as `Subscription` re-exposes `Tenant.PLAN_CHOICES`, so a
    #: template and a filter read the same object.
    PLAN_CHOICES = PLAN_CHOICES

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="plan_entitlements", db_index=True)
    #: PE-##### — minted in save(); see `settings_engine.LITERAL_PREFIX_MODELS`.
    number = models.CharField(max_length=20, editable=False)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="starter")
    feature = models.ForeignKey("tenants.EntitlementFeature", on_delete=models.CASCADE,
                                related_name="plan_entitlements")
    #: Holds `true` / `10` / `okta` — a CHAR, not typed columns, because ONE column must serve all
    #: three privilege types. `clean()` is what makes the privilege actually typed.
    privilege_value = models.CharField(max_length=120, blank=True)
    is_add_on = models.BooleanField(default=False)
    #: NULLABLE, and that nullability is the whole model: NULL = the plan-level grant, set = the
    #: subscription-level OVERRIDE. `unique_together` includes it so two identical overrides collide.
    subscription = models.ForeignKey("tenants.Subscription", on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="entitlement_overrides")
    effective_from = models.DateField(null=True, blank=True)
    #: Chargebee's "Forever" vs "Until <date>". NULL is Forever, not "unset".
    effective_to = models.DateField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["plan", "feature__code", "-id"]
        unique_together = (("tenant", "plan", "feature", "subscription"),)
        indexes = [
            models.Index(fields=["tenant", "plan"], name="planent_tenant_plan_idx"),
            models.Index(fields=["tenant", "feature"], name="planent_tenant_feature_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        # Assign PE-#####; retry on the rare concurrent-collision (unique_together).
        for _ in range(5):
            self.number = next_number(PlanEntitlement, self.tenant, "PE")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    # --------------------------------------------------------------- derived (never stored)
    @property
    def is_override(self):
        """True when this row overrides the plan grant for ONE subscription ([RULING] 3).

        A @property, never a column: `subscription` is `SET_NULL`, so a stored boolean would outlive
        the row it claims to describe.
        """
        return self.subscription_id is not None

    def clean(self):
        """Three rules.

        (a) the [RULING] 2 duplicate-plan-grant guard, (b) the date ordering guard, and (c) the
        privilege-value type check that makes a TYPED privilege typed. Rule (c) is the one that
        matters: without it `privilege_type` is a label and "granted: `banana` for an integer
        privilege" is shippable.
        """
        super().clean()
        # (d) Tenant consistency on the override. The form scopes the `subscription` dropdown, so a
        # crafted POST is already rejected; this closes the UNSCOPED Django admin, which is the only
        # remaining path. It matters here because the detail page's whole read-order argument
        # ([RULING] 3) assumes an override's subscription lives in the same workspace as the grant.
        #
        # `Subscription` is referenced through the models PACKAGE, not imported from
        # `apps.tenants.models.Subscription`: both are in the same package, and `_base` does not
        # re-export it, so the name is genuinely out of scope here.
        if self.tenant_id and self.subscription_id:
            from apps.tenants.models import Subscription as _Subscription
            if not _Subscription.objects.filter(
                pk=self.subscription_id, tenant_id=self.tenant_id
            ).exists():
                raise ValidationError({
                    "subscription": "That subscription belongs to another workspace.",
                })
        if self.subscription_id is None and self.tenant_id and self.plan and self.feature_id:
            clash = PlanEntitlement.objects.filter(
                tenant_id=self.tenant_id, plan=self.plan, feature_id=self.feature_id,
                subscription__isnull=True,
            ).exclude(pk=self.pk)
            if clash.exists():
                raise ValidationError({
                    "subscription": "This plan already has a grant for that feature. Edit it, or "
                                     "set a subscription to record an override instead.",
                })
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({
                "effective_to": "The end of the entitlement cannot be before its start.",
            })
        self._check_privilege_value()

    def _check_privilege_value(self):
        """Rule (c): `privilege_value` must parse against the feature's `privilege_type`.

        A blank value is always allowed — "this plan is NOT granted the feature" is a real answer,
        and the row's existence is the statement. Only a SET value is type-checked.
        """
        value = (self.privilege_value or "").strip()
        if not value:
            return
        feature = self.feature if self.feature_id else None
        privilege_type = getattr(feature, "privilege_type", None)
        if privilege_type == "boolean":
            if value.lower() not in ("true", "false"):
                raise ValidationError({
                    "privilege_value": "A Boolean privilege takes `true` or `false`.",
                })
        elif privilege_type == "integer":
            try:
                int(value)
            except (TypeError, ValueError):
                raise ValidationError({
                    "privilege_value": "An Integer privilege takes a whole number.",
                })
        elif privilege_type == "select":
            options = _select_option_list(feature.select_options)
            if options and value not in options:
                raise ValidationError({
                    "privilege_value": f"Choose one of the feature's options: {', '.join(options)}.",
                })

    def __str__(self):
        return f"{self.plan}: {self.feature.code} = {self.privilege_value or '—'}"



def _select_option_list(text):
    """Split a `select_options` blob into comparable option values.

    The field is free text (newline- OR comma-separated), so both separators are honoured; values are
    stripped and blanks dropped, so a trailing separator is not an option.
    """
    raw = (text or "").replace("\r", "\n")
    parts = []
    for chunk in raw.replace(",", "\n").split("\n"):
        value = chunk.strip()
        if value:
            parts.append(value)
    return parts
