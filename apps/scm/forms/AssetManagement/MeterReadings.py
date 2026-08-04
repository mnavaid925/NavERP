"""SCM 4.13 Asset Management — the ``MeterReading`` create form. There is no edit form, by design.

``MeterReading`` is append-only, the ``scm.StockMove`` posture: list, create and detail, with **no
edit route and no delete route**. A wrong reading is corrected by posting a later, correct one — the
same way a wrong stock movement is corrected by a compensating move. ``Asset.latest_reading()`` reads
the newest row, so the correction takes effect the moment it is posted and the mistaken row stays
visible in the history, which is the point of an append-only log rather than a defect in it. So this
module ships **one** form, and its absence of a sibling is a decision: an editable meter reading is a
number a scheduler already acted on, changed after the fact, with no trace that it ever said anything
else.

**``recorded_by`` is not a field.** "Who took this reading" is an audit fact stamped by the view from
the request user's ``core.Party``, not an input (L22 — the ``ComplianceCheck.performed_by`` posture).

**And the view must stamp it AFTER ``is_valid()``.** ``MeterReading.clean()`` tenant-checks both
``asset`` and ``recorded_by``, and a model error keyed on a column the FORM does not have raises
``ValueError`` out of ``Form.add_error`` — a 500 instead of a field error. Stamping the party onto
``form.instance`` before validation would put that shape one bad row away; stamping it on the object
returned by ``form.save(commit=False)`` cannot, because the guard's ``recorded_by_id is None`` leg
skips it during validation. (The tenant stamp below is the opposite case and IS wanted pre-validation
— ``tenant`` gates the whole guard, and every field it can key an error on is on this form.)

**``source`` keeps all three choices, including ``work_order`` and ``sensor``.** The list is not
narrowed to ``manual`` even though a human is typing this screen, because the
``maintenanceworkorder_record_reading`` verb files its capture through this same form with
``source="work_order"``; narrowing the ``ChoiceField`` would make that verb's own value invalid. The
value is provenance, not authorisation — nothing reads it to decide what somebody may do.

**``read_at`` may be back-dated freely and never post-dated.** ``MeterReading.clean()`` refuses a
future timestamp: a reading dated ahead would sort to the top of the log and become "the current
value" for a machine that has not reached it yet, silently advancing every meter-based due date and
firing condition triggers off a number nobody observed.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms.AssetManagement.Assets import _reject_foreign, _scope_to_tenant

from apps.scm.models import Asset, MeterReading


class MeterReadingForm(TenantModelForm):
    """One observed meter value on one asset at one moment. Create only — see the module docstring."""

    class Meta:
        model = MeterReading
        # A WHITELIST, never `Meta.exclude`. Deliberately ABSENT: `recorded_by` (stamped by the view
        # from the request user's party — see the module docstring), `tenant` (stamped by
        # `crud_create`, and in __init__ below so clean() can read it), `created_at` / `updated_at`.
        # `MeterReading` is `TenantOwned` and carries no `number` — a reading is a data point in a
        # series, not a document anybody quotes.
        #
        # `source` and `reference` are ABSENT too, and that is a security decision rather than a
        # tidiness one: together they are the reading's PROVENANCE. The work-order complete and
        # record-reading verbs file a reading as `source="work_order"` with `reference=<MWO number>`,
        # and the job's readings panel selects on exactly that reference. Leaving both on the human
        # form let any logged-in member post a reading claiming to have been filed by a verb, onto
        # somebody else's job — on an append-only log with no edit route to correct it. Both are now
        # stamped by whichever code path actually files the reading, after `save(commit=False)`,
        # exactly as `recorded_by` already was and for the same reason. A manual capture keeps the
        # model default `manual` and a blank reference, which is the truth about where it came from.
        fields = ["asset", "meter_name", "unit", "reading", "read_at", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP. `crud_create` assigns the tenant only AFTER `is_valid()`, so without this an
        # unsaved reading reaches `MeterReading.clean()` with `tenant_id` None — the exact case its
        # cross-tenant guard skips — and the guard would be dead code on the create path, which is
        # the only path this model has.
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # `Asset.__str__` is "code · name" off its own columns, so no select_related is owed.
        # Deliberately NOT narrowed to assets that declare a meter: an asset legitimately carries
        # SEVERAL meters (hours AND temperature AND pressure) while `Asset.meter_name` marks only the
        # primary one, and a secondary reading on an asset with no primary named is still a fact
        # worth logging. Nor narrowed to `is_active`: a machine being read is a machine.
        _scope_to_tenant(self, "asset", Asset.objects.all())

    def clean(self):
        """Re-check the chosen asset against this workspace — see :func:`_reject_foreign`.

        Without it a reading could be hung off another workspace's machine and would then feed that
        workspace's meter-based due dates and condition triggers. ``MeterReading.clean()`` carries
        the same guard at the database boundary; the future-date rule stays there, once.
        """
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ("asset",))
        return cleaned
