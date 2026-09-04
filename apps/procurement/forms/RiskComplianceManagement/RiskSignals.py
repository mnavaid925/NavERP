"""Procurement 6.17 Risk & Compliance Management — supplier risk signal form.

One shape: ``SupplierRiskSignalForm``, which captures or amends one observation.

**The exclusions are the contract.** An operator supplies exactly what a provider's report
actually says — who published it, which metric, on what date, the number, where it came from —
and *nothing* about what it means. Every interpretation column is ``editable=False`` on the model
and absent here: ``scale_min`` / ``scale_max`` / ``higher_is_better`` / ``risk_position`` /
``band`` / ``previous_value`` / ``trend`` are stamped by ``SupplierRiskSignal.derive()``, and
``review_status`` / ``review_note`` / ``reviewed_by`` / ``reviewed_at`` belong to the three review
verbs. ``tenant``, ``number``, ``captured_by`` and ``alert`` are the system's.

A form field for "what band is this?" would defeat the entire model: two people entering the same
D&B report would produce two different bands, and the inverted scales would stop being enforced
anywhere.

**There is deliberately no review form.** The three verbs read ``action`` and ``review_note``
straight off the POST and re-check their guards on the model, exactly as the 6.17 screening
decision verbs do — see ``views/RiskComplianceManagement/RiskSignals.py``.
"""
from decimal import Decimal

from django.utils import timezone

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.RiskComplianceManagement.RiskSignals import (
    SupplierRiskSignal, _finite)

#: How far outside a metric's registered scale a value may still be accepted, as a fraction of
#: the scale's own span.
#:
#: The check exists because a mis-keyed number is the single most likely way a wrong band gets
#: into the register, and the inverted scales make it invisible: a D&B SER typed as 70 instead of
#: 7 clamps silently to 9 and reports the supplier as maximally dangerous with no complaint at
#: all. Expressed as a fraction of the SPAN rather than as a flat number because the scales are
#: not comparable — 20% of SER's 8-point span is 1.6, while 20% of FHR's 99-point span is 19.8.
#:
#: The tolerance is not zero on purpose: providers do rescale and backfill, and a value a point
#: or two outside a published range is a real observation that clamps correctly. Twenty times the
#: range is a typo.
SCALE_TOLERANCE = Decimal("0.20")


class SupplierRiskSignalForm(TenantUniqueMixin, TenantModelForm):
    """Capture or amend one observation of a supplier's financial health.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``SupplierRiskSignal.clean()`` compares each chosen FK's tenant against
    ``self.tenant_id``, and without the stamp every CREATE would be falsely rejected as
    cross-tenant.
    """

    class Meta:
        model = SupplierRiskSignal
        fields = ["party", "provider", "metric", "observed_on", "value", "next_refresh_on",
                  "source_ref", "evidence", "notes"]
        widgets = {
            # The two DateFields need no widget here: TenantModelForm replaces every DateField
            # widget with a type="date" input of its own, so declaring one would be discarded.
            "source_ref": forms.TextInput(attrs={"class": "form-input"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's rows and
            # must not be able to post one either.
            for name in ("party", "evidence"):
                self.fields[name].queryset = self.fields[name].queryset.none()
            return

        from apps.core.models import Document, Party

        # TenantModelForm has already scoped both of these to the tenant (each target model
        # carries a ``tenant`` column). The narrowing below is the EXTRA rule per axis — only
        # suppliers are monitored, and evidence is listed newest-first — not the tenant boundary.
        self.fields["party"].queryset = (
            Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))
        self.fields["evidence"].queryset = (
            Document.objects.filter(tenant=tenant).order_by("-uploaded_at", "-id"))
        self.fields["evidence"].empty_label = "- none attached -"

    def clean_observed_on(self):
        """Refuse an observation a provider could not yet have made.

        The model repeats this as the non-form backstop (a seeder or a shell write never reaches
        a form); saying it here gets the operator a clear message on the field itself rather than
        a generic one from ``_post_clean``.
        """
        observed_on = self.cleaned_data.get("observed_on")
        if observed_on and observed_on > timezone.localdate():
            raise ValidationError(
                "A provider cannot have measured this in the future. Enter the date on the "
                "report, not the date you are capturing it.")
        return observed_on

    def clean(self):
        cleaned = super().clean()
        # Re-check every tenant-scoped FK against the workspace: the narrowed <select> above is
        # presentation, and a crafted POST never goes near it.
        _reject_foreign(self, cleaned, ["party", "evidence"])
        self._check_value_against_scale(cleaned)
        return cleaned

    def _check_value_against_scale(self, cleaned):
        """Refuse a value that is nowhere near the metric's registered scale.

        The model CLAMPS out-of-range values when it derives the risk position, which is right
        for a genuine edge reading and wrong for a typo: an SER of 70 clamps to 9 and reports the
        supplier as maximally dangerous, silently and with total confidence. So the plausibility
        question is asked once, HERE, where it can still be a field error the operator can fix.

        ``metric="other"`` has no registered scale and is therefore never checked — there is
        nothing to check it against, and refusing an unscaled number would be inventing a rule.
        """
        metric = cleaned.get("metric")
        # L35: is_finite() BEFORE any ordering comparison. forms.DecimalField already rejects
        # NaN/Infinity, so this is the belt to that braces — but the comparison below is exactly
        # where a non-finite value raises InvalidOperation, so it is guarded where it happens.
        value = _finite(cleaned.get("value"))
        if metric is None or value is None:
            return

        scale_min, scale_max, _ = SupplierRiskSignal.METRIC_SCALES.get(
            metric, (None, None, True))
        if scale_min is None or scale_max is None or scale_max <= scale_min:
            return

        tolerance = (scale_max - scale_min) * SCALE_TOLERANCE
        if scale_min - tolerance <= value <= scale_max + tolerance:
            return

        label = dict(SupplierRiskSignal.METRIC_CHOICES).get(metric, metric)
        self.add_error("value", ValidationError(
            "%(value)s is well outside the range for %(label)s, which runs %(low)s to %(high)s. "
            "Check the number against the provider's report — a mis-keyed value would be "
            "clamped to the end of the scale and banded with total confidence.",
            params={"value": value, "label": label, "low": scale_min, "high": scale_max}))
