"""SCM 4.16 Customer Portal — the ``PortalAccount`` staff form.

This row IS the configuration: there is no lifecycle on it and no verb that owns a field, so the
form takes everything except the system columns. The two rules worth reading before editing:

* **``catalog_scope == "categories"`` needs at least one category, and that rule can only live
  here.** ``catalog_categories`` is a ManyToMany, and an M2M has no rows until *after* ``save()`` —
  on create the instance has no pk to hang them on, so the equivalent check in
  ``PortalAccount.clean()`` would see an empty set for every new account and reject configurations
  that are perfectly valid. At the form boundary the submitted category ids are already in
  ``cleaned_data``, which is the only place the rule is enforceable at all.
* **Narrowed dropdowns are UX, never the boundary.** ``customer`` and ``default_ship_to`` are
  re-checked through ``_reject_foreign`` because a ``<select>`` has never held against a crafted
  POST (L39 §2), and ``PortalAccount.clean()`` carries the ownership rule a third time at the model
  boundary. Three layers is not belt-and-braces here: the model check is the one that holds for the
  seeder and the shell, and the form check is the one that renders as a field error instead of a 500.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _customer_parties, _reject_foreign

from apps.core.models import Address
from apps.scm.models import ItemCategory, PortalAccount


class PortalAccountForm(TenantUniqueMixin, TenantModelForm):
    """Staff-facing create/edit for one customer's portal configuration.

    ``TenantUniqueMixin`` is mixed in FIRST because ``PortalAccount`` carries
    ``unique_together = (("tenant", "number"), ("tenant", "customer"))`` and the second pair is a
    rule a user can break by hand: enabling the portal twice for the same company. Without the
    mixin that duplicate passes ``is_valid()`` and then raises an uncaught ``IntegrityError`` on
    ``save()`` — an everyday mistake turning into a 500 on a mainline CRUD path.
    """

    class Meta:
        model = PortalAccount
        # EXPLICIT whitelist, never `exclude`. With `exclude` a field added to the model later is
        # silently added to the form too, which is how a system column ends up user-editable without
        # anybody deciding it should be. Everything absent here is either a system column
        # (`tenant`, `number`, `activated_on`, the timestamps) or does not exist.
        fields = [
            "customer", "is_active",
            # entitlements
            "can_track_shipments", "can_view_invoices", "can_view_documents",
            "can_raise_inquiries", "can_request_returns", "show_credit_and_balance",
            # stock presentation
            "stock_display", "low_stock_threshold", "show_by_location",
            # catalog scope
            "catalog_scope", "catalog_categories",
            # pricing
            "price_basis",
            # shipping default
            "default_ship_to",
            # notification preferences (stored intent only — see the help text)
            "notify_on_shipment", "notify_on_delivery", "notify_on_exception", "preferred_channel",
            # presentation extras
            "welcome_message", "support_email", "notes",
        ]
        widgets = {
            "welcome_message": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "catalog_categories": forms.SelectMultiple(attrs={"size": 8}),
        }
        help_texts = {
            # Stated ABOVE the field rather than only in a validation error: someone choosing
            # "Last ordered" is entitled to know what it will actually show before they pick it.
            "price_basis":
                "There is no customer price list in this system yet. 'Last ordered' shows this "
                "customer their own most recent unit price for each item, worked out when the page "
                "renders; 'Hidden' shows no price at all. Neither one quotes a new price.",
            "catalog_categories":
                "Only used when the scope is 'Selected categories only' — pick at least one there.",
            # Says out loud what the empty queryset below would otherwise leave the user guessing
            # about. A dropdown that is blank for a reason and a dropdown that is blank because
            # nothing was set up look identical, and the user cannot tell which one they are facing.
            "default_ship_to":
                "Only this customer's own addresses can be chosen. On a new account the list is "
                "empty until the account is saved — pick the customer, save, then come back and set "
                "the default delivery address.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # `customer` is narrowed to parties actually tagged as customers. TenantModelForm already
        # scopes any FK whose target has a tenant field, so this narrows by ROLE on top of that —
        # without it the dropdown offers the whole party book, suppliers and carriers included.
        if "customer" in self.fields:
            self.fields["customer"].queryset = _customer_parties(self.tenant)

        if "catalog_categories" in self.fields:
            self.fields["catalog_categories"].queryset = (
                ItemCategory.objects.filter(tenant=self.tenant) if self.tenant is not None
                else ItemCategory.objects.none())

        # `default_ship_to` narrows to the customer's OWN addresses once a customer is known, and to
        # nothing at all when one is not.
        #
        # An EMPTY queryset is the deliberate fallback on create, never the tenant-wide default: on
        # a blank form there is no customer yet, so every address in the workspace would be on offer
        # and the first one picked would belong to whichever company the user happened to scroll to.
        # `PortalAccount.clean()` would still refuse it, but only after the user filled the form in
        # — offering a choice the system will reject is the 4.11 finding. On edit the customer is
        # known, so the select shows exactly the right addresses.
        if "default_ship_to" in self.fields:
            customer_id = getattr(self.instance, "customer_id", None)
            self.fields["default_ship_to"].queryset = (
                Address.objects.filter(tenant=self.tenant, party_id=customer_id)
                if self.tenant is not None and customer_id is not None
                else Address.objects.none())

    def clean(self):
        cleaned = super().clean()

        # THE FORM-ONLY RULE. See the module docstring for why it cannot live on the model.
        # Checked against `cleaned_data`, which holds the submitted ids on create and edit alike.
        if cleaned.get("catalog_scope") == "categories" and not cleaned.get("catalog_categories"):
            self.add_error(
                "catalog_categories",
                "Pick at least one category — a 'Selected categories only' catalog with no "
                "categories shows this customer an empty catalog.")

        # Re-check every tenant-scoped FK against a crafted POST. Keyed on fields the FORM has, so
        # the failure renders as a field error rather than raising out of add_error (L39 §2).
        _reject_foreign(self, cleaned, ("customer", "default_ship_to"))
        return cleaned
