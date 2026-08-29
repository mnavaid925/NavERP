"""Procurement 6.12 Goods Receipt & Inspection — the receiving console's book form.

The three boards in this lane are COMPUTED pages with no model of their own, so there is exactly
one form here and it belongs to the console's single write verb: booking a **draft**
``scm.GoodsReceiptNote`` from a supplier's ASN declaration.

It is a plain :class:`django.forms.Form`, deliberately NOT a ``ModelForm`` over
``scm.GoodsReceiptNote``. Two reasons, both structural:

* The GRN is SCM's document (L36). A ModelForm here would put a second editor on a spine model
  that already has one at ``scm:goodsreceipt_edit``, and the two would drift on which fields are
  writable.
* The console's rows each post their OWN inline HTML form (one per ASN on the page); the template
  never renders a bound Django form, so there is no ``book_form`` in the page context. This class
  exists purely as the SERVER-SIDE validator for whatever those inline forms post — the
  ``<input>`` names below are the contract, not the widgets.

**Input-name contract** (the one place the backend and the template must agree byte for byte):
``receipt_date`` (``type="date"``), ``location`` (a ``<select>`` built from the ``locations``
context var), ``notes``, and one ``qty_<asn_line.pk>`` number input per declared line. The
mint-lots verb posts a separate form carrying only the CSRF token.

The dynamic per-line fields are declared in ``__init__`` from the ASN's own lines, which is what
makes a crafted ``qty_<pk>`` for somebody else's line a field this form simply does not have —
the quantity is dropped rather than applied.
"""
from decimal import Decimal

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.scm.models import Location

ZERO = Decimal("0")


class ReceivingConsoleBookForm(forms.Form):
    """Validates one console row's "book this arrival" POST.

    ``location`` is a ``ModelChoiceField`` narrowed to the workspace's own active locations: for a
    ModelChoiceField the queryset IS the authorization boundary (a pk outside it fails
    ``to_python`` as an invalid choice), so a crafted POST cannot land this receipt in another
    tenant's warehouse.
    """

    receipt_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
        help_text="The day the goods physically arrived on the dock",
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.none(), required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Receiving / staging location the goods land in",
    )
    notes = forms.CharField(
        required=False, max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
    )

    def __init__(self, *args, asn=None, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.asn = asn
        self.tenant = tenant

        self.fields["location"].queryset = (
            Location.objects.filter(tenant=tenant, is_active=True).order_by("code")
            if tenant is not None else Location.objects.none()
        )

        # Fetched ONCE and kept on the form: the view reads back ``asn_lines`` to build the
        # receipt lines, so the ASN's lines are never queried twice on the write path.
        self.asn_lines = []
        if asn is not None:
            self.asn_lines = list(asn.lines.select_related("po_line").order_by("id"))

        #: Names of the dynamically declared quantity fields, in line order.
        self.line_field_names = []
        for line in self.asn_lines:
            name = f"qty_{line.pk}"
            self.fields[name] = forms.DecimalField(
                required=False, min_value=ZERO, max_digits=14, decimal_places=4,
                label=str(line.item_description or line.sku_hint or line.pk),
                widget=forms.NumberInput(attrs={"step": "0.0001", "min": "0",
                                                "class": "form-input"}),
            )
            self.line_field_names.append(name)

    def quantity_for(self, line):
        """The cleaned quantity posted for one ASN line, or ``None`` when it was left blank."""
        return self.cleaned_data.get(f"qty_{line.pk}")

    def clean(self):
        cleaned = super().clean()

        # DecimalField already refuses NaN/Infinity and enforces min_value, but the console is a
        # hand-posted inline form and the guard is cheap: re-check finiteness and sign HERE so a
        # bad figure reads as a field error rather than dying on the DecimalField column.
        total = ZERO
        for name in self.line_field_names:
            quantity = cleaned.get(name)
            if quantity is None:
                continue
            if not quantity.is_finite() or quantity < ZERO:
                self.add_error(name, "Enter a quantity of zero or more.")
                continue
            total += quantity

        # A receipt with nothing on it is not a receipt. Refusing here is what stops a stray
        # double-click on an empty row from minting an empty draft GRN (and burning a GRN number).
        if not self.errors and total <= ZERO:
            raise ValidationError("Enter a received quantity on at least one line.")
        return cleaned
