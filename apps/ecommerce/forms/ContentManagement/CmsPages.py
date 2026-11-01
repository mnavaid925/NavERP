from django import forms
from django.core.exceptions import ValidationError

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin
from apps.ecommerce.models.ContentManagement.CmsPages import CmsPage


class CmsPageForm(TenantUniqueMixin, TenantModelForm):
    ab_traffic_percentage = forms.IntegerField(
        required=False,
        initial=50,
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
    )

    class Meta:
        model = CmsPage
        fields = [
            "title",
            "slug",
            "page_type",
            "status",
            "template_layout",
            "meta_title",
            "meta_description",
            "canonical_url",
            "is_indexable",
            "raw_html_body",
            "is_ab_test_active",
            "ab_variant_label",
            "ab_traffic_percentage",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Page headline"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "about-us or summer-sale"}),
            "page_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "template_layout": forms.Select(attrs={"class": "form-select"}),
            "meta_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "SEO Title (optimal 50-60 chars)"}),
            "meta_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "SEO snippet for search results"}),
            "canonical_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://example.com/canonical-url"}),
            "is_indexable": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "raw_html_body": forms.Textarea(attrs={"class": "form-textarea", "rows": 8, "placeholder": "Editorial content / HTML markup"}),
            "is_ab_test_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "ab_variant_label": forms.TextInput(attrs={"class": "form-input", "placeholder": "Variant B - Discount Focus"}),
            "ab_traffic_percentage": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get("slug", "").strip().lower()
        if not slug:
            raise ValidationError("Slug cannot be empty.")
        qs = CmsPage.objects.filter(tenant=self.tenant, slug=slug)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"A page with slug '{slug}' already exists for this tenant.")
        return slug

    def clean_ab_traffic_percentage(self):
        val = self.cleaned_data.get("ab_traffic_percentage")
        if val is None:
            return 50
        return val

    def clean_raw_html_body(self):
        import re
        raw_html = self.cleaned_data.get("raw_html_body", "")
        if not raw_html:
            return raw_html
        dangerous_patterns = [
            (r"<\s*script\b", "Script tags (<script>) are not permitted in CMS page body."),
            (r"<\s*iframe\b", "Iframe elements (<iframe>) are not permitted in CMS page body."),
            (r"<\s*object\b", "Object elements (<object>) are not permitted in CMS page body."),
            (r"<\s*embed\b", "Embed elements (<embed>) are not permitted in CMS page body."),
            (r"javascript\s*:", "Inline JavaScript URIs (javascript:) are not permitted."),
            (r"\bon\w+\s*=", "Inline event handlers (e.g. onload, onerror, onclick) are not permitted."),
        ]
        for pattern, msg in dangerous_patterns:
            if re.search(pattern, raw_html, re.IGNORECASE):
                raise ValidationError(msg)
        return raw_html
