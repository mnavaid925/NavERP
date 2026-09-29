"""Forms for the 8.6 change order.

Three forms, three different jobs, and the split matters more than usual here because this is
the layer the 0.20 close-out finding was about.

``OrderAmendmentForm`` carries the authorable fields and nothing else. What makes an amendment
*trustworthy* is deliberately absent (L22):

* ``impact_snapshot`` — frozen evidence, server-generated at propose time. A form that accepted
  one would let a clerk write "costs us nothing" into the very record that is supposed to prove
  what the change actually costs. It is ``editable=False`` and appears in no ``Meta.fields``.
* ``status`` — workflow. Only the decide / apply / withdraw verbs move an amendment between
  statuses, and ``apply()`` re-checks its own precondition in the method.
* every action stamp (``requested_at`` / ``requested_by`` / ``decided_by`` / ``decided_at`` /
  ``applied_by`` / ``applied_at``) — each written by exactly one named POST view.

``OrderAmendmentLineForm`` is constructed with the parent as ``amendment=`` and **not** from
user input: the line belongs to the amendment the URL named, and a form that let the POST body
choose the parent would be a way to append a line to somebody else's change order.

``OrderAmendmentDecisionForm`` is a plain ``forms.Form`` — approve and reject share one form, so
they cannot stamp different things. It is the only authorable path to the decision, and the
**view** writes the stamps, never the form.

``OrderAmendmentLine.clean()`` raises on ``NON_FIELD_ERRORS`` for exactly the reason the
0.20 close-out describes: this form's ``Meta.fields`` exclude ``amendment`` and the timestamps,
so a guard keyed on either would route through ``add_error(None, …)`` and raise ``ValueError``.
"""
from django import forms

from apps.sales.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.sales.models.OrderManagement.OrderAmendments import OrderAmendment, OrderAmendmentLine


class OrderAmendmentForm(TenantUniqueMixin, TenantModelForm):
    """Propose one change order. The lifecycle and the impact are the verbs' job."""

    class Meta:
        model = OrderAmendment
        # Excluded, with the reason for each:
        #   tenant       — set by the mixin from the view's request.tenant, never from input.
        #   number       — auto-numbered AMD- by TenantNumbered.save().
        #   status       — WORKFLOW: written only by the decide / apply / withdraw verbs.
        #   impact_snapshot — FROZEN EVIDENCE, server-generated, editable=False.
        #   requested_at / requested_by — ACTION-STAMPED by the create view.
        #   decided_by / decided_at     — ACTION-STAMPED by the decide view.
        #   applied_by / applied_at     — ACTION-STAMPED by apply() itself.
        #   created_at / updated_at     — auto_now* stamps.
        fields = [
            "sales_order",
            "change_type",
            "reason",
            "document",
            "notes",
        ]
        widgets = {
            "sales_order": forms.Select(attrs={"class": "form-select"}),
            "change_type": forms.Select(attrs={"class": "form-select"}),
            "reason": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 4,
                "placeholder": "Why is this order being changed, in words a colleague can act on?",
            }),
            "document": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "Anything the approver should know that is not the reason itself.",
            }),
        }
        help_texts = {
            "sales_order": "The live order this changes. 8.6 extends SCM's order; it never replaces it.",
            "change_type": "What KIND of change this is. Cancel acts on the whole order.",
            "reason": "The commercial reason. This is what the approver reads first.",
            "document": "Optional — the customer's email, a signed change note, a credit memo.",
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # TenantModelForm already narrows every ModelChoiceField to the tenant. These two are
        # spelled out anyway so the ORDERING is pinned (the order dropdown is read by eye, and
        # an unordered pk list on a thousand-order workspace is unusable) and so the ELIGIBILITY
        # rule is the frozen AMENDABLE_STATUSES tuple itself rather than a copy of it — the same
        # tuple recompute_impact() and apply() read, so the page and the method cannot disagree.
        if self.tenant is not None:
            from apps.core.models import Document
            from apps.scm.models import SalesOrder

            self.fields["sales_order"].queryset = (
                SalesOrder.objects
                .filter(tenant=self.tenant, status__in=OrderAmendment.AMENDABLE_STATUSES)
                .select_related("customer")
                .order_by("-order_date", "-id")
            )
            self.fields["document"].queryset = Document.objects.filter(
                tenant=self.tenant
            ).order_by("-uploaded_at")
        self.fields["document"].required = False

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
            return cleaned
        if self.instance.pk and self.instance.tenant_id != tenant_id:
            self.add_error(None, "The amendment must belong to this workspace.")
            return cleaned

        order = cleaned.get("sales_order")
        if order is None:
            return cleaned

        # The dropdown is already narrowed; this catches a POST that bypasses the widget and
        # says WHY in the author's own terms rather than "Select a valid choice".
        _reject_foreign(self, cleaned, ["sales_order", "document"])
        # Belt and braces on the dropdown: the order can leave AMENDABLE_STATUSES between the
        # page being rendered and the form being posted.
        if order.status not in OrderAmendment.AMENDABLE_STATUSES:
            self.add_error(
                None,
                f"Order {order.number} is {order.get_status_display().lower()} and can no longer "
                "be amended. Only a live order can be changed by amendment.",
            )
        # Two open change orders against one order is how two clerks end up applying
        # contradictory quantities to the same line: the second one's impact analysis was taken
        # against figures the first one has already moved. Excluded on EDIT, so re-saving an
        # existing amendment does not collide with itself.
        elif OrderAmendment.has_open_for(order, self.tenant, exclude_pk=self.instance.pk or None):
            self.add_error(
                None,
                f"Order {order.number} already carries an amendment that is still open. Decide "
                "or withdraw it before proposing another.",
            )
        return cleaned


class OrderAmendmentLineForm(TenantModelForm):
    """Add or edit ONE proposed line change on a parent amendment.

    Constructed with ``amendment=<OrderAmendment>`` — the parent comes from the URL, never from
    the POST body. ``amendment`` is therefore NOT in ``Meta.fields``, and this is the reason the
    model's ``clean()`` is keyed on ``NON_FIELD_ERRORS``: a guard keyed on the parent would hit
    ``add_error(None, …)`` and raise ``ValueError`` on every create and edit (the 0.20
    close-out finding, verbatim).

    ``sales_order_line``'s queryset is narrowed to **the parent amendment's own order**. That
    is simultaneously the usability rule (an author is picking among the lines of the order in
    front of them, not among every line in the workspace) and the IDOR guard: a line from
    another order is not selectable, and a hand-posted id from another order is refused by
    ``_reject_foreign`` with a message that says why.
    """

    class Meta:
        model = OrderAmendmentLine
        # Excluded, with the reason for each:
        #   amendment   — SET BY THE PARENT VIEW from the URL, never from user input. A form
        #                 that accepted it would let a POST body append a line to somebody
        #                 else's change order.
        #   created_at / updated_at — not on this model at all (it is tenant-less and reaches
        #                 the tenant through its amendment), so nothing to exclude.
        fields = [
            "sales_order_line",
            "operation",
            "new_quantity",
            "new_unit_price",
            "note",
        ]
        widgets = {
            "sales_order_line": forms.Select(attrs={"class": "form-select"}),
            "operation": forms.Select(attrs={"class": "form-select"}),
            "new_quantity": forms.NumberInput(attrs={
                "class": "form-input",
                "step": "any",
                "placeholder": "Leave blank to keep the ordered quantity",
            }),
            "new_unit_price": forms.NumberInput(attrs={
                "class": "form-input",
                "step": "0.01",
                "placeholder": "Leave blank to keep the unit price",
            }),
            "note": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "What this line is for — becomes the description on an Add.",
            }),
        }
        help_texts = {
            "sales_order_line": "Only the lines of this amendment's own order can be chosen.",
            "operation": "Add creates a new line. Update changes an existing one. Remove deletes it.",
            "new_quantity": "The quantity AFTER the change. Blank on an Update means 'unchanged'.",
            "new_unit_price": "The unit price AFTER the change. Blank on an Update means 'unchanged'.",
        }

    def __init__(self, *args, tenant=None, amendment=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.amendment = amendment
        # An Add line has no original to point at, so blank is a legitimate answer here — and
        # ``SalesOrderLine`` has no `tenant` of its own (it is tenant-less, reached through
        # ``sales_order``), so TenantModelForm cannot narrow this queryset for us. The ORDER
        # scope below is therefore the real guard, and ``clean()`` re-checks it on the
        # submitted value — a narrowed widget is a usability feature, not a security boundary.
        self.fields["sales_order_line"].required = False
        if amendment is not None:
            from apps.scm.models import SalesOrderLine

            self.fields["sales_order_line"].queryset = (
                SalesOrderLine.objects
                .filter(sales_order_id=amendment.sales_order_id)
                .select_related("item")
                .order_by("id")
            )

    def clean(self):
        cleaned = super().clean()
        # The parent is not a form field, so a mismatch with the URL's amendment is a non-field
        # message — never add_error("amendment", ...), which is the exact 0.20 ValueError.
        if self.amendment is None:
            self.add_error(None, "This line must be added through its amendment.")
            return cleaned
        if self.instance.pk and self.instance.amendment_id != self.amendment.pk:
            self.add_error(None, "This line belongs to a different amendment.")
            return cleaned

        order_id = self.amendment.sales_order_id
        chosen = cleaned.get("sales_order_line")
        if chosen is not None and chosen.sales_order_id != order_id:
            self.add_error(
                "sales_order_line",
                "That line belongs to a different order. Only this amendment's own order lines "
                "can be changed.",
            )
        return cleaned


class OrderAmendmentDecisionForm(forms.Form):
    """The approve / reject form — ONE form for both outcomes.

    Approve and reject share this form deliberately: two forms would be two chances to stamp
    the amendment's decision fields differently, and a change order whose rejection leaves a
    ``decided_by`` but no reason is worse than one that was never decided at all.

    The field is named ``decision_note`` to match the column it writes. It is kept SEPARATE from
    the amendment's own ``notes`` (which the view appends the decision to as well): a later
    application appends to ``notes``, and if the approver's reasoning lived only there it would
    end up interleaved with operational chatter. It is not on any ModelForm — an approval
    justification a later edit could rewrite is not evidence of why the approver said yes (L22).
    """

    decision = forms.ChoiceField(
        label="Decision",
        choices=[("approved", "Approve"), ("rejected", "Reject")],
        widget=forms.RadioSelect(),
    )
    decision_note = forms.CharField(
        label="Decision note",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-textarea",
            "rows": 3,
            "placeholder": "Why you are approving or rejecting this change. Required in spirit, optional in the form.",
        }),
        max_length=2000,
    )

