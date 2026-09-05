"""Procurement 6.18 Inventory & Warehouse Integration — replenishment run + suggestion forms.

Two shapes, and the interesting thing about both is how SMALL they are.

``ReplenishmentRunForm`` carries the five things a person decides before a run happens — where,
when, why, which ABC class, and a note. Everything the run *produces* is excluded, because a
proposal that could be typed in is not a proposal: ``status``, ``generated_by``, ``generated_at``
and ``released_at`` are stamped by :meth:`ReplenishmentRun.generate` / ``release`` alone, and
``number`` by ``TenantNumbered.save()``.

``ReplenishmentSuggestionDecisionForm`` exposes exactly FOUR fields on a model with eleven
snapshot columns. Those eleven are ``editable=False`` on the model, so Django's ``ModelForm``
would refuse to render them anyway — the explicit ``fields`` list is the second lock, and it is
there because a snapshot that a POST could rewrite would let somebody edit the evidence for a
decision after taking it. ``requisition`` is excluded for the same reason: it records where the
line was released to, and it is stamped by ``release()``.

**Tenant discipline.** Both forms accept ``tenant=`` (every ``crud_*`` helper passes it) and both
narrow their dropdowns to the workspace. A narrowed ``<select>`` is presentation, **not** an
authorization boundary — a crafted POST never goes near the rendered page — so each form
re-checks its FKs in ``clean()`` via ``_reject_foreign``, and the model's own ``clean()`` sits
behind that as the last line. Three layers, because a cross-tenant vendor on an accepted
suggestion would put another workspace's supplier on a requisition that commits real money.

**Why the decision form is not a ``TenantUniqueMixin`` form.** ``ReplenishmentSuggestion`` has no
``tenant`` column at all — tenant is reached through the run — so the mixin's ``instance.tenant``
stamp has nothing to write to. The line's workspace comes from ``run.tenant``, and the decide view
loads it as ``run__tenant=request.tenant``, which is where that boundary is actually enforced.
"""
from django.utils import timezone

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.InventoryWarehouseIntegration.Runs import (ReplenishmentRun,
                                                                        ReplenishmentSuggestion)


class ReplenishmentRunForm(TenantUniqueMixin, TenantModelForm):
    """Create or amend the header of a replenishment run.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``:
    ``ReplenishmentRun.clean()`` compares the chosen location's tenant against ``self.tenant_id``,
    and without the stamp every CREATE would be falsely rejected as cross-tenant. The mixin's
    ``validate_unique`` override matters too — ``unique_together`` is ``(tenant, number)`` and
    neither is a form field, so Django's default exclusion list would drop the constraint.

    Editing the header of a run that has already proposed is allowed by the form and gated by the
    VIEW (``is_editable``): changing the location on a proposed run would leave lines that no
    longer match their own scope, so the view refuses it and offers Generate instead.
    """

    class Meta:
        model = ReplenishmentRun
        # Listed explicitly rather than via ``exclude`` so a column added to the model later
        # cannot silently become a form input — which for this model would mean a status or a
        # generated_at that a POST can set.
        fields = ["location", "run_date", "trigger", "abc_class_filter", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's locations
            # and must not be able to post one either.
            self.fields["location"].queryset = self.fields["location"].queryset.none()
        else:
            from apps.scm.models import Location

            self.fields["location"].queryset = (
                Location.objects.filter(tenant=tenant, is_active=True).order_by("code"))

        # Blank means something specific here, so it does not get the bare "---------".
        self.fields["location"].empty_label = "- whole network -"
        self.fields["abc_class_filter"].help_text = (
            "Optional. Plan only this ABC class. This is the reorder rule's UPPERCASE revenue "
            "rank (A/B/C) — not the location's lowercase bin-velocity class.")

        if not self.instance.pk and not self.initial.get("run_date"):
            # A run is almost always for today; pre-filling it removes the one field a buyer
            # would otherwise have to key on every single run.
            self.initial["run_date"] = timezone.localdate()

    def clean(self):
        cleaned = super().clean()
        # Re-check the one tenant-scoped FK: the narrowed <select> above is presentation, and a
        # crafted POST never goes near it.
        _reject_foreign(self, cleaned, ["location"])
        return cleaned


class ReplenishmentSuggestionDecisionForm(TenantModelForm):
    """The buyer's verdict on one proposed line — and nothing else.

    Four fields on a model with eleven snapshot columns. The snapshots are ``editable=False``, so
    this list is belt AND braces: what a run measured stays what a run measured, and the record
    still explains itself when somebody asks in three weeks why 40 were ordered.

    ``vendor`` is here on purpose. The policy's preferred vendor is a DEFAULT, not a verdict, and
    the person accepting the line is the one who knows a better price exists this month. Changing
    it changes which requisition the line groups into at release, and nothing else.
    """

    class Meta:
        model = ReplenishmentSuggestion
        fields = ["decision", "snooze_until", "vendor", "decision_note"]
        widgets = {
            "decision_note": forms.TextInput(
                attrs={"class": "form-input",
                       "placeholder": "Why — the next person reading this run has only this line"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            self.fields["vendor"].queryset = self.fields["vendor"].queryset.none()
        else:
            from apps.core.models import Party

            # Same supplier-or-vendor rule the policy form uses: core.PartyRole distinguishes
            # 'supplier' from 'vendor' and workspaces use both interchangeably, so both are
            # offered — hiding half the counterparties would be a worse bug than the one this
            # narrowing prevents. TenantModelForm has already applied the TENANT filter; this is
            # the extra rule on top of it.
            self.fields["vendor"].queryset = (
                Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
                .distinct().order_by("name"))

        self.fields["vendor"].empty_label = "- unassigned -"
        self.fields["decision_note"].required = False

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["vendor"])
        return cleaned
