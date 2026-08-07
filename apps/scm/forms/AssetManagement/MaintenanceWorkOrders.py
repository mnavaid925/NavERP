"""SCM 4.13 Asset Management — the ``MaintenanceWorkOrder`` form and its parts formset.

**``status`` is ABSENT from ``Meta.fields``, and that absence is the mechanism.** The column is
``editable=False`` and moved only by the ten verbs (approve / schedule / start / hold / resume /
complete / close / cancel / issue-parts / record-reading). A crafted ``status=completed`` in a POST
body cannot land — not because a view checks for it, but because there is no path from form data to
the column at all. ``started_at`` / ``completed_at`` are system stamps for the same reason (L22), and
``downtime_minutes`` is derived in ``MaintenanceWorkOrder.save()`` from the window, so typing it
would be typing a subtraction.

**``downtime_start`` / ``downtime_end`` ARE on the form, and that is deliberate.** A technician
recording the outage afterwards ("it actually went down at 02:10") is the normal case; forcing the
window through a verb would mean it could never be corrected. The pair's ordering is checked in
``MaintenanceWorkOrder.clean()`` and the total is derived in ``save()``, so nothing here re-derives
it.

**``plan`` is offered unfiltered across the workspace and NOT narrowed to the chosen asset.** A
create form is unbound, so no asset has been chosen yet; narrowing the plan list to "plans for this
asset" would render a permanently empty select on the screen that matters (the 4.5
``ship_to_address`` failure, and the ``WorkOrderForm.bom`` reading of it).
``MaintenanceWorkOrder.clean()`` is what REFUSES a plan that maintains a different machine — which
also holds against a crafted POST, as a narrowed dropdown never did.

**The parts formset does not inherit tenant scoping for free.** ``MaintenanceWorkOrderPart`` carries
no ``tenant`` column — it is reached through ``work_order__tenant`` — so nothing about being an
inline of a tenant-scoped parent narrows its ``item`` / ``lot_serial`` dropdowns. They are scoped
here through ``TenantModelForm``, which means the view MUST construct the formset with
``form_kwargs={"tenant": request.tenant}``, exactly as ``PurchaseOrderLineFormSet`` and
``StockAdjustmentLineFormSet`` are constructed
(``apps/scm/views/ProcurementManagement/PurchaseOrders.py:90``). The parent work order is itself
resolved with ``tenant=request.tenant``, so "this tenant" and "the parent work order's tenant" are
the same set by construction.

**``unit_cost`` / ``is_issued`` / ``issued_at`` are absent from the parts formset.** All three are
``editable=False`` and written only by the issue verb, which stamps the cost from the item's average
cost at the moment the negative ``maintenance`` ``StockMove`` is posted. A form field for any of them
would be a way to claim a consumption the stock ledger never saw.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _employee_parties, _reject_foreign, _supplier_parties
from apps.scm.forms.AssetManagement.Assets import _keep_current, _scope_to_tenant

from apps.scm.models import (Asset, Item, Location, LotSerial, MaintenancePlan,
                             MaintenanceWorkOrder, MaintenanceWorkOrderPart, NonConformance)


class MaintenanceWorkOrderForm(TenantModelForm):
    """One maintenance job — a request, a generated PM occurrence or a breakdown. One table, one form."""

    class Meta:
        model = MaintenanceWorkOrder
        # A WHITELIST, never `Meta.exclude`. Deliberately ABSENT: `status` (verb-driven,
        # `editable=False` — see the module docstring, this is the whole point), `started_at` /
        # `completed_at` (system stamps, L22), `downtime_minutes` (derived in `save()` from the
        # window), `tenant` (stamped by `crud_create`, and in __init__ below so clean() can read it),
        # `number` (auto-assigned in `TenantNumbered.save()`), `created_at` / `updated_at`.
        fields = [
            # what and how urgent
            "title", "work_type", "priority", "source",
            # who and what
            "asset", "plan", "reported_by", "assigned_to", "service_vendor", "parts_location",
            "non_conformance",
            # dates: the two a human owns. The other two are stamped by the start/complete verbs.
            "reported_at", "scheduled_start",
            # the outage — editable on purpose, see the module docstring
            "downtime_start", "downtime_end", "is_unplanned_downtime",
            # Maximo's failure hierarchy, bottom three levels. A CLOSED vocabulary is what makes
            # "which cause costs us the most downtime?" a GROUP BY rather than a text-mining project.
            "problem_code", "cause_code", "remedy_code",
            # cost inputs. `labour_rate` is capped by a model validator, not clamped — an absurd rate
            # flows into three other pages, so it is refused on the way in.
            "labour_hours", "labour_rate", "external_cost",
            # capture only: the complete verb turns this into a MeterReading row.
            "meter_reading_at_work",
            "description", "resolution_notes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "resolution_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP. `crud_create` assigns the tenant only AFTER `is_valid()`, so without this an
        # unsaved job reaches `MaintenanceWorkOrder.clean()` with `tenant_id` None — the exact case
        # its cross-tenant FK guard skips — and both that guard and the plan/asset agreement check
        # would be dead code on the create path. (Not `TenantUniqueMixin`: the only unique_together
        # is `(tenant, number)` and `number` is auto and off the form, so its second half would have
        # nothing to check.)
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # --- what the job is against ----------------------------------------------------------------
        # Every one of these carries its own tenant column, so TenantModelForm already scoped them;
        # re-filtering from the model makes it true by construction. None of the four __str__ methods
        # walks a second FK (Asset "code · name", MaintenancePlan "number · name", Location
        # "code · name", NonConformance "number · title") — checked, not assumed, so no
        # select_related is owed on any of these dropdowns.
        _scope_to_tenant(self, "asset", Asset.objects.all())
        # Not narrowed to the chosen asset, and not narrowed to `is_active` either: a job is
        # routinely raised against a plan that has since been retired, and the provenance link is
        # worth more than the tidier list. See the module docstring.
        _scope_to_tenant(self, "plan", MaintenancePlan.objects.all())
        _scope_to_tenant(self, "parts_location", Location.objects.all())
        # A link OUT to 4.9's existing engine. 4.13 owns no root-cause table.
        _scope_to_tenant(self, "non_conformance", NonConformance.objects.all())

        # --- the three party dropdowns ----------------------------------------------------------------
        # `reported_by` and `assigned_to` are people on the payroll (reported_by + status="requested"
        # IS the maintenance request); `service_vendor` is the outside contractor, so it takes the
        # commercial set. `_keep_current` stops a party whose role was removed from silently NULLing
        # the FK on the next unrelated edit — on `reported_by` that would erase who raised a fault.
        employees = _employee_parties(self.tenant)
        for name in ("reported_by", "assigned_to"):
            if name in self.fields:
                self.fields[name].queryset = _keep_current(
                    employees, self.tenant, getattr(self.instance, f"{name}_id", None))
        if "service_vendor" in self.fields:
            self.fields["service_vendor"].queryset = _keep_current(
                _supplier_parties(self.tenant), self.tenant, self.instance.service_vendor_id)

    def clean(self):
        """Re-check every chosen FK against this workspace — see :func:`_reject_foreign`.

        ``TENANT_SCOPED_FKS`` covers ``asset`` / ``plan`` / ``parts_location`` /
        ``non_conformance``; the three ``core.Party`` pointers are added here because the model's
        table-driven guard does not list them (a party is scoped, but the model treats the three as
        soft references). The plan/asset agreement and the downtime ordering stay in
        ``MaintenanceWorkOrder.clean()`` — one implementation each.
        """
        cleaned = super().clean()
        _reject_foreign(self, cleaned, tuple(MaintenanceWorkOrder.TENANT_SCOPED_FKS)
                        + ("reported_by", "assigned_to", "service_vendor"))
        return cleaned


class MaintenanceWorkOrderPartForm(TenantModelForm):
    """One spare a job needs. Planned when it is added, issued when the issue verb posts the move."""

    class Meta:
        model = MaintenanceWorkOrderPart
        # A WHITELIST. `work_order` is supplied by the inline formset from the parent instance;
        # `unit_cost` / `is_issued` / `issued_at` are `editable=False` and belong to the issue verb
        # — see the module docstring.
        fields = ["item", "lot_serial", "quantity"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The child has no tenant column, so NOTHING scopes these two automatically — see the module
        # docstring. `LotSerial.__str__` dereferences `item.sku`, which is one query per rendered
        # <option> without the select_related, and formset fields are deep-copied PER FORM, so the
        # cost is paid once per row on the page (the `WorkOrderComponentForm.lot_serial` finding).
        _scope_to_tenant(self, "item", Item.objects.all())
        _scope_to_tenant(self, "lot_serial", LotSerial.objects.select_related("item"))

    def clean(self):
        cleaned = super().clean()
        # A crafted POST could name another workspace's item or lot: this child has no tenant column
        # of its own, so nothing downstream would catch it before the issue verb posted a StockMove
        # against a stranger's stock.
        _reject_foreign(self, cleaned, ("item", "lot_serial"))

        item, lot = cleaned.get("item"), cleaned.get("lot_serial")
        # The model's validator allows zero (it is a MinValueValidator(0)); a zero line is a no-op
        # that the issue verb would post as a zero-quantity StockMove. Reject it here instead — the
        # StockAdjustmentLineForm rule.
        if item and not cleaned.get("quantity"):
            self.add_error("quantity", "Enter how many of this part the job needs.")
        # A lot belongs to exactly one item. Scoping the dropdowns to the tenant is not enough: a
        # crafted pairing would draw item A's stock against item B's lot in the append-only ledger,
        # permanently corrupting both items' lot history (the `WorkOrderComponentForm` rule).
        if item and lot and lot.item_id != item.pk:
            self.add_error("lot_serial", f"{lot.number} belongs to {lot.item.sku}, not {item.sku}.")
        return cleaned


class BaseMaintenanceWorkOrderPartFormSet(forms.BaseInlineFormSet):
    """An ISSUED line is history: it may be neither edited nor removed on this form.

    Issuing posts a negative ``maintenance`` ``StockMove`` and stamps ``unit_cost`` from the item's
    average cost at that instant. Deleting the line afterwards would leave the ledger move standing
    with nothing to explain it and silently drop the cost off the job, off the asset's
    ``maintenance_cost_to_date()`` and off the repair-vs-replace ratio on the depreciation report;
    re-typing its quantity or item would restate a consumption the ledger never saw. An over-issue is
    corrected with a stock adjustment, the way every other posted movement in this module is
    corrected — the ``BasePurchaseOrderLineFormSet`` posture, which refuses to remove a line goods
    have already been received against.
    """

    def clean(self):
        super().clean()
        blocked = []
        for form in self.forms:
            # `is_issued` is editable=False and off the form, so `construct_instance` cannot have
            # touched it — this is the stored value.
            if not form.instance.pk or not form.instance.is_issued:
                continue
            # DELETE is a formset-added field and would otherwise read as an edit; the tick itself
            # is handled by the `_should_delete_form` leg.
            touched = [name for name in form.changed_data if name != "DELETE"]
            if self._should_delete_form(form) or touched:
                blocked.append(str(form.instance.item))
        if blocked:
            raise forms.ValidationError(
                "These parts have already been issued from stock and can no longer be changed or "
                f"removed here: {', '.join(blocked)}. Post a stock adjustment to correct an issue."
            )


#: ``extra=3``, matching the shipped line formsets: with ``extra=0`` a part could never be
#: hand-added, or re-added after deletion, and a brand-new job could never gain its first one.
MaintenanceWorkOrderPartFormSet = inlineformset_factory(
    MaintenanceWorkOrder, MaintenanceWorkOrderPart, form=MaintenanceWorkOrderPartForm,
    formset=BaseMaintenanceWorkOrderPartFormSet, extra=3, can_delete=True,
)
