"""Projects 7.9 — Channel forms.

``ChannelForm`` carries the channel's working data — ``project``, ``name``, ``topic`` and
``kind``. ``tenant``, ``number``, ``is_archived``, ``archived_by``, ``archived_at`` and
``created_by`` are all OFF it: the archive state and its stamps are written exactly once per
direction by the POST-only ``chn_archive`` toggle verb, so the evidence keeps its timestamps
(the 7.4/7.6/7.8 verb-written-stamp idiom).

``TenantUniqueMixin`` is mixed in FIRST (the house idiom): it stamps ``instance.tenant`` before
``full_clean()`` runs on CREATE so the per-tenant ``unique_together`` binds — which matters twice
here, because ``Channel`` carries a second constraint (``("tenant", "project", "name")``) that the
form must be able to report as a field error rather than an ``IntegrityError``. ``clean()`` then
runs ``_reject_foreign`` on ``project``: a narrowed ``<select>`` is UX, not an authorization
boundary, so the chosen project is re-checked against the form's workspace.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import Channel


class ChannelForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = Channel
        fields = ["project", "name", "topic", "kind"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project"])
        return cleaned
