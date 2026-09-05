"""Procurement 6.16 Supplier Performance & Evaluation — SupplierImprovementPlan form.

One shape: ``SupplierImprovementPlanForm``, used by both create and edit. It asks what went
wrong, what was agreed about it, by when, and who owns it on each side. Everything the WORKFLOW
owns is absent, and each absence has one reason:

* ``tenant`` — stamped by ``TenantUniqueMixin`` / ``crud_create``.
* ``number`` — assigned once by ``TenantNumbered.save()`` (SIP-#####).
* ``status`` — workflow-controlled by the activate / monitor / close / cancel verbs. A typed
  status would let a plan claim to have been closed with nothing behind the claim.
* ``outcome`` — written by the close verb from its POST body, alongside ``closure_note``, and
  refused there when it is missing or not one of the four. An outcome on this form would be a
  result nobody signed off.
* ``actual_close_date`` — ``editable=False``; stamped by close, so "when did it close?" always
  means the moment somebody closed it.
* ``acknowledged_by`` / ``acknowledged_at`` — ``editable=False`` acknowledgement stamps, written
  by the acknowledge verb alone (L22).
* ``verified_by`` / ``verified_at`` — ``editable=False`` verification stamps, written by close.
* ``closure_note`` — ``editable=False``; taken from the close POST body, next to the outcome it
  explains.
* ``created_at`` / ``updated_at`` — base timestamps.

``extended_close_date`` IS on the form, and deliberately: granting an extension is an ordinary
editorial act with a date behind it, not a lifecycle transition. The model's rule — an extension
must fall STRICTLY AFTER the original target — is what keeps it from being a way to quietly
re-write what was agreed, and this module does not restate it.

The validation that matters is the model's. ``SupplierImprovementPlan.clean()`` enforces the date
ordering, the extension rule, the outcome/closed conjunction, the escalation's tenant AND supplier
match, and the same-tenant guards, and raises them together so this form shows every problem at
once. Nothing here duplicates any of it — a rule stated twice is a rule that will disagree with
itself.

**Two ``TenantModelForm`` behaviours this module must NOT duplicate** (``apps/core/forms/_common.py``):

1. ``TenantModelForm.__init__`` already tenant-scopes every ``ModelChoiceField`` whose target
   model has a ``tenant`` field, and ``accounts.User.tenant`` is exactly such a field — so
   ``owner`` is auto-scoped. It is narrowed here only to live accounts, with ``_reject_foreign``
   left as the crafted-POST re-check (the ``ProcurementAlert.assigned_to`` precedent).
2. Every ``DateField`` widget is unconditionally replaced with a styled ``type="date"``
   ``DateInput``. The four date entries in ``Meta.widgets`` below are therefore NO-OPS, kept only
   so a reader recognises them as such rather than adding them again. ``rows=`` on a Textarea IS
   meaningful and stays.

**Import discipline.** ``SupplierImprovementPlan`` and ``SupplierKpi`` come from their ENTITY
modules, never from ``apps.procurement.models``: this sub-package is not wired into the package
``__init__`` re-export block until the Integrate phase, and a package-level import here would be
a star-import cycle at URLconf import time (the ``CostForecasts`` form module's precedent). The
querysets that reach outside this sub-module — ``core.Party``, ``scm.SupplierScorecard`` and 6.4's
``VendorSuspension`` — are imported inside ``__init__`` for the same reason.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign  # noqa: F401
# NOT-YET-WIRED entities: import the entity MODULES directly — see the module docstring.
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierImprovementPlans import (
    SupplierImprovementPlan)
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import SupplierKpi


def _supplier_parties(tenant):
    """The supplier/vendor cohort, deduplicated.

    ``.distinct()`` is load-bearing: ``roles__role__in`` joins PartyRole, so a party carrying
    both the ``supplier`` and the ``vendor`` role would otherwise appear twice in the dropdown.
    """
    from apps.core.models import Party
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


class SupplierImprovementPlanForm(TenantUniqueMixin, TenantModelForm):
    """Open or correct one improvement plan.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs. The model's ``clean()`` compares four FKs' tenants against ``self.tenant_id``; without
    the stamp every CREATE would be falsely rejected as cross-tenant, because the CRUD helpers
    only assign the real tenant AFTER ``is_valid()``.
    """

    class Meta:
        model = SupplierImprovementPlan
        fields = ["title", "supplier", "scorecard", "kpi", "severity", "finding", "root_cause",
                  "corrective_actions", "support_provided", "success_criteria", "start_date",
                  "target_close_date", "next_review_date", "extended_close_date", "owner",
                  "supplier_owner_name", "supplier_owner_email", "escalated_suspension",
                  "evidence", "evidence_url"]
        widgets = {
            "finding": forms.Textarea(attrs={"class": "form-textarea", "rows": 4}),
            "root_cause": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "corrective_actions": forms.Textarea(attrs={"class": "form-textarea", "rows": 4}),
            "support_provided": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "success_criteria": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            # The four date entries are NO-OPS — TenantModelForm replaces every DateField widget
            # with its own styled type="date" DateInput. Listed so a reader recognises them
            # rather than adding them a second time.
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "target_close_date": forms.DateInput(attrs={"type": "date"}),
            "next_review_date": forms.DateInput(attrs={"type": "date"}),
            "extended_close_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) is offered nothing at all rather than another
            # workspace's rows — and crud_create refuses the write before this form is saved.
            for name in ("supplier", "scorecard", "kpi", "owner", "escalated_suspension"):
                field = self.fields[name]
                field.queryset = field.queryset.none()
            return

        # Querysets reaching outside this sub-module, imported locally — see the docstring.
        from apps.procurement.models.VendorManagement.VendorSuspensions import VendorSuspension
        from apps.scm.models import SupplierScorecard

        self.fields["supplier"].queryset = _supplier_parties(tenant)

        scorecard = self.fields["scorecard"]
        scorecard.queryset = (SupplierScorecard.objects.filter(tenant=tenant)
                              .select_related("party").order_by("-period_end", "-id"))
        scorecard.empty_label = "- no triggering period -"

        kpi = self.fields["kpi"]
        kpi.queryset = (SupplierKpi.objects.filter(tenant=tenant, is_active=True)
                        .order_by("display_order", "code"))
        kpi.empty_label = "- not one KPI -"

        # ``owner`` targets accounts.User, whose nullable ``tenant`` makes it AUTO-SCOPED by
        # TenantModelForm — narrow only to live accounts here. Re-filtering by tenant would
        # duplicate the base class's own rule (the ProcurementAlert.assigned_to idiom).
        owner = self.fields["owner"]
        owner.queryset = owner.queryset.filter(is_active=True).order_by("email")
        owner.empty_label = "- unassigned -"

        # 6.4's block register — the ONE blocking mechanism this module escalates INTO. The
        # model additionally insists the chosen suspension is against this plan's own supplier.
        suspension = self.fields["escalated_suspension"]
        suspension.queryset = (VendorSuspension.objects.filter(tenant=tenant)
                               .select_related("supplier").order_by("-id"))
        suspension.empty_label = "- not escalated -"

    def clean_evidence(self):
        """Extension allowlist then size cap, the house rule for every upload.

        The two constants are imported LOCALLY and are deliberately NOT re-exported from
        ``apps/procurement/forms/__init__.py``: ``forms/CatalogManagement/UploadBatches.py``
        already defines its own, different ``MAX_UPLOAD_BYTES`` (2 MB), and a package-level
        re-export would make which limit applies depend on import order.
        """
        import os

        from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES

        upload = self.cleaned_data.get("evidence")
        if upload and hasattr(upload, "name"):
            ext = os.path.splitext(upload.name)[1].lower()
            if ext not in ALLOWED_DOC_EXTENSIONS:
                raise forms.ValidationError(f"File type '{ext}' is not allowed.")
            if getattr(upload, "size", 0) and upload.size > MAX_UPLOAD_BYTES:
                raise forms.ValidationError(
                    f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
        return upload

    def clean(self):
        cleaned = super().clean()
        # A narrowed <select> is UX, not an authorization boundary: a crafted POST naming another
        # workspace's row becomes a field error here instead of a cross-tenant reference.
        _reject_foreign(self, cleaned,
                        ["supplier", "scorecard", "kpi", "owner", "escalated_suspension"])
        return cleaned
