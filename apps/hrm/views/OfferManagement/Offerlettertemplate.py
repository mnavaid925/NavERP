"""HRM 3.8 Offer Management — Offerlettertemplate views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    OfferLetterTemplate,
)
from apps.hrm.forms import (
    OfferLetterTemplateForm,
)


# --------------------------------------------------------------- Offer Letter Templates (3.8)
@login_required
def offerlettertemplate_list(request):
    return crud_list(
        request, OfferLetterTemplate.objects.filter(tenant=request.tenant),
        "hrm/offer/offerlettertemplate/list.html",
        search_fields=["number", "name", "body_html"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def offerlettertemplate_create(request):
    return crud_create(request, form_class=OfferLetterTemplateForm,
                       template="hrm/offer/offerlettertemplate/form.html",
                       success_url="hrm:offerlettertemplate_list")


@login_required
def offerlettertemplate_detail(request, pk):
    return crud_detail(request, model=OfferLetterTemplate, pk=pk,
                       template="hrm/offer/offerlettertemplate/detail.html")


@login_required
def offerlettertemplate_edit(request, pk):
    return crud_edit(request, model=OfferLetterTemplate, pk=pk, form_class=OfferLetterTemplateForm,
                     template="hrm/offer/offerlettertemplate/form.html",
                     success_url="hrm:offerlettertemplate_list")


@tenant_admin_required
@require_POST
def offerlettertemplate_delete(request, pk):
    return crud_delete(request, model=OfferLetterTemplate, pk=pk,
                       success_url="hrm:offerlettertemplate_list")
