"""HRM 3.6 Candidate Management — CareersApply views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.CandidateManagement._helpers import _send_candidate_email
from apps.hrm.models import (
    CandidateProfile,
    JobApplication,
    JobRequisition,
)
from apps.hrm.forms import (
    PublicApplicationForm,
)
from apps.hrm.views.CandidateManagement._helpers import _send_candidate_email


def careers_apply(request, token):
    """Public application page for one posted requisition (resolved by its public_token)."""
    req = get_object_or_404(
        JobRequisition.objects.select_related("tenant", "department"),
        public_token=token, status="posted")
    form = PublicApplicationForm()
    if request.method == "POST":
        form = PublicApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            cd = form.cleaned_data
            with transaction.atomic():
                candidate = (CandidateProfile.objects
                             .filter(tenant=req.tenant, email__iexact=cd["email"]).first())
                if candidate is None:
                    party = Party.objects.create(
                        tenant=req.tenant, kind="person",
                        name=f"{cd['first_name']} {cd['last_name']}".strip())
                    PartyRole.objects.create(tenant=req.tenant, party=party, role="candidate")
                    candidate = CandidateProfile.objects.create(
                        tenant=req.tenant, party=party, first_name=cd["first_name"],
                        last_name=cd["last_name"], email=cd["email"], phone=cd["phone"],
                        linkedin_url=cd["linkedin_url"], city=cd["city"], source=cd["source"],
                        resume_file=cd["resume_file"])
                if cd["gdpr_consent"] and not candidate.gdpr_consent:
                    candidate.gdpr_consent = True
                    candidate.gdpr_consent_date = timezone.now()
                    candidate.save(update_fields=["gdpr_consent", "gdpr_consent_date", "updated_at"])
                application, created = JobApplication.objects.get_or_create(
                    tenant=req.tenant, candidate=candidate, requisition=req,
                    defaults={"source": "careers_page", "cover_letter_text": cd["cover_letter_text"]})
            if not created:
                messages.info(request, "You have already applied for this position.")
            else:
                write_audit_log(None, application, "create", {"via": "careers_portal"})
                # Reuse the already-loaded requisition so the merge-render doesn't refetch it.
                application.requisition = req
                _send_candidate_email(application, template_type="application_received", sent_by=None)
            return redirect(f"{reverse('hrm:careers_apply', args=[token])}?submitted=1")
    return render(request, "hrm/candidates/careers_apply.html", {
        "req": req, "form": form, "submitted": request.GET.get("submitted") == "1"})
