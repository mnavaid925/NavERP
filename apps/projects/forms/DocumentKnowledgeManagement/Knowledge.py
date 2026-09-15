"""Projects 7.10 — KnowledgeEntry forms.

``KnowledgeEntryForm`` carries the library row's working data — ``title``, ``kind``, ``summary``,
``body``, ``category``, ``tags``, ``source_project``, ``document``, ``owner``, ``status``,
``review_on`` and ``is_featured``.

**`usage_count` is OFF the form** — it is incremented only by the ``kne_use`` verb's atomic
``F("usage_count") + 1``, so no save path anywhere can reset somebody's counter to zero by saving a
stale copy of the row.

**`source_project` is nullable on purpose** and ``_reject_foreign`` still re-checks it when set: a
crafted POST must not attribute a lesson to another workspace's project. ``document`` is re-checked
for the same reason. ``owner`` is a User FK and stays exempt (the 7.8/7.9 ruling).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import KnowledgeEntry


class KnowledgeEntryForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = KnowledgeEntry
        fields = [
            "title", "kind", "summary", "body", "category", "tags", "source_project", "document",
            "owner", "status", "review_on", "is_featured",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The library is read by everybody and written sparingly; the featured shelf is a curation
        # act, so it stays on the form but the counter next to it is never editable.
        self.fields["summary"].widget.attrs.setdefault("maxlength", 255)

    def clean(self):
        cleaned = super().clean()

        # `owner` is a User FK — deliberately not re-checked (the 7.8/7.9 exemption).
        _reject_foreign(self, cleaned, ["source_project", "document"])

        return cleaned