"""Procurement 6.19 Document & Knowledge Management — ProcurementPolicy form.

One shape: ``ProcurementPolicyForm``, the create-or-edit form for a policy in the library. It
carries the rule as written, its version, its scope and its advisory threshold; everything the
SYSTEM owns is excluded, each for its own reason:

* ``tenant`` — stamped by ``TenantUniqueMixin`` / ``crud_create``.
* ``number`` — allocated once by ``TenantNumbered.save()``.
* ``status`` — verb-driven. Publish and archive are POST-only actions with their own audit
  rows, and publish is additionally administrator-gated. A status ``<select>`` here would let a
  form save skip the workflow, the predecessor retirement and the audit trail in one move.
* ``published_at`` — stamped by the publish verb alone. Typed here it would claim a publication
  that never happened.
* ``created_by`` — an authorship stamp, not an input.
* ``created_at`` / ``updated_at`` — the ``TenantOwned`` base timestamps (L22).

**No file field, on purpose.** A policy PDF is an ordinary ``ProcurementDocument``, chosen
through the ``document`` FK, so it goes through the repository's allow-list, size cap, checksum,
text extraction and approval step like every other file in this sub-module. There is no second
upload path that skips all five.

**The threshold fields are advisory input, not a control.** What the user types here is quoted
back to readers; nothing in 6.19 branches on it. The help text on the form says so in the same
words the model docstring and ``ADVISORY_NOTE`` use, so a person filling the form in is told what
it does before they wonder.

Tenant discipline: every dropdown is narrowed to the workspace in ``__init__`` AND re-checked in
``clean()``. A narrowed ``<select>`` is UX, not an authorization boundary — an unscoped
``ModelChoiceField`` both displays another tenant's rows and accepts their pk from a crafted POST.
``threshold_currency`` is the one FK exempt from that re-check, and only because
``accounting.Currency`` is a GLOBAL table with no tenant column at all.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.DocumentKnowledgeManagement.Policies import ProcurementPolicy


#: The tenant-scoped FKs re-checked against the workspace on POST — the same three the model's
#: own ``clean()`` backstops. ``owner`` is deliberately absent: it is narrowed to workspace
#: members in ``__init__``, and ``ModelChoiceField.to_python`` validates a submitted pk against
#: the field's own queryset, so a foreign user pk is already refused as "Select a valid choice".
#: ``threshold_currency`` is absent for the opposite reason — its table is global, so there is no
#: workspace for a currency to belong to.
_SCOPED_LINKS = ["previous_version", "applies_to", "document"]


def _workspace_members(tenant):
    """Active users of this workspace, ordered for human scanning."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if tenant is None:
        return User.objects.none()
    return User.objects.filter(tenant=tenant, is_active=True).order_by("username")


class ProcurementPolicyForm(TenantUniqueMixin, TenantModelForm):
    """Create or amend one policy in the library.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``ProcurementPolicy.clean()`` compares each chosen FK's tenant against
    ``self.tenant_id``, and without the stamp every CREATE would be falsely rejected as
    cross-tenant. The mixin's second job matters here too — the ``(tenant, title,
    version_number)`` constraint is only checked when ``tenant`` is on the instance.
    """

    class Meta:
        model = ProcurementPolicy
        fields = ["title", "policy_type", "summary", "body", "version_number", "previous_version",
                  "applies_to", "owner", "document", "effective_from", "next_review_on",
                  "threshold_amount", "threshold_basis", "threshold_currency",
                  "requires_acknowledgment"]
        widgets = {
            # ``summary`` is a CharField(500) — a 500-character sentence typed into a one-line
            # box is unreadable while it is being written. The Textarea is presentation only;
            # the column's max_length still enforces the limit.
            "summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "body": forms.Textarea(attrs={"class": "form-textarea", "rows": 10}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's rows
            # and must not be able to post one either. ``threshold_currency`` is included: with
            # no workspace selected there is no policy to label, so offering the global currency
            # list would be the only live control on a form that cannot save.
            for name in ("previous_version", "applies_to", "owner", "document",
                         "threshold_currency"):
                self.fields[name].queryset = self.fields[name].queryset.none()
            return

        # ``previous_version``, ``applies_to`` and ``document`` all target models that carry a
        # ``tenant`` column, so ``TenantModelForm`` has already scoped them. What is added here
        # is ORDERING — and, for the self-FK, the exclusion below.
        previous = self.fields["previous_version"].queryset.order_by("-created_at", "-id")
        if self.instance.pk is not None:
            # A policy may not supersede itself. Removing it from the dropdown is the UX half;
            # ``ProcurementPolicy.clean()`` refuses the same link (and every longer loop) on a
            # crafted POST, which is the half that actually holds.
            previous = previous.exclude(pk=self.instance.pk)
        self.fields["previous_version"].queryset = previous

        self.fields["applies_to"].queryset = (
            self.fields["applies_to"].queryset.order_by("name"))
        self.fields["document"].queryset = (
            self.fields["document"].queryset.order_by("-created_at", "-id"))
        self.fields["owner"].queryset = _workspace_members(tenant)

        # ``threshold_currency`` is a GLOBAL table (no tenant column) — TenantModelForm leaves it
        # alone, and the narrowing is active-only ordering, not a tenancy boundary. The 6.15
        # CostForecastForm note applies verbatim.
        from apps.accounting.models import Currency

        self.fields["threshold_currency"].queryset = (
            Currency.objects.filter(is_active=True).order_by("code"))
        self.fields["threshold_currency"].empty_label = "- not labelled -"

        self.fields["previous_version"].empty_label = "- first version -"
        self.fields["applies_to"].empty_label = "- the whole workspace -"
        for name in ("owner", "document"):
            self.fields[name].empty_label = "- none -"

    def clean(self):
        cleaned = super().clean()
        # Re-check every tenant-scoped FK against the workspace: the narrowed <select> above is
        # presentation, and a crafted POST never goes near it.
        _reject_foreign(self, cleaned, _SCOPED_LINKS)
        return cleaned
