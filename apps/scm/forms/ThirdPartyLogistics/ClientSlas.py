"""SCM 4.17 Third-Party Logistics (3PL) — the ``ClientSLA`` form.

**What a human types here is the PROMISE**: which client, which metric, what number was agreed, how
wide the at-risk band is, over what window, and what a breach is worth. **What a human never types is
the EVIDENCE.** All eight measured columns — ``last_measured_value``, ``last_measured_at``,
``measurement_window_start``, ``measurement_window_end``, ``measurement_summary``, ``sample_size``,
``breach_count`` and ``status`` — are ``editable=False`` on the model and are written only by
``ClientSLA.recompute()``. They are therefore already unreachable by a ``ModelForm``; they are NAMED
in the ``Meta.fields`` comment below anyway, so that nobody re-adds one while "fixing" a page. A
measured figure a user can retype is not a measurement, and a system ``*_at`` reached by a
``DateInput`` is silently truncated to midnight (L22).

**``is_active`` IS on this form and ``status`` is NOT** — the two look similar and are opposites.
``is_active`` is the human's switch (is this promise in force?), with exactly one writer, and it is the
``ColdChainMonitor.status`` posture. ``ClientSLA.status`` is a MEASUREMENT (meeting / at risk /
breached / no data) with exactly one writer that is the recompute pass, and it is the
``TemperatureExcursion.status`` / ``ClientBillingRun.status`` posture. Do not "fix" either one to look
like the other.

**``TenantUniqueMixin`` is mixed in, and it is load-bearing on this model rather than decorative.**
``ClientSLA`` carries ``unique_together ("tenant", "client", "metric", "scope_location")``, and every
member except ``tenant`` is a field on this form. Django skips a ``unique_together`` check outright if
ANY of its fields is excluded from validation — and a non-form field always is — so without the mixin
a duplicate (client, metric, location) would pass ``is_valid()`` and then raise an uncaught
``IntegrityError`` from ``.save()``: a 500 on an everyday user mistake. The mixin's other half (it
stamps ``instance.tenant`` before validation) is what makes the tenant-dependent legs of
``ClientSLA.clean()`` live on the CREATE path — ``crud_create`` assigns the tenant only AFTER
``is_valid()`` (``apps/core/crud.py:120-123``), and the create path is the one a crafted POST takes.

Stamping the tenant before validation is safe HERE because every field ``ClientSLA.clean()`` can key
an error on — ``client``, ``unit``, ``direction``, ``warning_threshold``, ``service_credit_cap_pct``,
``scope_location``, ``metric``, ``target_value`` — is on this form. A model error keyed on a column
the form does NOT carry raises ``ValueError`` out of ``Form.add_error`` (a 500 instead of a field
error), which is why 4.13's ``MeterReadingForm`` stamps its party after ``is_valid()`` instead.
Checked here, not assumed.

**The metric registry is rendered as STATIC help text, never as JavaScript.** ``ClientSLA.clean()``
refuses a unit or a direction that disagrees with ``SLA_METRIC_META``, so the user has to be told the
rule BEFORE they submit — but a JS widget that rewrote the two selects would be a second copy of the
registry living in the template, free to drift from the one the model validates against. The whole
table is printed once instead; it is nine rows.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _reject_foreign

from apps.scm.models import (
    ClientSLA,
    Location,
    LogisticsClient,
    SLA_DIRECTION_CHOICES,
    SLA_METRIC_META,
    SLA_UNIT_CHOICES,
)


def _metric_registry_help():
    """The closed metric registry as one line of help text per metric.

    Built from ``SLA_METRIC_META`` at import time rather than typed into the template, so the rule the
    form ADVERTISES and the rule ``ClientSLA.clean()`` ENFORCES are the same data. A hand-written copy
    in a template is the version that goes stale the first time a default target is renegotiated.
    """
    units = dict(SLA_UNIT_CHOICES)
    directions = dict(SLA_DIRECTION_CHOICES)
    rows = []
    for meta in SLA_METRIC_META.values():
        rows.append(f"{meta['label']}: {units.get(meta['unit'], meta['unit'])}, "
                    f"{directions.get(meta['direction'], meta['direction']).lower()}, "
                    f"typical target {meta['default_target']}")
    return " · ".join(rows)


#: Printed under BOTH the unit and the direction field. One string, because the two are validated
#: together and telling somebody only half the rule is how they submit twice.
METRIC_REGISTRY_HELP = (
    "Each metric fixes its own unit and direction, and a mismatch is refused — a percentage metric "
    "saved in hours would compare 98 against 24 and breach forever. " + _metric_registry_help()
)


class ClientSLAForm(TenantUniqueMixin, TenantModelForm):
    """One service promise: this client, this metric, this number, over this window."""

    class Meta:
        model = ClientSLA
        # A WHITELIST, never `Meta.exclude`. A whitelist fails CLOSED when a column is added later;
        # an exclude list fails open, and the column it would silently admit here is the next
        # recompute-written measurement somebody adds.
        #
        # This is the model's FULL editable set, in declaration order. Deliberately ABSENT, and why:
        #   * `tenant`        — stamped by `crud_create` (and by TenantUniqueMixin before validation)
        #   * `number`        — auto-assigned SLA-##### in `TenantNumbered.save()`; nobody types a
        #                       document number
        #   * `created_at` / `updated_at` — automatic
        # and the EIGHT evidence columns, every one of them `editable=False` and therefore already
        # unreachable by a ModelForm. Named so nobody re-adds them: `last_measured_value`,
        # `last_measured_at`, `measurement_window_start`, `measurement_window_end`,
        # `measurement_summary`, `sample_size`, `breach_count`, `status`.
        fields = ["client", "metric", "name", "target_value", "unit", "direction",
                  "warning_threshold", "measurement_window", "scope_location",
                  "service_credit_pct", "service_credit_cap_pct", "is_active", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # --- tenant-scoped dropdowns ---------------------------------------------------------------
        # `TenantModelForm` already scopes any FK whose target carries a `tenant` column, but only
        # `if tenant is not None`; a tenant-less caller falls through to the UNSCOPED default manager.
        # Re-filtering from the model makes the scoping true by CONSTRUCTION rather than true by the
        # caller behaving, and points a tenant-less caller at nothing at all.
        self._scope("client", LogisticsClient.objects.select_related("party").order_by("code", "id"))

        # Locations dedicated to ANOTHER client are excluded: measuring this client's promise against
        # somebody else's bin would score them on stock that is not theirs. `owner_client__isnull=True`
        # keeps every shared location available, which is the normal case.
        self._scope("scope_location",
                    Location.objects.filter(Q(owner_client__isnull=True)
                                            | Q(owner_client_id=self._client_id()))
                    .order_by("code", "id"))

        # --- union the current selection back in, on EDIT ------------------------------------------
        # A narrowed queryset that no longer contains the stored value drops it out of the <select>
        # and the next save silently NULLs the FK. On `scope_location` that would quietly re-point a
        # location-scoped promise at the whole workspace, restating every figure derived from it.
        self._keep_current("client")
        self._keep_current("scope_location")

        for name in ("unit", "direction"):
            if name in self.fields:
                self.fields[name].help_text = METRIC_REGISTRY_HELP

    # ---------------------------------------------------------------------------------------------
    # Private helpers. They stay in this entity module (Backend Package Structure rule 5): the three
    # sibling 4.17 form modules are written independently, and a shared helper that two agents each
    # believe they own is how one of them ends up deleted. Promote to `forms/_common.py` the day a
    # SECOND sub-module wants them.
    # ---------------------------------------------------------------------------------------------
    def _client_id(self):
        """The client this SLA is (or is being) attached to — for narrowing ``scope_location``.

        Read from the BOUND data first, then from the instance, so a create-page POST that names a
        client narrows the location list the same way an edit does. ``None`` on a blank create form,
        which makes the ``owner_client_id=None`` leg match only unowned locations — the correct
        conservative default when we do not yet know whose promise this is.
        """
        if self.is_bound:
            chosen = (self.data.get("client") or "").strip()
            if chosen.isdecimal():
                return int(chosen)
        return self.instance.client_id

    def _scope(self, name, queryset):
        """Point one dropdown at this workspace's rows — and at NOTHING when there is no workspace."""
        if name in self.fields:
            self.fields[name].queryset = (
                queryset.filter(tenant=self.tenant) if self.tenant is not None else queryset.none()
            )

    def _keep_current(self, name):
        """Union the instance's CURRENT value back into a narrowed queryset (edit path only).

        Scoped by the same tenant filter as :meth:`_scope`, so this widens the choices without ever
        widening the workspace: a stored value that somehow belongs to another tenant stays out, and
        ``ClientSLA.clean()`` refuses it at the model boundary regardless.
        """
        if name not in self.fields or self.instance.pk is None or self.tenant is None:
            return
        current_id = getattr(self.instance, f"{name}_id", None)
        if current_id is None:
            return
        field = self.fields[name]
        field.queryset = (field.queryset
                          | field.queryset.model.objects.filter(pk=current_id, tenant=self.tenant))

    def clean(self):
        """Re-check every chosen FK against this workspace — see :func:`_reject_foreign`.

        ``ClientSLA.TENANT_SCOPED_FKS`` is ``("client", "scope_location")`` — ONE tuple read by both
        boundaries, so a pointer added to the model later is covered here the moment it is named
        there. ``ClientSLA.clean()`` carries the same guard and it is the one that holds at the
        database boundary; this repeats it at the FORM boundary because **a narrowed ``<select>`` has
        never held against a crafted POST** (L39 §2), and because the form-boundary copy keys its
        error on a field this form can actually render.

        Everything else — the unit and direction rules, the at-risk band's side, the credit cap, the
        cross-client location check, the NULL-scope duplicate and the percentage range — stays in
        ``ClientSLA.clean()``, once, where it also holds against a management command and a shell.
        """
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ClientSLA.TENANT_SCOPED_FKS)
        return cleaned
