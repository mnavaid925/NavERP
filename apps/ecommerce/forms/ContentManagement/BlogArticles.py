from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ContentManagement.BlogArticles import BlogArticle

User = get_user_model()


class BlogArticleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BlogArticle
        fields = [
            "title",
            "slug",
            "author",
            "category",
            "excerpt",
            "body_markdown",
            "featured_media",
            "status",
            "tags",
            "reading_time_minutes",
            "allow_comments",
            "is_featured",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Enter article headline"}
            ),
            "slug": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. spring-wardrobe-trends"}
            ),
            "author": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "excerpt": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Short summary for index lists and meta tags"}
            ),
            "body_markdown": forms.Textarea(
                attrs={"class": "form-textarea font-mono", "rows": 12, "placeholder": "# Article Heading\n\nWrite article in Markdown..."}
            ),
            "featured_media": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "tags": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "fashion, trends, style, news"}
            ),
            "reading_time_minutes": forms.NumberInput(
                attrs={"class": "form-input", "min": 1, "max": 60}
            ),
            "allow_comments": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["author"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["author"].required = False
        self.fields["featured_media"].required = False
        self.fields["tags"].required = False
        self.fields["excerpt"].required = False

        if self.tenant:
            try:
                MediaAsset = apps.get_model("ecommerce", "MediaAsset")
                if MediaAsset:
                    self.fields["featured_media"].queryset = MediaAsset.objects.filter(tenant=self.tenant)
            except (LookupError, AttributeError):
                pass

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["featured_media"])
        return cleaned
