import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.CollaborationStorytelling.BiDataStories import BiDataStoryForm
from apps.bi.models.CollaborationStorytelling.BiDataStories import BiDataStory
from apps.bi.models.CollaborationStorytelling.BiSharedWorkspaces import BiSharedWorkspace
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def bi_data_story_list(request):
    qs = bi_scope(BiDataStory.objects.all(), request).select_related("workspace", "author", "created_by")

    counts = qs.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status="published")),
        draft=Count("id", filter=Q(status="draft")),
    )
    total_count = counts["total"] or 0
    published_count = counts["published"] or 0
    draft_count = counts["draft"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(slug__icontains=q)
            | Q(summary__icontains=q)
        )

    # Filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    story_type = request.GET.get("story_type", "").strip()
    if story_type:
        qs = qs.filter(story_type=story_type)

    workspace_id = request.GET.get("workspace", "").strip()
    if workspace_id and workspace_id.isdigit():
        qs = qs.filter(workspace_id=int(workspace_id))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    workspaces = BiSharedWorkspace.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "stories": page_obj,
        "bi_data_stories": page_obj,
        "total_count": total_count,
        "published_count": published_count,
        "draft_count": draft_count,
        "status_choices": BiDataStory.STATUS_CHOICES,
        "story_type_choices": BiDataStory.STORY_TYPE_CHOICES,
        "workspaces": workspaces,
    }
    return render(
        request,
        "bi/collaboration_storytelling/bidatastory/list.html",
        context,
    )


@login_required
def bi_data_story_create(request):
    workspace_initial = None
    w_id = request.GET.get("workspace", "").strip()
    if w_id and w_id.isdigit():
        workspace_initial = BiSharedWorkspace.objects.filter(tenant=request.tenant, pk=int(w_id)).first()

    if request.method == "POST":
        form = BiDataStoryForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                story = form.save(commit=False)
                story.tenant = request.tenant
                story.created_by = request.user
                if not story.author:
                    story.author = request.user
                story.save()
                write_audit_log(
                    request.user,
                    story,
                    "create",
                    tenant=request.tenant,
                )
            messages.success(request, f"Data Story '{story.title}' created successfully.")
            return redirect("bi:bi_data_story_detail", pk=story.pk)
    else:
        initial = {}
        if workspace_initial:
            initial["workspace"] = workspace_initial
        initial["author"] = request.user
        form = BiDataStoryForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "bi/collaboration_storytelling/bidatastory/form.html",
        {"form": form, "title": "New Data Story", "is_edit": False},
    )


@login_required
def bi_data_story_detail(request, pk):
    story = bi_object(
        request,
        BiDataStory,
        pk,
        select_related=("workspace", "author", "created_by"),
    )

    comments = story.comments.filter(parent_comment__isnull=True).select_related("author").order_by("-created_at")

    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    office_link = f"{scheme}://{host}/bi/stories/{story.pk}/export-office/?token={story.office_embed_token}"

    context = {
        "story": story,
        "bi_data_story": story,
        "obj": story,
        "comments": comments,
        "office_link": office_link,
    }
    return render(
        request,
        "bi/collaboration_storytelling/bidatastory/detail.html",
        context,
    )


@login_required
def bi_data_story_edit(request, pk):
    story = bi_object(request, BiDataStory, pk)

    if request.method == "POST":
        form = BiDataStoryForm(request.POST, instance=story, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                story = form.save()
                write_audit_log(
                    request.user,
                    story,
                    "update",
                    tenant=request.tenant,
                )
            messages.success(request, f"Data Story '{story.title}' updated successfully.")
            return redirect("bi:bi_data_story_detail", pk=story.pk)
    else:
        form = BiDataStoryForm(instance=story, tenant=request.tenant)

    return render(
        request,
        "bi/collaboration_storytelling/bidatastory/form.html",
        {
            "form": form,
            "title": f"Edit Story: {story.title}",
            "story": story,
            "bi_data_story": story,
            "obj": story,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def bi_data_story_delete(request, pk):
    story = bi_object(request, BiDataStory, pk)
    title = story.title
    with transaction.atomic():
        write_audit_log(
            request.user,
            story,
            "delete",
            tenant=request.tenant,
        )
        story.delete()
    messages.success(request, f"Data Story '{title}' deleted successfully.")
    return redirect("bi:bi_data_story_list")


@login_required
def bi_data_story_presentation(request, pk):
    story = bi_object(request, BiDataStory, pk, select_related=("workspace", "author"))

    # Update presentation telemetry
    BiDataStory.objects.filter(pk=story.pk).update(
        view_count=F("view_count") + 1,
        last_presented_at=timezone.now(),
    )

    slides = story.slides_data if isinstance(story.slides_data, list) else []

    context = {
        "story": story,
        "bi_data_story": story,
        "obj": story,
        "slides": slides,
    }
    return render(
        request,
        "bi/collaboration_storytelling/bidatastory/presentation.html",
        context,
    )


@login_required
def bi_data_story_export_office(request, pk):
    story = bi_object(request, BiDataStory, pk)
    token = request.GET.get("token", "").strip()
    if story.office_embed_token:
        if not token or not secrets.compare_digest(token, story.office_embed_token):
            return JsonResponse({"error": "Invalid or missing embed token"}, status=403)

    payload = {
        "story_number": story.number,
        "title": story.title,
        "story_type": story.get_story_type_display(),
        "status": story.status,
        "tenant_id": str(story.tenant_id),
        "slides_count": story.slides_count,
        "slides": story.slides_data,
        "exported_at": timezone.now().isoformat(),
        "office_integration": {
            "version": "1.0",
            "provider": "NavERP BI Office Hub",
            "refreshable": True,
        },
    }
    return JsonResponse(payload)
