"""Projects 7.9 — ChannelMessage forms.

``ChannelMessageForm`` carries the message's working data — ``channel``, ``parent``, ``body`` and
``mentions``. ``tenant``, ``number``, ``edited_by``, ``edited_at`` and ``created_by`` are all OFF
it: the edit stamps are written by ``msg_edit`` alone, so the "edited" evidence keeps its
timestamp (the 7.4/7.6/7.8 verb-written-stamp idiom).

**The M2M scoping gap — this is the one thing not to "simplify".**
``TenantModelForm.__init__`` scopes ``forms.ModelChoiceField`` only
(``apps/core/forms/_common.py:52``). ``mentions`` is a ``ModelMultipleChoiceField``, so it is
**NOT** auto-scoped, and without the narrowing below a crafted POST could mention a user in
**another workspace** — leaking that user's name and email into this tenant's message and minting
a notification row in the wrong inbox. The narrowed queryset IS the authorization boundary:
``ModelMultipleChoiceField.clean()`` re-validates every submitted pk against it.

That narrowing is also why ``mentions`` is **not** passed to ``_reject_foreign`` — an M2M cleaned
value is a LIST, so ``getattr(chosen, "tenant_id")`` would raise ``AttributeError``. ``channel``
and ``parent`` are single tenant-scoped FKs and ARE re-checked.

``TenantUniqueMixin`` is mixed in FIRST (the house idiom): it stamps ``instance.tenant`` before
``full_clean()`` runs on CREATE, which is what lets ``ChannelMessage.clean()``'s same-channel and
one-level-deep guards read a stamped tenant on the create path.
"""
from django.contrib.auth import get_user_model

from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ChannelMessage


class ChannelMessageForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ChannelMessage
        fields = ["channel", "parent", "body", "mentions"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # See the module docstring: TenantModelForm scopes ModelChoiceField only, so the M2M
        # audience is scoped here. `.none()` for a tenant-less user — a filter dropdown (and a
        # mention picker) for them is empty, not an error (the `owners()` ruling).
        users = get_user_model().objects
        users = users.none() if self.tenant is None else users.filter(tenant=self.tenant)
        self.fields["mentions"].queryset = users.order_by("email")
        self.fields["mentions"].help_text = (
            "Each mentioned teammate gets a notification on save. "
            "Hold Ctrl (or Cmd) to pick more than one.")

    def clean(self):
        cleaned = super().clean()
        # `mentions` is deliberately absent — a M2M cleaned value is a list, and _reject_foreign
        # compares a single row's tenant_id. Its boundary is the queryset narrowed in __init__.
        _reject_foreign(self, cleaned, ["channel", "parent"])
        return cleaned
