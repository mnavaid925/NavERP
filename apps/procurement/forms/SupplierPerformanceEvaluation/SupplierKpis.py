"""Procurement 6.16 Supplier Performance & Evaluation — SupplierKpi form.

One shape: ``SupplierKpiForm``, the whole KPI *definition*. Every column a human decides is a
field here; the three the system owns are not:

* ``tenant`` — stamped by ``TenantUniqueMixin`` / ``crud_create``.
* ``number`` — assigned once by ``TenantNumbered.save()`` (SKP-#####).
* ``created_at`` / ``updated_at`` — the base timestamps, system-owned (L22).

The validation that matters is the model's: ``SupplierKpi.clean()`` enforces band ordering
against ``direction``, the ``source``/``derived_metric`` conjunction and the
``applies_to``/``applies_to_tier`` conjunction, and raises them all together so the form shows
every problem at once. This module deliberately adds none of that a second time — a rule stated
twice is a rule that will disagree with itself.

**Import discipline.** ``SupplierKpi`` is imported from its ENTITY module, never from
``apps.procurement.models``: this sub-package is not wired into the package ``__init__``
re-export block until the Integrate phase, and a package-level import here would be a
star-import cycle at URLconf import time. Same reason, same comment, as the ``CostForecasts``
form module.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entity: import the entity MODULE directly — see the module docstring.
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import SupplierKpi


class SupplierKpiForm(TenantUniqueMixin, TenantModelForm):
    """Create or edit one KPI definition.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs. Two things depend on that stamp: the ``(tenant, code)`` uniqueness probe, and any
    tenant comparison inside the model's ``clean()``. Without it every CREATE would be rejected
    — the CRUD helpers only assign the real tenant AFTER ``is_valid()``.
    """

    class Meta:
        model = SupplierKpi
        fields = ["code", "name", "description", "category", "unit", "direction", "source",
                  "derived_metric", "weight", "target_value", "warning_threshold",
                  "critical_threshold", "scoring_method", "maps_to_dimension", "applies_to",
                  "applies_to_tier", "review_frequency", "industry_benchmark_value", "owner",
                  "display_order", "is_active", "notes"]
        widgets = {
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        field = self.fields["owner"]
        if tenant is None:
            # A tenant-less user (the superuser) offers no owners at all rather than the whole
            # directory — and crud_create refuses the write before this form is ever saved.
            field.queryset = field.queryset.none()
            return

        # ``owner`` targets accounts.User, whose nullable ``tenant`` makes it auto-scoped by
        # TenantModelForm — narrow only to live accounts here. Re-filtering by tenant would
        # duplicate the base class's own rule (the ProcurementAlert.assigned_to idiom).
        field.queryset = field.queryset.filter(is_active=True).order_by("email")
        field.empty_label = "- unassigned -"

    def clean(self):
        cleaned = super().clean()
        # ``owner`` is the only tenant-scoped choice on this form. A narrowed <select> is UX,
        # not an authorization boundary: a crafted POST naming another workspace's user becomes
        # a field error here instead of a cross-tenant row.
        _reject_foreign(self, cleaned, ["owner"])
        return cleaned
