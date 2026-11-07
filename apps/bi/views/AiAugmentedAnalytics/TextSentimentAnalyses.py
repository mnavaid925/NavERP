import json
import re
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.AiAugmentedAnalytics.TextSentimentAnalyses import TextSentimentAnalysisForm
from apps.bi.models.AiAugmentedAnalytics.TextSentimentAnalyses import TextSentimentAnalysis
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log

POSITIVE_WORDS = {
    "great", "excellent", "good", "fast", "helpful", "friendly", "love", "best",
    "improved", "impressive", "smooth", "happy", "satisfied", "efficient", "perfect",
    "reliable", "fantastic", "outstanding", "superb", "easy", "clean"
}
NEGATIVE_WORDS = {
    "bad", "terrible", "slow", "poor", "broken", "worst", "unhelpful", "hate",
    "bug", "delay", "error", "unhappy", "frustrating", "awful", "expensive",
    "confusing", "useless", "fail", "failed", "crash", "issue", "problem"
}


def compute_sentiment_from_text(text):
    if not text:
        return Decimal("0.00"), Decimal("0.50"), "neutral", []

    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    pos_matches = [w for w in words if w in POSITIVE_WORDS]
    neg_matches = [w for w in words if w in NEGATIVE_WORDS]

    pos_count = len(pos_matches)
    neg_count = len(neg_matches)
    total_sentiment_words = pos_count + neg_count

    if total_sentiment_words == 0:
        polarity = Decimal("0.00")
        subjectivity = Decimal("0.10")
        category = "neutral"
    else:
        raw_polarity = (pos_count - neg_count) / max(total_sentiment_words, 1)
        polarity = Decimal(str(round(raw_polarity, 2)))
        subjectivity = Decimal(str(round(min(total_sentiment_words / max(len(words), 1) * 3, 1.0), 2)))

        if polarity >= Decimal("0.40"):
            category = "very_positive"
        elif polarity > Decimal("0.05"):
            category = "positive"
        elif polarity <= Decimal("-0.40"):
            category = "very_negative"
        elif polarity < Decimal("-0.05"):
            category = "negative"
        else:
            category = "neutral"

    thematic_tags = list(set(pos_matches + neg_matches))[:5]
    return polarity, subjectivity, category, thematic_tags


@login_required
def text_sentiment_analysis_list(request):
    qs = bi_scope(TextSentimentAnalysis.objects.all(), request).select_related(
        "linked_party", "linked_org_unit"
    )

    counts = qs.aggregate(
        positive=Count("id", filter=Q(sentiment_category__in=["very_positive", "positive"])),
        negative=Count("id", filter=Q(sentiment_category__in=["very_negative", "negative"])),
        avg_polarity=Avg("polarity_score"),
    )
    positive_count = counts["positive"] or 0
    negative_count = counts["negative"] or 0
    avg_polarity = round(counts["avg_polarity"] or Decimal("0.00"), 2)

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(source_reference__icontains=q)
            | Q(text_content__icontains=q)
            | Q(number__icontains=q)
            | Q(linked_party__name__icontains=q)
        )

    # Filters
    source_type = request.GET.get("source_type", "").strip()
    if source_type:
        qs = qs.filter(source_type=source_type)

    sentiment_category = request.GET.get("sentiment_category", "").strip()
    if sentiment_category:
        qs = qs.filter(sentiment_category=sentiment_category)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "bi/ai_augmented_analytics/text_sentiment_analysis/list.html",
        {
            "analyses": page_obj,
            "source_type_choices": TextSentimentAnalysis.SOURCE_TYPE_CHOICES,
            "sentiment_category_choices": TextSentimentAnalysis.SENTIMENT_CATEGORY_CHOICES,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "avg_polarity": avg_polarity,
        },
    )


@login_required
def text_sentiment_analysis_detail(request, pk):
    analysis = bi_object(
        request,
        TextSentimentAnalysis,
        pk,
        select_related=("linked_party", "linked_org_unit"),
    )

    thematic_tags_list = []
    if isinstance(analysis.thematic_tags, list):
        thematic_tags_list = analysis.thematic_tags
    elif isinstance(analysis.thematic_tags, str) and analysis.thematic_tags.strip():
        try:
            thematic_tags_list = json.loads(analysis.thematic_tags)
        except json.JSONDecodeError:
            thematic_tags_list = [t.strip() for t in analysis.thematic_tags.split(",") if t.strip()]

    return render(
        request,
        "bi/ai_augmented_analytics/text_sentiment_analysis/detail.html",
        {
            "analysis": analysis,
            "thematic_tags_list": thematic_tags_list,
        },
    )


@login_required
def text_sentiment_analysis_create(request):
    if request.method == "POST":
        form = TextSentimentAnalysisForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            analysis = form.save(commit=False)
            analysis.tenant = request.tenant

            # Auto-score if left default
            if analysis.polarity_score == Decimal("0.00") and analysis.sentiment_category == "neutral":
                pol, sub, cat, tags = compute_sentiment_from_text(analysis.text_content)
                analysis.polarity_score = pol
                analysis.subjectivity_score = sub
                analysis.sentiment_category = cat
                analysis.thematic_tags = tags

            analysis.save()
            write_audit_log(
                request.user,
                analysis,
                "create",
                changes={"details": f"Created sentiment record {analysis.number} for {analysis.source_reference}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Sentiment analysis {analysis.number} created successfully.")
            return redirect("bi:text_sentiment_analysis_detail", pk=analysis.pk)
    else:
        form = TextSentimentAnalysisForm(tenant=request.tenant)

    return render(
        request,
        "bi/ai_augmented_analytics/text_sentiment_analysis/form.html",
        {
            "form": form,
            "analysis": None,
            "is_edit": False,
        },
    )


@login_required
def text_sentiment_analysis_edit(request, pk):
    analysis = bi_object(request, TextSentimentAnalysis, pk)
    if request.method == "POST":
        form = TextSentimentAnalysisForm(request.POST, instance=analysis, tenant=request.tenant)
        if form.is_valid():
            analysis = form.save()
            write_audit_log(
                request.user,
                analysis,
                "update",
                changes={"details": f"Updated sentiment record {analysis.number}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Sentiment analysis {analysis.number} updated successfully.")
            return redirect("bi:text_sentiment_analysis_detail", pk=analysis.pk)
    else:
        form = TextSentimentAnalysisForm(instance=analysis, tenant=request.tenant)

    return render(
        request,
        "bi/ai_augmented_analytics/text_sentiment_analysis/form.html",
        {
            "form": form,
            "analysis": analysis,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def text_sentiment_analysis_delete(request, pk):
    analysis = bi_object(request, TextSentimentAnalysis, pk)
    number = analysis.number
    write_audit_log(
        request.user,
        analysis,
        "delete",
        changes={"number": number, "details": f"Deleted sentiment record {number}"},
        tenant=request.tenant,
    )
    analysis.delete()
    messages.success(request, f"Sentiment record {number} was deleted.")
    return redirect("bi:text_sentiment_analysis_list")


@login_required
@require_POST
def text_sentiment_analysis_recalculate(request, pk):
    analysis = bi_object(request, TextSentimentAnalysis, pk)
    pol, sub, cat, tags = compute_sentiment_from_text(analysis.text_content)
    analysis.polarity_score = pol
    analysis.subjectivity_score = sub
    analysis.sentiment_category = cat
    analysis.thematic_tags = tags
    analysis.save()

    write_audit_log(
        request.user,
        analysis,
        "recalc",
        changes={"polarity": str(pol), "category": cat, "details": f"Recalculated sentiment for {analysis.number}: polarity={pol}, category={cat}"},
        tenant=request.tenant,
    )
    messages.success(request, f"Recalculated sentiment: {analysis.get_sentiment_category_display()} (Polarity: {pol}).")
    return redirect("bi:text_sentiment_analysis_detail", pk=analysis.pk)
