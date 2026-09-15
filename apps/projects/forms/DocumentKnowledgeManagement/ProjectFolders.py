"""Projects 7.10 — ProjectFolder forms.

``ProjectFolderForm`` carries the tree's working data — ``project``, ``parent``, ``name``,
``description`` and ``sequence``. ``tenant``, ``number``, ``is_archived``, ``archived_by``,
``archived_at`` and ``created_by`` are all OFF it: the archive state is written by ``pfd_archive``
alone, so the stamps keep their evidence (the 7.4/7.6/7.8/7.9 verb-written-stamp idiom).

``TenantUniqueMixin`` is mixed in FIRST (the house idiom): it stamps ``instance.tenant`` before
``full_clean()`` runs on CREATE so the per-tenant ``unique_together`` binds. ``clean()`` then runs
``_reject_foreign`` on the two tenant-scoped FKs — ``project`` and ``parent`` — so a crafted POST
cannot graft another workspace's branch into this tree.

**The ``parent`` queryset is narrowed twice in ``__init__``.** ``TenantModelForm`` already scopes it
to the tenant; this adds (a) the chosen project, because a folder from another project would make the
tree a graph, and (b) on EDIT, the folder itself so the obvious self-parent is not even offered —
``clean()`` refuses it regardless, because a narrowed ``<select>`` is UX and never a boundary.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ProjectFolder


class ProjectFolderForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectFolder
        fields = ["project", "parent", "name", "description", "sequence"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        project_id = None
        if self.instance and self.instance.pk:
            project_id = self.instance.project_id
        elif self.data.get("project"):
            project_id = self.data.get("project")
        elif self.initial.get("project") is not None:
            initial = self.initial["project"]
            project_id = getattr(initial, "pk", initial)

        queryset = self.fields["parent"].queryset
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = queryset.order_by("name")

    def clean(self):
        cleaned = super().clean()

        # `_reject_foreign` re-checks the tenant on the FKs the form exposes. Both are tenant-scoped
        # on the model, so both are re-checkable (unlike a User FK — see Documents.py's form).
        _reject_foreign(self, cleaned, ["project", "parent"])

        # The same-project rule, restated here so the error lands on the field rather than only in
        # the model's `clean()` (which the view calls too — defense in depth, not duplication).
        parent = cleaned.get("parent")
        project = cleaned.get("project")
        if parent and project and parent.project_id != project.pk:
            self.add_error("parent", "The parent folder belongs to another project.")

        return cleaned
