"""HRM 3.6 Candidate Management — Candidate views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    CANDIDATE_GENDER_CHOICES,
    CANDIDATE_SOURCE_CHOICES,
    CANDIDATE_STATUS_CHOICES,
    CandidateProfile,
    CandidateSkill,
    CandidateTag,
    QUALIFICATION_CHOICES,
)
from apps.hrm.forms import (
    CandidateProfileForm,
    CandidateSkillForm,
)
from apps.hrm.views.CandidateManagement.Partys import party_has_only_candidate_role


# --------------------------------------------------------------- Candidates (3.6) CRUD + hub
@login_required
def candidate_list(request):
    # The Count annotation's GROUP BY already collapses the skill/tag join-filter rows to one per
    # candidate; .distinct() makes that explicit so the list stays unique even if the annotation changes.
    qs = (CandidateProfile.objects.filter(tenant=request.tenant)
          .select_related("party").prefetch_related("tags", "skills")
          .annotate(application_count=Count("applications", distinct=True))
          .order_by("-created_at").distinct())
    return crud_list(
        request, qs, "hrm/candidates/candidate/list.html",
        search_fields=["first_name", "last_name", "email", "phone", "current_job_title",
                       "current_employer", "skill_set", "resume_text", "number"],
        filters=[("status", "status", False), ("source", "source", False),
                 ("gender", "gender", False), ("qualification", "highest_qualification", False),
                 ("tag", "tags__id", True), ("skill", "skills__skill_name__icontains", False)],
        extra_context={
            "status_choices": CANDIDATE_STATUS_CHOICES,
            "source_choices": CANDIDATE_SOURCE_CHOICES,
            "gender_choices": CANDIDATE_GENDER_CHOICES,
            "qualification_choices": QUALIFICATION_CHOICES,
            "tags": CandidateTag.objects.filter(tenant=request.tenant).only("pk", "name", "color"),
        },
    )


@login_required
def candidate_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = CandidateProfileForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            cd = form.cleaned_data
            with transaction.atomic():
                party = Party.objects.create(
                    tenant=request.tenant, kind="person",
                    name=f"{cd['first_name']} {cd['last_name']}".strip())
                PartyRole.objects.create(tenant=request.tenant, party=party, role="candidate")
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.party = party
                # Stamp the consent timestamp when a staff member records consent (the public apply
                # flow does the same), so a ticked consent is never left undated.
                if obj.gdpr_consent and not obj.gdpr_consent_date:
                    obj.gdpr_consent_date = timezone.now()
                obj.save()
                form.save_m2m()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Candidate {obj.number} created.")
            return redirect("hrm:candidate_detail", pk=obj.pk)
    else:
        form = CandidateProfileForm(tenant=request.tenant)
    return render(request, "hrm/candidates/candidate/form.html", {"form": form, "is_edit": False})


@login_required
def candidate_detail(request, pk):
    obj = get_object_or_404(
        CandidateProfile.objects.filter(tenant=request.tenant).select_related("party", "sourced_by"),
        pk=pk)
    applications = (obj.applications.select_related("requisition").order_by("-applied_at")[:25])
    communications = (obj.communications.select_related("template", "sent_by").order_by("-sent_at")[:20])
    return render(request, "hrm/candidates/candidate/detail.html", {
        "obj": obj,
        "skills": obj.skills.all(),
        "applications": applications,
        "communications": communications,
        "candidate_tags": obj.tags.all(),
        "all_tags": CandidateTag.objects.filter(tenant=request.tenant),
        "skill_form": CandidateSkillForm(tenant=request.tenant),
    })


@login_required
def candidate_edit(request, pk):
    obj = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = CandidateProfileForm(request.POST, request.FILES, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            # Stamp the consent timestamp the first time consent is recorded via the staff form.
            if obj.gdpr_consent and not obj.gdpr_consent_date:
                obj.gdpr_consent_date = timezone.now()
                obj.save(update_fields=["gdpr_consent_date"])
            # Keep the Party display name in sync with the denormalized candidate name.
            new_name = obj.name
            if obj.party_id and obj.party.name != new_name:
                obj.party.name = new_name
                obj.party.save(update_fields=["name"])
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Candidate updated.")
            return redirect("hrm:candidate_detail", pk=obj.pk)
    else:
        form = CandidateProfileForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/candidates/candidate/form.html",
                  {"form": form, "obj": obj, "is_edit": True})


@tenant_admin_required  # destructive — cascades the Party, its roles, applications and communications
@require_POST
def candidate_delete(request, pk):
    obj = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant)
                            .select_related("party"), pk=pk)
    party = obj.party
    with transaction.atomic():
        # Audit inside the transaction so the row only survives if the delete commits.
        write_audit_log(request.user, obj, "delete")
        # The candidate Party is dedicated (minted per candidate); deleting it cascades the profile,
        # its PartyRole, skills, applications and communications in one shot.
        if party_has_only_candidate_role(party):
            party.delete()
        else:
            obj.delete()
    messages.success(request, "Candidate deleted.")
    return redirect("hrm:candidate_list")


@login_required
@require_POST
def candidate_mark_hired(request, pk):
    obj = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    obj.status = "hired"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "mark_hired"})
    messages.success(request, f"{obj.name} marked as hired.")
    return redirect("hrm:candidate_detail", pk=obj.pk)


@tenant_admin_required  # contact-suppression is an authoritative HR decision
@require_POST
def candidate_blacklist(request, pk):
    obj = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    obj.status = "blacklisted"
    obj.do_not_contact = True
    obj.save(update_fields=["status", "do_not_contact", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "blacklist"})
    messages.success(request, f"{obj.name} blacklisted and marked do-not-contact.")
    return redirect("hrm:candidate_detail", pk=obj.pk)


@tenant_admin_required  # inverse of blacklist — same authoritative bar
@require_POST
def candidate_restore(request, pk):
    obj = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    obj.status = "active"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "restore"})
    messages.success(request, f"{obj.name} restored to active.")
    return redirect("hrm:candidate_detail", pk=obj.pk)


@login_required
@require_POST
def candidate_skill_add(request, pk):
    candidate = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    form = CandidateSkillForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        cd = form.cleaned_data
        CandidateSkill.objects.get_or_create(
            candidate=candidate, skill_name=cd["skill_name"],
            defaults={"tenant": request.tenant, "proficiency": cd["proficiency"],
                      "source": cd["source"]})
        messages.success(request, "Skill added.")
    else:
        messages.error(request, "Enter a skill name.")
    return redirect("hrm:candidate_detail", pk=candidate.pk)


@login_required
@require_POST
def candidate_skill_delete(request, pk, skill_pk):
    candidate = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    skill = get_object_or_404(CandidateSkill, pk=skill_pk, candidate=candidate, tenant=request.tenant)
    skill.delete()
    messages.success(request, "Skill removed.")
    return redirect("hrm:candidate_detail", pk=candidate.pk)


@login_required
@require_POST
def candidate_tag_add(request, pk):
    candidate = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    tag = get_object_or_404(CandidateTag, pk=request.POST.get("tag"), tenant=request.tenant)
    candidate.tags.add(tag)
    messages.success(request, f'Tag "{tag.name}" added.')
    return redirect("hrm:candidate_detail", pk=candidate.pk)


@login_required
@require_POST
def candidate_tag_remove(request, pk, tag_pk):
    candidate = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    tag = get_object_or_404(CandidateTag, pk=tag_pk, tenant=request.tenant)
    candidate.tags.remove(tag)
    messages.success(request, f'Tag "{tag.name}" removed.')
    return redirect("hrm:candidate_detail", pk=candidate.pk)
