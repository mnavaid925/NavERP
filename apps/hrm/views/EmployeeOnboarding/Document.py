"""HRM 3.3 Employee Onboarding — Document views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    OnboardingDocument,
    OnboardingProgram,
)
from apps.hrm.forms import (
    OnboardingDocumentForm,
)


# ============================================================ Onboarding Documents (3.3)
@login_required
def onboardingdocument_list(request):
    return crud_list(
        request,
        OnboardingDocument.objects.filter(tenant=request.tenant)
        .select_related("program"),  # rows show program.number only
        "hrm/onboarding/document/list.html",
        search_fields=["title", "description", "external_ref", "program__number"],
        filters=[("program", "program_id", True), ("document_type", "document_type", False),
                 ("esign_status", "esign_status", False)],
        extra_context={"type_choices": OnboardingDocument.DOCUMENT_TYPE_CHOICES,
                       "esign_choices": OnboardingDocument.ESIGN_STATUS_CHOICES,
                       "programs": OnboardingProgram.objects.filter(tenant=request.tenant)
                       .select_related("employee__party").order_by("-start_date")},
    )


@login_required
def onboardingdocument_create(request):
    return crud_create(request, form_class=OnboardingDocumentForm,
                       template="hrm/onboarding/document/form.html",
                       success_url="hrm:onboardingdocument_list")


@login_required
def onboardingdocument_detail(request, pk):
    obj = get_object_or_404(
        OnboardingDocument.objects.select_related("program__employee__party"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/document/detail.html", {"obj": obj})


@login_required
def onboardingdocument_edit(request, pk):
    return crud_edit(request, model=OnboardingDocument, pk=pk, form_class=OnboardingDocumentForm,
                     template="hrm/onboarding/document/form.html",
                     success_url="hrm:onboardingdocument_list")


@login_required
@require_POST
def onboardingdocument_delete(request, pk):
    return crud_delete(request, model=OnboardingDocument, pk=pk,
                       success_url="hrm:onboardingdocument_list")


@login_required
@require_POST
def onboardingdocument_mark_signed(request, pk):
    obj = get_object_or_404(OnboardingDocument, pk=pk, tenant=request.tenant)
    # A document that needs no signature can't be "signed" — keeps the e-sign trail meaningful.
    if obj.esign_status == "not_required":
        messages.error(request, "This document does not require a signature.")
    elif obj.esign_status != "signed":
        obj.esign_status = "signed"
        obj.signed_at = timezone.now()
        obj.save(update_fields=["esign_status", "signed_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_signed"})
        messages.success(request, f"Document '{obj.title}' marked signed.")
    return redirect("hrm:onboardingdocument_detail", pk=obj.pk)
