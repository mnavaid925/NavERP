"""SCM 4.10 Returns Management — the receiving-bench forms.

**§7.2 — ``extra=0`` does NOT stop row injection.** A ``ReturnDisposition`` row becomes an AUDIT
record the moment ``stock_posted`` is True: it is the only evidence of a movement in an append-only
ledger that cannot be corrected in place. So :data:`ReturnDispositionFormSet` is built with
``can_delete=False`` AND :class:`BaseReturnDispositionFormSet` carries an explicit injection guard
that compares the POSTed management form's ``INITIAL_FORMS`` against the server-side row count. A
crafted POST that lowers ``INITIAL_FORMS`` makes Django treat existing rows as NEW ones and write a
second set; one that raises it makes it index past the queryset. Neither is caught by ``extra=0``,
which only controls RENDERING.

**§7.1 — the formset ``clean()`` reads the PARENT** (``return_line.quantity_approved``), so the
view must assign ``formset.instance`` from the picked line BEFORE ``formset.is_valid()``. On create
the instance is an empty ``ReturnLine()`` whose ``quantity_approved`` is None and the cap silently
passes everything.

**§7.6 — ``lot_serial`` is ``select_related("item")`` everywhere.** ``LotSerial.__str__`` reads
``self.item.sku``, so an unjoined queryset is one SELECT per rendered ``<option>``.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _scope_to_parent
from apps.scm.models import Location, ReturnDisposition, ReturnLine

ZERO = Decimal("0")


def _receivable_lines(tenant):
    """Return lines a bench row may be booked against — approved, live, physical returns.

    ``ReturnLine`` has no tenant column of its own (it is reached through its authorisation), so
    this walks the parent. A ``credit_only`` RMA is excluded because it never gets a bench row at
    all: there is no physical unit — that is the whole point of the type.
    """
    if tenant is None:
        return ReturnLine.objects.none()
    return (ReturnLine.objects
            .filter(return_authorization__tenant=tenant,
                    return_authorization__return_type="physical")
            .filter(return_authorization__status__in=("approved", "awaiting_receipt",
                                                      "partially_received", "received"))
            .select_related("return_authorization", "item", "reason")
            .order_by("-return_authorization__requested_on", "id"))


class ReturnDispositionForm(TenantModelForm):
    """One bench row.

    EXCLUDES the whole stamped block (§7.7): ``received_on`` / ``received_by``, ``refurbished_on``,
    ``stock_posted``, ``stock_move``, ``decided_on`` / ``decided_by``. ``restock_unit_cost`` IS a
    field and this form is its only writer — it is SEEDED once from
    ``policy.grade_X_cost_pct × item.average_cost`` on an unbound form that already knows its line,
    and after that the human's figure stands. That is the difference between a default and a
    derived column, and it is the ``NonConformance.cost_of_quality`` posture exactly.

    The item's own ``average_cost`` is exposed as ``item_average_cost`` so the template can show it
    next to the field and an outlier is visible rather than merely possible.
    """

    class Meta:
        model = ReturnDisposition
        fields = ["return_line", "quantity", "location", "lot_serial", "condition_grade",
                  "disposition", "restock_location", "restock_unit_cost", "recovery_value",
                  "nonconformance", "notes"]

    #: The three columns `returndisposition_decide` reserves for a tenant admin. This form writes the
    #: SAME columns, so without the same gate the one on the action is decoration — a plain member
    #: could choose restock vs scrap and set the cost at which returned goods re-enter stock. Exactly
    #: the ReorderRuleForm / safety_stock_apply situation, and the same remedy.
    ADMIN_ONLY_FIELDS = ("disposition", "restock_location", "restock_unit_cost")

    def __init__(self, *args, is_tenant_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        # ReturnLine is tenant-less, so TenantModelForm cannot scope it — by hand, or the picker
        # lists every tenant's return lines.
        _scope_to_parent(self, "return_line", _receivable_lines(self.tenant))
        if not is_tenant_admin:
            for name in self.ADMIN_ONLY_FIELDS:
                if name in self.fields:
                    # `disabled`, not readonly: Django ignores the SUBMITTED value entirely and keeps
                    # the instance's, so a crafted POST cannot set it either.
                    self.fields[name].disabled = True
                    self.fields[name].help_text = (
                        "Set by a workspace admin on the bench — use Decide on the disposition "
                        "detail page.")
        if "lot_serial" in self.fields:
            self.fields["lot_serial"].queryset = (
                self.fields["lot_serial"].queryset.select_related("item")
                .order_by("item__sku", "number"))
        for name in ("location", "restock_location"):
            if name in self.fields:
                self.fields[name].queryset = (
                    self.fields[name].queryset.filter(is_active=True).order_by("code"))
        if "nonconformance" in self.fields:
            # NonConformance.__str__ is number + title, but every page that renders it shows the
            # item beside it — one join, saved on every option.
            self.fields["nonconformance"].queryset = (
                self.fields["nonconformance"].queryset.select_related("item"))
        if "disposition" in self.fields and self.instance.pk and self.instance.stock_move_id is not None:
            # A posted row's decision is history. The view refuses the edit too (§7.5 — the gate
            # lives in both places); this makes the field itself inert so a crafted POST that got
            # past the view still cannot rewrite what the ledger recorded.
            self.fields["disposition"].disabled = True
            self.fields["quantity"].disabled = True

        line = self.instance.return_line if self.instance.return_line_id else None
        if line is not None:
            self.item_average_cost = (line.item.average_cost or ZERO) if line.item_id else ZERO
            if (not self.is_bound and "restock_unit_cost" in self.fields
                    and not self.initial.get("restock_unit_cost")
                    and not self.instance.restock_unit_cost):
                from apps.scm.models import select_policy
                policy = (line.return_authorization.policy
                          if line.return_authorization.policy_id
                          else select_policy(self.tenant, line.item if line.item_id else None))
                if policy is not None:
                    self.initial["restock_unit_cost"] = policy.restock_cost_for(
                        self.instance.condition_grade or "a", self.item_average_cost)
        else:
            self.item_average_cost = ZERO

    def clean(self):
        cleaned = super().clean()
        line = cleaned.get("return_line") or (
            self.instance.return_line if self.instance.return_line_id else None)
        if line is None:
            return cleaned
        item = line.item if line.item_id else None
        lot = cleaned.get("lot_serial")
        disposition = cleaned.get("disposition")

        if item is not None and item.tracking != "none" and lot is None:
            self.add_error("lot_serial",
                           f"{item.sku} is {item.get_tracking_display().lower()}-tracked — record "
                           "which lot or serial came back, or the movement is untraceable.")
        if lot is not None and item is not None and lot.item_id != item.pk:
            self.add_error("lot_serial",
                           f"{lot.number} belongs to {lot.item.sku}, not {item.sku}.")
        if disposition == "restock":
            # blocks_restock is enforced HERE and re-checked inside the posting transaction — a
            # form is a convenience, not a control (§7.5).
            if line.reason_id and line.reason.blocks_restock:
                self.add_error("disposition",
                               f"Reason '{line.reason.code}' blocks restocking — this unit can "
                               "never go back into sellable stock.")
            if cleaned.get("restock_location") is None:
                self.add_error("restock_location",
                               "Choose where the unit goes back into sellable stock.")
            elif cleaned.get("restock_location") == cleaned.get("location"):
                self.add_error("restock_location",
                               "That is the returns bench — a restock has to move the unit into "
                               "sellable stock, not leave it where it is.")
            if lot is not None and lot.status == "expired":
                self.add_error("disposition",
                               f"Lot {lot.number} is expired — scrap or quarantine it instead.")
        return cleaned


class BaseReturnDispositionFormSet(forms.BaseInlineFormSet):
    """The bench formset — the parent-reading cap (§7.1) and the injection guard (§7.2)."""

    def clean(self):
        super().clean()
        # ---- §7.2 injection guard ---------------------------------------------------------------
        # extra=0/can_delete=False govern RENDERING. The management form governs PARSING, and it
        # arrives from the client. If INITIAL_FORMS disagrees with what is actually on file, the
        # POST is either stale (somebody else graded a row while this page was open) or crafted —
        # and in both cases writing it would silently duplicate or skip audit rows.
        # Only comparable when the formset was RENDERED against this same parent. The bare "Receive
        # a return line" page loads with no `?line`, so BaseInlineFormSet substitutes an unsaved
        # ReturnLine() and the management form goes out with INITIAL_FORMS=0; the view then attaches
        # the picked line on POST. Comparing 0 against that line's existing rows dead-ended the
        # module's main create button for every line `receive_all` had already touched — which is
        # every partially-received line. The guard is right in principle, so it is narrowed rather
        # than dropped: a stale or crafted POST against a page that WAS rendered with the parent
        # still fails.
        rendered_against_parent = self.initial_form_count() > 0
        on_file = self.instance.dispositions.count() if self.instance.pk else 0
        if rendered_against_parent and self.initial_form_count() != on_file:
            raise ValidationError(
                "The rows on this page no longer match the ones on file — reload the bench and "
                "grade it again.")
        for form in self.forms[:self.initial_form_count()]:
            if form.instance.pk and form.instance.stock_move_id is not None and form.has_changed():
                changed = set(form.changed_data) - {"notes", "recovery_value"}
                if changed:
                    raise ValidationError(
                        "A row that has already posted to the stock ledger cannot be re-graded — "
                        "the ledger is append-only. Split or raise a new adjustment instead.")

        rows = [form for form in self.forms
                if getattr(form, "cleaned_data", None) and not form.cleaned_data.get("DELETE")]
        if not rows:
            return

        # ---- §7.1 the cap that READS THE PARENT -------------------------------------------------
        line = self.instance
        approved = getattr(line, "quantity_approved", None)
        if not approved:
            # On CREATE this is an empty ReturnLine() and `approved` is None — which is exactly why
            # the view must assign formset.instance BEFORE is_valid(). Nothing to cap against here.
            return
        total = sum((form.cleaned_data.get("quantity") or ZERO for form in rows), ZERO)
        if total > approved:
            raise ValidationError(
                f"That receives {total} against only {approved} approved on this line. Reduce the "
                "quantities, or approve more on the return first.")

    def add_fields(self, form, index):
        """Build the lot/location option lists ONCE for the whole formset — the ``CapaTask``
        precedent. ``ModelChoiceField.__deepcopy__`` calls ``queryset.all()``, discarding any
        cache, so each row would otherwise re-run the same SELECT."""
        super().add_fields(form, index)
        for name in ("lot_serial", "location", "restock_location", "nonconformance"):
            if name not in form.fields:
                continue
            cache = f"_{name}_choices"
            if not hasattr(self, cache):
                setattr(self, cache, list(form.fields[name].choices))
            form.fields[name].choices = getattr(self, cache)


class ReturnDispositionRowForm(ReturnDispositionForm):
    """The formset's row form — the standalone form WITHOUT its ``return_line`` picker.

    The parent is the formset's instance, so repeating the picker on every row would let one row
    be re-pointed at another line and quietly escape the cap in ``clean()``.
    """

    class Meta(ReturnDispositionForm.Meta):
        fields = ["quantity", "location", "lot_serial", "condition_grade", "disposition",
                  "restock_location", "restock_unit_cost", "recovery_value", "notes"]


ReturnDispositionFormSet = inlineformset_factory(
    ReturnLine, ReturnDisposition, form=ReturnDispositionRowForm,
    formset=BaseReturnDispositionFormSet, extra=1,
    # can_delete=False: a bench row is an audit record the moment it posts, and the formset cannot
    # know which rows those are at render time. Removing an un-posted row is a delete action on the
    # row itself, which goes through its own tenant-scoped view.
    can_delete=False, max_num=50, validate_max=True,
)


class ReturnLinePickerForm(forms.Form):
    """Which return line is being received. The header half of the bench create page.

    Separate from the formset because the formset's parent IS this choice: the view validates this
    form first, assigns ``formset.instance = cleaned_data["return_line"]``, and only THEN calls
    ``formset.is_valid()`` — §7.1 in its most literal form.
    """

    return_line = forms.ModelChoiceField(queryset=ReturnLine.objects.none(),
                                         label="Return line being received")

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.fields["return_line"].queryset = _receivable_lines(tenant)


class ReturnDispositionDecideForm(forms.Form):
    """The bench decision.

    ``disposition`` deliberately omits ``received_pending``: that state is arrived at by RECEIVING,
    never by deciding, and offering it here would let somebody "decide" a row back into limbo after
    it had already posted stock.

    The choice list is narrowed further IN THE VIEW when the line's reason ``blocks_restock`` —
    a gate lives in two places (§7.5), and this form is constructed with the line so it can do it
    here as well as there.
    """

    disposition = forms.ChoiceField(choices=ReturnDisposition.DECIDED_DISPOSITION_CHOICES)
    condition_grade = forms.ChoiceField(choices=ReturnDisposition.GRADE_CHOICES, required=False)
    restock_location = forms.ModelChoiceField(queryset=Location.objects.none(), required=False)
    restock_unit_cost = forms.DecimalField(max_digits=14, decimal_places=4, min_value=ZERO,
                                           required=False,
                                           help_text="Blank re-seeds from the grade write-down")
    recovery_value = forms.DecimalField(max_digits=14, decimal_places=2, min_value=ZERO,
                                        required=False)
    notes = forms.CharField(required=False, max_length=255)

    def __init__(self, *args, tenant=None, line=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.line = line
        self.fields["restock_location"].queryset = (
            Location.objects.filter(tenant=tenant, is_active=True).order_by("code")
            if tenant is not None else Location.objects.none())
        if line is not None and line.reason_id and line.reason.blocks_restock:
            self.fields["disposition"].choices = [
                choice for choice in ReturnDisposition.DECIDED_DISPOSITION_CHOICES
                if choice[0] not in ("restock", "refurbish")]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("disposition") == "restock" and cleaned.get("restock_location") is None:
            self.add_error("restock_location",
                           "Choose where the unit goes back into sellable stock.")
        return cleaned


class ReturnDispositionSplitForm(forms.Form):
    """Split a bench row in two — the ONLY thing that makes disposition-as-a-row survive reality.

    Three units back as 2 restock + 1 scrap is the case that justifies the row grain at all, and it
    is not knowable at intake. Permitted ONLY while the row is ``received_pending`` and unposted;
    the view re-checks both inside the lock.
    """

    quantity = forms.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"),
                                  label="Quantity to move onto the new row")

    def __init__(self, *args, row=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.row = row

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if self.row is not None and quantity >= (self.row.quantity or ZERO):
            raise ValidationError(
                f"Splitting off {quantity} of {self.row.quantity} would leave nothing behind — "
                "just re-grade the row instead.")
        return quantity
