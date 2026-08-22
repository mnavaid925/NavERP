"""Procurement 6.2 Requisition Management â€” RequisitionTemplates forms.

A template is edited as a header form + an inline line formset (the same shape 4.1 uses for its
requisitions), so a recurring order reads exactly like the requisition it produces.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import _reject_foreign
from apps.procurement.models import RequisitionTemplate, RequisitionTemplateLine


class RequisitionTemplateForm(TenantModelForm):
    class Meta:
        model = RequisitionTemplate
        # EXCLUDED and why: ``number`` is assigned once by TenantNumbered.save();
        # ``created_by`` is stamped from request.user in the view (never choosable).
        fields = ["name", "description", "org_unit", "currency", "default_lead_days",
                  "justification", "is_active"]

    def clean(self):
        cleaned = super().clean()
        # Same crafted-POST re-check as every tenant-scoped FK this form renders (currency is a
        # global master with no workspace column, so only org_unit needs the re-check here).
        _reject_foreign(self, cleaned, ["org_unit"])
        return cleaned


class RequisitionTemplateLineForm(TenantModelForm):
    class Meta:
        model = RequisitionTemplateLine
        fields = ["item_description", "sku_hint", "uom_hint", "quantity",
                  "estimated_unit_price", "gl_account"]


class BaseRequisitionTemplateLineFormSet(forms.BaseInlineFormSet):
    """Crafted-POST re-check for each line's tenant-scoped FKs.

    TenantModelForm narrows the rendered ``gl_account`` dropdown to this workspace, but a narrowed
    select is UX, not an authorization boundary â€” a hand-posted foreign pk must land as a field
    error instead of silently charging another workspace's account.
    """

    def clean(self):
        super().clean()
        for form in self.forms:
            if hasattr(form, "cleaned_data"):
                _reject_foreign(form, form.cleaned_data, ["gl_account"])


RequisitionTemplateLineFormSet = inlineformset_factory(
    RequisitionTemplate, RequisitionTemplateLine, form=RequisitionTemplateLineForm,
    # max_num caps a crafted management form (TOTAL_FORMSâ‰ˆ1000) at a sane row count â€” each
    # accepted row is validated and later copied verbatim on every apply.
    formset=BaseRequisitionTemplateLineFormSet, extra=2, can_delete=True, max_num=50, validate_max=True,
)
