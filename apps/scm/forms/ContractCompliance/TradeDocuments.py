"""SCM 4.12 Contract & Compliance — the ``TradeDocument`` header form + its line formset.

**What is deliberately NOT on this form.** ``tenant`` (stamped by the view), ``number`` (assigned in
``TenantNumbered.save()``), ``status`` (moved only by the issue / submit / accept / void verbs —
issuing is what charges a licence balance, so a free-text status dropdown would let someone spend a
balance no one checked), ``issued_at`` / ``issued_by`` (system stamps, L22), ``void_reason``
(stamped by the void verb) and the two automatic timestamps. That is a WHITELIST ``Meta.fields``,
not an ``exclude``: a blacklist means the next column added to ``TradeDocument`` joins this form
silently.

**Why ``incoterm`` is redeclared here as a ``ChoiceField``.** The model column carries no
``choices=`` on purpose — Incoterms is a versioned external standard, so the vocabulary lives in
``TradeDocument.INCOTERM_CHOICES`` where the next revision is a data edit rather than an
``AlterField`` on a shipped table. That constant is read in exactly two places: the model's
``clean()``, which enforces membership, and this field, which offers it. Restating the eleven terms
here would be a third copy and the one that drifts. A term a later revision retires is appended back
onto the choices for the row that already stores it, so opening that document does not silently
blank a legal allocation of cost and risk (the ``KpiTargetForm`` deactivated-owner idiom); saving it
unchanged still meets the model's message naming the current vocabulary.

**Every FK queryset is re-filtered to the tenant here even where the base class already would.**
``TenantModelForm`` scopes a ``ModelChoiceField`` only when the target model carries a ``tenant``
column *and* a tenant was passed; a tenant-less caller falls through to the unscoped default
manager. Re-filtering from the model makes the scoping true by construction rather than true by the
caller behaving. It is UX either way — ``TradeDocument.clean()`` is what holds against a crafted
POST (L39 §2).

**The three party dropdowns are NOT narrowed by ``PartyRole``.** ``TradeLicenseForm`` narrows its
holder/end-user to suppliers ∪ carriers, but a trade document's shipper, consignee and notify party
are a different question: an export consignee is a *customer*, an import shipper is a *supplier*,
and the notify party is routinely a broker or forwarder tagged ``partner`` — or nobody's counterparty
at all. Narrowing to any one role would hide the majority of legitimate counterparties on the
majority of documents, which is the 4.5 ``ship_to_address`` failure. The tenant's party book is the
correct scope, and it is enforced.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _active_currencies

from apps.core.models import Document
from apps.scm.models import (Carrier, Item, PurchaseOrder, SalesOrder, Shipment, TradeDocument,
                             TradeDocumentLine, TradeLicense, UOM)


class TradeDocumentForm(TenantModelForm):
    """One piece of import/export paperwork — its parties, its transport and its declared money."""

    # See the module docstring: the vocabulary is the model's constant, offered rather than restated.
    incoterm = forms.ChoiceField(
        required=False,
        choices=[("", "---------")] + TradeDocument.INCOTERM_CHOICES,
        help_text="Incoterms 2020 delivery term, e.g. FOB or DAP",
    )

    class Meta:
        model = TradeDocument
        # 31 fields — the model's full editable set. The four columns it omits (`status`,
        # `issued_at`, `issued_by`, `void_reason`) are all `editable=False`, plus `tenant`/`number`
        # and the timestamps from the base. Listing them is the boundary; `editable=False` is the
        # mechanism.
        fields = [
            # what kind of paper
            "doc_type", "direction", "document_number", "issue_date",
            # what movement it papers (link-outs — 4.6 / 4.1 / 4.5 own these rows)
            "shipment", "carrier", "purchase_order", "sales_order", "license",
            # who the parties are
            "shipper_party", "consignee_party", "notify_party",
            "country_of_origin", "country_of_destination",
            # the money on the form
            "currency", "declared_value", "freight_charges", "insurance_value", "incoterm",
            # what is in the box
            "gross_weight_kg", "net_weight_kg", "package_count",
            # how it travels (as PRINTED on the form)
            "vessel_or_flight", "voyage_number", "port_of_loading", "port_of_discharge",
            "container_numbers", "is_negotiable",
            # filing and evidence
            "filing_reference", "document", "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Stamp the tenant onto the unsaved instance so TradeDocument.clean()'s cross-tenant guard
        # over the nine named FKs actually RUNS on create. The create path assigns the tenant only
        # AFTER `is_valid()` (apps/core/crud.py:120-123, and the hand-rolled formset view does the
        # same), so without this the instance is validated with `tenant_id` None — the exact case
        # that guard skips — and the check is dead code on the one path a crafted POST exercises.
        # Not `TenantUniqueMixin`: this model's only unique_together is (tenant, number), and
        # `number` is auto-assigned and off the form, so its validate_unique half has nothing to do.
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # A term retired by a later Incoterms revision stays SELECTABLE on the row that stores it —
        # see the module docstring. `dict()` over the pairs, so the lookup is by value not by label.
        stored = (self.instance.incoterm or "").strip().upper()
        if stored and stored not in dict(self.fields["incoterm"].choices):
            self.fields["incoterm"].choices = (
                list(self.fields["incoterm"].choices) + [(stored, f"{stored} (retired term)")])

        # --- the link-outs ------------------------------------------------------------------------
        self._scope_to_tenant("shipment", Shipment.objects.all())
        # select_related is load-bearing on these three and nowhere else here: `Carrier.__str__`
        # renders `Carrier.name`, which is a PROPERTY reading `self.party.name`, and the two order
        # models' `__str__` reach `vendor` / `customer`. Without it each select fires one query per
        # rendered <option>. Shipment / Party / Document / TradeLicense all render from their own
        # columns and need nothing.
        self._scope_to_tenant("carrier", Carrier.objects.select_related("party"))
        self._scope_to_tenant("purchase_order", PurchaseOrder.objects.select_related("vendor"))
        self._scope_to_tenant("sales_order", SalesOrder.objects.select_related("customer"))
        # NOT narrowed to the chargeable statuses. A document is prepared against the licence it will
        # move under long before that licence is active, and the gate belongs at issue time where
        # `TradeLicense.can_charge()` states its refusal — a dropdown that hides a draft licence
        # would make the pairing impossible to record rather than impossible to abuse.
        self._scope_to_tenant("license", TradeLicense.objects.all())

        # --- the parties (full party book — see the module docstring) -------------------------------
        for name in ("shipper_party", "consignee_party", "notify_party"):
            self._scope_to_tenant(name, Party.objects.all())

        # --- money and evidence ---------------------------------------------------------------------
        # `Currency` is GLOBAL (no tenant column), so the base class cannot scope it and the shared
        # helper constrains it to the active set instead.
        _active_currencies(self)
        self._scope_to_tenant("document", Document.objects.all())

    def _scope_to_tenant(self, name, queryset):
        """Point one dropdown at this tenant's rows — and at NOTHING when there is no tenant."""
        if name in self.fields:
            self.fields[name].queryset = (
                queryset.filter(tenant=self.tenant) if self.tenant is not None else queryset.none()
            )


class TradeDocumentLineForm(TenantModelForm):
    """One declared line — what it is, how much of it, and what it is worth.

    ``document`` is absent because the formset owns it, and ``line_value`` is absent because it is a
    ``@property``: a stored line total is a column somebody can edit into disagreeing with its own
    two factors.

    The four snapshot columns (``description`` / ``hs_code`` / ``country_of_origin`` / ``uom_text``)
    are typed here and never back-filled from ``item`` — deliberately, and there is no ``save()``
    override on the model doing it either. A filed declaration must record what was DECLARED, so a
    helpful default that mirrors the item master a year later is exactly the bug.
    """

    class Meta:
        model = TradeDocumentLine
        fields = ["item", "description", "hs_code", "country_of_origin", "uom_text", "uom",
                  "quantity", "unit_value", "net_weight_kg"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `TradeDocumentLine` has no tenant column of its own — it is reached through
        # `document.tenant` — so nothing here can be left to the base class by default (see
        # forms/_common.py:7-11). `Item` and `UOM` do carry a tenant, so the base WOULD scope both
        # *provided* the view passes `form_kwargs={"tenant": request.tenant}`; stating the filter
        # here means the select cannot list another workspace's items even if a future caller
        # forgets that kwarg, and a tenant-less caller gets an empty select rather than everything.
        # This is UX: `TradeDocumentLine.clean()` re-checks both against `document.tenant`, which is
        # what holds against a crafted POST.
        for name, queryset in (("item", Item.objects.all()), ("uom", UOM.objects.all())):
            if name not in self.fields:
                continue
            self.fields[name].queryset = (
                queryset.filter(tenant=self.tenant) if self.tenant is not None else queryset.none()
            )


class BaseTradeDocumentLineFormSet(forms.BaseInlineFormSet):
    """Builds the ``item`` / ``uom`` option lists ONCE for the whole formset.

    ``TenantModelForm`` assigns a fresh queryset per form and ``ModelChoiceField.__deepcopy__``
    calls ``queryset.all()``, which discards any cache — so every rendered row re-ran the same two
    SELECTs (a 20-line customs invoice is 40 identical queries). Assigning ``.choices``
    short-circuits the rendering; ``clean()`` / ``to_python()`` still go through ``self.queryset``,
    so POST validation and the tenant scoping above are untouched.

    There is deliberately **no "at least one line" rule** here, unlike ``BaseReturnLineFormSet``.
    Several of the thirteen document types legitimately carry no lines at all — an ocean bill of
    lading, an insurance certificate, a licence copy — and refusing to save one would make the form
    unusable for a third of the register. ``declared_value`` is what those documents state, and the
    detail page gates its lines-vs-declared divergence badge on the document HAVING lines.
    """

    def add_fields(self, form, index):
        super().add_fields(form, index)
        for name in ("item", "uom"):
            if name not in form.fields:
                continue
            cache = f"_{name}_choices"
            if not hasattr(self, cache):
                setattr(self, cache, list(form.fields[name].choices))
            form.fields[name].choices = getattr(self, cache)


TradeDocumentLineFormSet = inlineformset_factory(
    TradeDocument, TradeDocumentLine, form=TradeDocumentLineForm,
    formset=BaseTradeDocumentLineFormSet, extra=1, can_delete=True,
)
