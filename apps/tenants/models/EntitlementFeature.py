"""tenants — EntitlementFeature (0.19 "License & Subscription Administration", bullet 2).

THE COMMERCIAL FEATURE CATALOG A PLAN CAN GRANT.

A row here is a commercial term somebody wrote down, not a control that ran. `EntitlementFeature` is
the vocabulary: "this plan may do X". Whether any code consults it is a separate question, and in 0.19
the answer is NO (see the ten declines below). Writing the catalog is the work; enforcing it is
explicitly not in scope.

Deliberately NOT FK'd to `core.FeatureFlag` (0.6). `FeatureFlag` is a RUNTIME on/off switch
(`key`, `label`, `is_enabled`, `applies_to_plan`, `exempt_roles`) — "is this switch thrown right now".
This is the COMMERCIAL catalog a plan grants — "is this thing sellable". Two different facts about
two different things, and merging them would mean a feature's price-list entry and its kill switch are
the same row, so turning the feature off would rewrite what past subscriptions were entitled to.

**TEN capabilities are DECLINED by this sub-module, not partially faked:**
1. entitlement enforcement — no interceptor consults `PlanEntitlement` at request time;
2. quota enforcement / throttling — `UsageQuota.action_on_breach` is a recorded policy with no
   interceptor;
3. seat auto-deprovisioning — there is no identity sync, so reclaiming a seat does not disable a
   login;
4. metered event ingestion — there is no event pipeline;
5. proration — no money arithmetic is performed anywhere in 0.19 (L29);
6. prepaid credit grants — that would be a second money store (L29);
7. rate cards / tiered / multi-currency pricing — a monetization engine, not a sub-module;
8. plan versioning & grandfathering;
9. automatic renewal execution — no scheduler exists (0.20 owns it);
10. expiry email delivery — there is no sender in `tenants` (0.20/0.21 own it).

**The three ownership rulings, so no future reader re-litigates them:**
* 0.19 owns the **COMMERCIAL** limit. `UsageQuota` must NEVER be presented as an anti-abuse
  control — that bound belongs to `core.IpAccessRule` (0.18).
* `core.IpAccessRule` (0.18) owns the **abuse** bound; `core.AlertRule` (0.17) owns operational
  thresholds. Neither is a commercial term, so neither is re-declared here.
"""
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from apps.tenants.models._base import *  # noqa: F401,F403


#: A code is referenced by grants and by future config, so it is lowercase-and-underscored only.
#: Without this, "SSO" and "sso" become two features — the exact duplication 0.19 exists to prevent.
CODE_VALIDATOR = RegexValidator(
    r"^[a-z][a-z0-9_]{1,58}$",
    "Code must be lowercase letters, digits and underscores, starting with a letter.",
)


class EntitlementFeature(models.Model):
    #: Typed privileges (Lago `value_type`; OpenMeter Metered/Static/Boolean). The most reusable idea
    #: the survey produced: one catalog serves "is it on" AND "how many" AND "which variant".
    PRIVILEGE_TYPE_CHOICES = [
        ("boolean", "Boolean"),
        ("integer", "Integer"),
        ("select", "Select"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("archived", "Archived"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="entitlement_features", db_index=True)
    #: ENT-##### — minted in save() with a hardcoded literal rather than declared via NUMBER_PREFIX,
    #: which is why `settings_engine.LITERAL_PREFIX_MODELS` has to name this model.
    number = models.CharField(max_length=20, editable=False)
    #: The stable key a PlanEntitlement grant references. Indexed because grants join on it.
    code = models.CharField(max_length=60, db_index=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    privilege_type = models.CharField(max_length=12, choices=PRIVILEGE_TYPE_CHOICES,
                                      default="boolean")
    #: Newline- or comma-separated option list, meaningful ONLY when privilege_type == "select".
    #: `clean()` requires it non-blank in that case — a select privilege with no options is a value
    #: nobody can ever grant.
    select_options = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    #: Add-ons are sold on top of the plan (Lago fixed charges, Chargebee addons) rather than
    #: included in it.
    is_add_on = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]
        unique_together = (("tenant", "code"),)
        indexes = [
            models.Index(fields=["tenant", "status"], name="entfeat_tenant_status_idx"),
            models.Index(fields=["tenant", "code"], name="entfeat_tenant_code_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        # Assign ENT-#####; retry on the rare concurrent-collision (unique_together).
        for _ in range(5):
            self.number = next_number(EntitlementFeature, self.tenant, "ENT")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    def clean(self):
        """Two rules, both cheap and both real.

        Both live in `clean()` rather than as a DB constraint or a custom manager —
        `ModuleAccessScope` and `UsageRecord` put this class of rule in `clean()` too, and
        `ModelForm._post_clean()` calls `instance.full_clean()` automatically, so a form gets them
        for free and a second copy in the form would only drift.
        """
        super().clean()
        if self.privilege_type == "select" and not (self.select_options or "").strip():
            raise ValidationError({
                "select_options": "A Select privilege needs its option list, or it is a privilege "
                                  "nobody can ever be granted.",
            })
        if self.code:
            CODE_VALIDATOR(self.code)

    def __str__(self):
        # The CODE is what a grant references, so a stray "ENT-00001 · …" in an audit row is useless
        # and this is not.
        return f"{self.code} · {self.name}"

