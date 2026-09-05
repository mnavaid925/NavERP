"""Procurement 6.16 Supplier Performance & Evaluation — SupplierFeedback form.

One shape: ``SupplierFeedbackForm``, the request-a-response form. It asks who is being rated,
over what window, by whom, in what capacity, and how much their answer should count. Everything
the WORKFLOW owns is absent, and each absence has one reason:

* ``tenant`` — stamped by ``TenantUniqueMixin`` / the create view.
* ``number`` — assigned once by ``TenantNumbered.save()`` (SFB-#####).
* ``status`` — workflow-controlled by the submit / decline / expire verbs. A typed status would
  let a response claim to have been submitted with nothing behind the claim.
* ``requested_by`` — authorship stamp, taken from ``request.user`` by the create view.
* ``requested_at`` — ``editable=False`` raise stamp (L22).
* ``submitted_at`` — ``editable=False``; stamped by the submit verb alone, so "when did they
  answer?" always means the moment the answer arrived.
* ``created_at`` / ``updated_at`` — base timestamps.

``rating`` IS on the form, and deliberately: a paper survey collected offline is filed complete,
and the create page is where that happens. It stays optional, because the ordinary flow is
"request now, rate later through the submit verb" — the model's own rule (a *submitted* response
needs a rating) is what keeps that honest, and this module does not restate it.

The validation that matters is the model's. ``SupplierFeedback.clean()`` enforces the real
uniqueness rule, the survey-KPI rule, the period ordering, the submitted-needs-a-rating rule and
the self-assessment conjunction, and raises them together so this form shows every problem at
once. Nothing here duplicates any of it — a rule stated twice is a rule that will disagree with
itself.

**Two ``TenantModelForm`` behaviours this module must NOT duplicate** (``apps/core/forms/_common.py``):

1. ``TenantModelForm.__init__`` already tenant-scopes every ``ModelChoiceField`` whose target
   model has a ``tenant`` field, and ``accounts.User.tenant`` is exactly such a field — so
   ``respondent`` is auto-scoped. It is narrowed here only to live accounts, with
   ``_reject_foreign`` left as the crafted-POST re-check (the ``ProcurementAlert.assigned_to``
   precedent).
2. Every ``DateField`` widget is unconditionally replaced with a styled ``type="date"``
   ``DateInput``. The three date entries in ``Meta.widgets`` below are therefore NO-OPS, kept
   only so a reader recognises them as such rather than adding them again.

**Import discipline.** ``SupplierFeedback`` and ``SupplierKpi`` come from their ENTITY modules,
never from ``apps.procurement.models``: this sub-package is not wired into the package
``__init__`` re-export block until the Integrate phase, and a package-level import here would be
a star-import cycle at URLconf import time (the ``CostForecasts`` form module's precedent). The
cross-app querysets (``core.Party``, ``scm.SupplierScorecard``) are imported inside ``__init__``
for the same reason.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign  # noqa: F401
# NOT-YET-WIRED entities: import the entity MODULES directly — see the module docstring.
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierFeedback import (
    SupplierFeedback)
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import SupplierKpi


def _supplier_parties(tenant):
    """The supplier/vendor cohort, deduplicated.

    ``.distinct()`` is load-bearing: ``roles__role__in`` joins PartyRole, so a party carrying
    both the ``supplier`` and the ``vendor`` role would otherwise appear twice in the dropdown.
    """
    from apps.core.models import Party
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


class SupplierFeedbackForm(TenantUniqueMixin, TenantModelForm):
    """Request one 360 response — or file one collected offline.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs. The model's ``clean()`` compares three FKs' tenants against ``self.tenant_id`` and runs
    its duplicate probe scoped to it; without the stamp every CREATE would be falsely rejected as
    cross-tenant, because the CRUD helpers only assign the real tenant AFTER ``is_valid()``.
    """

    class Meta:
        model = SupplierFeedback
        fields = ["supplier", "scorecard", "kpi", "period_start", "period_end", "respondent_kind",
                  "respondent_function", "respondent", "respondent_name", "rating", "importance",
                  "due_date", "comment"]
        widgets = {
            # The three date entries are NO-OPS — TenantModelForm replaces every DateField
            # widget with its own styled type="date" DateInput. Listed so a reader recognises
            # them rather than adding them a second time. rows= on the Textarea IS meaningful.
            "period_start": forms.DateInput(attrs={"type": "date"}),
            "period_end": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "comment": forms.Textarea(attrs={"class": "form-textarea", "rows": 4}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) is offered nothing at all rather than another
            # workspace's rows — and the create view refuses the write before this form is saved.
            for name in ("supplier", "scorecard", "kpi", "respondent"):
                field = self.fields[name]
                field.queryset = field.queryset.none()
            return

        # Cross-app queryset, imported locally — see the module docstring.
        from apps.scm.models import SupplierScorecard

        self.fields["supplier"].queryset = _supplier_parties(tenant)

        scorecard = self.fields["scorecard"]
        scorecard.queryset = (SupplierScorecard.objects.filter(tenant=tenant)
                              .select_related("party").order_by("-period_end", "-id"))
        scorecard.empty_label = "- not tied to a period -"

        # ONLY survey KPIs are offered. The model refuses a derived one outright; narrowing the
        # dropdown to match means the rule is a guard rather than a trap somebody falls into.
        kpi = self.fields["kpi"]
        kpi.queryset = (SupplierKpi.objects.filter(tenant=tenant, is_active=True, source="survey")
                        .order_by("display_order", "code"))
        kpi.empty_label = "- general commentary -"

        # ``respondent`` targets accounts.User, whose nullable ``tenant`` makes it AUTO-SCOPED by
        # TenantModelForm — narrow only to live accounts here. Re-filtering by tenant would
        # duplicate the base class's own rule (the ProcurementAlert.assigned_to idiom).
        respondent = self.fields["respondent"]
        respondent.queryset = respondent.queryset.filter(is_active=True).order_by("email")
        respondent.empty_label = "- external / not a system user -"

    def clean(self):
        cleaned = super().clean()
        # A narrowed <select> is UX, not an authorization boundary: a crafted POST naming another
        # workspace's row becomes a field error here instead of a cross-tenant reference.
        _reject_foreign(self, cleaned, ["supplier", "scorecard", "kpi", "respondent"])
        return cleaned
