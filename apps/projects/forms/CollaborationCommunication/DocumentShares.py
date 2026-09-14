"""Projects 7.9 — DocumentShare forms.

``DocumentShareForm`` carries the share's working data — ``project``, ``channel``, ``document``,
``access_level``, ``shared_with`` and ``note``. ``tenant``, ``number``, ``is_active``,
``revoked_by``, ``revoked_at``, ``claimed_by``, ``claimed_at`` and ``created_by`` are all OFF it:
the revoke state and the edit claim are written by their POST-only verbs alone, so the evidence
keeps its timestamps (the 7.4/7.6/7.8 verb-written-stamp idiom).

``TenantUniqueMixin`` is mixed in FIRST (the house idiom): it stamps ``instance.tenant`` before
``full_clean()`` runs on CREATE so the per-tenant ``unique_together`` binds. ``clean()`` then runs
``_reject_foreign`` on the three tenant-scoped FKs — ``project``, ``channel`` and ``document``
(``core.Document`` DOES carry its own ``tenant``, so it is re-checkable, unlike the global
``accounting.Currency`` L29 warns about). ``shared_with`` is **deliberately absent** from that
list: it is a ``settings.AUTH_USER_MODEL`` FK and users can be tenant-less, so a narrowed
``<select>`` (``TenantModelForm`` scopes it) is the boundary and re-comparing
``user.tenant_id`` would reject legitimate rows — the 7.8 ``assignee`` exemption.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import DocumentShare


class DocumentShareForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentShare
        fields = ["project", "channel", "document", "access_level", "shared_with", "note"]

    def clean(self):
        cleaned = super().clean()
        # `shared_with` is a User FK — deliberately not re-checked (see the module docstring).
        _reject_foreign(self, cleaned, ["project", "channel", "document"])
        return cleaned
