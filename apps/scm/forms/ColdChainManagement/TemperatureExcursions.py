"""SCM 4.15 Cold Chain Management — the ``TemperatureExcursion`` triage forms.

An excursion has **two halves written by two different owners**, and the whole design of this module
is keeping them apart (the ``SupplyChainAlert`` detector-vs-triage split, one domain over):

* **the measured half is DETECTOR-WRITTEN.** ``started_at`` / ``ended_at`` / ``duration_minutes`` /
  ``breach_direction`` / ``extreme_temperature`` / ``limit_min`` / ``limit_max`` / ``reading_count``
  / ``mkt`` / ``last_detected_at`` are computed by ``apps/scm/coldchain.py`` from the reading ledger.
  Every one is ``editable=False`` on the model, and **not one of them appears on any form in this
  file.** A measurement a user can retype is not a measurement.
* **the human half is the only writable block:** severity, the cause code, the corrective action,
  the notes, and the three links out to the NCR / work order / lot that somebody else acts on.
  **``assessment`` is NOT in it** — the product release decision belongs to the gated ``assess``
  verb, which is the only writer of that column (see ``Meta.fields`` below).

**``status`` is absent from every form here**, in deliberate contrast to ``ColdChainMonitor.status``
which IS on its form. Excursion status is workflow state moved only by the four verbs on the model,
each of which validates the transition it is making; monitor status is user-owned lifecycle with
exactly one writer. **Do not "fix" either one to match the other** — the models say so too.

**Three forms, and the third is why a create page can exist at all.**
``TemperatureExcursionWindowForm`` collects a monitor and two moments; the view then asks
``coldchain.window_stats()`` for every measured figure and writes those. That is how CRUD
Completeness ("every model with a list page gets a create view") and the ``editable=False`` contract
are BOTH honoured. **Nobody types a number. Do not "simplify" it into typed numbers.**

**``_ModelErrorSafe`` is mixed into the ModelForm.** ``TemperatureExcursion.clean()`` legitimately
keys errors on ``monitor``, ``started_at``, ``ended_at`` and ``limit_max`` — none of which this
triage whitelist carries — and ``Form.add_error`` raises ``ValueError`` (a 500) on a key that is not
a form field. Each of those legs is structurally unreachable from this form today; the mixin is what
stops "unreachable" from turning into a crash on an audit record two sub-modules from now. See the
mixin's own docstring in ``ColdChainMonitors.py``.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _reject_foreign
from apps.scm.forms.ColdChainManagement.ColdChainMonitors import _ModelErrorSafe, _scope_to_tenant

from apps.scm.models import (
    ASSESSMENT_CHOICES,
    ColdChainMonitor,
    EXCURSION_CAUSE_CHOICES,
    EXCURSION_SEVERITY_CHOICES,
    LotSerial,
    MAX_EXCURSION_MINUTES,
    MaintenanceWorkOrder,
    NonConformance,
    TemperatureExcursion,
)

from django.utils import timezone


#: The `datetime-local` triple, in one place. All three travel together or the control misbehaves:
#: the TYPE (so the browser renders a date AND a time — a plain `date` input silently truncates the
#: moment to midnight, which is the L22 failure), the FORMAT (a `datetime-local` cannot parse
#: Django's default `%Y-%m-%d %H:%M:%S` rendering and shows an EMPTY box for a stored value), and the
#: theme CLASS. `TenantModelForm.__init__` does this for every ModelForm in the app; a plain
#: `forms.Form` gets none of it, so the two below carry it themselves.
_MOMENT_WIDGET_ATTRS = {"type": "datetime-local", "class": "form-input"}
_MOMENT_FORMAT = "%Y-%m-%dT%H:%M"
_MOMENT_INPUT_FORMATS = ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S",
                         "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]


def _moment_field(label, *, required=True, help_text=""):
    """One ``datetime-local`` field carrying the whole triple above."""
    return forms.DateTimeField(
        label=label, required=required, help_text=help_text,
        input_formats=_MOMENT_INPUT_FORMATS,
        widget=forms.DateTimeInput(attrs=dict(_MOMENT_WIDGET_ATTRS), format=_MOMENT_FORMAT))


class TemperatureExcursionForm(_ModelErrorSafe, TenantModelForm):
    """The human triage block, and nothing else."""

    class Meta:
        model = TemperatureExcursion
        # A WHITELIST, never `Meta.exclude`. A whitelist fails CLOSED when a column is added later;
        # an exclude list fails open, and on THIS model the column it would silently admit is a
        # measured one — the single worst field in the sub-module to let a user post.
        #
        # Deliberately ABSENT, and why: `tenant` (stamped by `crud_create`, and in __init__ below);
        # `number` (auto-assigned in `TenantNumbered.save()`); `monitor` (an episode does not change
        # which monitor it happened on — re-pointing it would restate a compliance figure about a
        # different cold room); every DETECTOR-WRITTEN column (`started_at`, `ended_at`,
        # `duration_minutes`, `breach_direction`, `extreme_temperature`, `limit_min`, `limit_max`,
        # `reading_count`, `mkt`, `last_detected_at`); `status` (moved only by the four verbs); and
        # the four stamps `acknowledged_by` / `acknowledged_at` / `assessed_by` / `assessed_on`
        # (provenance, written by the verbs that record the decision).
        #
        # Every one of those is ALREADY `editable=False` on the model, so a crafted POST naming one
        # cannot reach `cleaned_data` — the whitelist is the second lock, not the only one.
        #
        # `assessment` is ABSENT too, and it is the one absence the whitelist itself has to enforce:
        # the column is `editable=True` (the `assess` verb writes it), so nothing but this list keeps
        # it off the form. The edit view is `@login_required` while `temperatureexcursion_assess` is
        # `@tenant_admin_required`, so while it was here ANY member could POST
        # `assessment=product_ok` and mark product released for sale — with no `assessed_by` /
        # `assessed_on` signature, on a form that does not move `status` either. The detail page, the
        # triage queue, the compliance report and the CSV would then all print a release verdict no
        # admin ever gave. `TemperatureExcursion.assess()` is documented as the ONLY writer of
        # `assessment` / `assessed_by` / `assessed_on`; leaving it off this list is what makes that
        # sentence true rather than aspirational. A verdict with no signature on it is not a verdict.
        fields = ["severity", "cause", "corrective_action", "notes",
                  "non_conformance", "maintenance_work_order", "lot_serial"]
        widgets = {
            "corrective_action": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # THE STAMP. `crud_create` assigns the tenant only AFTER `is_valid()`, so without it the
        # instance reaches `TemperatureExcursion.clean()` with `tenant_id` None — the exact case its
        # cross-tenant FK guard and its open-episode clash check both skip. This form is normally an
        # EDIT form (the row already has its tenant), but the create path exists too and a guard
        # that only runs on one of two paths is the one a crafted POST takes.
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # --- the three links out ------------------------------------------------------------------
        # All tenant-scoped models, so `TenantModelForm` already narrowed them; re-filtering from the
        # model makes the scoping true by CONSTRUCTION rather than true by the caller having passed a
        # tenant. Deliberately NOT narrowed by status on any of the three:
        #
        #   * an NCR that has been closed is still the right NCR to cite for last month's excursion;
        #   * a completed work order is still the repair this excursion led to — that is the whole
        #     point of recording it;
        #   * a CONSUMED or QUARANTINED lot is exactly the lot an affected-product verdict is about.
        #
        # Narrowing any of them would drop the stored choice out of the `<select>` on a later edit
        # and silently NULL the link when somebody saved an unrelated note (the `_keep_current`
        # failure mode, avoided here by not creating it).
        _scope_to_tenant(self, "non_conformance", NonConformance.objects.all())
        _scope_to_tenant(self, "maintenance_work_order", MaintenanceWorkOrder.objects.all())
        # `LotSerial.__str__` reads `self.item.sku`, so without this the dropdown is one query per
        # option — the N+1 that only shows up once a workspace has a few hundred lots.
        _scope_to_tenant(self, "lot_serial", LotSerial.objects.select_related("item"))

    def clean(self):
        """Re-check every chosen FK against this workspace — see :func:`_reject_foreign`.

        ``TemperatureExcursion.TENANT_SCOPED_FKS`` is passed whole, one tuple read by both
        boundaries, so a pointer added to the model later is covered here the moment it is named
        there. Its ``monitor`` entry is a no-op on this form (``monitor`` is not a field, so
        ``cleaned`` never holds one and the helper skips it) — the model's own guard is what covers
        that column, and ``_ModelErrorSafe`` is what makes its error renderable.

        Everything else — the episode ordering, the future-start refusal, the snapshotted-band
        ordering, the affected-product-needs-an-action rule and the belt-and-braces open-episode
        clash check — stays in ``TemperatureExcursion.clean()``, once.
        """
        cleaned = super().clean()
        _reject_foreign(self, cleaned, TemperatureExcursion.TENANT_SCOPED_FKS)
        return cleaned


class TemperatureExcursionAssessForm(forms.Form):
    """The PRODUCT-LEVEL release decision — the payload of the ``_assess`` verb.

    A plain ``forms.Form`` rather than a second ModelForm, deliberately. ``_assess`` is the one
    excursion verb that is hand-rolled instead of going through ``_status_transition``, because it
    consumes typed input; it opens its own ``transaction.atomic()`` + ``select_for_update()`` and
    then calls :meth:`TemperatureExcursion.assess`, which is the **only** writer of ``assessment`` /
    ``assessed_by`` / ``assessed_on`` and re-validates every value it is handed. Binding this to the
    instance would give the verb a second way to write those columns, and the model method's own
    refusals (a wrong value is loud, a wrong state is a silent no-op) would then be reachable from
    only one of the two.

    ``assessed_by`` is NOT a field: it is the acting user's ``core.Party``, resolved by the view
    through ``_acting_party(request)`` (L22). A signature somebody can choose whose name to put on it
    is not a signature.

    **This form makes no compliance claim.** Recording who assessed what and when is an audit TRAIL;
    it is not 21 CFR Part 11 / EU Annex 11 conformance — there is no re-authentication at signing, no
    stated meaning of signature and no tamper-evident record. No label on this page may say otherwise.
    """

    assessment = forms.ChoiceField(
        choices=ASSESSMENT_CHOICES, label="Product assessment",
        help_text="Was the product affected? The DISPOSITION that follows is 4.9's — link the "
                  "non-conformance that acts on it",
        widget=forms.Select(attrs={"class": "form-select"}))
    cause = forms.ChoiceField(
        choices=[("", "---------")] + list(EXCURSION_CAUSE_CHOICES), required=False,
        help_text="A closed vocabulary, so 'what costs us the most spoilage' is a GROUP BY",
        widget=forms.Select(attrs={"class": "form-select"}))
    corrective_action = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 4, "class": "form-textarea"}),
        help_text="Required for an affected-product verdict unless a non-conformance is linked")

    def clean_corrective_action(self):
        return (self.cleaned_data.get("corrective_action") or "").strip()


class TemperatureExcursionWindowForm(forms.Form):
    """The MANUAL, BACK-DATED create — a monitor and a window, and **not one measured number**.

    Somebody legitimately needs to file an episode the detector cannot see: a logger whose file was
    lost, an event witnessed on a mechanical chart, an incident carried over from another system. So
    this form takes the two things a human genuinely knows — **which monitor, and between when and
    when** — plus the triage fields, and the view asks ``coldchain.window_stats()`` for
    ``duration_minutes`` / ``breach_direction`` / ``extreme_temperature`` / ``limit_min`` /
    ``limit_max`` / ``reading_count`` / ``mkt`` / ``severity`` computed from the readings actually in
    that window.

    That is the ONLY way both house rules survive at once: CRUD Completeness wants a create view for
    every model with a list page, and every measured column on this model is ``editable=False``
    because a measurement a user can retype is not a measurement. **Write that down before
    "simplifying" this into typed numbers.**

    ``assessment`` is deliberately NOT here even though it is a triage field: recording a product
    verdict stamps ``assessed_by`` / ``assessed_on``, and stamping a signature as a side effect of
    creating a row is exactly what the ``assess`` verb exists to prevent. The three links out
    (NCR / work order / lot) are likewise added on the edit form, once the row exists to link from.
    """

    monitor = forms.ModelChoiceField(
        queryset=ColdChainMonitor.objects.none(),
        help_text="The monitoring point this happened on — its limits are snapshotted onto the row",
        widget=forms.Select(attrs={"class": "form-select"}))
    started_at = _moment_field("Started at", help_text="First moment outside the limits")
    ended_at = _moment_field(
        "Ended at", required=False,
        help_text="Leave blank if it is STILL breaching — the detector will close it")
    severity = forms.ChoiceField(
        choices=EXCURSION_SEVERITY_CHOICES, initial="major",
        help_text="Suggested from the readings in the window; override it if you know better",
        widget=forms.Select(attrs={"class": "form-select"}))
    cause = forms.ChoiceField(
        choices=[("", "---------")] + list(EXCURSION_CAUSE_CHOICES), required=False,
        widget=forms.Select(attrs={"class": "form-select"}))
    corrective_action = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}))
    notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}))

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        # Scoped from the MODEL, so a tenant-less caller is offered nothing rather than everything.
        # Not narrowed to `status="active"`: a retired deployment can legitimately receive a
        # back-dated episode from the period it WAS active, and offering only live monitors would
        # make exactly the historical record this form exists for impossible to file.
        self.fields["monitor"].queryset = (
            ColdChainMonitor.objects.filter(tenant=tenant) if tenant is not None
            else ColdChainMonitor.objects.none())

    def clean_monitor(self):
        """Re-check the chosen monitor against this workspace.

        The narrowed ``<select>`` above is UX; **it has never held against a crafted POST** (L39 §2).
        Without this an episode could be filed against another workspace's cold room and would then
        appear on that workspace's compliance report.
        """
        monitor = self.cleaned_data.get("monitor")
        tenant_id = self.tenant.pk if self.tenant is not None else None
        if monitor is not None and monitor.tenant_id != tenant_id:
            raise ValidationError("That record belongs to another workspace.")
        return monitor

    def clean(self):
        """The window rules, stated where the user can see which box is wrong.

        ``TemperatureExcursion.clean()`` carries the same rules at the database boundary and is the
        one that also holds against a management command; these repeat them at the FORM boundary
        because that is the only boundary that can key an error onto ``started_at`` rather than onto
        the whole page.
        """
        cleaned = super().clean()
        monitor = cleaned.get("monitor")
        started_at = cleaned.get("started_at")
        ended_at = cleaned.get("ended_at")

        if started_at and started_at > timezone.now():
            self.add_error("started_at", "An excursion cannot start in the future.")
        if started_at and ended_at:
            if ended_at < started_at:
                self.add_error("ended_at", "An excursion cannot end before it started.")
            elif (ended_at - started_at).total_seconds() // 60 > MAX_EXCURSION_MINUTES:
                # Not merely implausible: this figure is fed to `timedelta(minutes=…)` on the report
                # pages, where an out-of-range value is an uncaught OverflowError — a 500, not a
                # message (the 4.10 DoS finding).
                self.add_error("ended_at", "That window is longer than a year — check the dates.")

        # BELT AND BRACES, and it is NOT the concurrency guard. A form runs outside the detector's
        # transaction and outside its monitor row lock, so two simultaneous posts can both pass this
        # and both insert; the real guard is `coldchain.detect_excursions()`. This exists so a
        # hand-created row cannot land on top of a live episode on the ordinary single-user path,
        # and because a message here is far kinder than the model's error surfacing on a page that
        # has no `monitor` field to attach it to.
        if monitor is not None and ended_at is None:
            clash = (TemperatureExcursion.objects
                     .filter(tenant_id=monitor.tenant_id, monitor=monitor, ended_at__isnull=True)
                     .first())
            if clash is not None:
                self.add_error("ended_at", (
                    f"{clash.number or 'An excursion'} on this monitor is still running — an "
                    f"episode is extended, never duplicated. Give this one an end time, or close "
                    f"the running one first."))
        return cleaned
