"""Forms for the 8.6 order hold.

``OrderHoldForm`` carries the six authorable fields and nothing else. Everything that makes
a hold *trustworthy* is deliberately absent (L22):

* ``evaluation_snapshot`` — frozen evidence, server-generated. A form that accepted one
  would let a clerk write "approved by finance" into the very record that is supposed to
  prove the hold was automatic.
* ``severity`` — copied from the rule at fire time.
* ``status`` — workflow-governed, written only by the raise / clear / supersede verbs.
* every action stamp (``raised_at``/``raised_by``/``checked_out_by``/``checked_out_at``/
  ``cleared_by``/``cleared_at``) and ``superseded_by``.

``clear_note`` is on the form precisely because it is the one field a human must supply: a
hold released without a stated reason is the failure this whole workbench exists to prevent.

``OrderHoldActionForm`` is the plain (non-model) form the POST verbs bind. It validates the
justification *before* the view does any work, so a blank reason is an inline form error
rather than a half-applied release.
"""
from django import forms

from apps.core.models import Party
from apps.sales.forms._common import TenantActionForm, TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.sales.models.OrderManagement.OrderHolds import OrderHold
from apps.sales.models.OrderManagement.OrderValidationRules import OrderValidationRule


class OrderHoldForm(TenantUniqueMixin, TenantModelForm):
    """Create / edit one hold. The lifecycle is the verbs' job, not this form's."""

    class Meta:
        model = OrderHold
        # Excluded, with the reason for each:
        #   tenant       — set by the mixin from the view's request.tenant, never from input.
        #   number       — auto-numbered OHD- by TenantNumbered.save().
        #   status       — WORKFLOW: written only by the raise / clear / supersede verbs.
        #   severity     — FROZEN at fire time, editable=False.
        #   evaluation_snapshot — FROZEN EVIDENCE, server-generated, editable=False.
        #   raised_at / raised_by / checked_out_by / checked_out_at / cleared_by /
        #   cleared_at       — ACTION-STAMPED: each written by exactly one named POST view.
        #   superseded_by     — system.
        #   created_at / updated_at — auto_now* stamps.
        fields = [
            "sales_order",
            "rule",
            "party",
            "hold_type",
            "reason",
            "clear_note",
        ]
        widgets = {
            "sales_order": forms.Select(attrs={"class": "form-select"}),
            "rule": forms.Select(attrs={"class": "form-select"}),
            "party": forms.Select(attrs={"class": "form-select"}),
            "hold_type": forms.Select(attrs={"class": "form-select"}),
            "reason": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 4,
                "placeholder": "Why is this order being held, in words a colleague can act on?",
            }),
            "clear_note": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "Filled in by whoever releases the hold — what changed, and who agreed.",
            }),
        }
        help_texts = {
            "sales_order": "The order this hold blocks. 8.6 extends SCM's order; it never replaces it.",
            "rule": "Leave blank for a hold placed by hand. Deleting the rule later will not delete this hold.",
            "party": "Leave blank to follow the order's own customer.",
            "hold_type": "Where the hold came from, for triage on the board.",
            "clear_note": "The only lifecycle field a person writes. A release with no reason is not a release.",
        }


    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # TenantModelForm already narrows every ModelChoiceField to the tenant. These three are
        # spelled out anyway so the ORDERING is pinned (the order dropdown is read by eye, and
        # an unordered pk list on a thousand-row workspace is unusable), and so the nullable
        # ones offer an explicit blank rather than implying one.
        if self.tenant is not None:
            from apps.scm.models import SalesOrder

            self.fields["sales_order"].queryset = SalesOrder.objects.filter(
                tenant=self.tenant
            ).select_related("customer").order_by("-order_date", "-id")
            self.fields["rule"].queryset = OrderValidationRule.objects.filter(
                tenant=self.tenant
            ).order_by("priority", "number")
            self.fields["party"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")
        self.fields["rule"].required = False
        self.fields["party"].required = False

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
        elif self.instance.pk and self.instance.tenant_id != tenant_id:
            self.add_error(None, "The hold must belong to this workspace.")
        # Belt and braces on top of the narrowed querysets: a queryset filter alone would
        # reject a cross-tenant pk with "Select a valid choice", and this says WHY in the
        # author's own terms — the same helper every other 8.6 form uses.
        _reject_foreign(self, cleaned, ["sales_order", "rule", "party"])
        return cleaned


class OrderHoldActionForm(TenantActionForm):
    """The plain form the hold's POST verbs bind — a justification, not a model.

    ``clear_note`` is required because every verb that uses it either releases a hold or
    releases a batch of them, and an unattributed release is the audit hole this module
    exists to close. ``release_note`` is optional at the FORM level and required by the view
    only in the override case (releasing somebody else's checkout), because in the ordinary
    case the release is self-evident and demanding prose for it only trains people to type
    noise.
    """

    clear_note = forms.CharField(
        label="Reason for release",
        widget=forms.Textarea(attrs={
            "class": "form-textarea",
            "rows": 3,
            "placeholder": "What changed, who agreed, and anything the next person should know.",
        }),
        max_length=2000,
    )
    release_note = forms.CharField(
        label="Override note",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-textarea",
            "rows": 2,
            "placeholder": "Required only when releasing a checkout held by somebody else.",
        }),
        max_length=2000,
    )

