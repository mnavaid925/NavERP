"""Procurement 6.19 Document & Knowledge Management — KnowledgeResource form.

One shape: ``KnowledgeResourceForm``, the create-or-edit form for a resource in the shared
library. It carries the guidance as written, who it is for, what it is about and the artifact it
points at; everything the SYSTEM owns is excluded, each for its own reason:

* ``tenant`` — stamped by ``TenantUniqueMixin`` / ``crud_create``.
* ``number`` — allocated once by ``TenantNumbered.save()``.
* ``status`` — verb-driven. Publish and archive are POST-only buttons on the detail page, each
  with its own audit row. A status ``<select>`` here would let a form save skip both.
* ``usage_count`` / ``last_used_at`` — owned by the "use this" verb alone, and written there
  through an atomic ``F("usage_count") + 1``. Typed here they would be a claim about how often
  colleagues reached for something, entered by the person who wants it to look popular; and a
  form save would clobber the concurrent increments the F() expression exists to protect.
* ``created_by`` — an authorship stamp, not an input.
* ``created_at`` / ``updated_at`` — the ``TenantOwned`` base timestamps (L22).

**No file field, on purpose — and this is the design, not an omission.** The downloadable
scorecard workbook or playbook PDF is an ordinary ``ProcurementDocument`` chosen through the
``document`` FK, so it goes through the repository's extension allow-list, its 20 MB cap, its
checksum, its text read and its approval step, and it gains a revision chain. A second upload
path on this form would skip all five and leave the library holding an unversioned copy of a file
that also exists, differently, somewhere else.

**``is_featured`` IS on the form, and it is a display choice.** It decides what the shelf shows
first and nothing else — it is not an approval, it grants nothing, and the help text on the form
says so, because a checkbox that looks like a sign-off is how a display flag quietly becomes a
control nobody implemented.

Tenant discipline: the one tenant-scoped dropdown is narrowed to the workspace in ``__init__``
AND re-checked in ``clean()``. A narrowed ``<select>`` is UX, not an authorization boundary — an
unscoped ``ModelChoiceField`` both displays another tenant's rows and accepts their pk from a
crafted POST.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.DocumentKnowledgeManagement.KnowledgeResources import (
    KnowledgeResource)


#: The tenant-scoped FKs re-checked against the workspace on POST — here, the one the model's own
#: ``clean()`` backstops. ``owner`` is deliberately absent: it is narrowed to workspace members in
#: ``__init__``, and ``ModelChoiceField.to_python`` validates a submitted pk against the field's
#: own queryset, so a foreign user pk is already refused as "Select a valid choice".
_SCOPED_LINKS = ["document"]


def _workspace_members(tenant):
    """Active users of this workspace, ordered for human scanning."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if tenant is None:
        return User.objects.none()
    return User.objects.filter(tenant=tenant, is_active=True).order_by("username")


class KnowledgeResourceForm(TenantUniqueMixin, TenantModelForm):
    """Create or amend one resource in the shared library.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``KnowledgeResource.clean()`` compares the chosen document's tenant against
    ``self.tenant_id``, and without the stamp every CREATE would be falsely rejected as
    cross-tenant. The mixin's second job matters here too — the ``(tenant, number)`` constraint
    is only checked when ``tenant`` is on the instance.
    """

    class Meta:
        model = KnowledgeResource
        fields = ["title", "resource_type", "category", "audience", "summary", "body", "tags",
                  "is_featured", "owner", "document", "review_on"]
        widgets = {
            # ``summary`` is a CharField(500) — a 500-character sentence typed into a one-line
            # box is unreadable while it is being written. The Textarea is presentation only;
            # the column's max_length still enforces the limit.
            "summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "body": forms.Textarea(attrs={"class": "form-textarea", "rows": 12}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's rows and
            # must not be able to post one either.
            for name in ("owner", "document"):
                self.fields[name].queryset = self.fields[name].queryset.none()
            return

        # ``document`` targets a model that carries a ``tenant`` column, so ``TenantModelForm``
        # has already scoped it. What is added here is ORDERING — newest first, which is what
        # somebody who just uploaded the scorecard is looking for.
        self.fields["document"].queryset = (
            self.fields["document"].queryset.order_by("-created_at", "-id"))
        self.fields["owner"].queryset = _workspace_members(tenant)

        for name in ("owner", "document"):
            self.fields[name].empty_label = "- none -"

    def clean(self):
        cleaned = super().clean()
        # Re-check the tenant-scoped FK against the workspace: the narrowed <select> above is
        # presentation, and a crafted POST never goes near it.
        _reject_foreign(self, cleaned, _SCOPED_LINKS)
        return cleaned
