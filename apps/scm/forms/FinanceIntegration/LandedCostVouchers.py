"""SCM 4.18 Finance & Accounting Integration — ``LandedCostVoucher`` + ``LandedCostCharge`` forms.

Two forms, and the gap between them is the point:

* :class:`LandedCostVoucherForm` creates the *envelope* — which receipt, which payee, which
  consignment, which date, which default basis. It carries **no money at all**. Every figure on a
  voucher is derived: the totals from its charges by ``recalc_totals()``, the allocation from the
  stock ledger by ``allocate()``. A typed total would be a second, un-auditable answer to what it
  cost to land these goods.
* :class:`LandedCostChargeForm` adds ONE cost line. It carries no ``voucher`` field: the parent comes
  from the URL, because a parent pk in a POST body is how a caller grafts a charge onto another
  workspace's voucher.

There is deliberately **no form for** ``LandedCostAllocation``. Every column on it is
``editable=False`` and ``LandedCostVoucher.allocate()`` is its only writer.

**Whitelists, never ``Meta.exclude``.** A whitelist fails CLOSED when a column is added later; an
exclude list fails open, and the columns it would silently admit here are ``status`` (the verb
ladder's), ``bill`` (the accounting hand-off) and the six derived money/stamp columns.

SCOPING NOTE — :class:`LandedCostChargeForm` gets NO automatic scoping. ``TenantModelForm`` narrows a
``ModelChoiceField`` only when the target model carries its own ``tenant`` column *and* a tenant was
passed; it cannot know that ``LandedCostCharge`` reaches its tenant through its parent. Every FK on
that form is therefore narrowed BY HAND, and re-checked in ``clean()`` — a narrowed ``<select>`` has
never held against a crafted POST (L39 §2).
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import (_active_currencies, _carrier_parties, _keep_current,
                                    _reject_foreign)

from apps.accounting.models import GLAccount, TaxCode

from apps.scm.models import (
    DutyTariff,
    FreightInvoice,
    GoodsReceiptNote,
    LandedCostCharge,
    LandedCostVoucher,
    Shipment,
    TradeDocument,
)


class LandedCostVoucherForm(TenantModelForm):
    """The landed-cost envelope: receipt + payee + context + basis. No money.

    ``TenantUniqueMixin`` is deliberately NOT mixed in, unlike ``ClientBillingRunForm`` and
    ``DutyTariffForm``: the only ``unique_together`` on this model is ``("tenant", "number")`` and
    ``number`` is auto-assigned by ``TenantNumbered.save()`` with its own retry-on-collision guard,
    so there is no user-enterable duplicate for the mixin to catch. Adding it would imply a check that
    does nothing.
    """

    class Meta:
        model = LandedCostVoucher
        # Deliberately ABSENT, named so nobody re-adds them: `tenant` (stamped by `crud_create`);
        # `number` (auto LC-#####); `status` (the verb ladder's — ruling 4 in the model docstring);
        # `bill` (the AP hand-off, set by `draft_bill()`); `estimated_total`, `actual_total`,
        # `variance_amount`, `variance_pct`, `allocated_total` (all derived by `recalc_totals()`);
        # `accrued_at` (stamped by `accrue()`); `created_at` / `updated_at`.
        #
        # Every one of those workflow columns is ALREADY `editable=False` and therefore unreachable
        # by a ModelForm (L22). They are listed anyway: a later hand dropping `editable=False` for an
        # admin convenience would otherwise silently open them here — and `accrued_at` in particular
        # would be rendered by a `DateInput` that TRUNCATES the time half on the next save (L22).
        fields = ["goods_receipt", "party", "shipment", "trade_document", "currency", "cost_date",
                  "allocation_basis", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = self.tenant

        # RECEIVED receipts only. A draft GRN has posted nothing to the stock ledger, so a voucher
        # against one could be created and then never allocated — offering it is offering a dead end.
        # `.none()` for a tenant-less user rather than the unscoped default, which would list every
        # workspace's receipts.
        self.fields["goods_receipt"].queryset = (
            GoodsReceiptNote.objects.filter(tenant=tenant, status="received")
            .select_related("purchase_order").order_by("-receipt_date", "-id")
            if tenant is not None else GoodsReceiptNote.objects.none())

        # REUSED, not re-invented: a forwarder or a customs broker is procured from in exactly the
        # way a carrier is, and `_carrier_parties` already accepts the supplier / vendor / partner
        # spellings. A sixth near-identical role helper is how two copies of one rule start to drift.
        self.fields["party"].queryset = _carrier_parties(tenant)

        self.fields["shipment"].queryset = (
            Shipment.objects.filter(tenant=tenant).select_related("carrier").order_by("-id")
            if tenant is not None else Shipment.objects.none())
        self.fields["trade_document"].queryset = (
            TradeDocument.objects.filter(tenant=tenant).order_by("-id")
            if tenant is not None else TradeDocument.objects.none())

        # `accounting.Currency` is GLOBAL — no tenant column — so `TenantModelForm` cannot scope it
        # and filtering it by tenant would empty the dropdown. Active currencies only.
        _active_currencies(self)

        self.fields["goods_receipt"].help_text = (
            "The received goods this cost lands on. Its posted receipt moves are the allocation base.")
        self.fields["party"].help_text = (
            "Who gets paid — the drafted vendor bill is raised to this party.")
        self.fields["cost_date"].help_text = "The date these charges were incurred."
        self.fields["allocation_basis"].help_text = (
            "Default basis for every charge that does not override it. Weight and volume fall back "
            "to quantity when the items carry no weight or volume.")

    def clean(self):
        cleaned = super().clean()
        # The FORM-boundary copy of the model's cross-tenant guard, keyed on fields this form
        # actually carries so it renders as a field error instead of raising `ValueError` out of
        # `add_error`. `party` is included even though the model's `TENANT_SCOPED_FKS` omits it —
        # the tuple omits soft `core.Party` pointers, and a foreign payee is exactly what would put
        # another workspace's party onto a drafted `accounting.Bill`.
        _reject_foreign(self, cleaned, ("goods_receipt", "shipment", "trade_document", "party"))
        return cleaned


class LandedCostChargeForm(TenantModelForm):
    """ONE cost line on a voucher. The parent comes from the ROUTE, never from the POST body.

    Built on ``TenantModelForm`` rather than a bare ``forms.ModelForm`` for the same reason every
    other child-line form in ``apps/scm`` is (``ClientBillingRunLineForm``, ``SalesOrderLineForm``,
    ``FreightInvoiceLineForm``): the base is what puts ``form-input`` / ``form-select`` /
    ``form-textarea`` on every widget and what gives every form in this package the same ``tenant=``
    constructor. It scopes nothing automatically here — see the module docstring — so all four FKs
    are narrowed by hand below.
    """

    class Meta:
        model = LandedCostCharge
        # `voucher` is deliberately ABSENT: it comes from the URL. A parent pk in a POST body is how
        # a caller grafts a charge onto another workspace's voucher (the 4.17 `run` /
        # 4.15 `cold-chain-monitors/<pk>/readings/add/` precedent).
        fields = ["charge_type", "description", "party", "freight_invoice", "estimated_amount",
                  "actual_amount", "allocation_basis", "gl_account", "tax_code", "is_recoverable",
                  "capitalise_to_inventory", "hs_code", "country_of_origin", "duty_rate_pct"]

    def __init__(self, *args, voucher=None, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = self.tenant

        # THE PARENT, from the ROUTE. Assigned before validation so `full_clean()` on the unsaved
        # instance has a voucher to read (`effective_basis` walks it), and so the view never has to
        # depend on POST for the column that decides which voucher owns the charge.
        self.voucher = voucher
        if voucher is not None and self.instance.voucher_id is None:
            self.instance.voucher = voucher

        self.fields["party"].queryset = _carrier_parties(tenant)
        # `carrier__party`, NOT `carrier`: `FreightInvoice.__str__` renders `self.carrier.name`, and
        # `Carrier.name` is a PROPERTY that reads `self.party.name`
        # (models/TransportationManagement/Carriers.py:103-106). Joining only as far as the carrier
        # leaves the party a lazy fetch, so rendering this <select> costs one query PER OPTION. The
        # app-wide reference pattern for this dropdown is the two-hop join —
        # views/TransportationManagement/FreightInvoices.py and ContractCompliance/TradeDocuments.py
        # both already use `select_related("carrier__party")` for exactly this reason.
        self.fields["freight_invoice"].queryset = (
            FreightInvoice.objects.filter(tenant=tenant).select_related("carrier__party")
            .order_by("-invoice_date", "-id")
            if tenant is not None else FreightInvoice.objects.none())
        self.fields["gl_account"].queryset = (
            GLAccount.objects.filter(tenant=tenant, is_active=True).order_by("code")
            if tenant is not None else GLAccount.objects.none())
        self.fields["tax_code"].queryset = (
            TaxCode.objects.filter(tenant=tenant, is_active=True).order_by("name")
            if tenant is not None else TaxCode.objects.none())

        # Re-admit each narrowed dropdown's ALREADY-STORED row on the EDIT path. `party` is narrowed
        # by ROLE and `gl_account` / `tax_code` by `is_active`, and all three columns are OPTIONAL
        # (`null=True`) — so once the stored row stops qualifying (the carrier role is removed, the
        # account or tax code is deactivated) its <option> silently disappears, the browser posts an
        # empty value, and saving an unrelated edit NULLs the FK with NO validation error to warn
        # anybody. On `gl_account` that is the expense account `draft_bill()` copies onto the vendor
        # bill line, lost by somebody who came to fix a typo in the description.
        #
        # The base querysets are TENANT-SCOPED (not `.objects.all()`), so the union can only ever
        # re-admit this workspace's own row, and they carry the same ordering as the narrowed ones so
        # the dropdown does not re-sort itself on an edit.
        _keep_current(self, "party",
                      Party.objects.filter(tenant=tenant) if tenant is not None
                      else Party.objects.none())
        _keep_current(self, "gl_account",
                      GLAccount.objects.filter(tenant=tenant).order_by("code") if tenant is not None
                      else GLAccount.objects.none())
        _keep_current(self, "tax_code",
                      TaxCode.objects.filter(tenant=tenant).order_by("name") if tenant is not None
                      else TaxCode.objects.none())

        # Blank MEANS "inherit the voucher's", so the empty option says so rather than showing the
        # anonymous "---------" a reader has to guess at. `required=False` is what lets it be blank.
        basis = self.fields["allocation_basis"]
        basis.required = False
        basis.choices = ([("", "Inherit the voucher's basis")]
                         + list(LandedCostVoucher.ALLOCATION_BASIS_CHOICES))

        self.fields["party"].help_text = (
            "Leave blank to bill this to the voucher's payee. A different vendor here is EXCLUDED "
            "from the drafted bill and reported as such.")
        self.fields["estimated_amount"].help_text = (
            "Allocated when there is no actual yet, so a receipt gets a usable landed cost before "
            "the invoice arrives.")
        self.fields["actual_amount"].help_text = (
            "Once entered, this is what allocates — re-allocate the voucher to apply it.")
        self.fields["is_recoverable"].help_text = (
            "Recoverable import VAT/GST is reclaimed, so it never capitalises into stock.")
        self.fields["duty_rate_pct"].help_text = (
            "Snapshotted from the duty tariff — a later rate change never rewrites this shipment. "
            "Only valid on a Customs Duty charge.")

    def clean(self):
        cleaned = super().clean()
        # All four are tenant-scoped targets; the narrowed dropdowns above are UX, this is the check
        # a crafted POST has to get past.
        _reject_foreign(self, cleaned, ("party", "freight_invoice", "gl_account", "tax_code"))

        # DEFAULT the rate from the workspace's own duty schedule when the typist did not state one.
        # This is the request-path caller of `DutyTariff.rate_for()` — without it the Tax Management
        # master feeds nothing at runtime and the help_text above ("Snapshotted from the duty
        # tariff") is a promise nothing keeps, leaving every rate to be retyped by hand.
        #
        # GUARDED ON `charge_type == "duty"` AND NOTHING ELSE. `LandedCostCharge.clean()` REJECTS a
        # non-zero rate on any other charge type, so defaulting a freight or handling charge that
        # happens to carry an HS code would turn a valid line into a validation error the typist
        # cannot see the cause of.
        #
        # A left-alone box and a typed 0 are the SAME input here — the widget pre-fills the model
        # default 0 — so "no rate stated" is the falsy test rather than `is None`. A rate the typist
        # actually typed is never overwritten, and neither is an already-snapshotted one on an edit:
        # the lookup runs only when the box carries nothing.
        if (cleaned.get("charge_type") == "duty"
                and not cleaned.get("duty_rate_pct")
                and cleaned.get("hs_code")):
            tariff = DutyTariff.rate_for(
                self.tenant, cleaned["hs_code"], cleaned.get("country_of_origin", ""),
                self.voucher.cost_date if self.voucher is not None else None)
            # `None` means no schedule covers this code on that date — the field keeps whatever it
            # had, because "type it yourself" is the documented answer, not "fail the page".
            if tariff is not None:
                cleaned["duty_rate_pct"] = tariff.duty_rate_pct
        return cleaned
