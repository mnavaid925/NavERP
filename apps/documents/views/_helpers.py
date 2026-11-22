import difflib
import re


def count_words(text):
    if not text:
        return 0
    # Strip HTML tags if present
    clean_text = re.sub(r"<[^>]+>", " ", text)
    words = clean_text.split()
    return len(words)


def substitute_tokens(content, context_data):
    """Replace {{token_name}} placeholders with values from context_data dict."""
    if not content or not context_data:
        return content or ""
    result = content
    for key, value in context_data.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, str(value or ""))
    return result


def compute_text_diff(original, modified):
    """Return lines with diff markers comparing original to modified text."""
    orig_lines = (original or "").splitlines(keepends=True)
    mod_lines = (modified or "").splitlines(keepends=True)
    diff = list(difflib.unified_diff(orig_lines, mod_lines, fromfile="Template Baseline", tofile="Draft Active"))
    return diff
