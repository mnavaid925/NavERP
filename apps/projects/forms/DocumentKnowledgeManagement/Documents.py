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
model's ``clean()`` refuses. ``status`` is likewise narrowed to the three states a human may type
(``draft``/``expected``/``in_review``): ``approved``, ``archived`` and ``superseded`` belong to the
verbs, and a form that offered them minted the state with no verb behind it.

``owner`` is a ``settings.AUTH_USER_MODEL`` FK and is **deliberately absent** from the
``_reject_foreign`` list: users can be tenant-less, so a narrowed ``<select>`` is the boundary and
re-comparing ``user.tenant_id`` would reject legitimate rows (the 7.8 ``assignee`` / 7.9
``shared_with`` exemption).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ProjectDocument


class ProjectDocumentForm(TenantUniqueMixin, TenantModelForm):
    #: The statuses a human may TYPE. ``approved`` is `pdv_approve`'s, ``archived`` is
    #: `pdm_archive`'s and ``superseded`` is nobody's to type — offering them on the form let a
    #: crafted POST mint an `approved` or `archived` record with no verb behind it, and a typed
    #: ``archived`` rendered "Archived" on a HELD row without tripping the hold's own refusal.
    TYPED_STATUSES = ("draft", "expected", "in_review")

    class Meta:
        model = ProjectDocument
        fields = [
            "project", "folder", "title", "document_type", "classification", "owner", "tags",
            "description", "status", "milestone", "task", "retention_months", "review_on",
        ]

    def __init__(self, *args, project_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project_id and not self.initial.get("project"):
            self.initial["project"] = project_id

        # Narrow `status` to the states a human may type. On EDIT the row's OWN status is added
        # back so the widget renders it selected: without that the browser would fall back to the
        # first option and any save would silently demote an approved/archived record.
        allowed = set(self.TYPED_STATUSES)
        if self.instance and self.instance.pk:
            allowed.add(self.instance.status)
        self.fields["status"].choices = [
            (value, label) for value, label in ProjectDocument.STATUS_CHOICES if value in allowed
        ]

        # The project this document belongs to drives every narrowed queryset. On EDIT it is the
        # instance's own project and the field is not even offered (a document never moves between
        # projects — its number and its revisions belong to one).
        if not project_id:
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

        if self.instance and self.instance.pk:
            # A document does not move between projects: its per-tenant number and its revision
            # chain belong to one. Disabling the field (rather than merely narrowing the three FKs
            # above) is what makes that true — those querysets are narrowed from the INSTANCE's
            # project, so a posted change of `project` would leave every folder/milestone/task on
            # the form failing "Select a valid choice" with no way to recover. Django reads a
            # disabled field's value from the instance, so a crafted POST cannot move it either.
            self.fields["project"].disabled = True

    def clean(self):
        cleaned = super().clean()

        # `owner` is a User FK — deliberately not re-checked (see the module docstring).
        _reject_foreign(self, cleaned, ["project", "folder", "milestone", "task"])

        folder = cleaned.get("folder")
        project = cleaned.get("project")
        if folder and project and folder.project_id != project.pk:
            self.add_error("folder", "That folder belongs to another project.")

        return cleaned