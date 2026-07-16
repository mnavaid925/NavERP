"""core — Search views (split from apps/core/views.py)."""
from apps.core.views._common import *  # noqa: F401,F403


# ------------------------------------------------------------ Global search
@login_required
def global_search_suggest(request):
    """Live suggestions for the header search dropdown (JSON), tenant-scoped."""
    q = request.GET.get("q", "").strip()[:80]
    groups = run_search(request.tenant, q, per_target=5, total_cap=8)
    return JsonResponse({"q": q, "groups": groups})


@login_required
def global_search(request):
    """Full search results page (Enter / 'see all'), tenant-scoped."""
    q = request.GET.get("q", "").strip()[:80]
    groups = run_search(request.tenant, q, per_target=20, total_cap=99)  # all groups on the results page
    count = sum(len(g["items"]) for g in groups)
    return render(request, "core/search.html", {"q": q, "groups": groups, "count": count})
