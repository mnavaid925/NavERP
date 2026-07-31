"""SCM 4.11 Supply Chain Analytics — the hand-raise/edit form and the three triage payloads.

A hand-raised exception is a real workflow (a planner spots something the detector cannot see), so
``SupplyChainAlert`` ships full CRUD. What this module is careful about is the line between the two
kinds of column on that model.

**The form is a WHITELIST, and it stops at the triage columns.** ``Meta.fields`` names the seventeen
editable columns explicitly rather than blacklisting the rest with ``exclude``. Same set either way
today; a whitelist is what keeps it that set *tomorrow*, when a column is added to the model and a
blacklist would quietly put it on the form. It also matches every other form in this repo — there is
no ``Meta.exclude`` anywhere in ``apps/``. Deliberately absent, each with exactly ONE writer and it
is never a form:

* ``status`` / ``acknowledged_by`` / ``acknowledged_at`` / ``snoozed_until`` / ``resolved_by`` /
  ``resolved_at`` / ``raised_at`` / ``last_seen_at`` / ``number`` — ``editable=False`` on the model
  and written only by the five workflow methods (or by ``TenantNumbered.save``);
* ``resolution_note`` — :class:`AlertResolveForm` and ``resolve()`` own it, so a resolution note can
  never exist without a resolver beside it;
* ``dedupe_key`` and ``dimension_key`` — machine-side. Both are what ``detect_alerts()`` matches an
  open row on; a hand-edited key would either strand a detector row or collide with one;
* ``detail`` — the evidence JSON the detector writes, not free-form user text;
* ``tenant`` — assigned by ``crud_create``.

``assigned_to`` is the ONE triage column the form does write, deliberately: it is not *state*, it is
a name. The state columns each keep a single writer.

**The tenant has to be on the instance before validation.** ``SupplyChainAlert.clean()`` gates every
one of its cross-tenant checks on ``self.tenant_id``, and ``crud_create`` assigns the tenant AFTER
``is_valid()`` — so without :class:`TenantUniqueMixin` stamping it in ``__init__``, those checks
would silently no-op on exactly the path they exist for (create). That is why the mixin is here;
its ``validate_unique`` half is a no-op for this model, whose only ``unique_together`` is
``("tenant", "number")`` over a system-assigned number.

**``select_related`` was verified against each ``__str__``, not assumed.** Only two of the seven FK
dropdowns walk a second FK: ``Carrier.__str__`` renders ``self.name``, which is a *property* reading
``self.party.name`` (Carriers.py:105), and ``PurchaseOrder.__str__`` interpolates ``self.vendor``
(PurchaseOrders.py:168). Those two are joined — one query per rendered ``<option>`` otherwise. The
other five (``KpiTarget`` number+name, ``Item`` sku+name, ``Party`` name, ``Shipment`` number+
direction, ``Location`` code+name) read their own columns only, so a join there would be noise. No
``order_by`` overrides either: every target's ``Meta.ordering`` is already the right picker order
(``Carrier`` is ordered by ``party__name`` — note it has no ``name`` COLUMN, so ``order_by("name")``
would be a ``FieldError``).

**L39 §2 — a narrowed dropdown is UX, the guard is ``clean()``.** The six subject FKs are offered as
the FULL tenant-scoped set, unfiltered by status: an exception can legitimately be about a wound-down
location or a cancelled order, and narrowing on a key the create form does not know yet is how a
field ends up permanently empty. What matters — that the records named actually agree on more than
the tenant (L40 §3) — is checked in ``clean()`` here and in the model's ``clean()``, which holds
against a crafted POST as a dropdown never did.
"""
from django.contrib.auth import get_user_model

from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin
from apps.scm.models import SupplyChainAlert

ZERO = Decimal("0")


def _assignable_users(tenant, keep=None):
    """Logins this tenant can hand an exception to.

    ``is_active=False`` is filtered out — assigning work to a disabled login is a queue item nobody
    will ever see. ``keep`` re-admits the person who ALREADY holds the alert, so deactivating someone
    cannot turn every later edit of their alerts into "Select a valid choice" on a field the editor
    never touched.

    Falls back to an EMPTY queryset when there is no tenant (the superuser has ``tenant=None``);
    ``TenantModelForm`` leaves FK querysets unscoped in that case, and the whole user table is not an
    acceptable default.
    """
    user_model = get_user_model()
    if tenant is None:
        return user_model.objects.none()
    live = Q(is_active=True)
    if keep:
        live |= Q(pk=keep)
    return user_model.objects.filter(tenant=tenant).filter(live).order_by("email")


class SupplyChainAlertForm(TenantUniqueMixin, TenantModelForm):
    """Raise or correct one supply-chain exception.

    Everything the detector writes about the LIFECYCLE of an alert is off this form — see the module
    docstring for the full list and for why the mixin is in front of ``TenantModelForm``.
    """

    class Meta:
        model = SupplyChainAlert
        fields = [
            # what fired
            "alert_type", "metric", "kpi_target", "title", "severity",
            # the numbers behind it
            "observed_value", "threshold_value", "impact_value",
            # what it is about
            "dimension_label", "item", "party", "carrier", "shipment", "purchase_order",
            "location",
            # triage
            "assigned_to", "notes",
        ]
        labels = {
            "kpi_target": "KPI target",
            "dimension_label": "Subject label",
        }
        help_texts = {
            "kpi_target": "The target this breaches, when there is one. Picking it fills the metric "
                          "in — a rule-based exception has no target and needs none",
            "dimension_label": "The one line the queue shows. Falls back to the record named below "
                               "when blank, and to 'Network-wide' when nothing is named",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "What is wrong, in one line"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The only two dropdowns whose __str__ walks a second FK — verified, see the module
        # docstring. Both joins also pay for themselves in clean() below, where the error messages
        # render `carrier.name` and `order.vendor` off the already-cached relation.
        if "carrier" in self.fields:
            self.fields["carrier"].queryset = (
                self.fields["carrier"].queryset.select_related("party"))
        if "purchase_order" in self.fields:
            self.fields["purchase_order"].queryset = (
                self.fields["purchase_order"].queryset.select_related("vendor"))
        if "assigned_to" in self.fields:
            self.fields["assigned_to"].queryset = _assignable_users(
                self.tenant, keep=self.instance.assigned_to_id)

    def clean_impact_value(self):
        """Value at risk is a magnitude, and it is the queue's ORDERING key.

        ``Meta.ordering = ["-impact_value", …]`` — a negative figure sorts the exception below every
        zero-impact one, which is a silent way to hide the thing you just said was expensive.
        """
        value = self.cleaned_data.get("impact_value")
        if value is not None and value < ZERO:
            raise ValidationError("Value at risk is what acting on this is worth — it cannot be "
                                  "negative.")
        return value

    def clean(self):
        """The combination checks. Tenant agreement and metric-vs-target live in the model's
        ``clean()``; what is here is what only the form can see, plus the one column with a second
        writer."""
        cleaned = super().clean()

        # L40 §3 — same tenant is not the same subject. A shipment and a carrier both named on one
        # alert have to be the SAME movement, or the detail page points at two unrelated things and
        # the freight figures beside them are nonsense. Only checked when the shipment HAS a carrier:
        # an unbooked shipment has nothing yet to disagree with.
        shipment = cleaned.get("shipment")
        carrier = cleaned.get("carrier")
        if shipment is not None and carrier is not None and shipment.carrier_id \
                and shipment.carrier_id != carrier.pk:
            self.add_error("shipment", f"{shipment.number} is not moving with {carrier.name} — "
                                       "name the carrier that is actually on it, or clear one of "
                                       "the two.")

        # Same rule for the buy side: `PurchaseOrder.vendor` is non-null, so a mismatch here is
        # always a real disagreement rather than a missing value.
        order = cleaned.get("purchase_order")
        party = cleaned.get("party")
        if order is not None and party is not None and order.vendor_id != party.pk:
            self.add_error("purchase_order", f"{order.number} was raised on {order.vendor}, not "
                                             f"{party.name}.")

        # A "KPI breach" that names neither the target nor the metric it breached is an alert with no
        # subject: the detail page has nothing to link to and no report page to send the reader to.
        # Both fields are offered in full, so this asks for something the user can always supply.
        if cleaned.get("alert_type") == "kpi_breach" and not cleaned.get("kpi_target") \
                and not cleaned.get("metric"):
            self.add_error("metric", "A KPI-breach alert has to say WHICH figure breached — pick "
                                     "the target or the metric, or choose the exception type that "
                                     "describes this instead.")

        # `assign()` refuses to hand a CLOSED exception to somebody ("a queue that never empties"),
        # so the edit form must not be the way round it — gating the action is not gating the column
        # (L40 §3). Defense in depth: the detail page hides the button too. `self.instance` still
        # holds the stored values here, because _post_clean() runs after clean().
        if self.instance.pk and not self.instance.is_open and "assigned_to" in cleaned:
            chosen = cleaned["assigned_to"]
            if getattr(chosen, "pk", None) != self.instance.assigned_to_id:
                self.add_error("assigned_to",
                               "This exception is closed — there is nothing left to hand over.")
        return cleaned


# ==================================================================== the triage payloads
# Plain ``forms.Form``s, like every other action payload in this app: each collects the argument for
# ONE workflow method on the model, and that method — not the form — is what writes the columns and
# returns the audit diff. Nothing here can move a state column by itself.

class AlertAssignForm(forms.Form):
    """The assign payload — put a name on an exception, or take one off it.

    ``required=False`` is the un-assign path, and ``assign(None)`` is explicitly supported by the
    model. Without it the only way to release an alert would be to hand it to somebody else.
    """

    assigned_to = forms.ModelChoiceField(
        queryset=None, required=False, label="Assign to",
        help_text="Leave blank to un-assign",
        widget=forms.Select(attrs={"class": "form-select"}))

    def __init__(self, *args, tenant=None, current=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        # `current` is the alert's present holder (an object or a pk) — passed so a disabled login
        # that still holds the alert renders as the selected option instead of vanishing from it.
        self.fields["assigned_to"].queryset = _assignable_users(
            tenant, keep=getattr(current, "pk", current))


class AlertSnoozeForm(forms.Form):
    """The snooze payload — suppress an exception for a bounded window.

    The bounds are READ FROM THE MODEL (``MIN_SNOOZE_DAYS`` / ``MAX_SNOOZE_DAYS``, public for exactly
    this reason) rather than re-typed, so the form and ``snooze()`` cannot drift into disagreeing
    about what a legal window is. ``snooze()`` re-validates anyway — this form is the message, that
    is the guard.
    """

    snooze_days = forms.IntegerField(
        min_value=SupplyChainAlert.MIN_SNOOZE_DAYS,
        max_value=SupplyChainAlert.MAX_SNOOZE_DAYS,
        initial=7, label="Snooze for (days)",
        help_text=f"{SupplyChainAlert.MIN_SNOOZE_DAYS}–{SupplyChainAlert.MAX_SNOOZE_DAYS} days. "
                  "Suppression, not closure — the queue hands it back when the window runs out",
        widget=forms.NumberInput(attrs={"class": "form-input",
                                        "min": SupplyChainAlert.MIN_SNOOZE_DAYS,
                                        "max": SupplyChainAlert.MAX_SNOOZE_DAYS}))


class AlertResolveForm(forms.Form):
    """The resolve payload — a note is REQUIRED.

    An exception closed with no account of what was done is a queue that cannot be audited and a
    number nobody can explain later. ``resolution_note`` is off the main form precisely so this is
    its only writer, alongside the resolver and the timestamp ``resolve()`` stamps in the same save.
    ``CharField`` strips by default, so whitespace alone does not satisfy it.
    """

    resolution_note = forms.CharField(
        max_length=2000, label="What was done?",
        help_text="Recorded against the alert with your name and the time",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea",
                                     "placeholder": "What was done about it?"}))
