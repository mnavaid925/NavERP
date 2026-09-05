"""Procurement 6.18 Inventory & Warehouse Integration — material issue + line forms.

Two shapes: the document header a person fills in, and the one-row line form the detail page posts
to add an item.

**What is NOT on either of them is the point.** ``number`` is minted by ``TenantNumbered.save()``;
``status``, ``posted_at`` and ``cancelled_at`` are stamped by the verbs
(:meth:`MaterialIssue.submit` / ``post`` / ``cancel``) alone; ``issued_by`` and ``adjustment`` are
stamped by ``post()``. All five of those are ``editable=False`` on the model, so a ``ModelForm``
would refuse to render them anyway — the explicit ``fields`` list is the second lock, and it is
what stops a column added to the model next year from silently becoming a POST-able input. A
document whose *posted* flag could be typed in would not be evidence of anything.

``unit_cost`` is excluded from the line form for the same reason with a sharper edge: it is a
snapshot of the item's moving-average cost stamped in ``MaterialIssueLine.save()``, and letting a
POST set it would let somebody value a consumption at whatever number suited them.

**Tenant discipline.** Both forms take ``tenant=`` (every ``crud_*`` helper passes it) and narrow
their dropdowns to the workspace. A narrowed ``<select>`` is presentation, **not** an authorization
boundary — a crafted POST never goes near the rendered page — so each form re-checks its FKs in
``clean()`` via ``_reject_foreign``, and the model's own ``clean()`` sits behind that as the last
line.

**Why the line form is not a ``TenantUniqueMixin`` form.** ``MaterialIssueLine`` has no ``tenant``
column at all — tenant is reached through the issue — so the mixin's ``instance.tenant`` stamp has
nothing to write to. The line's workspace comes from ``issue.tenant``, and the line views load it
as ``issue__tenant=request.tenant``, which is where that boundary is actually enforced.
"""
from django.utils import timezone

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.InventoryWarehouseIntegration.MaterialIssues import (MaterialIssue,
                                                                                  MaterialIssueLine)

#: Every tenant-scoped FK the header form renders. Emptied wholesale for a tenant-less user and
#: re-checked wholesale in ``clean()`` — keeping ONE list means the two can never drift apart.
_HEADER_FKS = ("location", "org_unit", "gl_account", "requested_by", "reservation")


class MaterialIssueForm(TenantUniqueMixin, TenantModelForm):
    """Create or amend the header of a material issue / return.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``:
    ``MaterialIssue.clean()`` compares five chosen FKs against ``self.tenant_id``, and without the
    stamp every CREATE would be falsely rejected as cross-tenant. The mixin's ``validate_unique``
    override matters too — ``unique_together`` is ``(tenant, number)`` and neither is a form field,
    so Django's default exclusion list would drop the constraint.

    Editing is gated by the VIEW to draft documents only. Once a document is submitted its content
    is what somebody is about to post, and once it is posted it is evidence.
    """

    class Meta:
        model = MaterialIssue
        # Listed explicitly rather than via ``exclude`` so a column added to the model later
        # cannot silently become a form input.
        fields = ["location", "movement_type", "purpose", "reference", "issue_date",
                  "org_unit", "gl_account", "requested_by", "reservation", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "reference": forms.TextInput(
                attrs={"class": "form-input",
                       "placeholder": "Project / job / work-order number, e.g. JOB-0042"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's rows and
            # must not be able to post one either. ``location`` is required, so emptying it makes
            # the whole form fail validation — which is the correct outcome: a material issue with
            # no workspace has nothing to issue from.
            for name in _HEADER_FKS:
                self.fields[name].queryset = self.fields[name].queryset.none()
        else:
            from apps.accounting.models import GLAccount
            from apps.core.models import OrgUnit
            from apps.inventory.models import InventoryReservation
            from apps.scm.models import Location

            # ``TenantModelForm`` has already scoped each of these to the tenant (every target
            # model carries a ``tenant`` column, the user model included). The narrowing below is
            # the EXTRA rule per axis — active only, still-holding only, ordering — never the
            # tenant boundary itself.
            self.fields["location"].queryset = (
                Location.objects.filter(tenant=tenant, is_active=True).order_by("code"))
            self.fields["org_unit"].queryset = (
                OrgUnit.objects.filter(tenant=tenant).order_by("name"))
            self.fields["gl_account"].queryset = (
                GLAccount.objects.filter(tenant=tenant, is_active=True).order_by("code"))
            self.fields["requested_by"].queryset = (
                self.fields["requested_by"].queryset.filter(is_active=True).order_by("username"))
            # Only a lock that still HOLDS stock can be consumed. A reservation already consumed
            # or cancelled has nothing left to draw against, and offering it would invite somebody
            # to "use" the same lock twice.
            self.fields["reservation"].queryset = (
                InventoryReservation.objects
                .filter(tenant=tenant, status__in=InventoryReservation.ACTIVE_STATUSES)
                .select_related("item", "location").order_by("-id"))

        self.fields["org_unit"].empty_label = "- no cost centre -"
        self.fields["gl_account"].empty_label = "- use the account on each line -"
        self.fields["requested_by"].empty_label = "- not recorded -"
        self.fields["reservation"].empty_label = "- not against a reservation -"

        if not self.instance.pk and not self.initial.get("issue_date"):
            # Material almost always leaves the shelf today; pre-filling removes the one field
            # somebody would otherwise key on every single issue.
            self.initial["issue_date"] = timezone.localdate()

    def clean(self):
        cleaned = super().clean()
        # Re-check every tenant-scoped FK: the narrowed <select>s above are presentation, and a
        # crafted POST never goes near them.
        _reject_foreign(self, cleaned, list(_HEADER_FKS))
        return cleaned


class MaterialIssueLineForm(TenantModelForm):
    """One item on the document. Posted from the detail page, one row at a time.

    ``unit_cost`` is absent on purpose and it is the most important absence on this form: it is a
    snapshot of ``Item.average_cost`` stamped in ``MaterialIssueLine.save()``, so what a
    consumption cost the business is read off the item at the moment it happened rather than typed
    by the person consuming it.

    ``issue`` is absent too — the view sets it from the URL, which is what keeps a line from being
    posted onto somebody else's document by changing a hidden field.
    """

    class Meta:
        model = MaterialIssueLine
        fields = ["item", "lot_serial", "quantity", "gl_account", "notes"]
        widgets = {
            "notes": forms.TextInput(
                attrs={"class": "form-input",
                       "placeholder": "Optional — what this line in particular was for"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            for name in ("item", "lot_serial", "gl_account"):
                self.fields[name].queryset = self.fields[name].queryset.none()
        else:
            from apps.accounting.models import GLAccount
            from apps.scm.models import Item, LotSerial

            self.fields["item"].queryset = (
                Item.objects.filter(tenant=tenant, is_active=True)
                .select_related("uom").order_by("sku"))
            # Only lots that still exist as usable stock. The lot↔item consistency rule is the
            # model's (``MaterialIssueLine.clean()``): a dropdown cannot express "belongs to
            # whichever item you picked in the field above" without a round trip.
            self.fields["lot_serial"].queryset = (
                LotSerial.objects.filter(tenant=tenant, status="available")
                .select_related("item").order_by("item__sku", "number"))
            self.fields["gl_account"].queryset = (
                GLAccount.objects.filter(tenant=tenant, is_active=True).order_by("code"))

        self.fields["lot_serial"].empty_label = "- no lot / serial -"
        self.fields["gl_account"].empty_label = "- use the document's account -"
        self.fields["notes"].required = False

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item", "lot_serial", "gl_account"])
        return cleaned
