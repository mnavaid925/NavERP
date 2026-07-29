"""SCM 4.10 Returns Management — the RMA header form, its line formset and the action payloads.

Two things in this module are load-bearing rather than tidy:

**§7.6 — every dropdown whose target's ``__str__`` walks a second FK is ``select_related``.**
Verified in the code, not assumed: ``SalesOrderLine.__str__`` reads ``self.item.sku``
(``SalesOrders.py:249-251``) and ``LotSerial.__str__`` reads ``self.item.sku``
(``LotSerials.py:32``). Rendering either field without the join is ONE QUERY PER ``<option>``. The
lesson is usually applied to detail-page panels and missed on the form querysets — this is the form
querysets.

**§7.1 — ``BaseReturnLineFormSet.clean()`` reads the PARENT.** The over-return cap needs
``self.instance.sales_order``, and on CREATE the formset's instance is an empty
``ReturnAuthorization()`` whose ``sales_order_id`` is None. The view therefore does
``formset.instance = form.instance`` after ``form.is_valid()`` and BEFORE ``formset.is_valid()``,
without which this guard silently no-ops on exactly the path it exists for (the shipped 4.8
``BaseBOMLineFormSet`` bug).

**The over-return cap is WEAK BY CONSTRUCTION and says so.** ``SalesOrderLine`` carries no shipped
or delivered quantity anywhere in this codebase (``Shipment`` has no lines and no Item FK;
``PickTask`` has no FK to ``SalesOrder``), so the only ceiling available is ``quantity_ordered``. It
is ONE aggregate query, not a query per row, and it takes NO lock — two concurrent RMAs against the
same sold line can each pass it. Over-return is genuinely caught at RECEIPT, on the bench, not at
authorisation.
"""
from django.db.models import Sum

from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import (TenantUniqueMixin, _active_currencies, _customer_parties,
                                    _scope_to_parent)
from apps.scm.models import (Item, Location, ReturnAuthorization, ReturnLine, ReturnReason,
                             SalesOrder, SalesOrderLine)

ZERO = Decimal("0")


class ReturnAuthorizationForm(TenantUniqueMixin, TenantModelForm):
    """The RMA header.

    EXCLUDES the whole computed block (§7.7): ``number`` (auto), ``status``, ``policy_snapshot``,
    ``approved_on`` / ``approved_by``, ``rejected_reason``, ``customer_shipped_on``,
    ``public_token``, ``portal_note``, ``credit_note``, ``replacement_order`` and the four
    settlement figures. Each of those has exactly ONE writer and it is never a form — in particular
    ``credit_note`` is ``editable=False`` so no user can re-point an RMA at an arbitrary invoice.

    ``currency`` IS on the form. It is defaulted from the sales order at creation, but a blind
    return has no order to take it from, so a CSR has to be able to correct it — and the
    draft-credit-note action refuses outright while it is null.
    """

    class Meta:
        model = ReturnAuthorization
        fields = ["customer", "sales_order", "return_type", "source", "policy", "requested_on",
                  "resolution", "refund_method", "return_method", "dropoff_location",
                  "return_carrier", "return_tracking_number", "return_label_url", "label_cost",
                  "counterparty_rma_number", "currency", "advance_refund",
                  "advance_refund_deadline", "notes"]
        widgets = {
            "requested_on": forms.DateInput(attrs={"type": "date"}),
            "advance_refund_deadline": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "customer" in self.fields:
            self.fields["customer"].queryset = _customer_parties(self.tenant)
        if "sales_order" in self.fields:
            # SalesOrder.__str__ is its number — no FK walk — but the field is filtered to THIS
            # customer's orders as soon as one is known, which is the thing that makes the picker
            # usable on a tenant with a thousand orders.
            qs = self.fields["sales_order"].queryset.select_related("customer")
            if self.instance.customer_id:
                qs = qs.filter(customer_id=self.instance.customer_id)
            self.fields["sales_order"].queryset = qs.order_by("-order_date", "-id")
        if "policy" in self.fields:
            self.fields["policy"].queryset = (
                self.fields["policy"].queryset.filter(is_active=True)
                .select_related("item_category").order_by("priority", "name"))
        if "return_carrier" in self.fields:
            # Carrier.__str__ reaches its party (a carrier IS a TMS profile on a core.Party), which
            # is the §7.6 shape — one query per option without this. Ordered by `party__name`, not
            # `name`: Carrier has NO name COLUMN — `name` is a property that reads the party — so
            # `order_by("name")` is a FieldError at import-of-the-form time, not at render.
            self.fields["return_carrier"].queryset = (
                self.fields["return_carrier"].queryset.select_related("party")
                .order_by("party__name"))
        if "dropoff_location" in self.fields:
            self.fields["dropoff_location"].queryset = (
                self.fields["dropoff_location"].queryset.filter(is_active=True).order_by("code"))
        _active_currencies(self)

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get("customer")
        order = cleaned.get("sales_order")
        if order is not None and customer is not None and order.customer_id != customer.pk:
            self.add_error("sales_order",
                           f"{order.number} belongs to {order.customer.name}, not {customer.name}.")
        if cleaned.get("advance_refund") and not cleaned.get("advance_refund_deadline"):
            self.add_error("advance_refund_deadline",
                           "An advance refund needs a deadline — it is the only thing that makes "
                           "the exposure report actionable.")
        if cleaned.get("return_type") == "credit_only" and cleaned.get("return_method") != "keep_item":
            self.add_error("return_method",
                           "A credit-only return asks for nothing back — set the return method to "
                           "'Keep the item'.")
        return cleaned


class ReturnLineForm(TenantModelForm):
    """One item on the RMA.

    ``ReturnLine`` is TENANT-LESS (reached through its authorisation), so ``TenantModelForm`` can
    only scope the fields whose TARGET carries a tenant — ``item``, ``reason``, ``lot_serial``,
    ``photo`` all do, so those are scoped for free. ``sales_order_line`` does NOT: it is a child
    table with no tenant column, so leaving it alone would list EVERY tenant's order lines. It is
    narrowed by hand below (the ``_scope_to_parent`` rule).
    """

    class Meta:
        model = ReturnLine
        fields = ["sales_order_line", "item", "description", "quantity_requested",
                  "quantity_approved", "reason", "unit_price", "tax_pct", "unit_cost",
                  "line_fee", "condition_reported", "lot_serial", "photo"]

    def __init__(self, *args, tenant=None, sales_order=None, **kwargs):
        self.sales_order = sales_order
        super().__init__(*args, tenant=tenant, **kwargs)
        # §7.6: SalesOrderLine.__str__ and LotSerial.__str__ BOTH read item.sku. Without these two
        # joins each rendered <option> is its own SELECT — on a 200-line order that is 200 queries
        # for one dropdown.
        if "sales_order_line" in self.fields:
            scoped = (SalesOrderLine.objects.filter(sales_order__tenant=tenant)
                      .select_related("item", "sales_order")
                      if tenant is not None else SalesOrderLine.objects.none())
            if sales_order is not None:
                scoped = scoped.filter(sales_order=sales_order)
            # Through _scope_to_parent rather than a bare assignment: the fallback for "no parent
            # yet" is an EMPTY queryset, never the unscoped default, which would leak every
            # tenant's order lines into the select.
            _scope_to_parent(self, "sales_order_line", scoped)
        if "lot_serial" in self.fields:
            self.fields["lot_serial"].queryset = (
                self.fields["lot_serial"].queryset.select_related("item").order_by("item__sku",
                                                                                   "number"))
        if "item" in self.fields:
            self.fields["item"].queryset = (
                self.fields["item"].queryset.select_related("uom").order_by("sku"))
        if "reason" in self.fields:
            self.fields["reason"].queryset = (
                self.fields["reason"].queryset.filter(is_active=True)
                .order_by("sort_order", "code"))
        if "photo" in self.fields:
            self.fields["photo"].queryset = self.fields["photo"].queryset.order_by("-uploaded_at")

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("item")
        lot = cleaned.get("lot_serial")
        requested = cleaned.get("quantity_requested") or ZERO
        approved = cleaned.get("quantity_approved") or ZERO
        if approved > requested:
            self.add_error("quantity_approved",
                           "More is approved than the customer asked to return.")
        if item is not None and lot is not None and lot.item_id != item.pk:
            self.add_error("lot_serial",
                           f"{lot.number} belongs to {lot.item.sku}, not {item.sku}.")
        so_line = cleaned.get("sales_order_line")
        if so_line is not None and item is not None and so_line.item_id \
                and so_line.item_id != item.pk:
            self.add_error("sales_order_line", "That order line is for a different item.")
        return cleaned


class BaseReturnLineFormSet(forms.BaseInlineFormSet):
    """Guards the line list — including the two rules that READ THE PARENT (§7.1).

    Both only work because the view assigns ``formset.instance = form.instance`` before
    ``is_valid()``. On create the formset's own instance is an empty ``ReturnAuthorization()``, so
    without that line the sales-order cap below reads ``sales_order_id = None``, finds nothing to
    cap against, and passes everything — silently, on exactly the path it exists for.
    """

    def clean(self):
        super().clean()
        rows = [form for form in self.forms
                if getattr(form, "cleaned_data", None) and not form.cleaned_data.get("DELETE")]
        if not rows:
            raise ValidationError("A return needs at least one line — what is coming back?")

        # Duplicate order lines on one RMA make every derived quantity ambiguous: two rows against
        # the same sold line would each be capped independently and the pair could exceed the sale.
        seen = set()
        for form in rows:
            so_line = form.cleaned_data.get("sales_order_line")
            if so_line is None:
                continue
            if so_line.pk in seen:
                form.add_error("sales_order_line",
                               "This order line is already on another row of this return.")
            seen.add(so_line.pk)

        # ---- the over-return cap (weak by construction — see the module docstring) --------------
        parent = self.instance
        order_id = getattr(parent, "sales_order_id", None)
        if order_id is None:
            return
        wanted = {}
        for form in rows:
            so_line = form.cleaned_data.get("sales_order_line")
            if so_line is None:
                continue
            wanted[so_line.pk] = wanted.get(so_line.pk, ZERO) + (
                form.cleaned_data.get("quantity_requested") or ZERO)
        if not wanted:
            return
        # ONE aggregate for every line on the page, not a query per row.
        already = {
            row["sales_order_line_id"]: row["total"] or ZERO
            for row in (ReturnLine.objects
                        .filter(sales_order_line_id__in=list(wanted))
                        .exclude(return_authorization_id=parent.pk)
                        .exclude(return_authorization__status__in=("rejected", "cancelled"))
                        .values("sales_order_line_id")
                        .annotate(total=Sum("quantity_requested")))
        }
        ordered = dict(
            SalesOrderLine.objects.filter(pk__in=list(wanted))
            .values_list("pk", "quantity_ordered"))
        for form in rows:
            so_line = form.cleaned_data.get("sales_order_line")
            if so_line is None:
                continue
            cap = ordered.get(so_line.pk) or ZERO
            total = wanted[so_line.pk] + (already.get(so_line.pk) or ZERO)
            if cap > ZERO and total > cap:
                form.add_error(
                    "quantity_requested",
                    f"That returns {total} against only {cap} ever ordered on this line "
                    f"(including {already.get(so_line.pk) or ZERO} on other returns).")

    def add_fields(self, form, index):
        """Build the reason/item option lists ONCE for the whole formset.

        ``TenantModelForm`` re-assigns a fresh queryset per form and ``ModelChoiceField.__deepcopy__``
        calls ``queryset.all()``, which discards any cache — so every rendered row re-ran the same
        SELECT. Assigning ``.choices`` short-circuits the rendering; ``clean()``/``to_python()``
        still go through ``self.queryset``, so POST validation and tenant scoping are untouched.
        """
        super().add_fields(form, index)
        # `photo` included: it IS on Meta.fields and IS rendered per row, and
        # ModelChoiceField.__deepcopy__ calls queryset.all() per form — so leaving one field name
        # out of this tuple silently re-SELECTed the whole core.Document table once per line.
        for name in ("reason", "item", "sales_order_line", "lot_serial", "photo"):
            if name not in form.fields:
                continue
            cache = f"_{name}_choices"
            if not hasattr(self, cache):
                setattr(self, cache, list(form.fields[name].choices))
            form.fields[name].choices = getattr(self, cache)


ReturnLineFormSet = inlineformset_factory(
    ReturnAuthorization, ReturnLine, form=ReturnLineForm, formset=BaseReturnLineFormSet,
    extra=1, can_delete=True, max_num=100, validate_max=True,
)


# ==================================================================== the action payloads
class ReturnApprovalForm(forms.Form):
    """The approve payload.

    A plain ``Form``: every field it collects lands on an ``editable=False`` column written by
    ``returnauthorization_approve`` inside one transaction, so the resolution recorded and the
    verdict snapshotted cannot disagree.

    ``resolution`` is offered in full and NARROWED in the view against the eligibility verdict —
    the choices here are the vocabulary, the policy is the gate (§7.5: a gate lives in the view as
    well as the button).
    """

    resolution = forms.ChoiceField(
        choices=[c for c in ReturnAuthorization.RESOLUTION_CHOICES if c[0] != "none"])
    refund_method = forms.ChoiceField(choices=ReturnAuthorization.REFUND_METHOD_CHOICES,
                                      required=False)
    approved_on = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}),
                                  help_text="Defaults to today when left blank")
    override_window = forms.BooleanField(
        required=False,
        help_text="Approve anyway when the policy says the window has closed. The override and "
                  "who made it are recorded in the frozen verdict")
    notes = forms.CharField(required=False, max_length=2000,
                            widget=forms.Textarea(attrs={"rows": 3}))


class ReturnRejectForm(forms.Form):
    """The reject payload — a reason is REQUIRED.

    A rejection with no reason is a customer being told no by a system nobody can question later,
    and ``rejected_reason`` is ``editable=False`` precisely so this form is its only writer.
    """

    rejected_reason = forms.CharField(max_length=255, widget=forms.TextInput(
        attrs={"placeholder": "Why is this return refused?"}))


class ReturnReceiveAllForm(forms.Form):
    """The one-click receive payload — creates a ``received_pending`` row per approved line.

    ``location`` is the returns bench. It is REQUIRED: a disposition row with no location is a
    quantity nobody can find, and the write-off path would later hand ``None`` to
    ``_insufficient_stock``.
    """

    location = forms.ModelChoiceField(queryset=Location.objects.none(),
                                      label="Returns bench location")
    condition_grade = forms.ChoiceField(
        choices=[("a", "A — as new, sellable"), ("b", "B — light wear, refurbishable"),
                 ("c", "C — heavy wear, secondary channel"), ("d", "D — unsellable")],
        initial="a",
        help_text="Applied to every row created — each can be re-graded individually afterwards")
    received_on = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}),
                                  help_text="Defaults to today when left blank")

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.fields["location"].queryset = (
            Location.objects.filter(tenant=tenant, is_active=True).order_by("code")
            if tenant is not None else Location.objects.none())


class PortalReturnRequestForm(forms.Form):
    """The LOGGED-IN customer's own return request (``portal_return_create``).

    This is the honest half of the "Return Portal — request returns" bullet. It reuses the CRM
    binding that already exists (``crm.CustomerPortalAccess``) exactly as ``portal_case_create``
    does, and the view FORCES ``customer=access.customer_party`` and ``source="portal"``
    server-side — a portal user can never file a return for another customer, whatever they POST.

    Anonymous request is NOT buildable and is not attempted: nothing lets a stranger prove they own
    a ``SalesOrder``, and ``core.Address`` has kind/line1/city/country and NO postal-code field, so
    Loop's order-number + ZIP lookup would need a Module 0 change.
    """

    sales_order = forms.ModelChoiceField(queryset=SalesOrder.objects.none(), required=False,
                                         label="Which order?")
    sales_order_line = forms.ModelChoiceField(queryset=SalesOrderLine.objects.none(),
                                              required=False, label="Which item?")
    item = forms.ModelChoiceField(queryset=Item.objects.none(), required=False)
    quantity_requested = forms.DecimalField(max_digits=14, decimal_places=4,
                                            min_value=Decimal("0.0001"), initial=Decimal("1"))
    reason = forms.ModelChoiceField(queryset=ReturnReason.objects.none())
    condition_reported = forms.CharField(required=False, max_length=120,
                                         label="What condition is it in?")
    notes = forms.CharField(required=False, max_length=2000,
                            widget=forms.Textarea(attrs={"rows": 3}),
                            label="Anything else we should know?")

    def __init__(self, *args, tenant=None, customer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.customer = customer
        if tenant is None or customer is None:
            return
        # Scoped to THIS customer's orders, not merely to the tenant — the whole point of the
        # portal binding. select_related on both because SalesOrderLine.__str__ reads item.sku.
        orders = (SalesOrder.objects.filter(tenant=tenant, customer=customer)
                  .exclude(status="cancelled").order_by("-order_date", "-id"))
        self.fields["sales_order"].queryset = orders
        self.fields["sales_order_line"].queryset = (
            SalesOrderLine.objects.filter(sales_order__in=orders).select_related("item"))
        # Scoped to what THIS customer has actually been sold — not merely to the tenant. An
        # external party had the full internal catalogue in a dropdown, and could file returns
        # against items never sold to them, polluting the CSR approval inbox. Same reasoning as the
        # order and line querysets two lines up; `condition_reported` remains the free-text escape
        # hatch for anything genuinely off-catalogue.
        self.fields["item"].queryset = (
            Item.objects.filter(tenant=tenant,
                                sales_order_lines__sales_order__in=orders)
            .distinct().select_related("uom").order_by("sku"))
        self.fields["reason"].queryset = (
            ReturnReason.objects.filter(tenant=tenant, is_active=True)
            .order_by("sort_order", "code"))

    def clean(self):
        cleaned = super().clean()
        so_line = cleaned.get("sales_order_line")
        item = cleaned.get("item")
        if so_line is None and item is None:
            raise ValidationError("Pick the order line you are returning, or name the item.")
        if so_line is not None and item is None and so_line.item_id:
            cleaned["item"] = so_line.item
        order = cleaned.get("sales_order")
        if so_line is not None and order is not None and so_line.sales_order_id != order.pk:
            self.add_error("sales_order_line", "That line is not on the order you picked.")
        if cleaned.get("item") is None:
            self.add_error("item", "We could not work out which item this is — please name it.")
        return cleaned


class PublicReturnUpdateForm(forms.Form):
    """What an UNAUTHENTICATED visitor on the token page may send.

    Two actions discriminated by a hidden ``action`` field, and this form carries only the payload
    for both — no prices, no costs, no status field, nothing that could move the document's state.
    The writes themselves are TOCTOU-safe conditional UPDATEs in the view (the ``case_public`` CSAT
    shape), not read-then-save.

    # WARNING: unauthenticated POST — add per-IP rate-limiting (django-ratelimit) or a WAF throttle
    # in production. There is no rate limiting anywhere in this repo and none is being invented here.
    """

    action = forms.ChoiceField(choices=[("shipped", "shipped"), ("note", "note")],
                               widget=forms.HiddenInput())
    return_tracking_number = forms.CharField(required=False, max_length=64,
                                             label="Tracking number (if you have one)")
    portal_note = forms.CharField(required=False, max_length=500,
                                  widget=forms.Textarea(attrs={"rows": 3}),
                                  label="Add a note")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("action") == "note" and not (cleaned.get("portal_note") or "").strip():
            self.add_error("portal_note", "Write something before sending it.")
        return cleaned
