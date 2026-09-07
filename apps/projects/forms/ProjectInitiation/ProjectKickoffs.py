"""Projects 7.1 — ProjectKickoff form.

Everything the ceremony attests to is verb-driven and stamped, so the form is only the meeting
logistics and the two free-text blocks. ``status``, the baseline acknowledgement and
``completed_at`` are all excluded.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import _reject_foreign, forms
from apps.projects.models import Project, ProjectKickoff


class ProjectKickoffForm(TenantUniqueMixin, TenantModelForm):
    # .none(), not .all(): every __init__ branch below overwrites this, so the class-level value
    # is only ever the fallback for a path that forgets to — and the fail-closed fallback is an
    # empty dropdown, not every workspace's projects.
    project = forms.ModelChoiceField(queryset=Project.objects.none())

    class Meta:
        model = ProjectKickoff
        exclude = [
            "tenant", "number",
            "status",                                       # verb-driven
            "baseline_acknowledged_at", "baseline_acknowledged_by",   # stamps
            "completed_at",                                 # stamp
            "created_by",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A project that already has a kickoff cannot take a second one (unique_together), so the
        # dropdown offers only the ones still available — plus the row's own project on edit.
        qs = Project.objects.none() if self.tenant is None else Project.objects.filter(
            tenant=self.tenant)
        taken = ProjectKickoff.objects.filter(project__in=qs).values_list("project_id", flat=True)
        if self.instance and self.instance.pk:
            qs = qs.filter(pk=self.instance.project_id) | qs.exclude(pk__in=taken)
        else:
            qs = qs.exclude(pk__in=taken)
        self.fields["project"].queryset = qs

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project"])
        return cleaned
