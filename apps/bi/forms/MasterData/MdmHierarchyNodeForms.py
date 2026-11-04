from django import forms
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.MasterData.MdmHierarchyNodes import MdmHierarchyNode
from apps.bi.models.MasterData.MdmGoldenRecords import MdmGoldenRecord
from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit, Party
from apps.scm.models.InventoryManagement.Items import ItemCategory


class MdmHierarchyNodeForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MdmHierarchyNode
        fields = [
            "name",
            "code",
            "hierarchy_type",
            "parent",
            "golden_record",
            "party",
            "org_unit",
            "item_category",
            "relationship_kind",
            "sort_order",
            "valid_from",
            "valid_to",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. North American Operations"}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. na_operations"}),
            "hierarchy_type": forms.Select(attrs={"class": "form-select"}),
            "parent": forms.Select(attrs={"class": "form-select"}),
            "golden_record": forms.Select(attrs={"class": "form-select"}),
            "party": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "item_category": forms.Select(attrs={"class": "form-select"}),
            "relationship_kind": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. subsidiary_of, rolls_up_to"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-input", "placeholder": "10"}),
            "valid_from": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "valid_to": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Hierarchy role and organizational definition"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            parent_qs = MdmHierarchyNode.objects.filter(tenant=self.tenant)
            if self.instance and self.instance.pk:
                parent_qs = parent_qs.exclude(pk=self.instance.pk)
            self.fields["parent"].queryset = parent_qs.order_by("hierarchy_type", "level", "name")
            self.fields["golden_record"].queryset = MdmGoldenRecord.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["party"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["item_category"].queryset = ItemCategory.objects.filter(tenant=self.tenant).order_by("name")

    def clean(self):
        cleaned = super().clean()
        parent = cleaned.get("parent")
        hierarchy_type = cleaned.get("hierarchy_type")
        if parent:
            if hierarchy_type and parent.hierarchy_type != hierarchy_type:
                raise ValidationError({"parent": "Parent node hierarchy type must match node hierarchy type."})
            if self.instance and self.instance.pk:
                if parent.pk == self.instance.pk:
                    raise ValidationError({"parent": "A hierarchy node cannot be its own parent."})
                # Prevent circular reference if parent has this node in its path
                if self.instance.path and self.instance.path in parent.path:
                    raise ValidationError({"parent": "Cannot set a child node as parent (circular hierarchy)."})
        reject_foreign(
            self,
            cleaned,
            ["parent", "golden_record", "party", "org_unit", "item_category"],
        )
        return cleaned
