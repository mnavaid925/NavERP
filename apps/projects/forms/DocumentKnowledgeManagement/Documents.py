"""Projects 7.10 — ProjectDocument forms.

``ProjectDocumentForm`` carries the register's working data — ``project``, ``folder``, ``title``,
``document_type``, ``classification``, ``owner``, ``tags``, ``description``, ``status``,
``milestone``, ``task`` and the two retention-intent columns (``retention_months``, ``review_on``).

**Everything verb-written is OFF the form**, which is what keeps the evidence trustworthy:
``is_checked_out``/``checked_out_by``/``checked_out_at`` (``pdm_checkout``/``pdm_checkin``),
``is_archived``/``archived_by``/``archived_at`` (``pdm_archive``), ``is_legal_hold``/``hold_reason``/
``held_by``/``held_at`` (``pdm_hold``/``pdm_release``), ``current_revision_no`` and
``extracted_text`` (the revision verbs and the re-index Run) and ``created_by``. A form that could
set ``is_archived`` would let somebody archive a held record by typing, which is exactly what the
model's ``clean()`` refuses.

``owner`` is a ``settings.AUTH_USER_MODEL`` FK and is **deliberately absent** from the
``_reject_foreign`` list: users can be tenant-less, so a narrowed ``<select>`` is the boundary and
re-comparing ``user.tenant_id`` would reject legitimate rows (the 7.8 ``assignee`` / 7.9
``shared_with`` exemption).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ProjectDocument


class ProjectDocumentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectDocument
        fields = [
            "project", "folder", "title", "document_type", "classification", "owner", "tags",
            "description", "status", "milestone", "task", "retention_months", "review_on",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # The project this document belongs to drives every narrowed queryset. On EDIT it is the
        # instance's own project and the field is not even offered (a document never moves between
        # projects — its number and its revisions belong to one).
        project_id = None
        if self.instance and self.instance.pk:
            project_id = self.instance.project_id
        elif self.data.get("project"):
            project_id = self.data.get("project")
        elif self.initial.get("project") is not None:
            initial = self.initial["project"]
            project_id = getattr(initial, "pk", initial)

        # `TenantModelForm` already scoped each of these to the tenant; this adds the project, so a
        # folder/milestone/task from a sister project cannot be attached to this document.
        if project_id:
            for name in ("folder", "milestone", "task"):
                field = self.fields.get(name)
                if field is not None:
                    field.queryset = field.queryset.filter(project_id=project_id).order_by("pk")

    def clean(self):
        cleaned = super().clean()

        # `owner` is a User FK — deliberately not re-checked (see the module docstring).
        _reject_foreign(self, cleaned, ["project", "folder", "milestone", "task"])

        folder = cleaned.get("folder")
        project = cleaned.get("project")
        if folder and project and folder.project_id != project.pk:
            self.add_error("folder", "That folder belongs to another project.")

        return cleaned