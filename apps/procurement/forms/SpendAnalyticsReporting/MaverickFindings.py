"""Procurement 6.14 Spend Analytics & Reporting — MaverickSpendFinding form.

One shape: ``MaverickSpendFindingForm``, the hand-raise-or-amend form. Most findings are minted
by ``MaverickSpendFinding.scan()``; this form exists because a buyer who spots maverick spend the
detectors cannot see (a service bought on somebody's card, a contract nobody digitised) must be
able to put it on the same board rather than in an email.

Everything the system owns is EXCLUDED, and each exclusion is a deliberate one:

* ``tenant`` — stamped by ``crud_create`` / ``TenantUniqueMixin``.
* ``number`` — assigned once by ``TenantNumbered.save()`` (``MSF-#####``).
* ``status`` — moved ONLY by the four verb methods, through the disposition POST. It is
  ``editable=False`` on the model for the same reason; offering it here would let a crafted POST
  file a finding as "remediated" without a note, an actor or a timestamp.
* ``dedupe_key`` — the deterministic identity a re-scan matches on. Typed, it would let one
  finding masquerade as another and get silently overwritten by the next scan.
* ``leakage_amount`` — DERIVED in ``save()`` from ``amount`` minus ``benchmark_amount``. A stored
  editable balance is exactly what L29 forbids.
* ``detected_at`` — a system stamp. A ``DateTimeField`` on a form built by ``TenantModelForm``
  renders as ``datetime-local``, and a system timestamp routed through a date widget loses its
  seconds on every save (L22).
* ``resolution_note`` / ``resolved_by`` / ``resolved_at`` — written by the disposition POST, not
  typed here.
* ``created_at`` / ``updated_at`` — timestamps.

Tenant discipline: every dropdown is narrowed to the workspace in ``__init__`` AND re-checked in
``clean()`` — a narrowed ``<select>`` is UX, not an authorization boundary, and an unscoped
``ModelChoiceField`` both displays another workspace's rows and ACCEPTS their pk from a crafted
POST. ``SupplierInvoiceLine`` is the one exception to ``_reject_foreign``: it has NO tenant column
of its own (it is scoped through its header), so passing it to the shared helper would compare a
nonexistent ``tenant_id`` and reject every line, valid or not.

Import discipline: this sub-package is NOT YET WIRED (the Integrator adds the re-export blocks),
so every sibling entity is imported as a MODULE — never ``from apps.procurement.models import X``,
which would be a star-import cycle at URLconf import. Same rule the 6.13 ``InvoiceDisputes`` form
follows.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models.CatalogManagement.CatalogItems import CatalogItem
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoiceLines import SupplierInvoiceLine
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice
from apps.procurement.models.SpendAnalyticsReporting.MaverickFindings import MaverickSpendFinding


def _supplier_parties(tenant):
    """Parties this tenant can buy from — the 6.5 / 6.8 helper rule verbatim (supplier OR vendor).

    Suppliers are ``core.Party`` + ``core.PartyRole``; there is no vendor table in this tree and a
    standalone one would fork the party spine (L36).
    """
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects
            .filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct()
            .order_by("name"))


class MaverickSpendFindingForm(TenantUniqueMixin, TenantModelForm):
    """Raise or amend one maverick-spend finding.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``MaverickSpendFinding.clean()`` compares every chosen FK's tenant against
    ``self.tenant_id``, and without the stamp every CREATE would be falsely rejected as
    cross-tenant (the CRUD helpers only assign the real tenant AFTER ``is_valid()``).
    """

    # Declared explicitly rather than left to the model, so the magnitude and the sign are
    # enforced by the FIELD instead of being hand-parsed in ``clean()``. Both mirror the model's
    # DecimalField(18, 2) exactly.
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, required=True,
        help_text="What the maverick spend was worth.")
    benchmark_amount = forms.DecimalField(
        max_digits=18, decimal_places=2, min_value=0, required=False,
        help_text="What it should have cost, when a contracted or catalogue price exists. "
                  "Leakage is derived from the gap and is never stored editable.")

    class Meta:
        model = MaverickSpendFinding
        fields = ["reason", "severity", "supplier_invoice", "invoice_line", "purchase_order",
                  "vendor", "category", "org_unit", "contract", "catalog_item", "document_date",
                  "amount", "benchmark_amount", "is_addressable", "detail"]
        widgets = {
            "detail": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            # TenantModelForm re-applies a type="date" DateInput to every DateField after
            # ``super().__init__``; this states the intent at the declaration site as well.
            "document_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        fk_names = ("supplier_invoice", "invoice_line", "purchase_order", "vendor", "category",
                    "org_unit", "contract", "catalog_item")
        if tenant is None:
            # A tenant-less user (the superuser has ``tenant=None`` by design) must not be OFFERED
            # another workspace's rows, and must not be able to post one either.
            for name in fk_names:
                self.fields[name].queryset = self.fields[name].queryset.none()
            return

        from apps.core.models import OrgUnit
        from apps.scm.models import ItemCategory, PurchaseOrder, SupplierContract

        self.fields["supplier_invoice"].queryset = (
            SupplierInvoice.objects.filter(tenant=tenant)
            .select_related("vendor").order_by("-invoice_date", "-id"))
        # SupplierInvoiceLine has NO tenant column — it is narrowed through its header, and
        # re-checked the same way in clean().
        lines = (SupplierInvoiceLine.objects.filter(invoice__tenant=tenant)
                 .select_related("invoice").order_by("-id"))
        if self.instance.pk and self.instance.supplier_invoice_id:
            # Once a finding names an invoice, only that invoice's lines are a sane choice.
            lines = lines.filter(invoice_id=self.instance.supplier_invoice_id)
        self.fields["invoice_line"].queryset = lines
        self.fields["purchase_order"].queryset = (
            PurchaseOrder.objects.filter(tenant=tenant)
            .select_related("vendor").order_by("-order_date", "-id"))
        self.fields["vendor"].queryset = _supplier_parties(tenant)
        self.fields["category"].queryset = (
            ItemCategory.objects.filter(tenant=tenant, is_active=True).order_by("name"))
        self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=tenant).order_by("name")
        self.fields["contract"].queryset = (
            SupplierContract.objects.filter(tenant=tenant)
            .select_related("party").order_by("-start_date", "-id"))
        self.fields["catalog_item"].queryset = (
            CatalogItem.objects.filter(tenant=tenant, status="approved", is_active=True)
            .select_related("supplier").order_by("name"))

    def clean(self):
        cleaned = super().clean()

        # The crafted-POST re-check. ``invoice_line`` is deliberately absent: it carries no tenant
        # column, so ``_reject_foreign`` would read ``None`` off every row and reject them all.
        _reject_foreign(self, cleaned, ["supplier_invoice", "purchase_order", "vendor", "category",
                                        "org_unit", "contract", "catalog_item"])
        line = cleaned.get("invoice_line")
        if line is not None:
            tenant_id = self.tenant.pk if self.tenant is not None else None
            if line.invoice.tenant_id != tenant_id:
                self.add_error("invoice_line", "That record belongs to another workspace.")

        # At least one source pointer. The model enforces this too, but stating it here keys the
        # message onto a field the form actually renders instead of a non-field error.
        if not (cleaned.get("supplier_invoice") or cleaned.get("invoice_line")
                or cleaned.get("purchase_order")):
            self.add_error(
                "supplier_invoice",
                "Point the finding at an invoice, an invoice line or a purchase order — a "
                "finding with no evidence cannot be reviewed.")

        invoice = cleaned.get("supplier_invoice")
        if line is not None and invoice is not None and line.invoice_id != invoice.pk:
            self.add_error("invoice_line", "That line belongs to a different invoice.")

        # A benchmark below the amount is what leakage MEANS; a benchmark above it is simply a
        # good buy, and the model floors the derived leakage at zero rather than storing a
        # negative. Warned on the field so the operator knows nothing will be recorded.
        amount = cleaned.get("amount")
        benchmark = cleaned.get("benchmark_amount")
        if amount is not None and benchmark is not None and benchmark > amount:
            self.add_error(
                "benchmark_amount",
                "The benchmark is above the amount paid, so there is no leakage to record — "
                "leave it blank unless the spend cost more than it should have.")

        return cleaned
