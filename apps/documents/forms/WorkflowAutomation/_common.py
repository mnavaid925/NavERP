import json

from django.core.exceptions import ValidationError

MAX_BPM_JSON_BYTES = 65536
MAX_BPM_JSON_DEPTH = 20


def _measure_json_depth(value, current=0):
    if current > MAX_BPM_JSON_DEPTH:
        raise ValidationError(
            f"JSON payload exceeds maximum nesting depth ({MAX_BPM_JSON_DEPTH})."
        )
    if isinstance(value, dict):
        for item in value.values():
            _measure_json_depth(item, current + 1)
    elif isinstance(value, list):
        for item in value:
            _measure_json_depth(item, current + 1)


def parse_json_field_value(val, expected_type, label, max_bytes=MAX_BPM_JSON_BYTES):
    """Parse and bound a JSON form input (size <= 64 KiB, depth <= 20, expected list/dict)."""
    type_label = "array" if expected_type is list else "object"
    if val is None or val == "":
        return expected_type()
    if isinstance(val, expected_type):
        encoded = json.dumps(val).encode("utf-8")
        if len(encoded) > max_bytes:
            raise ValidationError(f"{label} exceeds maximum size of {max_bytes} bytes.")
        _measure_json_depth(val)
        return val
    if isinstance(val, str):
        stripped = val.strip()
        if not stripped:
            return expected_type()
        if len(stripped.encode("utf-8")) > max_bytes:
            raise ValidationError(f"{label} exceeds maximum size of {max_bytes} bytes.")
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON for {label}: {exc}") from exc
        if not isinstance(parsed, expected_type):
            raise ValidationError(f"{label} must be a JSON {type_label}.")
        _measure_json_depth(parsed)
        return parsed
    raise ValidationError(f"{label} must be a JSON {type_label}.")
