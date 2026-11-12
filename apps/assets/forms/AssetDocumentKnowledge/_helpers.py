"""Shared form helpers for Module 11.16 Document & Knowledge Management."""

import os

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES


def scope_tenant_querysets(form, tenant_field_models):
    """Scope every tenant-owned and user ForeignKey queryset strictly to ``form.tenant``."""
    tenant = getattr(form, "tenant", None)
    for field_name, model_cls in tenant_field_models.items():
        if field_name not in form.fields:
            continue
        if tenant is None:
            form.fields[field_name].queryset = model_cls.objects.none()
        else:
            qs = model_cls.objects.filter(tenant=tenant)
            if (
                field_name == "supersedes"
                and getattr(form.instance, "pk", None) is not None
                and isinstance(form.instance, model_cls)
            ):
                qs = qs.exclude(pk=form.instance.pk)
            form.fields[field_name].queryset = qs


def validate_safe_doc_upload(uploaded_file):
    """Validate uploaded files against NavERP's allowed extension allowlist and size ceiling."""
    if not uploaded_file:
        return uploaded_file
    if not isinstance(uploaded_file, UploadedFile):
        return uploaded_file
    filename = os.path.basename(str(getattr(uploaded_file, "name", "") or ""))
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        allowed_display = ", ".join(sorted(ALLOWED_DOC_EXTENSIONS))
        raise ValidationError(
            f"Unsupported file extension '{ext or '(none)'}'. Allowed formats: {allowed_display}."
        )
    file_size = getattr(uploaded_file, "size", 0) or 0
    if file_size > MAX_UPLOAD_BYTES:
        max_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ValidationError(f"Uploaded file exceeds maximum allowed size of {max_mb} MB.")
    return uploaded_file


def normalize_json_list_value(value):
    """Ensure blank JSONField submissions resolve to ``[]`` instead of ``None``."""
    if value in (None, ""):
        return []
    return value


def normalize_json_dict_value(value):
    """Ensure blank JSONField dict submissions resolve to ``{}`` instead of ``None``."""
    if value in (None, ""):
        return {}
    return value
