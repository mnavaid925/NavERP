"""Procurement 6.16 Supplier Performance & Evaluation — SupplierKpiScore edit form.

ONE shape, and it is deliberately tiny: ``SupplierKpiScoreEditForm`` offers **two fields**,
``measured_value`` and ``comment``. Everything else on the line is either the line's identity,
a frozen-at-generation column, or derived.

**There is NO create form and NO ``supplierkpiscore_create`` route.** Score lines are written by
``apps.procurement.performance.generate_scorecard_lines``; a hand-created line would be a
measurement with no computation behind it (the ``SpendReportSnapshot`` / ``CostForecast``
precedent). The one hand-editable case is a KPI whose ``source`` was ``manual`` at generation —
a figure only a human has — and even there the VIEW is the gate, not this form: a disabled widget
is UX, not an authorization boundary.

**``save()`` re-derives through the KPI.** A hand-typed value is banded and scored by exactly the
same ``SupplierKpi.score_and_band()`` a derived one goes through, so a number can never mean one
thing on a scorecard and another on a board. Typing ``score`` or ``band`` directly would break
that one-scale rule, which is why neither is a field here.

**Exclusions, one reason each:**

* ``tenant`` — system-stamped; the row is written by generate.
* ``scorecard`` / ``kpi`` — the line's identity. Changing either would be creating a different
  line, which ``unique_together (tenant, scorecard, kpi)`` exists to prevent.
* ``weight_applied`` — frozen at generation; a re-weight must not rewrite a closed period.
* ``target_at_time`` / ``direction_at_time`` / ``source_at_time`` / ``unit_at_time`` /
  ``kpi_name`` / ``kpi_category`` — ``editable=False`` frozen-at-time columns. History, not input.
* ``score`` / ``band`` — DERIVED in ``save()`` from ``kpi.score_and_band()``.
* ``breakdown`` — ``editable=False``; rewritten by ``save()`` to say "manual entry".
* ``respondent_count`` — ``editable=False``; only the survey aggregation sets it.
* ``computed_at`` / ``computed_by`` — ``editable=False`` freshness/authorship stamps (L22).

**Import discipline.** ``SupplierKpiScore`` is imported from its ENTITY module, never from
``apps.procurement.models``: this sub-package is not wired into the package ``__init__``
re-export block until the Integrate phase, and a package-level import here would be a
star-import cycle at URLconf import time (the ``CostForecasts`` form module's precedent).
``timezone`` is NOT part of the ``forms/_common`` star import, so it is named explicitly.
"""
from django.utils import timezone

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign  # noqa: F401
# NOT-YET-WIRED entity: import the entity MODULE directly — see the module docstring.
from apps.procurement.models.SupplierPerformanceEvaluation.ScorecardKpiScores import (
    SupplierKpiScore)


class SupplierKpiScoreEditForm(TenantUniqueMixin, TenantModelForm):
    """Hand-correct a manual-entry score line: the figure, and why.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs — the model's ``clean()`` compares both FKs' tenants against ``self.tenant_id``, and
    without the stamp a legitimate save would be rejected as cross-tenant. (This form only ever
    edits an existing row, so the instance already carries a tenant; the mixin stays for the
    same reason the other three forms carry it — the ordering rule must not have exceptions a
    later field addition would trip over.)
    """

    class Meta:
        model = SupplierKpiScore
        fields = ["measured_value", "comment"]          # TWO FIELDS. Nothing else, ever.
        widgets = {"comment": forms.Textarea(attrs={"class": "form-textarea", "rows": 3})}

    def __init__(self, *args, tenant=None, **kwargs):
        # No queryset narrowing: there is no ModelChoiceField on this form. The signature keeps
        # the ``tenant=`` keyword ``crud_edit`` always passes.
        super().__init__(*args, tenant=tenant, **kwargs)

    def save(self, commit=True):
        """Re-band and re-score through the KPI, then re-stamp freshness.

        A hand-typed value goes through the SAME ``score_and_band()`` a derived one does, so the
        two can never disagree about what "critical" means. ``breakdown`` is rewritten to say
        plainly that this figure was typed rather than computed — the detail page prints it, and
        a reader must never mistake a hand entry for a resolver's output.
        """
        obj = super().save(commit=False)
        score, band = obj.kpi.score_and_band(obj.measured_value)
        obj.score, obj.band = score, band
        obj.computed_at = timezone.now()
        obj.breakdown = {
            "source": "manual entry",
            "measured_value": (str(obj.measured_value)
                               if obj.measured_value is not None else None),
            "scoring_method": obj.kpi.scoring_method,
            "direction": obj.kpi.direction,
            "entered_at": obj.computed_at.isoformat(),
        }
        if commit:
            obj.save()
        return obj
