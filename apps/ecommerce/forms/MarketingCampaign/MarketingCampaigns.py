from django import forms
from django.utils.text import slugify

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.MarketingCampaign.MarketingCampaigns import MarketingCampaign
from apps.ecommerce.models.Personalization.AudienceSegments import AudienceSegment
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct


class MarketingCampaignForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MarketingCampaign
        fields = [
            "name",
            "code",
            "campaign_type",
            "channel",
            "status",
            "target_segment",
            "target_product",
            "subject",
            "preview_text",
            "content_body",
            "sender_name",
            "sender_address",
            "scheduled_at",
            "send_throttle_window_hours",
            "geofence_latitude",
            "geofence_longitude",
            "geofence_radius_km",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. VIP Early Access - Holiday Collection"}
            ),
            "code": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. holiday-vip-early-access"}
            ),
            "campaign_type": forms.Select(attrs={"class": "form-select"}),
            "channel": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "target_segment": forms.Select(attrs={"class": "form-select"}),
            "target_product": forms.Select(attrs={"class": "form-select"}),
            "subject": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. ✨ Exclusive VIP Access: Discover The New Season"}
            ),
            "preview_text": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Shop 24 hours before everyone else with free express shipping."}
            ),
            "content_body": forms.Textarea(
                attrs={
                    "class": "form-textarea font-mono text-sm",
                    "rows": 8,
                    "placeholder": "Enter HTML email template, SMS copy, or push message content...",
                }
            ),
            "sender_name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. NavStore Boutique"}
            ),
            "sender_address": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. vip@navstore.com or NAVSTORE"}
            ),
            "scheduled_at": forms.DateTimeInput(
                attrs={"class": "form-input", "type": "datetime-local"}
            ),
            "send_throttle_window_hours": forms.NumberInput(
                attrs={"class": "form-input", "min": 0, "max": 168}
            ),
            "geofence_latitude": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.000001", "placeholder": "37.774929"}
            ),
            "geofence_longitude": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.000001", "placeholder": "-122.419416"}
            ),
            "geofence_radius_km": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.1", "placeholder": "10.0"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["target_segment"].queryset = AudienceSegment.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["target_product"].queryset = CatalogProduct.objects.filter(
                tenant=self.tenant
            ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["target_segment", "target_product"])

        name = cleaned_data.get("name")
        code = cleaned_data.get("code")
        if not code and name:
            cleaned_data["code"] = slugify(name)[:60]

        channel = cleaned_data.get("channel")
        subject = cleaned_data.get("subject")
        content_body = cleaned_data.get("content_body")

        if channel in ("email", "omnichannel") and not subject:
            self.add_error("subject", "Subject line is required for email campaigns.")

        if channel == "sms" and content_body and len(content_body) > 1600:
            self.add_error("content_body", "SMS messages cannot exceed 1600 characters.")

        return cleaned_data
