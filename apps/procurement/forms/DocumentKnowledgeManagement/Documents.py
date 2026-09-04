"""Procurement 6.19 Document & Knowledge Management — ProcurementDocument form.

One shape: ``ProcurementDocumentForm``, the create-or-edit form for a repository record. It
carries the descriptive header and the spine links; everything the SYSTEM owns is excluded, each
for its own reason:

* ``tenant`` — stamped by ``TenantUniqueMixin`` / ``crud_create``.
* ``number`` — allocated once by ``TenantNumbered.save()``.
* ``status`` — verb-driven. Approving a revision moves draft to active; supersede and archive
  are POST-only actions with their own audit rows. A status ``<select>`` here would let a form
  save skip the workflow and its audit trail entirely.
* ``current_revision_no`` — moved only by the revision-approve verb, under a parent row lock.
* ``checked_out_by`` / ``checked_out_at`` — the checkout / release verbs own the advisory lock.
* ``extracted_text`` — machine-written from the approved file; never typed.
* ``created_by`` — an authorship stamp, not an input.
* ``created_at`` / ``updated_at`` — the ``TenantOwned`` base timestamps (L22).

The FILE is not on this form either: bytes arrive through
``ProcurementDocumentRevisionUploadForm`` on the revision, so that every version of a document
goes through the same allow-list, the same size cap and the same approval step. There is no
back door that attaches a file straight to the parent.

Tenant discipline: every dropdown is narrowed to the workspace in ``__init__`` AND re-checked in
``clean()``. A narrowed ``<select>`` is UX, not an authorization boundary — an unscoped
``ModelChoiceField`` both displays another tenant's rows and accepts their pk from a crafted POST.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.DocumentKnowledgeManagement.Documents import ProcurementDocument


#: The spine FKs re-checked against the workspace on POST — the same four the model's own
#: ``clean()`` backstops. ``owner`` is deliberately absent: it is narrowed to workspace members
#: in ``__init__``, and ``ModelChoiceField.to_python`` validates a submitted pk against the
#: field's own queryset, so a foreign user pk is already refused as "Select a valid choice".
_SPINE_LINKS = ["supplier", "contract", "purchase_order", "sourcing_event"]


def _supplier_parties(tenant):
    """Parties this tenant can buy from — the 6.5/6.8 helper rule, verbatim.

    ``PartyRole.ROLE_CHOICES`` carries both ``supplier`` and ``vendor``, and workspaces use them
    interchangeably, so both are offered. ``.distinct()`` because a party with two roles would
    otherwise appear twice in the dropdown.
    """
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects
            .filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct()
            .order_by("name"))


def _workspace_members(tenant):
    """Active users of this workspace, ordered for human scanning."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if tenant is None:
        return User.objects.none()
    return User.objects.filter(tenant=tenant, is_active=True).order_by("username")


class ProcurementDocumentForm(TenantUniqueMixin, TenantModelForm):
    """Create or amend one repository record.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``ProcurementDocument.clean()`` compares each chosen FK's tenant against
    ``self.tenant_id``, and without the stamp every CREATE would be falsely rejected as
    cross-tenant.
    """

    class Meta:
        model = ProcurementDocument
        fields = ["title", "doc_type", "description", "tags", "classification", "owner",
                  "supplier_visible", "effective_date", "expires_on", "review_on",
                  "retention_until",
                  "supplier", "contract", "purchase_order", "sourcing_event"]
        widgets = {
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's rows
            # and must not be able to post one either.
            for name in ("owner", "supplier", "contract", "purchase_order", "sourcing_event"):
                self.fields[name].queryset = self.fields[name].queryset.none()
            return

        self.fields["owner"].queryset = _workspace_members(tenant)
        self.fields["supplier"].queryset = _supplier_parties(tenant)

        # ``contract`` / ``purchase_order`` / ``sourcing_event`` all target models that carry a
        # ``tenant`` column, so ``TenantModelForm`` has already scoped them. What is left is
        # ORDERING — newest first, because a buyer is nearly always attaching to recent work —
        # and, for the order, ONE select_related: ``PurchaseOrder.__str__`` hops to ``vendor``,
        # so an unhinted dropdown is a query per option.
        from apps.scm.models import PurchaseOrder, SupplierContract

        self.fields["contract"].queryset = (
            SupplierContract.objects.filter(tenant=tenant).order_by("-id"))
        self.fields["purchase_order"].queryset = (
            PurchaseOrder.objects.filter(tenant=tenant)
            .select_related("vendor").order_by("-id"))
        self.fields["sourcing_event"].queryset = (
            self.fields["sourcing_event"].queryset.order_by("-id"))

        for name in ("owner", "supplier", "contract", "purchase_order", "sourcing_event"):
            self.fields[name].empty_label = "- none -"

    def clean(self):
        cleaned = super().clean()
        # Re-check every spine FK against the workspace: the narrowed <select> above is
        # presentation, and a crafted POST never goes near it.
        _reject_foreign(self, cleaned, _SPINE_LINKS)
        return cleaned
