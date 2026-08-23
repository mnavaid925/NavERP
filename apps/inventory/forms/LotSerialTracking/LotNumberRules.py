"""Inventory 5.8 Lot & Serial Number Tracking — forms."""
from django import forms
from django.db.models import Q

from apps.inventory.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.inventory.models import LotNumberRule, ShelfLifePolicy
from apps.scm.models import Item


class LotNumberRuleForm(TenantUniqueMixin, TenantModelForm):
    """A numbering pattern. ``TenantUniqueMixin`` makes the ``(tenant, name)``
    unique_together validate at the boundary AND stamps ``instance.tenant`` for
    ``clean()``'s foreign-item check on create."""

    class Meta:
        model = LotNumberRule
        fields = ["name", "item", "kind", "prefix", "include_date",
                  "sequence_padding", "is_active", "notes"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item"])
        return cleaned


class ShelfLifePolicyForm(TenantUniqueMixin, TenantModelForm):
    """One SKU's shelf-life regime. The OneToOne uniqueness is plain ``unique=True``
    on the item column (one regime per SKU row), which Django validates natively; the
    mixin stays for its tenant stamp so ``clean()``'s foreign-item check sees a tenant."""

    class Meta:
        model = ShelfLifePolicy
        fields = ["item", "shelf_life_days", "min_remaining_days", "warning_days",
                  "fefo_enforced", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A policy only bites where lots exist to age — steer to tracked SKUs. The
        # stored value is unioned back in so editing a row whose item was later
        # switched to untracked still re-renders instead of silently wiping the field.
        if self.tenant is not None:
            from apps.scm.models import Item
            condition = Q(tracking__in=("lot", "serial"))
            current_id = getattr(self.instance, "item_id", None)
            if current_id and not self.is_bound:
                condition |= Q(pk=current_id)
            self.fields["item"].queryset = (Item.objects.filter(tenant=self.tenant)
                                            .filter(condition).order_by("sku"))

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item"])
        return cleaned


class GenerateLotForm(forms.Form):
    """The one-click batch-number mint — not a ModelForm: the OUTPUT is an
    ``scm.LotSerial`` (the spine's row), assembled by ``LotNumberRule.generate()``
    under whichever rule resolves for the chosen item."""

    item = forms.ModelChoiceField(queryset=Item.objects.none(), label="Tracked item")
    expiry_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional — leave empty for goods that do not expire")
    notes = forms.CharField(max_length=255, required=False,
                            help_text="Why this batch exists, e.g. 'PO-00042 receipt'")

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None:
            self.fields["item"].queryset = (Item.objects
                                            .filter(tenant=tenant,
                                                    tracking__in=("lot", "serial"))
                                            .order_by("sku"))

    def clean(self):
        cleaned = super().clean()
        # Defence in depth: the queryset was already tenant-scoped in __init__, but the
        # re-check costs one comparison and keeps every form in the app under one rule.
        item = cleaned.get("item")
        if item is not None and self.tenant is not None \
                and item.tenant_id != self.tenant.pk:
            self.add_error("item", "That record belongs to another workspace.")
        return cleaned
