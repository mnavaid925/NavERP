"""SCM 4.16 Customer Portal — the two ``PortalOrderInquiry`` forms.

**Two forms, not one with a flag.** The staff triage form and the customer-facing form differ in
what they may *set*, not merely in what they render, and a single form gated by ``if is_staff``
puts an authorisation decision inside template-facing code where the next edit quietly widens it.
The customer form has no ``portal_account`` field at all and scopes every order dropdown to that
one customer, so there is no field on it that could name another company's document even if the
POST tried.

**``subject`` and ``description`` are non-model fields, and they exist only on create.** They are
the ``crm.Case``'s columns, not this model's — ``PortalOrderInquiry.open_for()`` is the single
writer of the case and takes them as arguments. On edit they are REMOVED rather than shown
read-only: a bound field that silently discards what the user typed is worse than an absent one,
and the case's own thread is where the conversation continues. The edit page links to it instead.

**``case``, ``outcome``, ``resolved_at``, ``return_authorization``, ``source`` and ``raised_by`` are
absent from both forms without being named anywhere below.** They are ``editable=False`` on the
model, so Django omits them from every ModelForm automatically. That is deliberately where the rule
lives: a field list can be edited by someone who does not know the invariant, whereas
``editable=False`` travels with the column and holds for a form nobody has written yet.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _reject_foreign

from apps.scm.models import PortalOrderInquiry, SalesOrder, SalesOrderLine, Shipment

#: The tenant-scoped FKs that actually appear on these forms. Deliberately NOT the model's whole
#: ``TENANT_SCOPED_FKS``: ``case`` and ``return_authorization`` are ``editable=False`` and never on a
#: form, so naming them here would call ``add_error`` with a field the form does not have — which
#: raises ``ValueError`` (a 500) instead of showing a field error.
#:
#: ``sales_order_line`` is absent for a different reason: a ``SalesOrderLine`` has NO tenant column
#: (it is reached through ``sales_order.tenant``, the scm child convention), so ``_reject_foreign``
#: would read ``tenant_id`` as ``None``, compare it against the real tenant and reject every line
#: ever submitted. Its scoping is done by queryset plus the model's own parent-match guard.
_FORM_SCOPED_FKS = ("portal_account", "sales_order", "shipment", "invoice")


class _InquiryFormBase(TenantModelForm):
    """What both forms share: the context querysets, the create-only case fields, and the re-check.

    Subclasses set ``Meta.fields`` and, for the customer form, narrow the querysets further to a
    single party. The base never assumes a customer, so the staff form keeps the whole workspace.
    """

    subject = forms.CharField(
        max_length=200,
        help_text="One line the customer will see as the title of their support case")
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="What happened, in the customer's own words where possible")

    #: Overridden by the customer form. ``None`` means "do not narrow beyond the tenant".
    customer = None

    def __init__(self, *args, **kwargs):
        # Popped before super() so TenantModelForm never sees an unexpected kwarg.
        self.customer = kwargs.pop("customer", None)
        super().__init__(*args, **kwargs)

        orders = SalesOrder.objects.none()
        lines = SalesOrderLine.objects.none()
        shipments = Shipment.objects.none()
        if self.tenant is not None:
            orders = SalesOrder.objects.filter(tenant=self.tenant)
            # A line has no tenant of its own — scope it through its parent order, never unscoped.
            lines = SalesOrderLine.objects.filter(sales_order__tenant=self.tenant)
            shipments = Shipment.objects.filter(tenant=self.tenant)
            if self.customer is not None:
                orders = orders.filter(customer=self.customer)
                lines = lines.filter(sales_order__customer=self.customer)
                shipments = shipments.filter(sales_order__customer=self.customer)

        # The `select_related` differs per field and MUST: `SalesOrder` has no `sales_order`
        # column, so a uniform `.select_related("sales_order")` across all three raises
        # `FieldError: Invalid field name(s) given in select_related` — but only when the widget
        # actually iterates its queryset to render the options, i.e. never at import time, never in
        # `manage.py check`, and never on any page that does not draw this form. It shipped that way
        # and the first thing to execute it was the smoke sweep.
        #
        # Each queryset is prefetched along the hop its `__str__` really walks: an order names its
        # customer, while a line and a shipment each name their parent order.
        for name, queryset, related in (("sales_order", orders, "customer"),
                                        ("sales_order_line", lines, "sales_order"),
                                        ("shipment", shipments, "sales_order")):
            if name in self.fields:
                self.fields[name].queryset = queryset.select_related(related)

        # CREATE ONLY. On edit the case already exists and open_for() has already run, so a bound
        # subject/description would collect text this form has no writer for. Removing the fields
        # is the honest version of that — see the module docstring.
        if self.instance.pk is not None:
            self.fields.pop("subject", None)
            self.fields.pop("description", None)

    def clean(self):
        cleaned = super().clean()
        # Narrowed dropdowns are UX; this is the boundary (L39 §2). The model's clean() repeats the
        # tenant rule and adds the parent-match and quantity rules on top.
        _reject_foreign(self, cleaned, [n for n in _FORM_SCOPED_FKS if n in self.fields])
        return cleaned


class PortalOrderInquiryForm(_InquiryFormBase):
    """Staff triage: file an inquiry for any customer in the workspace, or edit its context."""

    class Meta:
        model = PortalOrderInquiry
        fields = [
            "portal_account",
            "sales_order", "sales_order_line", "shipment", "invoice",
            "inquiry_type", "requested_resolution", "quantity_affected",
        ]
        help_texts = {
            "portal_account":
                "Leave blank when filing for a customer who is not on the portal — the inquiry is "
                "still recorded, it just has no portal account behind it.",
        }


class PortalInquiryCustomerForm(_InquiryFormBase):
    """The portal-side form. Deliberately narrower than the staff one in three ways.

    1. **No ``portal_account`` field.** The view resolves it from the signed-in user and stamps it
       server-side; a field would be a value the customer could name, and naming another account is
       the whole attack.
    2. **Every dropdown is scoped to that customer's own orders**, via the ``customer`` kwarg the
       base applies — not merely to the tenant.
    3. **No ``invoice``.** An invoice dispute raised from the portal still needs the order context,
       and exposing an invoice picker here would offer a document the customer may not be entitled
       to see at all (``PortalAccount.can_view_invoices`` gates that surface separately). Staff can
       attach the invoice during triage, which is where the entitlement is already known.
    """

    class Meta:
        model = PortalOrderInquiry
        fields = [
            "sales_order", "sales_order_line", "shipment",
            "inquiry_type", "requested_resolution", "quantity_affected",
        ]
        help_texts = {
            "sales_order": "Which of your orders is this about?",
            "quantity_affected":
                "How many units are affected, if it is only part of the order.",
        }
