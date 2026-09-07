"""Projects 7.1 — ProjectStakeholder form.

``project`` is an explicit tenant-scoped ``ModelChoiceField`` rather than the ModelForm default,
so the dropdown shows this workspace's projects only and the register can be entered from a
project's detail page with the project pre-selected.

The duplicate check lives on the MODEL's ``clean()`` (which ModelForm runs in ``_post_clean``) —
it needs the tenant stamp ``TenantUniqueMixin`` makes, and keeping it on the model means a seeder
or an API can't bypass it by going straight to ``.save()``… or rather, it means the one place that
skips validation has to do so deliberately.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import _reject_foreign, forms
from apps.projects.models import Project, ProjectStakeholder


class ProjectStakeholderForm(TenantUniqueMixin, TenantModelForm):
    project = forms.ModelChoiceField(queryset=Project.objects.all())

    class Meta:
        model = ProjectStakeholder
        exclude = ["tenant", "number", "created_by"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Narrow the dropdown to this workspace. A narrowed <select> is UX, not an authorization
        # boundary — _reject_foreign re-checks the POSTed value below.
        if self.tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(tenant=self.tenant)
        else:
            self.fields["project"].queryset = Project.objects.none()

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "party"])
        return cleaned
