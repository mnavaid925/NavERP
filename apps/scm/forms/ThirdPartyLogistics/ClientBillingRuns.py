"""SCM 4.17 Third-Party Logistics (3PL) Management — ``ClientBillingRun`` forms.

Two forms, and the gap between them is the point:

* :class:`ClientBillingRunForm` creates the *envelope* — which client, which tariff, which period.
  It carries **five fields and no money**. Every figure on a run is derived by
  ``ClientBillingRun.calculate()`` from the stock ledger, the receipts, the orders and the picks;
  a typed subtotal would be a second, un-auditable answer to what the client owes.
* :class:`ClientBillingRunLineForm` adds ONE **manual** charge — the pallet re-wrap nobody has a
  rate basis for, the quantity behind an un-measurable ``per_sqft`` line. It carries no ``run``
  field: the parent comes from the URL, because a parent pk in a POST body is how a caller grafts a
  charge onto another workspace's invoice.

**Whitelists, never ``Meta.exclude``.** A whitelist fails CLOSED when a column is added later; an
exclude list fails open, and the columns it would silently admit here are ``status`` (the verb
ladder's), ``approved_by`` (evidence) and ``invoice`` (the accounting hand-off).
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _reject_foreign

from apps.scm.models import ClientBillingRun, ClientBillingRunLine, ClientRateCard, LogisticsClient


class ClientBillingRunForm(TenantUniqueMixin, TenantModelForm):
    """The billing-run envelope: client + tariff + period. Nothing else.

    ``TenantUniqueMixin`` comes FIRST and is load-bearing. ``ClientBillingRun`` carries
    ``unique_together ("tenant", "client", "period_start", "period_end")``, and re-running a month
    that has already been run is the single most ordinary mistake on this page. Without the mixin
    that duplicate passes ``is_valid()`` and then raises an uncaught ``IntegrityError`` — a 500 on a
    mainline CRUD path — because Django skips a ``unique_together`` whenever ANY of its fields is
    excluded from validation, and ``tenant`` is never a form field. The mixin stamps the tenant AND
    removes it from the exclusions; both halves are required.

    Stamping the tenant early also makes ``ClientBillingRun.clean()``'s cross-tenant guard live on
    the CREATE path — it skips when ``tenant_id`` is ``None``, which is what an unstamped instance
    reaches it as.
    """

    class Meta:
        model = ClientBillingRun
        # Deliberately ABSENT, named so nobody re-adds them: `status` (verb-ladder only — ruling 1
        # in the model docstring); `subtotal` / `minimum_adjustment` / `total` (derived by
        # `recalc_amounts()`); `calculated_at` / `approved_at` / `approved_by` (evidence stamped by
        # the verbs); `invoice` (the accounting hand-off, set by `draft_invoice()`); `number`
        # (auto CBR-#####); `tenant` (stamped by `crud_create`, and in the mixin above so the
        # model's guards can read it); `created_at` / `updated_at`.
        #
        # All nine of the workflow columns are ALREADY `editable=False` and therefore unreachable by
        # a ModelForm (L22). They are listed anyway: a later hand that drops `editable=False` for an
        # admin convenience would otherwise silently open them here.
        fields = ["client", "rate_card", "period_start", "period_end", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = self.tenant

        # TenantModelForm already narrows both of these to the tenant (both targets carry a `tenant`
        # column). Restating `client` is not redundant — it pins the ORDER, which is what makes a
        # 200-client dropdown usable — and `rate_card` is narrowed FURTHER below.
        self.fields["client"].queryset = (
            LogisticsClient.objects.filter(tenant=tenant).select_related("party").order_by("code", "id")
            if tenant is not None else LogisticsClient.objects.none())

        cards = (ClientRateCard.objects.filter(tenant=tenant).select_related("client")
                 if tenant is not None else ClientRateCard.objects.none())
        # Narrow the tariff list to the run's own client once there IS one — on edit, or on a
        # re-rendered invalid POST. This is USABILITY, not a boundary: `ClientBillingRun.clean()`
        # refuses a foreign client's tariff regardless, because a narrowed <select> has never held
        # against a crafted POST (L39 §2), and "bill Acme at Contoso's rates" is the one mistake in
        # this sub-module whose output looks entirely plausible.
        client_id = (self.instance.client_id
                     or (self.data.get("client") if self.is_bound else None))
        if client_id:
            cards = cards.filter(client_id=client_id)
        self.fields["rate_card"].queryset = cards.order_by("-effective_from", "-version", "-id")

        self.fields["rate_card"].help_text = (
            "Must belong to the same client and be effective for part of the period.")
        self.fields["period_start"].help_text = "First day billed, inclusive."
        self.fields["period_end"].help_text = (
            f"Last day billed, inclusive — at most {ClientBillingRun.MINIMUM_CHARGE_MIN_DAYS}+ days "
            "for the monthly minimum to apply.")

    def clean(self):
        cleaned = super().clean()
        # The FORM-boundary copy of the model's cross-tenant guard. Keyed on fields this form
        # actually carries, so it renders as a field error instead of raising `ValueError` out of
        # `add_error`; the model's own guard is the one that holds at the database boundary.
        _reject_foreign(self, cleaned, ("client", "rate_card"))
        return cleaned


class ClientBillingRunLineForm(TenantModelForm):
    """ONE manually added charge on a run. Never the derived lines — those are ``calculate()``'s.

    Built on ``TenantModelForm`` rather than a bare ``forms.ModelForm`` (see the return note): every
    other child-line form in ``apps/scm`` — ``SalesOrderLineForm``, ``PurchaseOrderLineForm``,
    ``RFQLineForm``, ``GoodsReceiptLineForm`` — does the same over an equally tenant-less child,
    because the base is what puts ``form-input`` / ``form-select`` / ``form-textarea`` on every
    widget and what gives every form in this package the same ``tenant=`` constructor. It scopes
    nothing here (this form carries no ``ModelChoiceField`` at all), so the choice is purely about
    the widget contract.

    NEGATIVE CHARGES ARE NOT SUPPORTED HERE, and that is deliberate rather than an oversight.
    ``ClientBillingRunLine.save()`` floors ``amount`` at the rate line's minimum (zero for a manual
    line), so a negative quantity or rate would silently store 0.00 — worse than a refusal. A credit
    to a 3PL client is a ``credit_note`` in ``apps/accounting``, which is where AR lives (L29). The
    form refuses both signs outright rather than letting one round to nothing.
    """

    class Meta:
        model = ClientBillingRunLine
        # Deliberately ABSENT, and why: `run` (it comes from the URL — a parent pk in a POST body is
        # an IDOR); `rate_card_line` (NULL is what MAKES a line manual, and pointing a manual line
        # at a tariff line would make `calculate()`'s "regenerate the derived ones" ambiguous);
        # `amount` (`editable=False`, computed in save()); `is_manual` (FORCED True by the view — a
        # user-settable flag here would let somebody mark a derived line manual and freeze a wrong
        # figure past every recalculation); `needs_manual_quantity` (`editable=False`, set by the
        # engine when it cannot measure something).
        fields = ["charge_category", "charge_basis", "description", "quantity", "rate",
                  "source_reference"]

    def __init__(self, *args, run=None, **kwargs):
        super().__init__(*args, **kwargs)

        # THE PARENT, from the ROUTE. Assigned before validation so `full_clean()` on the unsaved
        # instance has a run to read, and so the view never has to depend on POST for it.
        self.run = run
        if run is not None and self.instance.run_id is None:
            self.instance.run = run

        self.fields["description"].help_text = (
            "What this charge is for — it is printed verbatim on the drafted invoice line.")
        self.fields["quantity"].help_text = "The measured quantity. Charge = quantity × rate."
        self.fields["source_reference"].help_text = (
            "Optional evidence, e.g. 'photo log 12 Jul' or 'GRN-00007' — shown beside the charge.")

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity is not None and quantity < 0:
            raise ValidationError(
                "A billing-run line cannot carry a negative quantity — it would be stored as 0.00. "
                "Raise a credit note in Accounting instead.")
        return quantity

    def clean_rate(self):
        rate = self.cleaned_data.get("rate")
        if rate is not None and rate < 0:
            raise ValidationError(
                "A billing-run line cannot carry a negative rate — it would be stored as 0.00. "
                "Raise a credit note in Accounting instead.")
        return rate
