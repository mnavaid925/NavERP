"""Projects 7.6 — DeliverableInspection forms.

``DeliverableInspectionForm`` carries the planning + execution-entry data. ``usage_decision``,
``accepted_by``, ``accepted_by_party``, ``accepted_at``, ``acceptance_note``, ``status`` and
``created_by`` are all OFF it: the acceptance decision and the lifecycle are verb-driven
(``qci_record`` / ``qci_accept`` / ``qci_reject``), so the evidence trail keeps its stamps — the
same rule 7.5 applied to ``IssueResolutionForm``. ``result`` and ``inspected_date`` ARE on the
form as entry data; the ``qci_record`` verb is the formal execution stamp that also moves the
status.

``InspectionAcceptanceForm`` is ``qci_accept``'s body — a plain ``forms.Form`` (not a ModelForm)
so the acceptor, the customer party and the conditions note are written by the verb that also
stamps ``accepted_by``/``accepted_at``, never by a generic edit. Its ``accepted_by_party``
choices are scoped to the workspace's parties in ``__init__`` — ``core.Party`` has no tenant on
``_reject_foreign``'s terms, so the queryset IS the boundary (and the verb re-checks it against
the row's tenant before saving).

``TenantUniqueMixin`` is mixed in FIRST on the ModelForm: ``DeliverableInspection.clean()``
compares three chosen FKs' project against ``self.project``, and the mixin is what stamps
``instance.tenant`` before ``full_clean()`` runs on CREATE (without it every create is falsely
rejected as cross-tenant).
"""
from apps.core.models import Party
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import DeliverableInspection


def _acceptor_parties(tenant):
    """This workspace's Parties, as the ``accepted_by_party`` dropdown's choices.

    Deliberately mirrors ``apps/projects/views/_helpers.py::clients`` (any Party of the tenant,
    name-ordered, not role-narrowed — a project's customer can be any organisation on the spine).
    It lives HERE rather than being imported from the views package because the dependency
    direction runs views → forms: the views package ``__init__`` re-exports the view modules (and
    they import this form), so a form reaching back into ``apps.projects.views`` would cycle the
    package — ``views/_helpers.py`` itself imports nothing from forms. ``None`` tenant yields an
    empty queryset rather than the unscoped default manager — the same posture every other
    scoping helper takes.
    """
    if tenant is None:
        return Party.objects.none()
    return Party.objects.filter(tenant=tenant).order_by("name")


class DeliverableInspectionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DeliverableInspection
        fields = ["project", "wbs_node", "quality_plan", "milestone", "title", "description",
                  "inspection_type", "planned_date", "inspected_date", "inspector", "result",
                  "findings"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned,
                        ["project", "wbs_node", "quality_plan", "milestone", "inspector"])
        return cleaned


class InspectionAcceptanceForm(forms.Form):
    """The ``qci_accept`` verb's body: the usage decision (accept / accept with deviation only —
    a rejection is ``qci_reject``'s, so the two decisions cannot be forged from one endpoint),
    the external acceptor and the conditions note."""

    usage_decision = forms.ChoiceField(
        choices=[("accept", "Accept"), ("accept_with_deviation", "Accept with Deviation")],
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="A conditional acceptance records its punch list as open defects.")
    accepted_by_party = forms.ModelChoiceField(
        queryset=_acceptor_parties(None), required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="The customer / external party signing the acceptance, if it is not a user.")
    acceptance_note = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        help_text="Conditions or reservations attached to the acceptance.")

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        # A Party is scoped by queryset, not by ``_reject_foreign`` — the plain form has no model
        # instance for the mixin to stamp, so the queryset IS the tenant boundary.
        self.fields["accepted_by_party"].queryset = _acceptor_parties(tenant)
