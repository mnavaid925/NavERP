import json
from django.conf import settings
from django.db import models

from apps.documents.models._base import TenantNumbered


class DocumentOcrJob(TenantNumbered):
    """
    Sub-module 13.5 Metadata & Indexing: Full-Text Indexing & OCR
    Asynchronous and on-demand OCR extraction job pipeline with confidence scoring,
    handwriting/barcode detection, and structured entity extraction.
    """
    NUMBER_PREFIX = "DOCR"

    STATUS_CHOICES = [
        ("queued", "Queued for Processing"),
        ("processing", "OCR & Analysis In Progress"),
        ("completed", "Completed Successfully"),
        ("failed", "Processing Failed"),
        ("reviewed", "Reviewed & Applied"),
    ]

    OCR_ENGINE_CHOICES = [
        ("internal_heuristic", "Internal Heuristic Text Extractor"),
        ("tesseract_ocr", "Tesseract Open Source OCR Engine"),
        ("azure_document_intelligence", "Microsoft Azure Document Intelligence"),
        ("aws_textract", "AWS Textract Intelligent Parser"),
        ("google_vision_ocr", "Google Cloud Vision Document AI"),
    ]

    STATUS_CSS = {
        "queued": "badge-slate",
        "processing": "badge-amber",
        "completed": "badge-green",
        "failed": "badge-red",
        "reviewed": "badge-info",
    }

    OCR_ENGINE_CSS = {
        "internal_heuristic": "badge-slate",
        "tesseract_ocr": "badge-info",
        "azure_document_intelligence": "badge-green",
        "aws_textract": "badge-amber",
        "google_vision_ocr": "badge-info",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="ocr_jobs",
        db_index=True,
    )
    version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ocr_jobs",
    )
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="queued", db_index=True)
    ocr_engine = models.CharField(max_length=40, choices=OCR_ENGINE_CHOICES, default="internal_heuristic")
    extracted_full_text = models.TextField(blank=True, help_text="Full text content extracted from document OCR")
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Extraction confidence score (0-100%)",
    )
    page_count = models.PositiveIntegerField(default=1)
    suggested_category = models.CharField(max_length=100, blank=True)
    suggested_tags_json = models.TextField(default="[]", help_text="JSON list of AI suggested tags")
    extracted_entities_json = models.TextField(
        default="{}",
        help_text="JSON dictionary of extracted structured entities (dates, parties, amounts, invoice #s)",
    )
    has_handwriting = models.BooleanField(default=False)
    has_barcode = models.BooleanField(default=False)
    processing_duration_ms = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    applied_to_document = models.BooleanField(
        default=False,
        help_text="True if OCR text & tags have been committed to document master",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_ocr_jobs",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Document OCR Job"
        verbose_name_plural = "Document OCR Jobs"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_docr_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "created_at"], name="doc_docr_tnt_sta_dt_idx"),
            models.Index(fields=["tenant", "document", "status"], name="doc_docr_tnt_doc_sta_idx"),
        ]

    def __str__(self):
        return f"{self.document.title} [{self.number}] ({self.status})"

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def engine_badge(self):
        return self.OCR_ENGINE_CSS.get(self.ocr_engine, "badge-slate")

    @property
    def parsed_entities(self):
        try:
            val = json.loads(self.extracted_entities_json)
            return val if isinstance(val, dict) else {}
        except (ValueError, TypeError):
            return {}

    @property
    def parsed_tags(self):
        try:
            val = json.loads(self.suggested_tags_json)
            return val if isinstance(val, list) else []
        except (ValueError, TypeError):
            return []
