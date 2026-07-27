"""SCM 4.8 Manufacturing — BillOfMaterials form + component line formset."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin
from apps.scm.models import BillOfMaterials, BOMLine


class BillOfMaterialsForm(TenantUniqueMixin, TenantModelForm):
    """The recipe header.

    EXCLUDES `number` (auto). Everything else IS editable, including `status` and `is_default` —
    a BOM's draft/active/obsolete progression is master-data curation, not a workflow that gates a
    stock posting, so unlike WorkOrder.status it needs no transition actions. `item`, `uom` and
    `default_work_center` each carry their own tenant, so the base class scopes them.

    The one-default-per-item rule lives in the model's `clean()` (MySQL has no conditional
    UniqueConstraint) and is reached from here because `TenantUniqueMixin` runs full model
    validation.
    """

    class Meta:
        model = BillOfMaterials
        fields = ["item", "name", "version", "bom_type", "output_quantity", "uom",
                  "lead_time_days", "default_work_center", "status", "effective_from",
                  "effective_to", "is_default", "notes"]
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "effective_to": forms.DateInput(attrs={"type": "date"}),
        }


class BOMLineForm(TenantModelForm):
    """One component of the recipe.

    `quantity_per` is the pre-scrap figure — the grossed-up number a work order actually requires is
    derived (`effective_quantity_per`), never typed, so the two can't disagree.
    """

    class Meta:
        model = BOMLine
        fields = ["sequence", "component", "quantity_per", "uom", "scrap_pct", "issue_method",
                  "notes"]


class BaseBOMLineFormSet(forms.BaseInlineFormSet):
    """Refuses a recipe that lists its own output as an ingredient.

    The model's `clean()` catches this too, but only for a BOM that already HAS the offending line
    saved — on create the line and the header arrive together, so without this the first save would
    write a self-referencing recipe that `explode()` then has to defend against.
    """

    def clean(self):
        super().clean()
        parent_item_id = getattr(self.instance, "item_id", None)
        if parent_item_id is None:
            return
        for form in self.forms:
            if not getattr(form, "cleaned_data", None) or form.cleaned_data.get("DELETE"):
                continue
            component = form.cleaned_data.get("component")
            if component is not None and component.pk == parent_item_id:
                raise ValidationError(
                    f"{component} is this BOM's own output — a recipe cannot consume itself.")


# max_num with validate_max: without it Django accepts up to absolute_max (2000) lines in ONE post
# and silently ignores the overflow. A recipe that wide feeds BillOfMaterials.explode(), whose
# output is the product of the branch factors — see MAX_EXPLODE_ROWS for why that is a DoS bound.
BOMLineFormSet = inlineformset_factory(
    BillOfMaterials, BOMLine, form=BOMLineForm, formset=BaseBOMLineFormSet, extra=3,
    can_delete=True, max_num=200, validate_max=True,
)
