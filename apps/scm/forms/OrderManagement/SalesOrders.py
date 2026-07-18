"""SCM 4.5 Order Management System — SalesOrder form + line formset."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _active_currencies, _customer_parties
from apps.scm.models import SalesOrder, SalesOrderLine


class SalesOrderForm(TenantModelForm):
    """The order header.

    EXCLUDES everything the workflow owns: `status` (advanced only by the submit/fulfill/cancel
    actions), `number`, `promised_date`, the three hold fields, the three notification timestamps
    and the three derived totals. `source_quote` is excluded too — it records where an order came
    from and is set by `salesorder_create_from_quote`; letting a user point an order at an arbitrary
    quote after the fact would make the provenance a claim rather than a fact.
    """

    class Meta:
        model = SalesOrder
        # `invoice` is NOT here. It is chosen on the mark-invoiced action instead: this form is
        # editable only while the order is `draft`, and the invoice does not exist until after
        # fulfillment, so a field here could never actually be filled in (code review).
        fields = ["customer", "ship_to_address", "source_channel", "order_date", "requested_date",
                  "currency", "payment_terms", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Party carries no `customer`-only flag of its own, so TenantModelForm's generic tenant
        # scoping would offer every party including suppliers. Narrow it to the customer role.
        self.fields["customer"].queryset = _customer_parties(self.tenant)
        # Currency is GLOBAL (no tenant FK), so it needs the shared explicit scoping helper.
        _active_currencies(self)
        if self.tenant is not None:
            from apps.core.models import Address
            self.fields["ship_to_address"].queryset = (
                Address.objects.filter(tenant=self.tenant).select_related("party").order_by("party__name"))
            self.fields["ship_to_address"].help_text = "Must be an address belonging to the customer"

    def clean(self):
        """Enforce that the ship-to address belongs to the chosen customer.

        This was originally done by narrowing the queryset to the customer's addresses, which made
        the field UNUSABLE on create: no customer is chosen yet when the form is first built, so the
        dropdown was always empty and a new order could never be given a ship-to at all (frontend
        review). Validating the relationship is the correct guard anyway — a narrowed queryset is
        only UX, and it is the clean() that actually stops a crafted POST attaching someone else's
        address.
        """
        cleaned = super().clean()
        customer, address = cleaned.get("customer"), cleaned.get("ship_to_address")
        if customer and address and address.party_id != customer.pk:
            self.add_error("ship_to_address",
                           f"That address belongs to {address.party.name}, not {customer.name}.")
        return cleaned


class SalesOrderLineForm(TenantModelForm):
    """One ordered item.

    `item` is a real FK, auto-scoped by TenantModelForm because `Item` carries its own tenant —
    no `_scope_to_parent` hand-scoping needed, unlike PurchaseOrderLine/RFQLine. That is a genuine
    simplification from shipping after 4.3, not an oversight.
    """

    class Meta:
        model = SalesOrderLine
        fields = ["item", "description", "quantity_ordered", "unit_price", "discount_pct", "tax_pct"]


class BaseSalesOrderLineFormSet(forms.BaseInlineFormSet):
    """Refuses to remove — or under-order — a line that stock is already reserved against.

    `SalesOrderAllocation.sales_order_line` is CASCADE, so deleting a line here would silently take
    its reservations with it: the stock would stop being spoken for with no record that it ever was,
    and the warehouse could already be picking against it. Same rule as
    `BasePurchaseOrderLineFormSet` blocking removal of a received line — you cannot un-order what is
    already committed.

    Also blocks reducing `quantity_ordered` below what is already allocated, which would leave the
    line over-allocated and `quantity_backordered()` clamped at zero, hiding the inconsistency.
    """

    def clean(self):
        super().clean()
        removed, shrunk = [], []
        for form in self.forms:
            inst = form.instance
            if not inst.pk:
                continue
            allocated = inst.quantity_allocated()
            if allocated <= 0:
                continue
            label = inst.item.sku if inst.item_id else f"line {inst.pk}"
            if self._should_delete_form(form):
                removed.append(label)
            elif form.cleaned_data.get("quantity_ordered") is not None \
                    and form.cleaned_data["quantity_ordered"] < allocated:
                shrunk.append(f"{label} ({allocated} allocated)")
        if removed:
            raise forms.ValidationError(
                "These lines have stock allocated against them and cannot be removed: "
                f"{', '.join(removed)}. Cancel the allocation first."
            )
        if shrunk:
            raise forms.ValidationError(
                "These lines would be ordered for less than is already allocated: "
                f"{', '.join(shrunk)}. Cancel some of the allocation first."
            )


SalesOrderLineFormSet = inlineformset_factory(
    SalesOrder, SalesOrderLine, form=SalesOrderLineForm,
    formset=BaseSalesOrderLineFormSet, extra=1, can_delete=True,
)
