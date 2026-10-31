from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ReviewUgc.ReviewSentimentSummaries import ReviewSentimentSummary


class ReviewSentimentSummaryForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ReviewSentimentSummary
        fields = [
            "product",
            "improvement_recommendation",
        ]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "improvement_recommendation": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 4,
                    "placeholder": "Actionable product quality guidance or manufacturing suggestions...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["product"])
        return cleaned
