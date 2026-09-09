"""Projects 7.2 — ProjectTask form.

``owner`` is deliberately NOT in the ``_reject_foreign`` list: it is a User FK, and users can be
tenant-less (the superuser), so a tenant comparison would reject legitimate picks — the same
treatment 7.1 gives ``project_manager`` / ``executive_sponsor`` on ProjectForm. ``project`` and
``parent`` ARE tenant-stamped rows and are re-checked.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ProjectTask


class TaskForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectTask
        fields = [
            "project", "parent", "node_type", "name", "description", "owner", "status",
            "planned_start", "planned_end", "effort_hours", "estimation_method", "confidence",
            "sequence",
        ]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "parent"])
        # A task must not be nested beneath its own descendant — walking UP from the candidate
        # parent reaches ``self`` exactly when the candidate sits in self's subtree, which would
        # make the tree unrenderable. The walk runs over a {pk: parent_id} map built with ONE
        # tenant-scoped query for the project — never ``node.parent`` per hop, which cost one
        # lazy FK query per ancestor level (up to 250 per POST). The cap keeps a pre-existing
        # cycle in the data (not creatable through this form) a bounded loop, not a hang.
        parent = cleaned.get("parent")
        project = cleaned.get("project")
        if parent is not None and self.instance.pk and project is not None:
            pairs = dict(ProjectTask.objects.filter(
                tenant=self.tenant, project_id=project.pk,
            ).values_list("id", "parent_id"))
            node_id, hops = parent.pk, 0
            while node_id is not None and hops < 250:
                if node_id == self.instance.pk:
                    self.add_error("parent",
                                   "A task cannot be nested beneath its own descendant.")
                    break
                node_id = pairs.get(node_id)
                hops += 1
        return cleaned
